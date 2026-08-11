from __future__ import annotations

import requests


def fetch_greenhouse(board_token: str, timeout: int = 20) -> list[dict]:
    """Fetch published Greenhouse jobs using the public Job Board API."""
    url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"
    response = requests.get(url, params={"content": "true"}, timeout=timeout)
    response.raise_for_status()
    payload = response.json()

    jobs = []
    for job in payload.get("jobs", []):
        location = (job.get("location") or {}).get("name", "")
        jobs.append({
            "source": "greenhouse",
            "source_id": str(job.get("id")),
            "company": board_token,
            "title": job.get("title", ""),
            "location": location,
            "url": job.get("absolute_url", ""),
            "description": job.get("content", ""),
            "updated_at": job.get("updated_at"),
        })
    return jobs
