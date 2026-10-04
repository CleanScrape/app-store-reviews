# app-store-reviews: a drop-in replacement for app-store-scraper

[app-store-scraper](https://github.com/cowboy-bebug/app-store-scraper) was archived in 2021 and no longer works for most apps. `app-store-reviews` keeps the same `AppStore` class, the same `review()` method and the same review dicts, so existing scripts keep working. It also has a `reviews()` function shaped like [google-play-scraper](https://github.com/JoMingyu/google-play-scraper)'s, for Google Play.

The reviews are collected by the [CleanScrape App Store & Google Play Reviews Actor](https://apify.com/cleanscrape/app-store-reviews-scraper) on Apify, which handles the requests, retries and Apple's flaky review feed for you.

```python
# from app_store_scraper import AppStore     # before
from app_store_reviews import AppStore       # after

minecraft = AppStore(country="nz", app_name="minecraft")
minecraft.review(how_many=20)
print(minecraft.reviews[0])
```

```
     Country | nz
        Name | minecraft
          ID | 479516143
         URL | https://apps.apple.com/nz/app/minecraft/id479516143
Review count | 20
```

## Install

```bash
pip install app-store-reviews
```

Then set your Apify API token. A free Apify account includes $5 of usage a month. Copy the token from [Apify Console > Settings > API & Integrations](https://console.apify.com/settings/integrations).

```bash
export APIFY_TOKEN=your_token          # macOS / Linux
setx APIFY_TOKEN your_token            # Windows (open a new terminal afterwards)
```

Or pass it in code: `AppStore(..., apify_token="...")`. Keep the token out of shared notebooks and repositories.

## App Store (same as app-store-scraper)

```python
from datetime import datetime
from app_store_reviews import AppStore

app = AppStore(country="us", app_name="spotify", app_id=324684580)  # app_id is optional
app.review(how_many=200, after=datetime(2026, 9, 1))

app.reviews        # list of dicts
app.reviews_count  # 200 or fewer
app.search_id()    # finds the numeric ID from the name, free (no Apify run)
```

Each review has the keys app-store-scraper used: `date` (datetime, UTC), `review`, `rating`, `title`, `userName`, `isEdited`, and `developerResponse` when there is one. It also adds `reviewId`, `appVersion`, `country` and `url`. `isEdited` is `None`, because Apple's public feed doesn't say.

**Limit:** Apple's public review feed holds about the 500 most recent reviews per app and country. For older reviews, run other countries, where the app has its own reviews.

`Podcast` is not supported.

## Google Play (shaped like google-play-scraper)

```python
from app_store_reviews import Sort, reviews, reviews_all

result, _ = reviews("com.spotify.music", lang="en", country="us", sort=Sort.NEWEST, count=500, filter_score_with=1)
everything = reviews_all("com.spotify.music")  # up to 10,000
```

Each review has google-play-scraper's keys: `reviewId`, `userName`, `content`, `score`, `thumbsUpCount`, `reviewCreatedVersion`, `at`, `replyContent`, `repliedAt` and `appVersion`. `userImage` is `None`. There is no paging token: ask for the count you need in one call.

## Errors

`ResponseError` when no reviews could be read (the message says why), `SpendingLimitError` when a run hits your spending cap, and `ApifyTokenError` for a missing or rejected token. Set a cap per run with `max_charge_usd=`.

## What it costs

You pay Apify for the Actor's reviews, at the [current price](https://apify.com/cleanscrape/app-store-reviews-scraper/pricing): $0.20 per 1,000 reviews plus a start fee of about $0.01 per call at the base price. 200 reviews cost about $0.05, and 2,000 Google Play reviews about $0.41. The free monthly credit covers tens of thousands of reviews.

## Testing

```bash
python -m unittest discover -s tests
```

The tests run offline on rows saved from the Actor, with reviewer names and texts replaced by placeholders.

## About

Maintained by [CleanScrape](https://apify.com/cleanscrape). Not affiliated with Apple, Google or the original libraries. MIT licence.

Bugs and ideas: [open an issue](https://github.com/CleanScrape/app-store-reviews/issues) or email contact.cleanscrape@gmail.com.
