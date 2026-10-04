"""Offline tests: the Apify run is replaced with rows saved from the Actor (names and text replaced with placeholders)."""
import json
import pathlib
import sys
import unittest
from datetime import datetime
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from app_store_reviews import AppStore, ApifyTokenError, Podcast, ResponseError, Sort, reviews, reviews_all  # noqa: E402

FIX = pathlib.Path(__file__).parent / "fixtures"


def rows(name):
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))


def fake(name=None, units=None, status="SUCCEEDED", message="ok", seen=None):
    def run(self, run_input, report_key="RUN_REPORT"):
        if seen is not None:
            seen.append(run_input)
        return (rows(name) if name else []), {"status": status, "statusMessage": message}, {"units": units or []}
    return run


class AppStoreTests(unittest.TestCase):
    def test_needs_a_token(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ApifyTokenError):
                AppStore(country="us", app_name="facebook", app_id=284882215)

    def test_same_shape_as_app_store_scraper(self):
        seen = []
        app = AppStore(country="US", app_name="facebook", app_id=284882215, apify_token="t")
        with patch("app_store_reviews._apify.ApifyRunner.run", fake("apple-facebook-us", seen=seen)):
            app.review(how_many=50)
        self.assertEqual(seen[0], {"store": "app_store", "appStoreId": "284882215", "country": "us", "maxReviews": 50, "sort": "newest"})
        self.assertEqual(app.reviews_count, 50)
        first = app.reviews[0]
        for key in ("date", "review", "rating", "isEdited", "title", "userName"):
            self.assertIn(key, first)
        self.assertIsInstance(first["date"], datetime)
        self.assertIsNone(first["date"].tzinfo)
        self.assertIn(first["rating"], range(1, 6))
        self.assertEqual(repr(app), "AppStore(country='us', app_name='facebook', app_id=284882215)")
        self.assertIn("Review count | 50", str(app))

    def test_after_filter_is_passed_and_applied(self):
        seen = []
        app = AppStore(country="us", app_name="facebook", app_id=284882215, apify_token="t")
        cutoff = datetime(2026, 10, 3, 12, 0)
        with patch("app_store_reviews._apify.ApifyRunner.run", fake("apple-facebook-us", seen=seen)):
            app.review(after=cutoff)
        self.assertEqual(seen[0]["reviewsSince"], "2026-10-03")
        self.assertTrue(all(r["date"] >= cutoff for r in app.reviews))

    def test_name_lookup_when_no_id(self):
        app = AppStore(country="nz", app_name="minecraft", apify_token="t")
        with patch("app_store_reviews.stores.requests.get") as get:
            get.return_value.json.return_value = {"results": [{"trackId": 479516143}]}
            self.assertEqual(app.search_id(), 479516143)

    def test_failure_message_is_raised(self):
        app = AppStore(country="us", app_name="x", app_id=1, apify_token="t")
        units = [{"source": "app_store", "status": "failed", "errors": ["The App Store returned no reviews for this app in this country."]}]
        with patch("app_store_reviews._apify.ApifyRunner.run", fake(None, units=units, status="FAILED")):
            with self.assertRaisesRegex(ResponseError, "no reviews"):
                app.review(how_many=5)

    def test_podcast_explains(self):
        with self.assertRaises(NotImplementedError):
            Podcast(country="us", app_name="x", apify_token="t")


class GooglePlayTests(unittest.TestCase):
    def test_same_shape_as_google_play_scraper(self):
        seen = []
        with patch("app_store_reviews._apify.ApifyRunner.run", fake("play-netflix", seen=seen)):
            result, token = reviews("com.netflix.mediaclient", sort=Sort.MOST_RELEVANT, count=40, filter_score_with=1, apify_token="t")
        self.assertIsNone(token)
        self.assertEqual(seen[0]["sort"], "helpfulness")
        self.assertEqual(seen[0]["ratings"], ["1"])
        self.assertEqual(len(result), 40)
        self.assertEqual(set(result[0]), {"reviewId", "userName", "userImage", "content", "score", "thumbsUpCount",
                                          "reviewCreatedVersion", "at", "replyContent", "repliedAt", "appVersion"})
        self.assertIsInstance(result[0]["at"], datetime)

    def test_reviews_all_and_paging(self):
        with patch("app_store_reviews._apify.ApifyRunner.run", fake("play-netflix")):
            self.assertEqual(len(reviews_all("com.netflix.mediaclient", apify_token="t")), 100)
        with self.assertRaises(ValueError):
            reviews("com.netflix.mediaclient", continuation_token="abc", apify_token="t")


if __name__ == "__main__":
    unittest.main()
