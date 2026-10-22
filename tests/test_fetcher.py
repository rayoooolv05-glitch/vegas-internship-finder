from fetcher import normalize_job


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


def test_normalize_job_falls_back_to_share_link():
    raw = {"title": "Construction Intern", "share_link": "https://example.com/share"}
    job = normalize_job(raw, "Construction Intern")

    assert job.apply_link == "https://example.com/share"
    assert job.company == "Unknown company"
