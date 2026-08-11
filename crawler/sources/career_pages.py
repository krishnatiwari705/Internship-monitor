"""Discover public startup boards and company career pages.

This uses public search/RSS discovery and ordinary public HTTP requests only. It does
not bypass authentication, robots controls, or anti-bot mechanisms.
"""
from __future__ import annotations

import re
from urllib.parse import quote_plus, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "InternshipMonitor/4.0 (+https://github.com/krishnatiwari705/Internship-monitor)"
}

STARTUP_QUERIES = [
    'site:wellfound.com/jobs internship (AI OR backend OR software OR full stack) India',
    'site:cutshort.io/job internship (AI OR backend OR software OR full stack) India',
    'site:internshala.com/internship/detail internship (AI OR backend OR software OR full stack) (Delhi OR Noida OR Gurgaon)',
    'site:unstop.com/internships internship (AI OR backend OR software OR full stack) (Delhi OR Noida OR Gurgaon)',
    'site:jobs.ashbyhq.com internship (AI OR backend OR software OR full stack) India',
    'site:jobs.workable.com internship (AI OR backend OR software OR full stack) India',
]

CAREER_QUERIES = [
    '"careers" "software engineer intern" India startup',
    '"careers" "AI intern" India startup',
    '"careers" "backend intern" India startup',
    '"careers" "SDE intern" India startup',
    '"careers" "full stack intern" India startup',
]


def _rss(query: str):
    return feedparser.parse(
        "https://news.google.com/rss/search?q="
        + quote_plus(query)
        + "&hl=en-IN&gl=IN&ceid=IN:en"
    )


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", BeautifulSoup(value or "", "html.parser").get_text(" ")).strip()


def _is_relevant_host(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    markers = (
        "wellfound.com",
        "cutshort.io",
        "internshala.com",
        "unstop.com",
        "ashbyhq.com",
        "workable.com",
    )
    return any(marker in host for marker in markers) or "/careers" in url.lower() or "/jobs" in url.lower()


def discover() -> list[dict]:
    """Return public startup-board and company-career leads."""
    results: list[dict] = []
    query_groups = (
        [(q, "startup_board") for q in STARTUP_QUERIES]
        + [(q, "career_page") for q in CAREER_QUERIES]
    )

    for query, kind in query_groups:
        feed = _rss(query)
        for entry in feed.entries:
            url = entry.get("link", "")
            if not url or not _is_relevant_host(url):
                continue
            results.append(
                {
                    "title": _clean(entry.get("title", "")),
                    "description": _clean(entry.get("summary", "")),
                    "url": url,
                    "published": entry.get("published") or entry.get("updated"),
                    "source": "Startup / career public search",
                    "source_type": kind,
                    "verification": "public_search_result",
                }
            )
    return results


def fetch_public_page(url: str, timeout: int = 20) -> dict | None:
    """Fetch an ordinary public HTML career page when accessible."""
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=timeout,
            allow_redirects=True,
        )
        response.raise_for_status()
    except requests.RequestException:
        return None

    if "text/html" not in response.headers.get("content-type", ""):
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    title = _clean(soup.title.get_text(" ") if soup.title else "")
    text = _clean(soup.get_text(" "))
    return {"title": title, "text": text[:12000], "url": response.url}
