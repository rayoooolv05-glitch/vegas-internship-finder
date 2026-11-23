import json
from datetime import date

import pytest

import tracking
from fetcher import Job, make_job_id


@pytest.fixture
def tracking_file(tmp_path, monkeypatch):
    path = tmp_path / "tracking.json"
    monkeypatch.setattr(tracking, "TRACKING_FILE", path)
    return path


def make_listing(title="Estimating Intern", company="Acme Builders", link="https://example.com/a"):
    return Job(
        company=company,
        title=title,
        location="Henderson, NV",
        description="Summer 2027 internship.",
        apply_link=link,
        query="Estimating Intern",
        posted_at="3 days ago",
        pay="$22 an hour",
        deadline="2026-12-15",
        posted_on="2026-11-20",
    )


def test_set_flag_round_trip_keeps_listing_details(tracking_file):
    job = make_listing()

    assert tracking.load_tracking() == {}
    assert tracking.set_flag(job.job_id, "saved", True, tracking.details_for(job))
    assert tracking.set_flag(job.job_id, "applied", True, tracking.details_for(job))
    assert tracking.set_flag(job.job_id, "saved", False)

    entry = tracking.load_tracking()[job.job_id]
    assert entry["saved"] is False
    assert entry["applied"] is True
    assert entry["company"] == "Acme Builders"
    assert entry["apply_link"] == "https://example.com/a"


def test_corrupt_file_is_set_aside_not_overwritten(tracking_file):
    tracking_file.write_text("not json", encoding="utf-8")

    assert tracking.load_tracking() == {}
    assert not tracking_file.exists()
    assert tracking_file.with_suffix(".corrupt.json").read_text(encoding="utf-8") == "not json"


def test_json_backup_round_trip(tracking_file):
    job = make_listing()
    tracking.set_flag(job.job_id, "applied", True, tracking.details_for(job))
    backup = tracking.tracking_to_json(tracking.load_tracking())

    tracking_file.unlink()
    restored = tracking.tracking_from_upload("tracking_backup.json", backup.encode("utf-8"))

    assert restored[job.job_id]["applied"] is True
    assert restored[job.job_id]["title"] == "Estimating Intern"


def test_restore_after_reset_brings_back_applied_state(tracking_file):
    job = make_listing()
    tracking.set_flag(job.job_id, "applied", True, tracking.details_for(job))
    csv_text = tracking.export_csv(tracking.load_tracking(), [job])

    tracking_file.unlink()  # simulate a redeploy that wiped data/
    assert tracking.merge_tracking(tracking.tracking_from_upload("backup.csv", csv_text.encode("utf-8")))

    assert tracking.load_tracking()[job.job_id]["applied"] is True


def test_csv_without_job_id_column_gets_matching_ids():
    text = (
        "Company,Job title,Location,Pay,Deadline,Posted,Saved,Applied,Apply link\n"
        "Acme Builders,Estimating Intern,Henderson NV,,,,True,False,https://example.com/a\n"
    )
    restored = tracking.tracking_from_csv(text)

    expected_id = make_job_id("Acme Builders", "Estimating Intern", "https://example.com/a")
    assert restored[expected_id]["saved"] is True
    assert restored[expected_id]["applied"] is False
    assert restored[expected_id]["location"] == "Henderson NV"


def test_export_csv_includes_only_saved_or_applied_and_fills_from_results():
    job = make_listing()
    other = make_listing(title="Safety Intern", company="Other Co", link="https://example.com/b")
    state = {
        job.job_id: {"applied": True},  # entry without details, e.g. from an older version
        other.job_id: {"saved": False, "applied": False},
    }
    lines = tracking.export_csv(state, [job, other]).strip().splitlines()

    assert lines[0].split(",")[:3] == ["Job ID", "Company", "Job title"]
    assert len(lines) == 2
    assert "Acme Builders" in lines[1]
    assert "Estimating Intern" in lines[1]


def test_merge_keeps_entries_not_in_the_backup(tracking_file):
    first = make_listing()
    second = make_listing(title="Safety Intern", link="https://example.com/b")
    tracking.set_flag(first.job_id, "saved", True)
    tracking.set_flag(second.job_id, "applied", True)

    tracking.merge_tracking({first.job_id: {"applied": True}})

    state = tracking.load_tracking()
    assert state[first.job_id] == {"saved": True, "applied": True}
    assert state[second.job_id] == {"applied": True}


@pytest.mark.parametrize(
    "filename,data,reason",
    [
        ("backup.txt", b"{}", "choose a .csv or .json"),
        ("backup.json", b"not json", "not valid JSON"),
        ("backup.json", b"[1, 2]", "not a tracking backup"),
        ("backup.json", b'{"abc": "saved"}', "not a tracking backup"),
        ("backup.csv", b"Name,Value\nx,y\n", "no Job ID or Company"),
        ("backup.csv", b"\xff\xfe", "not UTF-8"),
    ],
)
def test_invalid_uploads_raise_readable_errors(filename, data, reason):
    with pytest.raises(ValueError, match=reason):
        tracking.tracking_from_upload(filename, data)


def test_empty_json_backup_restores_nothing():
    assert tracking.tracking_from_upload("backup.json", b"{}") == {}


def test_has_tracked_ignores_unflagged_entries():
    assert not tracking.has_tracked({"a": {"saved": False, "applied": False}})
    assert tracking.has_tracked({"a": {"saved": False, "applied": True}})
