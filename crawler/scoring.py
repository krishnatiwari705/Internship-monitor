from __future__ import annotations

import re


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9+#.]+", (text or "").lower()))


def score_job(job: dict, profile: dict) -> dict:
    """Score a job deterministically so results remain explainable."""
    text = " ".join([
        job.get("title", ""),
        job.get("location", ""),
        job.get("description", ""),
    ]).lower()

    skills = profile.get("skills", [])
    skill_hits = [skill for skill in skills if skill.lower() in text]
    missing = [skill for skill in skills if skill.lower() not in text]

    location_hits = [x for x in profile.get("locations", []) if x.lower() in text]
    entry_hits = [x for x in profile.get("entry_terms", []) if x.lower() in text]

    score = 0
    score += min(55, len(skill_hits) * 5)
    score += min(20, len(location_hits) * 10)
    score += min(15, len(entry_hits) * 5)

    title = job.get("title", "").lower()
    if any(term in title for term in profile.get("preferred_roles", [])):
        score += 10

    score = min(score, 100)

    return {
        "match_score": score,
        "matched_skills": skill_hits,
        "missing_skills": missing[:12],
        "location_match": bool(location_hits),
        "entry_signal": bool(entry_hits),
    }
