from pathlib import Path

from typer.testing import CliRunner

from applypilot import config, database
from applypilot.cli import app

runner = CliRunner()


def _configure_test_home(monkeypatch, tmp_path):
    app_dir = tmp_path / ".applypilot"
    db_path = app_dir / "applypilot.db"

    monkeypatch.setattr(config, "APP_DIR", app_dir)
    monkeypatch.setattr(config, "DB_PATH", db_path)
    monkeypatch.setattr(config, "PROFILE_PATH", app_dir / "profile.json")
    monkeypatch.setattr(config, "RESUME_PATH", app_dir / "resume.txt")
    monkeypatch.setattr(config, "RESUME_PDF_PATH", app_dir / "resume.pdf")
    monkeypatch.setattr(config, "SEARCH_CONFIG_PATH", app_dir / "searches.yaml")
    monkeypatch.setattr(config, "ENV_PATH", app_dir / ".env")
    monkeypatch.setattr(config, "TAILORED_DIR", app_dir / "tailored_resumes")
    monkeypatch.setattr(config, "COVER_LETTER_DIR", app_dir / "cover_letters")
    monkeypatch.setattr(config, "LOG_DIR", app_dir / "logs")
    monkeypatch.setattr(config, "CHROME_WORKER_DIR", app_dir / "chrome-workers")
    monkeypatch.setattr(config, "APPLY_WORKER_DIR", app_dir / "apply-workers")
    monkeypatch.setattr(database, "DB_PATH", db_path)

    config.ensure_dirs()
    conn = database.init_db(db_path)
    return app_dir, db_path, conn


def test_cli_run_dedupe_uses_company_title_identity(monkeypatch, tmp_path):
    _, db_path, conn = _configure_test_home(monkeypatch, tmp_path)

    conn.execute(
        "INSERT INTO jobs (url, title, company, site, discovered_at, fit_score) VALUES (?, ?, ?, ?, ?, ?)",
        ("https://a.example/job", "Backend Engineer", "Acme", "Indeed", "2026-01-01T00:00:00Z", 7),
    )
    conn.execute(
        "INSERT INTO jobs (url, title, company, site, discovered_at, fit_score) VALUES (?, ?, ?, ?, ?, ?)",
        ("https://b.example/job", "Backend Engineer", "Acme", "LinkedIn", "2026-01-02T00:00:00Z", 9),
    )
    conn.execute(
        "INSERT INTO jobs (url, title, company, site, discovered_at, fit_score) VALUES (?, ?, ?, ?, ?, ?)",
        ("https://c.example/job", "Backend Engineer", "Globex", "Indeed", "2026-01-02T00:00:00Z", 8),
    )
    conn.commit()

    result = runner.invoke(app, ["run", "dedupe"])
    assert result.exit_code == 0, result.output

    rows = database.get_connection(db_path).execute("SELECT url FROM jobs ORDER BY url").fetchall()
    urls = [row[0] for row in rows]
    assert urls == ["https://b.example/job", "https://c.example/job"]

    database.close_connection(db_path)


