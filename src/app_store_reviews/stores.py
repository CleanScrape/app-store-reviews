"""App Store and Google Play reviews with the interfaces of app-store-scraper and google-play-scraper.

The reviews are collected by the CleanScrape App Store & Google Play Reviews Actor on Apify.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

import requests

from ._apify import ApifyRunner
from .exceptions import ResponseError, SpendingLimitError

MAX_REVIEWS = 10_000


def _parse_date(value):
    """ISO time from the Actor as a naive UTC datetime, like app-store-scraper and google-play-scraper return."""
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is not None:
        moment = moment.astimezone(timezone.utc).replace(tzinfo=None)
    return moment


def _since(after):
    """The day to pass to the Actor for a datetime or date filter."""
    if after is None:
        return None
    return after.date().isoformat() if isinstance(after, datetime) else str(after)[:10]


class _Collector:
    def __init__(self, apify_token=None, max_charge_usd=None, run_timeout=600, session=None):
        self.runner = ApifyRunner(apify_token or os.environ.get("APIFY_TOKEN"), session=session,
                                  run_timeout=run_timeout, max_charge_usd=max_charge_usd)
        self.last_status = None

    def _collect(self, run_input, source):
        rows, run, report = self.runner.run(run_input)
        self.last_status = run.get("statusMessage")
        rows = [r for r in rows if r.get("source") == source]
        if "spending limit" in (self.last_status or "").lower() and not rows:
            raise SpendingLimitError(self.last_status)
        unit = next((u for u in report.get("units", []) if u.get("source") == source), {})
        if not rows and (unit.get("status") == "failed" or run.get("status") != "SUCCEEDED"):
            reason = "; ".join(unit.get("errors") or []) or self.last_status or "No reviews could be read."
            raise ResponseError(reason)
        return rows, unit


class AppStore(_Collector):
    """Same constructor, attributes and review() method as app-store-scraper's AppStore.

    Each review is a dict with date, review, rating, title, userName and isEdited, plus developerResponse
    when there is one. Extra keys: reviewId, appVersion, country, url.

    Apple's public review feed holds about the 500 most recent reviews per app and country.
    """

    def __init__(self, country, app_name, app_id=None, log_format=None, log_level="INFO", log_interval=5, *,
                 apify_token=None, max_charge_usd=None, run_timeout=600, session=None):
        super().__init__(apify_token, max_charge_usd, run_timeout, session)
        self.country = str(country).lower()
        self.app_name = app_name
        self.app_id = int(app_id) if app_id not in (None, "") and str(app_id).isdigit() else app_id
        self.reviews = []
        self.reviews_count = 0

    @property
    def url(self):
        slug = str(self.app_name or "app").lower().replace(" ", "-")
        return f"https://apps.apple.com/{self.country}/app/{slug}/id{self.app_id}"

    def __repr__(self):
        return f"{type(self).__name__}(country='{self.country}', app_name='{self.app_name}', app_id={self.app_id})"

    def __str__(self):
        width = 12
        return "\n".join([f"{'Country'.rjust(width)} | {self.country}", f"{'Name'.rjust(width)} | {self.app_name}",
                          f"{'ID'.rjust(width)} | {self.app_id}", f"{'URL'.rjust(width)} | {self.url}",
                          f"{'Review count'.rjust(width)} | {self.reviews_count}"])

    def search_id(self):
        """Look up the app's numeric ID from its name with Apple's public search (no Apify run, no cost)."""
        response = requests.get("https://itunes.apple.com/search", timeout=30, params={
            "term": self.app_name, "country": self.country, "entity": "software", "limit": 1})
        response.raise_for_status()
        results = response.json().get("results") or []
        if not results:
            raise ResponseError(f"No App Store app called {self.app_name!r} in country {self.country!r}.")
        self.app_id = results[0]["trackId"]
        return self.app_id

    def review(self, how_many=sys.maxsize, after=None, sleep=None):
        """Collect up to how_many recent reviews (optionally only those on or after `after`) into self.reviews."""
        if not self.app_id:
            self.search_id()
        run_input = {"store": "app_store", "appStoreId": str(self.app_id), "country": self.country,
                     "maxReviews": max(1, min(int(how_many), MAX_REVIEWS)), "sort": "newest"}
        if after is not None:
            run_input["reviewsSince"] = _since(after)
        rows, _ = self._collect(run_input, "app_store")
        for r in rows:
            review = {"date": _parse_date(r.get("date")), "review": r.get("text"), "rating": r.get("rating"),
                      "isEdited": None, "title": r.get("title"), "userName": r.get("userName")}
            if after is not None and review["date"] is not None and isinstance(after, datetime) and review["date"] < after.replace(tzinfo=None):
                continue
            if r.get("developerReply"):
                review["developerResponse"] = {"body": r.get("developerReply"), "modified": _parse_date(r.get("developerReplyDate"))}
            review.update({"reviewId": r.get("reviewId"), "appVersion": r.get("appVersion"), "country": r.get("country"), "url": r.get("url")})
            self.reviews.append(review)
            if len(self.reviews) >= how_many:
                break
        self.reviews_count = len(self.reviews)
        return self.reviews


class Podcast(AppStore):
    def __init__(self, *args, **kwargs):
        raise NotImplementedError("Podcast reviews are not supported. AppStore and Google Play app reviews are.")


class Sort:
    """google-play-scraper's sort values."""
    MOST_RELEVANT = 1
    NEWEST = 2
    RATING = 3


_SORT = {Sort.MOST_RELEVANT: "helpfulness", Sort.NEWEST: "newest", Sort.RATING: "rating"}


def reviews(app_id, lang="en", country="us", sort=Sort.NEWEST, count=100, filter_score_with=None,
            filter_device_with=None, continuation_token=None, *, apify_token=None, max_charge_usd=None, run_timeout=600, session=None):
    """Like google_play_scraper.reviews(): returns (list_of_reviews, None).

    Each review has reviewId, userName, userImage, content, score, thumbsUpCount, reviewCreatedVersion, at,
    replyContent, repliedAt and appVersion. There is no paging token: ask for the count you need in one call.
    """
    if continuation_token is not None:
        raise ValueError("Paging tokens are not used here. Ask for the full count in one call (count=...).")
    collector = _Collector(apify_token, max_charge_usd, run_timeout, session)
    run_input = {"store": "google_play", "googlePlayAppId": app_id, "country": country, "language": lang,
                 "sort": _SORT.get(sort, "newest"), "maxReviews": max(1, min(int(count), MAX_REVIEWS))}
    if filter_score_with:
        run_input["ratings"] = [str(int(filter_score_with))]
    rows, _ = collector._collect(run_input, "google_play")
    result = [{"reviewId": r.get("reviewId"), "userName": r.get("userName"), "userImage": None, "content": r.get("text"),
               "score": r.get("rating"), "thumbsUpCount": r.get("thumbsUp"), "reviewCreatedVersion": r.get("appVersion"),
               "at": _parse_date(r.get("date")), "replyContent": r.get("developerReply"),
               "repliedAt": _parse_date(r.get("developerReplyDate")), "appVersion": r.get("appVersion")} for r in rows]
    return result[:count], None


def reviews_all(app_id, sleep_milliseconds=0, lang="en", country="us", sort=Sort.NEWEST, filter_score_with=None, **kwargs):
    """Like google_play_scraper.reviews_all(), capped at 10,000 reviews per call."""
    result, _ = reviews(app_id, lang=lang, country=country, sort=sort, count=MAX_REVIEWS, filter_score_with=filter_score_with, **kwargs)
    return result
