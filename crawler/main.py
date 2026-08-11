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

from discovery import discover_ats_targets
from scoring import score_job
from sources.greenhouse import fetch_greenhouse as greenhouse_adapter
from sources.lever import fetch_lever as lever_adapter

ROOT = Path(__file__).resolve().parent
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
PROFILE = json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
OUTPUT = DATA_DIR / "jobs.json"
SEEN = DATA_DIR / "seen.json"
NEW_OUTPUT = DATA_DIR / "new_jobs.json"

HEADERS = {
    "User-Agent": "InternshipMonitor/3.1 (+https://github.com/krishnatiwari705/Internship-monitor)",
    "Accept": "application/json, application/rss+xml, application/xml, text/html;q=0.9, */*;q=0.8",
}
TIMEOUT = 25

ROLE_TERMS = tuple(x.lower() for x in CONFIG["roles"])
ENTRY_TERMS = tuple(x.lower() for x in CONFIG["entry_terms"])
LOCATION_TERMS = tuple(x.lower() for x in CONFIG["locations"])


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", BeautifulSoup(value or "", "html.parser").get_text(" ")).strip()


def stable_id(source: str, external_id: str, url: str, title: str) -> str:
    raw = f"{source}|{external_id}|{url}|{title}".lower().strip()
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


def parse_dt(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
    except ValueError:
        return value


def relevant(title: str, description: str, location: str) -> bool:
    text = f"{title} {description}".lower()
    loc = location.lower()
    return (
        any(term in text for term in ROLE_TERMS)
        and any(term in text for term in ENTRY_TERMS)
        and any(term in loc or term in text for term in LOCATION_TERMS)
    )


def normalize(company: str, source: str, title: str, description: str, location: str,
              url: str, external_id: str, published: str | None = None,
              updated: str | None = None, source_type: str = "unknown") -> dict | None:
    title = clean(title)
    description = clean(description)
    location = clean(location) or "India"
    if not title or not url or not relevant(title, description, location):
        return None

    match = score_job({"title": title, "description": description, "location": location}, PROFILE)
    now = datetime.now(timezone.utc).isoformat()

    return {
        "id": stable_id(source, external_id, url, title),
        "title": title,
        "company": clean(company) or "Unknown company",
        "location": location,
        "source": source,
        "source_type": source_type,
        "url": url,
        "published": parse_dt(published),
        "updated": parse_dt(updated),
        "description": description[:6000],
        "match_score": match["match_score"],
        "matched_skills": match["matched_skills"],
        "missing_skills": match["missing_skills"],
        "first_seen": now,
        "last_seen": now,
    }


def google_news_url(query: str) -> str:
    return "https://news.google.com/rss/search?q=" + quote_plus(query) + "&hl=en-IN&gl=IN&ceid=IN:en"


def fetch_rss() -> list[dict]:
    results = []
    for source_cfg in CONFIG["sources"].get("rss", []):
        try:
            feed = feedparser.parse(google_news_url(source_cfg["query"]))
            for entry in feed.entries:
                title = entry.get("title", "")
                description = entry.get("summary", "")
                text = f"{title} {description}".lower()
                location = next((x for x in CONFIG["locations"] if x.lower() in text), "India")
                job = normalize(
                    company=getattr(entry.get("source"), "title", None) or source_cfg["name"],
                    source=source_cfg["name"],
                    title=title,
                    description=description,
                    location=location,
                    url=entry.get("link", ""),
                    external_id=entry.get("id", entry.get("link", "")),
                    published=entry.get("published") or entry.get("updated"),
                    updated=entry.get("updated") or entry.get("published"),
                    source_type="rss",
                )
                if job:
                    results.append(job)
        except Exception as exc:  # noqa: BLE001
            print(f"RSS source failed: {source_cfg['name']}: {exc}")
    return results


def fetch_structured_ats() -> tuple[list[dict], dict]:
    results = []
    discovered = {"greenhouse": set(), "lever": set()}

    # Discover public ATS identifiers from fresh search results, then query the ATS directly.
    if os.getenv("DISABLE_ATS_DISCOVERY", "0") != "1":
        try:
            discovered = discover_ats_targets(CONFIG.get("ats_discovery_queries", []))
        except Exception as exc:  # noqa: BLE001
            print(f"ATS discovery failed: {exc}")

    greenhouse = list(CONFIG["sources"].get("greenhouse", []))
    greenhouse += [x.strip() for x in os.getenv("GREENHOUSE_BOARDS", "").split(",") if x.strip()]
    greenhouse += sorted(discovered["greenhouse"])

    seen_greenhouse = set()
    for board in greenhouse:
        token = board.get("token") if isinstance(board, dict) else board
        company = board.get("company", token) if isinstance(board, dict) else token
        if not token or token in seen_greenhouse:
            continue
        seen_greenhouse.add(token)
        try:
            for item in greenhouse_adapter(token):
                job = normalize(
                    company=company,
                    source="Greenhouse",
                    title=item["title"],
                    description=item["description"],
                    location=item["location"],
                    url=item["url"],
                    external_id=item["source_id"],
                    updated=item.get("updated_at"),
                    source_type="greenhouse",
                )
                if job:
                    results.append(job)
        except requests.RequestException as exc:
            print(f"Greenhouse source failed for {company}: {exc}")

    lever = list(CONFIG["sources"].get("lever", []))
    lever += [x.strip() for x in os.getenv("LEVER_SITES", "").split(",") if x.strip()]
    lever += sorted(discovered["lever"])

    seen_lever = set()
    for site_cfg in lever:
        site = site_cfg.get("site") if isinstance(site_cfg, dict) else site_cfg
        company = site_cfg.get("company", site) if isinstance(site_cfg, dict) else site
        if not site or site in seen_lever:
            continue
        seen_lever.add(site)
        try:
            for item in lever_adapter(site):
                job = normalize(
                    company=company,
                    source="Lever",
                    title=item["title"],
                    description=item["description"],
                    location=item["location"],
                    url=item["url"],
                    external_id=item["source_id"],
                    updated=item.get("updated_at"),
                    source_type="lever",
                )
                if job:
                    results.append(job)
        except requests.RequestException as exc:
            print(f"Lever source failed for {company}: {exc}")

    return results, {
        "greenhouse_discovered": sorted(discovered["greenhouse"]),
        "lever_discovered": sorted(discovered["lever"]),
    }


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def merge_jobs(existing: list[dict], incoming: list[dict]) -> tuple[list[dict], list[dict]]:
    by_id = {job["id"]: job for job in existing if job.get("id")}
    seen_ids = set(load_json(SEEN, []))
    fresh = []

    for job in incoming:
        old = by_id.get(job["id"])
        if old:
            job["first_seen"] = old.get("first_seen", job["first_seen"])
            if job.get("updated") and job.get("updated") != old.get("updated"):
                job["status"] = "updated"
            else:
                job["status"] = old.get("status", "seen")
        else:
            job["status"] = "new"
        job["last_seen"] = datetime.now(timezone.utc).isoformat()
        by_id[job["id"]] = job
        if job["id"] not in seen_ids:
            fresh.append(job)
            seen_ids.add(job["id"])

    return list(by_id.values()), fresh


def main() -> None:
    existing = load_json(OUTPUT, {"generated": None, "jobs": []})
    structured, discovery_meta = fetch_structured_ats()
    incoming = structured + fetch_rss()
    jobs, fresh = merge_jobs(existing.get("jobs", []), incoming)

    jobs.sort(
        key=lambda x: (
            x.get("match_score", 0),
            x.get("updated") or x.get("published") or "",
        ),
        reverse=True,
    )

    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "generated": now,
        "new_count": len(fresh),
        "source_counts": {
            "greenhouse": sum(x.get("source_type") == "greenhouse" for x in incoming),
            "lever": sum(x.get("source_type") == "lever" for x in incoming),
            "rss": sum(x.get("source_type") == "rss" for x in incoming),
        },
        "discovery": discovery_meta,
        "jobs": jobs,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    SEEN.write_text(json.dumps(sorted({job["id"] for job in jobs}), indent=2), encoding="utf-8")
    NEW_OUTPUT.write_text(json.dumps({"generated": now, "jobs": fresh}, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Fetched relevant jobs: {len(incoming)}")
    print(f"New jobs: {len(fresh)}")
    print(f"Stored jobs: {len(jobs)}")
    print(f"Discovered Greenhouse boards: {len(discovery_meta['greenhouse_discovered'])}")
    print(f"Discovered Lever sites: {len(discovery_meta['lever_discovered'])}")


if __name__ == "__main__":
    main()
