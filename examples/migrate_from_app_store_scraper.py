"""A typical app-store-scraper script. The only change is the import line.

Before:  from app_store_scraper import AppStore
After:   from app_store_reviews import AppStore      (and set the APIFY_TOKEN environment variable)
"""
from app_store_reviews import AppStore, Sort, reviews

minecraft = AppStore(country="nz", app_name="minecraft")
minecraft.review(how_many=20)
print(minecraft)
for r in minecraft.reviews[:3]:
    print(r["date"], r["rating"], r["title"])

# Google Play, shaped like google_play_scraper.reviews()
result, _ = reviews("com.mojang.minecraftpe", lang="en", country="nz", sort=Sort.NEWEST, count=20)
for r in result[:3]:
    print(r["at"], r["score"], r["content"][:60])
