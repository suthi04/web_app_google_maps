"""Collect an auditable, bounded review pool for the Pupen evaluation.

Requires the project's existing APIFY_TOKEN. Never prints or saves the token.
Usage: python -m eval.collect_pupen_reviews start|status|download
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

import requests

import config

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "data" / "pupen_collection"
MAPS_URL = "https://www.google.com/maps/place/Pupen+Seafood/@12.86157,100.8954451,15z/data=!4m5!3m4!1s0x0:0x74db886f251470ae!8m2!3d12.86157!4d100.8954451"
ACTOR = "compass~google-maps-reviews-scraper"
API = "https://api.apify.com/v2"


def request(method, path, **kwargs):
    try:
        response = requests.request(
            method, API + path,
            headers={"Authorization": "Bearer " + config.get_apify_token()},
            timeout=45, **kwargs,
        )
    except requests.RequestException as exc:
        raise SystemExit(f"Apify network failure: {type(exc).__name__}") from None
    if response.status_code >= 300:
        error = response.json().get("error", {})
        raise SystemExit(f"Apify HTTP {response.status_code}: {error.get('type', 'unknown')}")
    return response.json()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "status", "download"])
    parser.add_argument("--sort", choices=["newest", "mostRelevant", "lowestRanking"], default="mostRelevant")
    parser.add_argument("--max-reviews", type=int, default=600)
    parser.add_argument("--filter", default="", help="Optional Google review keyword filter; recorded as sampling bias.")
    parser.add_argument("--tag", help="Distinct local collection name for a keyword-filtered run.")
    args = parser.parse_args()
    if not config.get_apify_token():
        raise SystemExit("APIFY_TOKEN is not configured; sample fallback is forbidden.")
    tag = args.tag or args.sort
    if not re.fullmatch(r"[A-Za-z0-9_-]+", tag):
        raise SystemExit("Invalid local collection tag.")
    path = DIRECTORY / f"{tag}_run.json"
    if args.action == "start":
        if path.exists():
            raise SystemExit("A recorded run already exists; use status/download instead.")
        if not 1 <= args.max_reviews <= 600:
            raise SystemExit("This collection is bounded to 600 reviews per run.")
        payload = {
            "startUrls": [{"url": MAPS_URL}], "maxReviews": args.max_reviews,
            "reviewsSort": args.sort, "language": "th", "reviewsOrigin": "google",
            "personalData": False,
        }
        if args.filter:
            payload["reviewsFilterString"] = args.filter
        run = request("POST", f"/acts/{ACTOR}/runs", params={"maxTotalChargeUsd": 0.50, "timeout": 600}, json=payload)["data"]
        metadata = {"actor": ACTOR, "input": payload, "max_total_charge_usd": 0.50,
                    "run_id": run["id"], "dataset_id": run["defaultDatasetId"],
                    "requested_at": datetime.now(timezone.utc).isoformat()}
        save(path, metadata)
    else:
        metadata = json.loads(path.read_text(encoding="utf-8"))
        run = request("GET", f"/actor-runs/{metadata['run_id']}")["data"]
    for field in ("status", "startedAt", "finishedAt", "buildId", "usageTotalUsd"):
        metadata[field] = run.get(field)
    save(path, metadata)
    print(json.dumps(metadata, ensure_ascii=False))
    if args.action == "download":
        if run["status"] != "SUCCEEDED":
            raise SystemExit("Only successful completed runs can be downloaded.")
        items = request("GET", f"/datasets/{metadata['dataset_id']}/items", params={"clean": "true", "limit": 1000})
        # Retain source evidence, not reviewer names, profiles or photographs.
        fields = ("reviewId", "reviewUrl", "text", "textTranslated", "originalLanguage",
                  "translatedLanguage", "stars", "publishedAtDate", "reviewOrigin",
                  "title", "placeId", "cid", "url", "reviewsCount", "scrapedAt")
        reviews = [{key: item.get(key) for key in fields if key in item} for item in items]
        save(DIRECTORY / f"{tag}_reviews.json", {"collection": metadata, "reviews": reviews})
        print(f"Saved {len(reviews)} source records; fields: {sorted({key for item in reviews for key in item})}")


if __name__ == "__main__":
    main()
