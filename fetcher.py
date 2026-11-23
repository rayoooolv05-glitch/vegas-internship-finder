"""Fetch, normalize, and cache Southern Nevada construction internships from SerpApi.

A refresh runs one Google Jobs search per entry in DEFAULT_QUERIES, so it uses
len(DEFAULT_QUERIES) searches from the monthly allowance. Results are saved to disk.
Ordinary page loads read that file and never call SerpApi.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

SERPAPI_URL = "https://serpapi.com/search.json"
SERPAPI_ACCOUNT_URL = "https://serpapi.com/account.json"
DEFAULT_LOCATION = "Las Vegas, Nevada, United States"
DEFAULT_QUERIES = [
    "Project Engineer Intern",
    "Field Engineer Intern",
    "Estimating Intern",
    "Preconstruction Intern",
    "Project Management Intern",
    "Superintendent Intern",
    "BIM / VDC Intern",
    "MEP Intern",
    "Heavy Civil Intern",
    "Safety Intern",
    "Construction Management Co-op",
    "CMST Intern",
    "Civil Engineering Intern",
    "Construction Intern",
    "Summer Associate",
    "Field/Operations Intern",
]
CACHE_FILE = Path(__file__).parent / "data" / "jobs_cache.json"
DESCRIPTION_LIMIT = 2000

# Only titles containing one of these words are kept, so full-time roles are dropped.
INTERN_TITLE_PATTERN = re.compile(
    r"\b(interns?|internships?|co-?ops?|summer associates?)\b", re.IGNORECASE
)
SOUTHERN_NEVADA_PATTERN = re.compile(
    r"\b(las vegas|henderson|north las vegas|summerlin|paradise|enterprise|"
    r"spring valley|boulder city|sunrise manor|southern nevada)\b",
    re.IGNORECASE,
)
TOP_CONTRACTORS = ["Clark Construction", "ARCO", "Whiting-Turner", "IMEG", "Harris"]
TOP_CONTRACTOR_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(name) for name in TOP_CONTRACTORS) + r")\b",
    re.IGNORECASE,
)
SUMMER_2027_PATTERN = re.compile(r"\bsummer\s+2027\b", re.IGNORECASE)
POSTED_AGO_PATTERN = re.compile(
    r"(\d+)\+?\s*(minute|hour|day|week|month)s?\s+ago", re.IGNORECASE
)
DAYS_PER_UNIT = {"minute": 0, "hour": 0, "day": 1, "week": 7, "month": 30}
DEADLINE_PATTERN = re.compile(
    r"(?:deadline|apply by|applications? (?:close|due)|closing date)[^0-9]{0,30}?"
    r"([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}|\d{1,2}/\d{1,2}/\d{2,4})",
    re.IGNORECASE,
)
DATE_FORMATS = ("%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%b %d %Y", "%m/%d/%Y", "%m/%d/%y")


@dataclass
class Job:
    company: str
    title: str
    location: str
    description: str
    apply_link: str
    query: str
    posted_at: str = ""  # SerpApi's relative label, e.g. "3 days ago"
    pay: str = ""  # empty when the listing shows no salary
    posted_on: str = ""  # ISO date estimated from posted_at at fetch time
    deadline: str = ""  # ISO date parsed from the description

    @property
    def job_id(self) -> str:
        return make_job_id(self.company, self.title, self.apply_link)

    @property
    def posted_date(self) -> date | None:
        return date.fromisoformat(self.posted_on) if self.posted_on else None

    @property
    def deadline_date(self) -> date | None:
        return date.fromisoformat(self.deadline) if self.deadline else None

    @property
    def top_contractor(self) -> bool:
        return is_top_contractor(self.company)

    @property
    def summer_2027(self) -> bool:
        return mentions_summer_2027(self.title, self.description)

    @property
    def in_southern_nevada(self) -> bool:
        return is_southern_nevada(self.location)


def make_job_id(company: str, title: str, apply_link: str) -> str:
    """Stable key for a listing, used to store its Saved and Applied flags."""
    key = f"{company}|{title}|{apply_link}".lower()
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def is_internship(title: str) -> bool:
    """Return True when the job title names an internship or co-op role."""
    return bool(INTERN_TITLE_PATTERN.search(title))


def is_southern_nevada(location: str) -> bool:
    """Return True when the location is in the Las Vegas valley or nearby Southern Nevada."""
    return bool(SOUTHERN_NEVADA_PATTERN.search(location))


def is_top_contractor(company: str) -> bool:
    """Return True when the company is one of the highlighted contractors."""
    return bool(TOP_CONTRACTOR_PATTERN.search(company))


def mentions_summer_2027(title: str, description: str) -> bool:
    """Return True when the title or description mentions Summer 2027."""
    return bool(SUMMER_2027_PATTERN.search(f"{title} {description}"))


def keep_job(job: Job) -> bool:
    """Return True for internship postings located in Southern Nevada."""
    return is_internship(job.title) and job.in_southern_nevada


def parse_posted_on(label: str, today: date) -> date | None:
    """Estimate the posting date from a label such as '3 days ago'. Returns None if unknown."""
    text = (label or "").strip().lower()
    if not text:
        return None
    if "just posted" in text or "today" in text:
        return today
    match = POSTED_AGO_PATTERN.search(text)
    if not match:
        return None
    count, unit = int(match.group(1)), match.group(2).lower()
    return today - timedelta(days=count * DAYS_PER_UNIT[unit])


def parse_deadline(text: str) -> date | None:
    """Find an application deadline in a job description. Returns None if none is stated."""
    match = DEADLINE_PATTERN.search(text or "")
    if not match:
        return None
    raw = " ".join(match.group(1).split())
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def normalize_job(raw: dict, query: str, today: date | None = None) -> Job:
    """Convert one SerpApi `jobs_results` entry into a flat Job record."""
    today = today or date.today()
    apply_options = raw.get("apply_options") or []
    apply_link = apply_options[0].get("link", "") if apply_options else ""
    if not apply_link:
        apply_link = raw.get("share_link", "")

    extensions = raw.get("detected_extensions") or {}
    description = " ".join((raw.get("description") or "").split())[:DESCRIPTION_LIMIT]
    posted_at = extensions.get("posted_at", "")
    posted_on = parse_posted_on(posted_at, today)
    deadline = parse_deadline(description)

    return Job(
        company=(raw.get("company_name") or "Unknown company").strip(),
        title=(raw.get("title") or "Untitled").strip(),
        location=(raw.get("location") or "").strip(),
        description=description,
        apply_link=apply_link,
        query=query,
        posted_at=posted_at,
        pay=(extensions.get("salary") or "").strip(),
        posted_on=posted_on.isoformat() if posted_on else "",
        deadline=deadline.isoformat() if deadline else "",
    )


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
    """Search every query, keep Southern Nevada internships, and drop duplicate postings."""
    seen: set[str] = set()
    jobs: list[Job] = []
    for query in queries or DEFAULT_QUERIES:
        for job in search_jobs(query, api_key, location):
            if not keep_job(job) or job.job_id in seen:
                continue
            seen.add(job.job_id)
            jobs.append(job)
    return jobs


def get_searches_left(api_key: str) -> int | None:
    """Return the remaining monthly SerpApi searches. The account endpoint uses no searches."""
    try:
        response = requests.get(
            SERPAPI_ACCOUNT_URL, params={"api_key": api_key}, timeout=15
        )
        response.raise_for_status()
        return response.json().get("total_searches_left")
    except (requests.RequestException, ValueError):
        return None


def read_cache() -> tuple[list[Job], str]:
    """Return the saved jobs and the time of the last successful refresh."""
    if not CACHE_FILE.exists():
        return [], ""
    payload = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    if isinstance(payload, list):  # cache written before the refresh time was recorded
        rows, fetched_at = payload, ""
    else:
        rows, fetched_at = payload.get("jobs", []), payload.get("fetched_at", "")
    jobs = [Job(**row) for row in rows]
    return [job for job in jobs if keep_job(job)], fetched_at


def write_cache(jobs: list[Job], fetched_at: str) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {"fetched_at": fetched_at, "jobs": [asdict(job) for job in jobs]}
    CACHE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_or_fetch(api_key: str, force: bool = False) -> tuple[list[Job], str, str]:
    """Return (jobs, fetched_at, message) without calling SerpApi unless needed.

    Page loads read the saved results. A search runs only when force is True (the
    Refresh button) or when nothing has been saved yet. If a search fails or finds
    nothing, the saved results are kept and the message says why.
    """
    saved_jobs, saved_at = read_cache()
    if not force and CACHE_FILE.exists():
        return saved_jobs, saved_at, ""

    try:
        jobs = fetch_all(api_key)
    except requests.RequestException:
        # Exception text can include the request URL, which contains the API key, so it is not shown.
        return saved_jobs, saved_at, "Could not reach SerpApi. Showing saved results."
    except RuntimeError as error:
        return saved_jobs, saved_at, f"{error}. Showing saved results."

    if not jobs:
        if saved_jobs:
            return saved_jobs, saved_at, "SerpApi found no internships. Showing saved results."
        return [], "", "SerpApi found no Southern Nevada internships for these searches."

    fetched_at = datetime.now().strftime("%b %d, %Y %I:%M %p")
    write_cache(jobs, fetched_at)
    return jobs, fetched_at, ""
