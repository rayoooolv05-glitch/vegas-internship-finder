import tracking


def test_set_flag_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(tracking, "TRACKING_FILE", tmp_path / "tracking.json")

    assert tracking.load_tracking() == {}
    assert tracking.set_flag("abc", "saved", True)
    assert tracking.set_flag("abc", "applied", True)
    assert tracking.set_flag("abc", "saved", False)

    assert tracking.load_tracking() == {"abc": {"saved": False, "applied": True}}


def test_load_tracking_tolerates_corrupt_file(tmp_path, monkeypatch):
    path = tmp_path / "tracking.json"
    path.write_text("not json", encoding="utf-8")
    monkeypatch.setattr(tracking, "TRACKING_FILE", path)

    assert tracking.load_tracking() == {}
