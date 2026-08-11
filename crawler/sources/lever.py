from __future__ import annotations

import requests


def fetch_lever(site: str, timeout: int = 20) -> list[dict]:
    """Fetch published Lever postings for a company's public site."""
    url = f"https://api.lever.co/v0/postings/{site}"
    response = requests.get(url, params={"mode": "json"}, timeout=timeout)
    response.raise_for_status()
    payload = response.json()

    jobs = []
    for job in payload:
        categories = job.get("categories") or {}
        jobs.append({
            "source": "lever",
            "source_id": str(job.get("id", "")),
            "company": site,
            "title": job.get("text", ""),
            "location": categories.get("location", ""),
            "url": job.get("hostedUrl") or job.get("applyUrl") or "",
            "description": job.get("descriptionPlain", "") or job.get("description", ""),
            "updated_at": job.get("createdAt"),
        })
    return jobs
