"""Filtering, sorting, and text snippets for the dashboard. No Streamlit imports."""

import textwrap
from datetime import date

from fetcher import Job

SORT_OPTIONS = ["Best Match", "Deadline / Soonest", "Newest Posted", "Company A–Z"]


def matches_filters(
    job: Job,
    titles: list[str],
    keyword: str,
    tracking: dict[str, dict],
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
