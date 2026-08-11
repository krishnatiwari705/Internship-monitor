import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("crawler_main", ROOT / "main.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_relevant_ai_internship_in_noida():
    assert module.relevant(
        "AI Engineer Intern",
        "Build RAG applications with Python, FastAPI and LangChain.",
        "Noida, Uttar Pradesh",
    )


def test_reject_unrelated_role():
    assert not module.relevant(
        "Marketing Intern",
        "Social media and campaign management.",
        "Noida, Uttar Pradesh",
    )


def test_normalize_scores_profile_skills():
    job = module.normalize(
        company="Example",
        source="test",
        title="Backend AI Engineer Intern",
        description="Python FastAPI REST APIs RAG LangChain MongoDB Docker Git",
        location="Gurgaon, Haryana",
        url="https://example.com/jobs/1",
        external_id="1",
        source_type="test",
    )
    assert job is not None
    assert job["match_score"] >= 80
    assert "python" in job["matched_skills"]
    assert "FastAPI" not in job["missing_skills"]
