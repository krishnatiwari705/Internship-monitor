"""Public LinkedIn hiring-post discovery.

This module deliberately uses search-engine/RSS discovery of publicly indexed LinkedIn
URLs. It does not log in to LinkedIn, bypass controls, or scrape authenticated pages.
"""
from __future__ import annotations

import re
from urllib.parse import quote_plus

import feedparser


QUERIES = [
    'site:linkedin.com/posts ("we are hiring" OR "hiring interns" OR "internship opportunity") (AI OR GenAI OR backend OR software)',
    'site:linkedin.com/posts ("looking for interns" OR "interns wanted" OR "hiring") (Python OR Java OR React OR Node.js)',
    'site:linkedin.com/posts ("AI intern" OR "ML intern" OR "GenAI intern" OR "RAG intern") (Delhi OR Noida OR Gurgaon OR Gurugram OR India)',
    'site:linkedin.com/posts ("backend intern" OR "SDE intern" OR "software engineer intern" OR "full stack intern") (Delhi OR Noida OR Gurgaon OR Gurugram OR India)',
]


def discover() -> list[dict]:
    """Return publicly indexed LinkedIn post leads for later verification."""
    results: list[dict] = []
    for query in QUERIES:
        feed = feedparser.parse(
            "https://news.google.com/rss/search?q="
            + quote_plus(query)
            + "&hl=en-IN&gl=IN&ceid=IN:en"
        )
        for entry in feed.entries:
            url = entry.get("link", "")
            title = re.sub(r"\s+", " ", entry.get("title", "")).strip()
            summary = re.sub(r"\s+", " ", entry.get("summary", "")).strip()
            if "linkedin.com" not in url.lower():
                continue
            results.append({
                "title": title,
                "description": summary,
                "url": url,
                "source": "LinkedIn public post lead",
                "verification": "public_search_result",
            })
    return results
