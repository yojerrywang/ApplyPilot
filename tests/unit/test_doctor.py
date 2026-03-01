import json

from applypilot import config, database, doctor


def _configure_paths(monkeypatch, tmp_path):
    app_dir = tmp_path / ".applypilot"
    db_path = app_dir / "applypilot.db"

    monkeypatch.setattr(config, "APP_DIR", app_dir)
    monkeypatch.setattr(config, "DB_PATH", db_path)
    monkeypatch.setattr(config, "PROFILE_PATH", app_dir / "profile.json")
    monkeypatch.setattr(config, "SEARCH_CONFIG_PATH", app_dir / "searches.yaml")
    monkeypatch.setattr(config, "ENV_PATH", app_dir / ".env")
    monkeypatch.setattr(config, "TAILORED_DIR", app_dir / "tailored_resumes")
    monkeypatch.setattr(config, "COVER_LETTER_DIR", app_dir / "cover_letters")
    monkeypatch.setattr(config, "LOG_DIR", app_dir / "logs")
    monkeypatch.setattr(config, "CHROME_WORKER_DIR", app_dir / "chrome-workers")
    monkeypatch.setattr(config, "APPLY_WORKER_DIR", app_dir / "apply-workers")
    monkeypatch.setattr(database, "DB_PATH", db_path)

    return app_dir


def test_doctor_reports_clean_setup(monkeypatch, tmp_path):
    app_dir = _configure_paths(monkeypatch, tmp_path)
    config.ensure_dirs()

    profile = {
        "personal": {"full_name": "Jane Doe", "email": "jane@example.com"},
        "preferences": {"location": {"accept_patterns": ["Remote"], "reject_non_remote": False}},
    }
    (app_dir / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
    (app_dir / "searches.yaml").write_text(
        "queries:\n  - query: Backend Engineer\nlocations:\n  - location: Remote\n    remote: true\n",
        encoding="utf-8",
    )
    (app_dir / ".env").write_text("GEMINI_API_KEY=test-key\n", encoding="utf-8")

    monkeypatch.setattr(doctor.shutil, "which", lambda cmd: "/usr/bin/claude" if cmd == "claude" else None)
    monkeypatch.setattr(config, "get_chrome_path", lambda: "/Applications/Google Chrome")

    checks = doctor.run_checks()
    levels = {c.level for c in checks}

    assert "fail" not in levels


def test_doctor_flags_profile_schema_conflict(monkeypatch, tmp_path):
    app_dir = _configure_paths(monkeypatch, tmp_path)
    config.ensure_dirs()

    profile = {
        "personal": {"full_name": "Jane Doe", "email": "jane@example.com"},
        "location_accept": ["Remote"],
        "location_reject_non_remote": True,
        "preferences": {"location": {"accept_patterns": ["Remote"], "reject_non_remote": False}},
    }
    (app_dir / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
    (app_dir / "searches.yaml").write_text(
        "queries:\n  - query: Backend Engineer\nlocations:\n  - location: Remote\n    remote: true\n",
        encoding="utf-8",
    )
    (app_dir / ".env").write_text("GEMINI_API_KEY=test-key\n", encoding="utf-8")

    monkeypatch.setattr(doctor.shutil, "which", lambda cmd: "/usr/bin/claude" if cmd == "claude" else None)
    monkeypatch.setattr(config, "get_chrome_path", lambda: "/Applications/Google Chrome")

    checks = doctor.run_checks()
    conflict_checks = [c for c in checks if c.check == "Location schema"]

    assert conflict_checks
    assert conflict_checks[0].level == "warn"
