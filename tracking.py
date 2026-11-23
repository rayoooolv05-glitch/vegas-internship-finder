"""Saved and Applied flags for each job, with backup, restore, and CSV export.

Flags live in data/tracking.json, keyed by job ID. Each entry also stores the listing's
details, so a backup stays readable and can be restored after a redeploy even when the
listing is no longer in the latest search results.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pandas as pd

from fetcher import Job, make_job_id

TRACKING_FILE = Path(__file__).parent / "data" / "tracking.json"
DETAIL_FIELDS = ("company", "title", "location", "apply_link", "pay", "deadline", "posted_at")
CSV_COLUMNS = [
    "Job ID",
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
# Each CSV column (other than the flags) and the tracking field it is read from and written to.
CSV_FIELD_MAP = {
    "Company": "company",
    "Job title": "title",
    "Location": "location",
    "Pay": "pay",
    "Deadline": "deadline",
    "Posted": "posted_at",
    "Apply link": "apply_link",
}


def _as_bool(value) -> bool:
    return value is True or str(value).strip().lower() == "true"


def load_tracking() -> dict[str, dict]:
    """Return the saved flags. A corrupt file is set aside, not overwritten."""
    try:
        payload = json.loads(TRACKING_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        try:
            TRACKING_FILE.replace(TRACKING_FILE.with_suffix(".corrupt.json"))
        except OSError:
            pass
        return {}
    return payload if isinstance(payload, dict) else {}


def _write(tracking: dict[str, dict]) -> bool:
    try:
        TRACKING_FILE.parent.mkdir(parents=True, exist_ok=True)
        TRACKING_FILE.write_text(json.dumps(tracking, indent=2), encoding="utf-8")
    except OSError:
        return False
    return True


def details_for(job: Job) -> dict[str, str]:
    return {field: getattr(job, field) for field in DETAIL_FIELDS}


def set_flag(job_id: str, flag: str, value: bool, details: dict[str, str] | None = None) -> bool:
    """Store one flag and the listing details. Returns False if the file could not be written."""
    tracking = load_tracking()
    entry = tracking.setdefault(job_id, {})
    entry[flag] = bool(value)
    if details:
        entry.update({key: str(val or "") for key, val in details.items() if key in DETAIL_FIELDS})
    return _write(tracking)


def merge_tracking(incoming: dict[str, dict]) -> bool:
    """Merge restored entries into the saved flags. Entries not in the file are kept."""
    tracking = load_tracking()
    for job_id, entry in incoming.items():
        tracking.setdefault(job_id, {}).update(entry)
    return _write(tracking)


def has_tracked(tracking: dict[str, dict]) -> bool:
    return any(_as_bool(entry.get("saved")) or _as_bool(entry.get("applied")) for entry in tracking.values())


def _clean_entry(entry: dict) -> dict:
    cleaned = {}
    for flag in ("saved", "applied"):
        if flag in entry:
            cleaned[flag] = _as_bool(entry[flag])
    for field in DETAIL_FIELDS:
        if field in entry:
            cleaned[field] = str(entry[field] or "")
    return cleaned


def tracking_to_json(tracking: dict[str, dict]) -> str:
    return json.dumps(tracking, indent=2)


def tracking_from_json(text: str) -> dict[str, dict]:
    try:
        payload = json.loads(text)
    except ValueError as error:
        raise ValueError("the file is not valid JSON") from error
    if not isinstance(payload, dict) or not all(isinstance(entry, dict) for entry in payload.values()):
        raise ValueError("the JSON is not a tracking backup")
    return {job_id: _clean_entry(entry) for job_id, entry in payload.items()}


def tracking_from_csv(text: str) -> dict[str, dict]:
    """Read a CSV from export_csv. Rows without a Job ID get one from company, title, and link."""
    try:
        frame = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    except (pd.errors.EmptyDataError, pd.errors.ParserError) as error:
        raise ValueError("the CSV could not be read") from error
    if "Job ID" not in frame.columns and not {"Company", "Job title"} <= set(frame.columns):
        raise ValueError("the CSV has no Job ID or Company and Job title columns")

    tracking = {}
    for row in frame.to_dict("records"):
        job_id = row.get("Job ID") or make_job_id(
            row.get("Company", ""), row.get("Job title", ""), row.get("Apply link", "")
        )
        entry = {"saved": _as_bool(row.get("Saved")), "applied": _as_bool(row.get("Applied"))}
        for column, field in CSV_FIELD_MAP.items():
            if column in row:
                entry[field] = row[column]
        tracking[job_id] = entry
    return tracking


def tracking_from_upload(filename: str, data: bytes) -> dict[str, dict]:
    """Parse an uploaded backup. Raises ValueError with a readable reason if it is not one."""
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("the file is not UTF-8 text") from error
    lowered = filename.lower()
    if lowered.endswith(".csv"):
        return tracking_from_csv(text)
    if lowered.endswith(".json"):
        return tracking_from_json(text)
    raise ValueError("choose a .csv or .json file")


def export_csv(tracking: dict[str, dict], jobs: list[Job]) -> str:
    """Export every saved or applied listing. Missing details are filled from current results."""
    current = {job.job_id: job for job in jobs}
    rows = []
    for job_id, entry in tracking.items():
        saved, applied = _as_bool(entry.get("saved")), _as_bool(entry.get("applied"))
        if not (saved or applied):
            continue
        listing = current.get(job_id)
        row = {"Job ID": job_id, "Saved": str(saved), "Applied": str(applied)}
        for column, field in CSV_FIELD_MAP.items():
            value = entry.get(field) or (getattr(listing, field) if listing else "")
            row[column] = value or ""
        rows.append(row)
    return pd.DataFrame(rows, columns=CSV_COLUMNS).to_csv(index=False)