def test_cli_run_scopes_enrich_score_tailor_cover_by_session(monkeypatch, tmp_path):
    app_dir, db_path, conn = _configure_test_home(monkeypatch, tmp_path)

    # Stage filters should only process batch-a when --session-id is passed.
    conn.execute(
        """
        INSERT INTO jobs (url, title, company, site, session_id, discovered_at, full_description, fit_score)
        VALUES (?, ?, ?, ?, ?, datetime('now'), ?, ?)
        """,
        ("https://a.example/job", "Role A", "Acme", "Indeed", "batch-a", "desc-a", None),
    )
    conn.execute(
        """
        INSERT INTO jobs (url, title, company, site, session_id, discovered_at, full_description, fit_score)
        VALUES (?, ?, ?, ?, ?, datetime('now'), ?, ?)
        """,
        ("https://b.example/job", "Role B", "Globex", "Indeed", "batch-b", "desc-b", None),
    )
    conn.commit()

    monkeypatch.setattr(config, "check_tier", lambda required, feature: None)

    from applypilot.enrichment import detail
    from applypilot.scoring import cover_letter, scorer, tailor

    def fake_enrich(limit=100, workers=1, session_id=None):
        assert session_id == "batch-a"
        return {"processed": 1, "ok": 1, "partial": 0, "error": 0, "tiers": {1: 1, 2: 0, 3: 0}}

    def fake_score(limit=0, rescore=False, session_id=None):
        assert session_id == "batch-a"
        c = database.get_connection(db_path)
        c.execute(
            "UPDATE jobs SET fit_score = 9, scored_at = datetime('now') WHERE session_id = ?",
            (session_id,),
        )
        c.commit()
        return {"scored": 1, "errors": 0, "elapsed": 0.0, "distribution": [(9, 1)]}

    def fake_tailor(min_score=7, limit=1000, session_id=None):
        assert session_id == "batch-a"
        c = database.get_connection(db_path)
        tailored_path = str(app_dir / "tailored_resumes" / "batch_a.txt")
        c.execute(
            "UPDATE jobs SET tailored_resume_path = ?, tailored_at = datetime('now') WHERE session_id = ?",
            (tailored_path, session_id),
        )
        c.commit()
        return {"approved": 1, "failed": 0, "errors": 0, "elapsed": 0.0}

    def fake_cover(min_score=7, limit=1000, session_id=None):
        assert session_id == "batch-a"
        c = database.get_connection(db_path)
        cover_path = str(app_dir / "cover_letters" / "batch_a.txt")
        c.execute(
            "UPDATE jobs SET cover_letter_path = ?, cover_letter_at = datetime('now') WHERE session_id = ?",
            (cover_path, session_id),
        )
        c.commit()
        return {"generated": 1, "errors": 0, "elapsed": 0.0}

    monkeypatch.setattr(detail, "run_enrichment", fake_enrich)
    monkeypatch.setattr(scorer, "run_scoring", fake_score)
    monkeypatch.setattr(tailor, "run_tailoring", fake_tailor)
    monkeypatch.setattr(cover_letter, "run_cover_letters", fake_cover)

    result = runner.invoke(
        app,
        ["run", "enrich", "score", "tailor", "cover", "--session-id", "batch-a"],
    )
    assert result.exit_code == 0, result.output

    row_a = database.get_connection(db_path).execute(
        "SELECT fit_score, tailored_resume_path, cover_letter_path FROM jobs WHERE session_id = 'batch-a'"
    ).fetchone()
    row_b = database.get_connection(db_path).execute(
        "SELECT fit_score, tailored_resume_path, cover_letter_path FROM jobs WHERE session_id = 'batch-b'"
    ).fetchone()

    assert row_a[0] == 9
    assert row_a[1] is not None
    assert row_a[2] is not None
    assert row_b[0] is None
    assert row_b[1] is None
    assert row_b[2] is None

    database.close_connection(db_path)


def test_cli_apply_utility_modes_update_state(monkeypatch, tmp_path):
    _, db_path, conn = _configure_test_home(monkeypatch, tmp_path)

    url = "https://apply.example/job"
    conn.execute(
        """
        INSERT INTO jobs (url, title, company, site, session_id, discovered_at, tailored_resume_path)
        VALUES (?, ?, ?, ?, ?, datetime('now'), ?)
        """,
        (url, "Role", "Acme", "Indeed", "batch-a", "/tmp/resume.txt"),
    )
    conn.commit()

    result_failed = runner.invoke(app, ["apply", "--mark-failed", url, "--fail-reason", "manual-test"])
    assert result_failed.exit_code == 0, result_failed.output

    failed_row = database.get_connection(db_path).execute(
        "SELECT apply_status, apply_error, apply_attempts FROM jobs WHERE url = ?",
        (url,),
    ).fetchone()
    assert failed_row[0] == "failed"
    assert failed_row[1] == "manual-test"
    assert failed_row[2] == 99

    result_reset = runner.invoke(app, ["apply", "--reset-failed"])
    assert result_reset.exit_code == 0, result_reset.output

    reset_row = database.get_connection(db_path).execute(
        "SELECT apply_status, apply_error, apply_attempts FROM jobs WHERE url = ?",
        (url,),
    ).fetchone()
    assert reset_row[0] is None
    assert reset_row[1] is None
    assert reset_row[2] == 0

    database.close_connection(db_path)


