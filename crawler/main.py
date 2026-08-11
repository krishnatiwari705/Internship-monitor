from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

import feedparser
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
OUTPUT = DATA_DIR / "jobs.json"
SEEN = DATA_DIR / "seen.json"

ROLE_TERMS = tuple(x.lower() for x in CONFIG["roles"])
ENTRY_TERMS = tuple(x.lower() for x in CONFIG["entry_terms"])
LOCATION_TERMS = tuple(x.lower() for x in CONFIG["locations"])


def clean(value: str) -> str:
    return re.sub(r"\\s+", " ", BeautifulSoup(value or "", "html.parser").get_text(" ")).strip()


def stable_id(source: str, url: str, title: str) -> str:
    raw = f"{source}|{url}|{title}".lower().strip()
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


def relevant(title: str, summary: str) -> bool:
    text = f"{title} {summary}".lower()
    return (
        any(term in text for term in ROLE_TERMS)
        and any(term in text for term in ENTRY_TERMS)
        and any(term in text for term in LOCATION_TERMS)
    )


def google_news_url(query: str) -> str:
    return "https://news.google.com/rss/search?q=" + quote_plus(query) + "&hl=en-IN&gl=IN&ceid=IN:en"


def fetch_rss():
    results = []
    for source in CONFIG["sources"].get("rss", []):
        url = google_news_url(source["query"])
        feed = feedparser.parse(url)
        for entry in feed.entries:
            title = clean(entry.get("title", ""))
            summary = clean(entry.get("summary", ""))
            link = entry.get("link", "")
            if not title or not link or not relevant(title, summary):
                continue
            published = entry.get("published", "")
            results.append({
                "id": stable_id(source["name"], link, title),
                "title": title,
                "company": source["name"],
                "location": next((x for x in CONFIG["locations"] if x.lower() in f"{title} {summary}".lower()), "India"),
                "source": source["name"],
                "url": link,
                "published": published,
                "summary": summary[:1000],
                "discovered_at": datetime.now(timezone.utc).isoformat(),
            })
    return results


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def main():
    existing = load_json(OUTPUT, {"generated": None, "jobs": []})
    seen = set(load_json(SEEN, []))
    fresh = fetch_rss()

    unique = {}
    for job in existing.get("jobs", []):
        unique[job["id"]] = job
    for job in fresh:
        unique[job["id"]] = job

    new_ids = [job["id"] for job in fresh if job["id"] not in seen]
    seen.update(job["id"] for job in fresh)

    payload = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "new_count": len(new_ids),
        "jobs": list(unique.values()),
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    SEEN.write_text(json.dumps(sorted(seen), indent=2), encoding="utf-8")

    print(f"Fetched relevant jobs: {len(fresh)}")
    print(f"New jobs since previous run: {len(new_ids)}")


if __name__ == "__main__":
    main()
