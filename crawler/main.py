from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
OUTPUT = DATA_DIR / "jobs.json"
SEEN = DATA_DIR / "seen.json"
NEW_OUTPUT = DATA_DIR / "new_jobs.json"

HEADERS = {
    "User-Agent": "InternshipMonitor/2.0 (+https://github.com/krishnatiwari705/Internship-monitor)",
    "Accept": "application/json, application/rss+xml, application/xml, text/html;q=0.9, */*;q=0.8",
}
TIMEOUT = 25

ROLE_TERMS = tuple(x.lower() for x in CONFIG["roles"])
ENTRY_TERMS = tuple(x.lower() for x in CONFIG["entry_terms"])
LOCATION_TERMS = tuple(x.lower() for x in CONFIG["locations"])
SKILLS = tuple(x.lower() for x in CONFIG.get("skills", []))


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", BeautifulSoup(value or "", "html.parser").get_text(" ")).strip()


def stable_id(source: str, external_id: str, url: str, title: str) -> str:
    raw = f"{source}|{external_id}|{url}|{title}".lower().strip()
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


def parse_dt(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc).isoformat()
    except ValueError:
        return value


def relevant(title: str, description: str, location: str) -> bool:
    text = f"{title} {description}".lower()
    loc = location.lower()
    has_role = any(term in text for term in ROLE_TERMS)
    has_entry = any(term in text for term in ENTRY_TERMS)
    has_location = any(term in loc or term in text for term in LOCATION_TERMS)
    return has_role and has_entry and has_location


def score(title: str, description: str, location: str) -> tuple[int, list[str], list[str]]:
    text = f"{title} {description}".lower()
    matched = [skill for skill in SKILLS if skill in text]
    missing = []
    for skill in CONFIG.get("priority_skills", []):
        if skill.lower() not in text:
            missing.append(skill)

    points = 35
    if any(x in text for x in ("ai engineer", "generative ai", "genai", "rag", "llm", "machine learning")):
        points += 20
    if any(x in text for x in ("backend", "software engineer", "sde", "full stack", "fullstack")):
        points += 15
    if any(x in location.lower() for x in ("delhi", "noida", "gurgaon", "gurugram")):
        points += 10
    if "2027" in text:
        points += 10
    elif any(x in text for x in ("2026", "2025", "2024")):
        points += 3
    points += min(10, len(matched))
    return min(points, 100), matched, missing[:6]


def resolve_url(url: str) -> str:
    """Follow search/feed redirects so the stored URL is useful to the applicant."""
    if not url or "news.google.com" not in url:
        return url
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        final = response.url
        if final and "news.google.com" not in final:
            return final
    except requests.RequestException:
        pass
    return url


