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


def test_score_prefers_profile_skills():
    score, matched, missing = module.score(
        "Backend AI Engineer Intern",
        "Python FastAPI REST APIs RAG LangChain MongoDB Docker Git",
        "Gurgaon, Haryana",
    )
    assert score >= 80
    assert "python" in matched
    assert "FastAPI" not in missing
