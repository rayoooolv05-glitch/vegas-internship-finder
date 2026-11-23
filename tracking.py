"""Saved and Applied flags for each job, kept in a local JSON file."""

import json
from pathlib import Path

TRACKING_FILE = Path(__file__).parent / "data" / "tracking.json"


def load_tracking() -> dict[str, dict[str, bool]]:
    try:
        return json.loads(TRACKING_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def set_flag(job_id: str, flag: str, value: bool) -> bool:
    """Store one flag for a job. Returns False if the file could not be written."""
    tracking = load_tracking()
    tracking.setdefault(job_id, {})[flag] = value
    try:
        TRACKING_FILE.parent.mkdir(parents=True, exist_ok=True)
        TRACKING_FILE.write_text(json.dumps(tracking, indent=2), encoding="utf-8")
    except OSError:
        return False
    return True