def normalize(company: str, source: str, title: str, description: str, location: str,
              url: str, external_id: str, published: str | None = None,
              updated: str | None = None, source_type: str = "unknown") -> dict | None:
    title = clean(title)
    description = clean(description)
    location = clean(location) or "India"
    if not title or not url or not relevant(title, description, location):
        return None

    final_url = resolve_url(url)
    match, matched, missing = score(title, description, location)
    now = datetime.now(timezone.utc).isoformat()

    return {
        "id": stable_id(source, external_id, final_url, title),
        "title": title,
        "company": clean(company) or "Unknown company",
        "location": location,
        "source": source,
        "source_type": source_type,
        "url": final_url,
        "published": parse_dt(published),
        "updated": parse_dt(updated),
        "description": description[:5000],
        "match_score": match,
        "matched_skills": matched,
        "missing_priority_skills": missing,
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
                source_name = getattr(entry.get("source"), "title", None) or source_cfg["name"]
                published = entry.get("published") or entry.get("updated")
                job = normalize(
                    company=source_name,
                    source=source_cfg["name"],
                    title=entry.get("title", ""),
                    description=entry.get("summary", ""),
                    location=" ".join(CONFIG["locations"]),
                    url=entry.get("link", ""),
                    external_id=entry.get("id", entry.get("link", "")),
                    published=published,
                    updated=published,
                    source_type="rss",
                )
                if job:
                    # Infer the actual location from title/description instead of using the full target list.
                    text = f"{job['title']} {job['description']}".lower()
                    job["location"] = next((x for x in CONFIG["locations"] if x.lower() in text), "India")
                    results.append(job)
        except Exception as exc:  # noqa: BLE001
            print(f"RSS source failed: {source_cfg['name']}: {exc}")
    return results


def fetch_greenhouse() -> list[dict]:
    """Fetch published Greenhouse boards. Public GET endpoints require no API key."""
    results = []
    boards = CONFIG["sources"].get("greenhouse", [])
    env_boards = [x.strip() for x in os.getenv("GREENHOUSE_BOARDS", "").split(",") if x.strip()]
    for board in boards + env_boards:
        token = board.get("token") if isinstance(board, dict) else board
        company = board.get("company", token) if isinstance(board, dict) else token
        if not token:
            continue
        url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
        try:
            response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            response.raise_for_status()
            payload = response.json()
            for item in payload.get("jobs", []):
                location = (item.get("location") or {}).get("name", "")
                job = normalize(
                    company=company,
                    source="Greenhouse",
                    title=item.get("title", ""),
                    description=item.get("content", ""),
                    location=location,
                    url=item.get("absolute_url", ""),
                    external_id=str(item.get("id", "")),
                    published=item.get("first_published"),
                    updated=item.get("updated_at"),
                    source_type="greenhouse",
                )
                if job:
                    results.append(job)
        except requests.RequestException as exc:
            print(f"Greenhouse source failed for {company}: {exc}")
    return results


def fetch_lever() -> list[dict]:
    """Fetch published Lever postings using the public postings endpoint."""
    results = []
    boards = CONFIG["sources"].get("lever", [])
    env_boards = [x.strip() for x in os.getenv("LEVER_SITES", "").split(",") if x.strip()]
    for board in boards + env_boards:
        site = board.get("site") if isinstance(board, dict) else board
        company = board.get("company", site) if isinstance(board, dict) else site
        if not site:
            continue
        url = f"https://api.lever.co/v0/postings/{site}?mode=json"
        try:
            response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            response.raise_for_status()
            payload = response.json()
            for item in payload:
                categories = item.get("categories") or {}
                location = categories.get("location", "")
                description = " ".join([
                    item.get("descriptionPlain", ""),
                    item.get("additionalPlain", ""),
                    json.dumps(item.get("lists", [])),
                ])
                job = normalize(
                    company=company,
                    source="Lever",
                    title=item.get("text", ""),
                    description=description,
                    location=location,
                    url=item.get("hostedUrl") or item.get("applyUrl", ""),
                    external_id=str(item.get("id", "")),
                    published=None,
                    updated=None,
                    source_type="lever",
                )
                if job:
                    results.append(job)
        except requests.RequestException as exc:
            print(f"Lever source failed for {company}: {exc}")
    return results


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def merge_jobs(existing: list[dict], incoming: list[dict]) -> tuple[list[dict], list[dict]]:
    by_id = {job["id"]: job for job in existing if job.get("id")}
    fresh = []
    seen_ids = set(load_json(SEEN, []))

    for job in incoming:
        old = by_id.get(job["id"])
        if old:
            job["first_seen"] = old.get("first_seen", job["first_seen"])
            # Preserve the original timestamp when a source does not expose updates.
            job["last_seen"] = datetime.now(timezone.utc).isoformat()
            if job.get("updated") and job.get("updated") != old.get("updated"):
                job["status"] = "updated"
            else:
                job["status"] = old.get("status", "seen")
        else:
            job["status"] = "new"

        by_id[job["id"]] = job
        if job["id"] not in seen_ids:
            fresh.append(job)
            seen_ids.add(job["id"])

    return list(by_id.values()), fresh


def main() -> None:
    existing = load_json(OUTPUT, {"generated": None, "jobs": []})
    incoming = fetch_greenhouse() + fetch_lever() + fetch_rss()
    jobs, fresh = merge_jobs(existing.get("jobs", []), incoming)

    # Highest-match jobs first, then newest/most recently updated.
    jobs.sort(key=lambda x: (x.get("match_score", 0), x.get("updated") or x.get("published") or ""), reverse=True)

    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "generated": now,
        "new_count": len(fresh),
        "source_counts": {
            "greenhouse": sum(x.get("source_type") == "greenhouse" for x in incoming),
            "lever": sum(x.get("source_type") == "lever" for x in incoming),
            "rss": sum(x.get("source_type") == "rss" for x in incoming),
        },
        "jobs": jobs,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    SEEN.write_text(json.dumps(sorted({job["id"] for job in jobs}), indent=2), encoding="utf-8")
    NEW_OUTPUT.write_text(json.dumps({"generated": now, "jobs": fresh}, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Fetched relevant jobs: {len(incoming)}")
    print(f"New jobs: {len(fresh)}")
    print(f"Stored jobs: {len(jobs)}")


if __name__ == "__main__":
    main()
