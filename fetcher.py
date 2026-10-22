"""Fetch and normalize Google Jobs listings through SerpApi.

Requires a SerpApi key in the SERPAPI_API_KEY environment variable.
Free accounts include a monthly search allowance, so results are cached
to disk and reused when the cache is still fresh.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import requests

SERPAPI_URL = "https://serpapi.com/search.json"
DEFAULT_LOCATION = "Las Vegas, NV"
DEFAULT_QUERIES = [
    "Project Engineer Intern",
    "Estimating Intern",
    "Construction Intern",
    "Project Management Intern",
    "Safety Intern",
    "BIM / VDC Intern",
    "Preconstruction Intern",
    "Field Engineer Intern",
    "Superintendent Intern",
    "Construction Management Co-op",
]
# Only titles containing one of these words are kept, so full-time roles are dropped.
INTERN_TITLE_PATTERN = re.compile(r"\b(interns?|internships?|co-?ops?)\b", re.IGNORECASE)
CACHE_FILE = Path(__file__).parent / "data" / "jobs_cache.json"
CACHE_TTL_SECONDS = 60 * 60 * 24  # refresh once a day to conserve free searches


@dataclass
class Job:
    company: str
    title: str
    location: str
    description: str
    apply_link: str
    query: str
    posted_at: str = ""


def normalize_job(raw: dict, query: str) -> Job:
    """Convert one SerpApi `jobs_results` entry into a flat Job record."""
    apply_options = raw.get("apply_options") or []
    apply_link = ""
    if apply_options:
        apply_link = apply_options[0].get("link", "")
    if not apply_link:
        apply_link = raw.get("share_link", "")

    description = (raw.get("description") or "").strip()
    snippet = " ".join(description.split())[:300]

    return Job(
        company=(raw.get("company_name") or "Unknown company").strip(),
        title=(raw.get("title") or "Untitled").strip(),
        location=(raw.get("location") or "").strip(),
        description=snippet,
        apply_link=apply_link,
        query=query,
        posted_at=(raw.get("detected_extensions") or {}).get("posted_at", ""),
    )


def is_internship(title: str) -> bool:
    """Return True when the job title names an internship or co-op role."""
    return bool(INTERN_TITLE_PATTERN.search(title))


def search_jobs(query: str, api_key: str, location: str = DEFAULT_LOCATION) -> list[Job]:
    """Run one Google Jobs search via SerpApi and return normalized jobs."""
    params = {
        "engine": "google_jobs",
        "q": query,
        "location": location,
        "hl": "en",
        "gl": "us",
        "api_key": api_key,
    }
    response = requests.get(SERPAPI_URL, params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()

    if "error" in payload:
        # SerpApi reports a query with no matches as an error; that is an empty result, not a failure.
        if "hasn't returned any results" in payload["error"]:
            return []
        raise RuntimeError(f"SerpApi error for '{query}': {payload['error']}")

    return [normalize_job(raw, query) for raw in payload.get("jobs_results", [])]


def fetch_all(
    api_key: str,
    queries: list[str] | None = None,
    location: str = DEFAULT_LOCATION,
) -> list[Job]:
    """Search every query, drop duplicate postings, and return the combined list."""
    seen: set[tuple[str, str, str]] = set()
    jobs: list[Job] = []
    for query in queries or DEFAULT_QUERIES:
        for job in search_jobs(query, api_key, location):
            if not is_internship(job.title):
                continue
            key = (job.company.lower(), job.title.lower(), job.apply_link)
            if key in seen:
                continue
            seen.add(key)
            jobs.append(job)
    return jobs


def load_or_fetch(api_key: str, force: bool = False) -> list[Job]:
    """Return cached jobs when fresh; otherwise hit SerpApi and update the cache."""
    if not force and CACHE_FILE.exists():
        age = time.time() - CACHE_FILE.stat().st_mtime
        if age < CACHE_TTL_SECONDS:
            cached = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            jobs = [Job(**row) for row in cached]
            return [job for job in jobs if is_internship(job.title)]

    jobs = fetch_all(api_key)
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(
        json.dumps([asdict(job) for job in jobs], indent=2), encoding="utf-8"
    )
    return jobs


def get_api_key() -> str | None:
    return os.environ.get("SERPAPI_API_KEY")
