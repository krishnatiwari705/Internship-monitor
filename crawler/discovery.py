from __future__ import annotations

import re
from urllib.parse import urlparse

import feedparser
import requests

from main import google_news_url, clean


def discover_ats_targets(queries: list[str], timeout: int = 20) -> dict[str, set[str]]:
    """Discover public ATS board identifiers from search/RSS results.

    This intentionally discovers only public identifiers; it never discovers or stores
    private credentials. The result can be fed into the public Greenhouse/Lever adapters.
    """
    greenhouse: set[str] = set()
    lever: set[str] = set()

    for query in queries:
        feed = feedparser.parse(google_news_url(query))
        for entry in feed.entries:
            candidate_urls = [entry.get("link", "")]
            source_url = entry.get("source")
            if isinstance(source_url, dict):
                candidate_urls.append(source_url.get("href", ""))

            for candidate in candidate_urls:
                try:
                    response = requests.get(candidate, timeout=timeout, allow_redirects=True,
                                            headers={"User-Agent": "InternshipMonitor/3.0"})
                    final = response.url
                except requests.RequestException:
                    final = candidate

                parsed = urlparse(final)
                host = parsed.netloc.lower()
                parts = [p for p in parsed.path.split("/") if p]

                if "boards.greenhouse.io" in host and parts:
                    greenhouse.add(parts[0])
                elif "jobs.lever.co" in host and parts:
                    lever.add(parts[0])

    return {"greenhouse": greenhouse, "lever": lever}
