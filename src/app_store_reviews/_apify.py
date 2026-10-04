"""Run the CleanScrape App Store & Google Play Reviews Actor on Apify and read its results, using the public REST API."""
from __future__ import annotations

import time

import requests

from .exceptions import ApifyTokenError, ResponseError, SpendingLimitError

ACTOR = "cleanscrape~app-store-reviews-scraper"
API = "https://api.apify.com/v2"
ACTIVE = ("READY", "RUNNING", "TIMING-OUT", "ABORTING")


class ApifyRunner:
    def __init__(self, token, session=None, run_timeout=600, max_charge_usd=None, http_timeout=90):
        if not token:
            raise ApifyTokenError(
                "No Apify token. Set the APIFY_TOKEN environment variable or pass apify_token='...'. "
                "A free account includes $5 of usage a month: https://console.apify.com/settings/integrations"
            )
        self.session = session or requests.Session()
        self.headers = {"Authorization": f"Bearer {token}"}
        self.run_timeout = run_timeout
        self.max_charge_usd = max_charge_usd
        self.http_timeout = http_timeout
        self.last_run = None

    def _call(self, method, path, **kwargs):
        response = self.session.request(method, f"{API}{path}", headers=self.headers, timeout=self.http_timeout, **kwargs)
        if response.status_code == 401:
            raise ApifyTokenError("Apify did not accept the token. Copy it again from https://console.apify.com/settings/integrations")
        if response.status_code == 402:
            raise SpendingLimitError("Your Apify account has no usage credit left this month.", response)
        if response.status_code >= 400:
            try:
                message = response.json().get("error", {}).get("message")
            except ValueError:
                message = None
            raise ResponseError(f"Apify returned HTTP {response.status_code}: {message or response.text[:200]}", response)
        return response

    def run(self, run_input, report_key="RUN_REPORT"):
        """Start a run, wait for it, and return (rows, run, report)."""
        params = {"waitForFinish": 60}
        if self.max_charge_usd is not None:
            params["maxTotalChargeUsd"] = self.max_charge_usd
        run = self._call("POST", f"/acts/{ACTOR}/runs", json=run_input, params=params).json()["data"]
        deadline = time.monotonic() + self.run_timeout
        while run["status"] in ACTIVE:
            if time.monotonic() > deadline:
                raise ResponseError(
                    f"The run took longer than {self.run_timeout} seconds. It keeps running on Apify: "
                    f"https://console.apify.com/view/runs/{run['id']}"
                )
            run = self._call("GET", f"/actor-runs/{run['id']}", params={"waitForFinish": 60}).json()["data"]
        self.last_run = run
        rows = []
        offset = 0
        while True:
            page = self._call(
                "GET", f"/datasets/{run['defaultDatasetId']}/items", params={"clean": "true", "limit": 1000, "offset": offset}
            ).json()
            rows.extend(page)
            if len(page) < 1000:
                break
            offset += 1000
        try:
            report = self._call("GET", f"/key-value-stores/{run['defaultKeyValueStoreId']}/records/{report_key}").json()
        except ResponseError:
            report = {}
        return rows, run, report