def test_cli_run_stream_forwards_stream_mode(monkeypatch, tmp_path):
    _configure_test_home(monkeypatch, tmp_path)
    captured = {}

    from applypilot import pipeline

    def fake_run_pipeline(stages, min_score, dry_run, stream, workers, session_id=None):
        captured["stages"] = stages
        captured["stream"] = stream
        captured["session_id"] = session_id
        return {"errors": []}

    monkeypatch.setattr(pipeline, "run_pipeline", fake_run_pipeline)

    result = runner.invoke(app, ["run", "discover", "--stream", "--session-id", "batch-stream"])
    assert result.exit_code == 0, result.output
    assert captured["stages"] == ["discover"]
    assert captured["stream"] is True
    assert captured["session_id"] == "batch-stream"


def test_cli_apply_url_forwards_target_url(monkeypatch, tmp_path):
    app_dir, db_path, conn = _configure_test_home(monkeypatch, tmp_path)
    target_url = "https://target.example/apply/123"

    (app_dir / "profile.json").write_text("{}", encoding="utf-8")
    conn.execute(
        """
        INSERT INTO jobs (url, title, company, site, discovered_at, tailored_resume_path, application_url, fit_score)
        VALUES (?, ?, ?, ?, datetime('now'), ?, ?, ?)
        """,
        (target_url, "Role", "Acme", "Indeed", str(app_dir / "tailored_resumes" / "resume.txt"), target_url, 8),
    )
    conn.commit()

    monkeypatch.setattr(config, "check_tier", lambda required, feature: None)

    from applypilot.apply import launcher

    captured = {}

    def fake_apply_main(limit, target_url, min_score, headless, model, dry_run, continuous, workers, session_id=None):
        captured["target_url"] = target_url
        captured["dry_run"] = dry_run
        captured["session_id"] = session_id

    monkeypatch.setattr(launcher, "main", fake_apply_main)

    result = runner.invoke(app, ["apply", "--url", target_url, "--dry-run"])
    assert result.exit_code == 0, result.output
    assert captured["target_url"] == target_url
    assert captured["dry_run"] is True
    assert captured["session_id"] is None

    database.close_connection(db_path)


def test_cli_apply_failure_then_retry_lifecycle(monkeypatch, tmp_path):
    app_dir, db_path, conn = _configure_test_home(monkeypatch, tmp_path)
    url = "https://retry.example/job"

    (app_dir / "profile.json").write_text("{}", encoding="utf-8")
    conn.execute(
        """
        INSERT INTO jobs (
            url, title, company, site, session_id, discovered_at,
            tailored_resume_path, application_url, fit_score, apply_status, apply_attempts
        ) VALUES (?, ?, ?, ?, ?, datetime('now'), ?, ?, ?, ?, ?)
        """,
        (
            url,
            "Retry Role",
            "Acme",
            "Indeed",
            "batch-a",
            str(app_dir / "tailored_resumes" / "retry.txt"),
            url,
            9,
            None,
            0,
        ),
    )
    conn.commit()

    monkeypatch.setattr(config, "check_tier", lambda required, feature: None)

    from applypilot.apply import launcher

    attempts = {"count": 0}

    def fake_apply_main(limit, target_url, min_score, headless, model, dry_run, continuous, workers, session_id=None):
        job = launcher.acquire_job(target_url=target_url, min_score=min_score, worker_id=0, session_id=session_id)
        assert job is not None
        if attempts["count"] == 0:
            launcher.mark_result(job["url"], "failed", error="temporary")
        else:
            launcher.mark_result(job["url"], "applied")
        attempts["count"] += 1

    monkeypatch.setattr(launcher, "main", fake_apply_main)

    first = runner.invoke(app, ["apply", "--limit", "1"])
    assert first.exit_code == 0, first.output
    first_row = database.get_connection(db_path).execute(
        "SELECT apply_status, apply_attempts, apply_error FROM jobs WHERE url = ?",
        (url,),
    ).fetchone()
    assert first_row[0] == "failed"
    assert first_row[1] == 1
    assert first_row[2] == "temporary"

    second = runner.invoke(app, ["apply", "--limit", "1"])
    assert second.exit_code == 0, second.output
    second_row = database.get_connection(db_path).execute(
        "SELECT apply_status, applied_at FROM jobs WHERE url = ?",
        (url,),
    ).fetchone()
    assert second_row[0] == "applied"
    assert second_row[1] is not None

    database.close_connection(db_path)
