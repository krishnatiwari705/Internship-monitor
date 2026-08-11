from __future__ import annotations

from urllib.parse import quote_plus, urlparse

import feedparser
import requests

HEADERS = {"User-Agent": "InternshipMonitor/3.0"}


def google_news_url(query: str) -> str:
    return "https://news.google.com/rss/search?q=" + quote_plus(query) + "&hl=en-IN&gl=IN&ceid=IN:en"


def discover_ats_targets(queries: list[str], timeout: int = 20) -> dict[str, set[str]]:
    """Discover public ATS board identifiers from search/RSS results.

    Only public identifiers are returned. No private credentials are discovered or stored.
    """
    greenhouse: set[str] = set()
    lever: set[str] = set()

    for query in queries:
        feed = feedparser.parse(google_news_url(query))
        for entry in feed.entries:
            candidate = entry.get("link", "")
            if not candidate:
                continue
            try:
                response = requests.get(candidate, timeout=timeout, allow_redirects=True, headers=HEADERS)
                final_url = response.url
            except requests.RequestException:
                final_url = candidate

            parsed = urlparse(final_url)
            host = parsed.netloc.lower()
            parts = [part for part in parsed.path.split("/") if part]

            if "boards.greenhouse.io" in host and parts:
                greenhouse.add(parts[0])
            elif "jobs.lever.co" in host and parts:
                lever.add(parts[0])

    return {"greenhouse": greenhouse, "lever": lever}
