from pathlib import Path

from applypilot import config
from applypilot.apply import prompt as prompt_mod


def test_build_prompt_does_not_include_plaintext_password(monkeypatch, tmp_path):
    resume_txt = tmp_path / "tailored_resume.txt"
    resume_pdf = tmp_path / "tailored_resume.pdf"
    resume_txt.write_text("Tailored resume text", encoding="utf-8")
    resume_pdf.write_bytes(b"%PDF-1.4\n%%EOF")

    profile = {
        "personal": {
            "full_name": "Test User",
            "preferred_name": "Test",
            "email": "test@example.com",
            "phone": "555-000-1111",
            "city": "Austin",
            "country": "USA",
            "password": "SUPER_SECRET_PASSWORD",
        },
        "work_authorization": {
            "legally_authorized_to_work": "Yes",
            "require_sponsorship": "No",
        },
        "compensation": {
            "salary_expectation": "100000",
            "salary_currency": "USD",
            "salary_range_min": "90000",
            "salary_range_max": "120000",
        },
        "experience": {"education_level": "Bachelor's"},
        "availability": {"earliest_start_date": "Immediately"},
        "eeo_voluntary": {},
    }

    monkeypatch.setattr(config, "APPLY_WORKER_DIR", tmp_path / "apply-workers")
    monkeypatch.setattr(config, "load_profile", lambda: profile)
    monkeypatch.setattr(config, "load_search_config", lambda: {"location": {"accept_patterns": ["Austin"]}})
    monkeypatch.setattr(config, "load_blocked_sso", lambda: ["accounts.google.com"])

    job = {
        "url": "https://jobs.example.com/1",
        "application_url": "https://jobs.example.com/apply/1",
        "title": "Software Engineer",
        "site": "Example",
        "fit_score": 9,
        "tailored_resume_path": str(resume_txt),
    }

    prompt = prompt_mod.build_prompt(job=job, tailored_resume="Tailored resume text", dry_run=True)

    assert "SUPER_SECRET_PASSWORD" not in prompt
    assert "Try sign in with your email" in prompt
    assert "password manager/autofill" in prompt
