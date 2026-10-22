import pytest

from fetcher import DEFAULT_QUERIES, is_internship, normalize_job


def test_normalize_job_extracts_core_fields():
    raw = {
        "title": "  Estimating Intern ",
        "company_name": "Acme Builders",
        "location": "Las Vegas, NV",
        "description": "Help   prepare\nquantity takeoffs.",
        "apply_options": [{"title": "Indeed", "link": "https://example.com/apply"}],
    }
    job = normalize_job(raw, "Estimating Intern")

    assert job.title == "Estimating Intern"
    assert job.company == "Acme Builders"
    assert job.description == "Help prepare quantity takeoffs."
    assert job.apply_link == "https://example.com/apply"
    assert job.query == "Estimating Intern"


def test_normalize_job_falls_back_to_share_link():
    raw = {"title": "Construction Intern", "share_link": "https://example.com/share"}
    job = normalize_job(raw, "Construction Intern")

    assert job.apply_link == "https://example.com/share"
    assert job.company == "Unknown company"


@pytest.mark.parametrize(
    "title",
    [
        "Project Engineer Intern - Summer 2027",
        "Construction Management Co-op",
        "Summer Internship | Reno",
        "Co-Op Estimating Student",
        "BIM/VDC Intern",
    ],
)
def test_is_internship_keeps_intern_and_coop_titles(title):
    assert is_internship(title)


@pytest.mark.parametrize(
    "title",
    [
        "Junior Estimator - Entry Level",
        "Senior Estimator - Residential Projects",
        "Project Engineer",
        "Internal Auditor",
        "Cooperative Marketing Manager",
    ],
)
def test_is_internship_drops_full_time_titles(title):
    assert not is_internship(title)


def test_default_queries_cover_expanded_roles():
    for query in [
        "Project Management Intern",
        "Safety Intern",
        "BIM / VDC Intern",
        "Preconstruction Intern",
    ]:
        assert query in DEFAULT_QUERIES
