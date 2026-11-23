import json
from dataclasses import asdict
from datetime import date

import pytest
import requests

import fetcher
from fetcher import (
    DEFAULT_QUERIES,
    Job,
    is_internship,
    is_southern_nevada,
    is_top_contractor,
    load_or_fetch,
    mentions_summer_2027,
    normalize_job,
    parse_deadline,
    parse_posted_on,
)

TODAY = date(2026, 11, 23)


def sample_job() -> Job:
    return Job(
        company="Acme Builders",
        title="Estimating Intern",
        location="Las Vegas, NV",
        description="",
        apply_link="https://example.com/apply",
        query="Estimating Intern",
    )


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


def test_normalize_job_reads_pay_posted_and_deadline():
    raw = {
        "title": "Project Engineer Intern",
        "company_name": "Harris Company",
        "location": "Henderson, NV",
        "description": "Paid internship. Application deadline: December 15, 2026. Start Summer 2027.",
        "apply_options": [{"link": "https://example.com/a"}],
        "detected_extensions": {"posted_at": "3 days ago", "salary": "$22–$25 an hour"},
    }
    job = normalize_job(raw, "Project Engineer Intern", today=TODAY)

    assert job.pay == "$22–$25 an hour"
    assert job.posted_date == date(2026, 11, 20)
    assert job.deadline_date == date(2026, 12, 15)
    assert job.top_contractor
    assert job.summer_2027
    assert job.in_southern_nevada


def test_normalize_job_handles_missing_fields():
    job = normalize_job({"title": "Safety Intern"}, "Safety Intern", today=TODAY)

    assert job.company == "Unknown company"
    assert job.pay == ""
    assert job.posted_date is None
    assert job.deadline_date is None
    assert job.apply_link == ""


def test_normalize_job_falls_back_to_share_link():
    raw = {"title": "Construction Intern", "share_link": "https://example.com/share"}
    job = normalize_job(raw, "Construction Intern")

    assert job.apply_link == "https://example.com/share"
    assert job.company == "Unknown company"


@pytest.mark.parametrize(
    "label,expected",
    [
        ("3 days ago", date(2026, 11, 20)),
        ("1 hour ago", TODAY),
        ("Just posted", TODAY),
        ("30+ days ago", date(2026, 10, 24)),
        ("", None),
        ("Check listing", None),
    ],
)
def test_parse_posted_on(label, expected):
    assert parse_posted_on(label, TODAY) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Application deadline: December 15, 2026", date(2026, 12, 15)),
        ("Apply by 11/30/2026", date(2026, 11, 30)),
        ("Deadline Date: Dec 1 2026", date(2026, 12, 1)),
        ("Deadline: rolling basis", None),
        ("Posted 12/01/2026, no deadline stated", None),
        ("", None),
    ],
)
def test_parse_deadline(text, expected):
    assert parse_deadline(text) == expected


@pytest.mark.parametrize(
    "location", ["Las Vegas, NV", "Henderson, NV", "North Las Vegas, NV", "Summerlin", "Las Vegas/Reno"]
)
def test_is_southern_nevada_accepts_valley_locations(location):
    assert is_southern_nevada(location)


@pytest.mark.parametrize("location", ["Reno, NV", "Sparks, NV", "Fresno, CA", "Nevada", ""])
def test_is_southern_nevada_rejects_other_locations(location):
    assert not is_southern_nevada(location)


def test_job_id_is_stable_and_depends_on_listing():
    first = sample_job()
    same = sample_job()
    other = Job(**{**asdict(first), "apply_link": "https://example.com/other"})

    assert first.job_id == same.job_id
    assert first.job_id != other.job_id


@pytest.mark.parametrize(
    "title",
    [
        "Project Engineer Intern - Summer 2027",
        "Construction Management Co-op",
        "Summer Internship | Reno",
        "Co-Op Estimating Student",
        "BIM/VDC Intern",
        "Summer Associate - Estimating",
    ],
)
def test_is_internship_keeps_intern_coop_and_summer_associate_titles(title):
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


@pytest.mark.parametrize(
    "company",
    ["Clark Construction Group", "ARCO Design/Build", "The Whiting-Turner Contracting", "IMEG Corp", "Harris Company"],
)
def test_is_top_contractor_matches_listed_firms(company):
    assert is_top_contractor(company)


@pytest.mark.parametrize("company", ["Harrisburg Builders", "Murray Company", "Arcosanti Foundation"])
def test_is_top_contractor_ignores_partial_matches(company):
    assert not is_top_contractor(company)


def test_mentions_summer_2027_checks_title_and_description():
    assert mentions_summer_2027("Summer 2027 Project Engineer Intern", "")
    assert mentions_summer_2027("Estimating Intern", "Paid internship starting SUMMER  2027.")
    assert not mentions_summer_2027("Estimating Intern", "Starts Summer 2026")
    assert not mentions_summer_2027("Estimating Intern", "Starts in fall 2027")


def test_default_queries_cover_requested_roles():
    for query in [
        "Project Management Intern",
        "Safety Intern",
        "BIM / VDC Intern",
        "Preconstruction Intern",
        "MEP Intern",
        "Heavy Civil Intern",
        "CMST Intern",
        "Civil Engineering Intern",
    ]:
        assert query in DEFAULT_QUERIES


def test_load_or_fetch_reads_saved_results_without_searching(tmp_path, monkeypatch):
    cache = tmp_path / "jobs_cache.json"
    cache.write_text(
        json.dumps({"fetched_at": "Nov 22, 2026 09:00 AM", "jobs": [asdict(sample_job())]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(fetcher, "CACHE_FILE", cache)

    def no_search(*args, **kwargs):
        raise AssertionError("SerpApi should not be called on a page load")

    monkeypatch.setattr(fetcher, "fetch_all", no_search)
    jobs, fetched_at, message = load_or_fetch("key")

    assert [job.title for job in jobs] == ["Estimating Intern"]
    assert fetched_at == "Nov 22, 2026 09:00 AM"
    assert message == ""


def test_failed_refresh_keeps_saved_results(tmp_path, monkeypatch):
    cache = tmp_path / "jobs_cache.json"
    cache.write_text(json.dumps({"fetched_at": "x", "jobs": [asdict(sample_job())]}), encoding="utf-8")
    monkeypatch.setattr(fetcher, "CACHE_FILE", cache)

    def unreachable(*args, **kwargs):
        raise requests.ConnectionError("network down")

    monkeypatch.setattr(fetcher, "fetch_all", unreachable)
    jobs, _, message = load_or_fetch("key", force=True)

    assert len(jobs) == 1
    assert "Could not reach SerpApi" in message


def test_empty_refresh_keeps_saved_results(tmp_path, monkeypatch):
    cache = tmp_path / "jobs_cache.json"
    cache.write_text(json.dumps({"fetched_at": "x", "jobs": [asdict(sample_job())]}), encoding="utf-8")
    monkeypatch.setattr(fetcher, "CACHE_FILE", cache)
    monkeypatch.setattr(fetcher, "fetch_all", lambda *args, **kwargs: [])

    jobs, _, message = load_or_fetch("key", force=True)

    assert len(jobs) == 1
    assert "Showing saved results" in message
