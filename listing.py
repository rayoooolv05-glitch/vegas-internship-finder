"""Filtering, sorting, text snippets, and CSV export for the dashboard. No Streamlit imports."""

import textwrap
from datetime import date

import pandas as pd

from fetcher import Job

SORT_OPTIONS = ["Best Match", "Deadline / Soonest", "Newest Posted", "Company A–Z"]
CSV_COLUMNS = [
    "Company",
    "Job title",
    "Location",
    "Pay",
    "Deadline",
    "Posted",
    "Saved",
    "Applied",
    "Apply link",
]


def matches_filters(
    job: Job,
    titles: list[str],
    keyword: str,
    tracking: dict[str, dict[str, bool]],
    hide_applied: bool,
) -> bool:
    if job.query not in titles:
        return False
    if keyword and keyword.lower() not in f"{job.company} {job.title} {job.description}".lower():
        return False
    if hide_applied and tracking.get(job.job_id, {}).get("applied"):
        return False
    return True


def sort_jobs(jobs: list[Job], sort_by: str) -> list[Job]:
    if sort_by == "Deadline / Soonest":
        return sorted(jobs, key=lambda job: (job.deadline_date is None, job.deadline_date or date.max))
    if sort_by == "Newest Posted":
        return sorted(
            jobs,
            key=lambda job: (job.posted_date is None, -(job.posted_date or date.min).toordinal()),
        )
    if sort_by == "Company A–Z":
        return sorted(jobs, key=lambda job: job.company.lower())
    # Best Match: Top Contractor listings first, otherwise SerpApi's original order.
    return sorted(jobs, key=lambda job: not job.top_contractor)


def snippet(text: str, width: int = 280) -> str:
    if not text:
        return "No description listed."
    return textwrap.shorten(text, width=width, placeholder="…")


def tracked_rows(jobs: list[Job], tracking: dict[str, dict[str, bool]]) -> list[dict]:
    rows = []
    for job in jobs:
        state = tracking.get(job.job_id, {})
        if not (state.get("saved") or state.get("applied")):
            continue
        rows.append(
            {
                "Company": job.company,
                "Job title": job.title,
                "Location": job.location,
                "Pay": job.pay or "Pay not listed",
                "Deadline": job.deadline,
                "Posted": job.posted_at,
                "Saved": bool(state.get("saved")),
                "Applied": bool(state.get("applied")),
                "Apply link": job.apply_link,
            }
        )
    return rows


def tracked_csv(jobs: list[Job], tracking: dict[str, dict[str, bool]]) -> str:
    return pd.DataFrame(tracked_rows(jobs, tracking), columns=CSV_COLUMNS).to_csv(index=False)
