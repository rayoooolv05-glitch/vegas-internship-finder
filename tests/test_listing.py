from datetime import date

from fetcher import Job
from listing import matches_filters, snippet, sort_jobs, tracked_csv


def make_job(company, title, deadline="", posted_on="", apply_link="", query="Estimating Intern"):
    return Job(
        company=company,
        title=title,
        location="Las Vegas, NV",
        description="Summer 2027 paid internship." if "Clark" in company else "Internship.",
        apply_link=apply_link or f"https://example.com/{company.replace(' ', '')}/{title.replace(' ', '')}",
        query=query,
        deadline=deadline,
        posted_on=posted_on,
        posted_at="3 days ago" if posted_on else "",
    )


JOBS = [
    make_job("Zeta Builders", "Estimating Intern", deadline="2026-12-20", posted_on="2026-11-20"),
    make_job("Clark Construction Group", "Preconstruction Intern", posted_on="2026-11-10"),
    make_job("Alpha Paving", "Safety Intern", deadline="2026-12-01", posted_on="2026-11-22", query="Safety Intern"),
    make_job("Mid Electric", "Estimating Intern", deadline="", posted_on=""),
]


def test_matches_filters_by_title_keyword_and_applied():
    tracking = {JOBS[0].job_id: {"applied": True}}

    assert [j.company for j in JOBS if matches_filters(j, ["Safety Intern"], "", {}, False)] == ["Alpha Paving"]
    assert len([j for j in JOBS if matches_filters(j, ["Estimating Intern"], "paving", {}, False)]) == 0
    visible = [j.company for j in JOBS if matches_filters(j, ["Estimating Intern"], "", tracking, True)]
    assert visible == ["Clark Construction Group", "Mid Electric"]


def test_sort_deadline_puts_undated_last():
    names = [j.company for j in sort_jobs(JOBS, "Deadline / Soonest")]
    assert names == ["Alpha Paving", "Zeta Builders", "Clark Construction Group", "Mid Electric"]


def test_sort_newest_posted_puts_undated_last():
    names = [j.company for j in sort_jobs(JOBS, "Newest Posted")]
    assert names == ["Alpha Paving", "Zeta Builders", "Clark Construction Group", "Mid Electric"]


def test_sort_company_az():
    names = [j.company for j in sort_jobs(JOBS, "Company A–Z")]
    assert names == ["Alpha Paving", "Clark Construction Group", "Mid Electric", "Zeta Builders"]


def test_best_match_puts_top_contractors_first():
    assert sort_jobs(JOBS, "Best Match")[0].company == "Clark Construction Group"


def test_snippet_trims_long_text_and_handles_empty():
    assert snippet("") == "No description listed."
    assert len(snippet("word " * 200)) <= 280


def test_tracked_csv_includes_only_saved_or_applied_jobs():
    tracking = {JOBS[2].job_id: {"saved": True}, JOBS[3].job_id: {"applied": True, "saved": False}}
    lines = tracked_csv(JOBS, tracking).strip().splitlines()

    assert lines[0].startswith("Company,Job title,Location,Pay,Deadline")
    assert len(lines) == 3
    assert "Pay not listed" in lines[1] or "Pay not listed" in lines[2]
