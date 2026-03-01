from applypilot import database
from applypilot.apply import launcher


def _insert_job(
    conn,
    *,
    url,
    title="Role",
    site="Example",
    fit_score=8,
    session_id="s1",
    application_url=None,
    apply_status=None,
    apply_attempts=0,
):
    conn.execute(
        """
        INSERT INTO jobs (
            url, title, site, fit_score, session_id,
            tailored_resume_path, application_url,
            apply_status, apply_attempts, discovered_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        (
            url,
            title,
            site,
            fit_score,
            session_id,
            "/tmp/resume.txt",
            application_url,
            apply_status,
            apply_attempts,
        ),
    )


def test_acquire_job_applies_blocked_filters_and_session(monkeypatch, tmp_path):
    db_path = tmp_path / "apply.db"
    conn = database.init_db(db_path)

    _insert_job(conn, url="https://ok.example/job1", site="GoodSite", session_id="batch-a")
    _insert_job(conn, url="https://forbidden.example/job2", site="GoodSite", session_id="batch-a")
    _insert_job(conn, url="https://blocked-site.example/job3", site="BlockedSite", session_id="batch-a")
    _insert_job(conn, url="https://wrong-session.example/job4", site="GoodSite", session_id="batch-b")
    conn.commit()

    monkeypatch.setattr(launcher, "get_connection", lambda: database.get_connection(db_path))
    monkeypatch.setattr(launcher, "_load_blocked", lambda: ({"BlockedSite"}, ["%forbidden%"] ))
    monkeypatch.setattr("applypilot.config.is_manual_ats", lambda _: False)

    job = launcher.acquire_job(min_score=7, worker_id=3, session_id="batch-a")

    assert job is not None
    assert job["url"] == "https://ok.example/job1"

    row = conn.execute("SELECT apply_status, agent_id FROM jobs WHERE url = ?", ("https://ok.example/job1",)).fetchone()
    assert row[0] == "in_progress"
    assert row[1] == "worker-3"

    database.close_connection(db_path)


def test_acquire_job_returns_none_when_session_has_no_eligible_jobs(monkeypatch, tmp_path):
    db_path = tmp_path / "apply-none.db"
    conn = database.init_db(db_path)
    _insert_job(conn, url="https://only-batch-b.example/job", session_id="batch-b")
    conn.commit()

    monkeypatch.setattr(launcher, "get_connection", lambda: database.get_connection(db_path))
    monkeypatch.setattr(launcher, "_load_blocked", lambda: (set(), []))
    monkeypatch.setattr("applypilot.config.is_manual_ats", lambda _: False)

    job = launcher.acquire_job(min_score=7, worker_id=1, session_id="batch-a")

    assert job is None
    database.close_connection(db_path)


def test_acquire_job_target_url_allows_null_apply_status(monkeypatch, tmp_path):
    db_path = tmp_path / "apply-target.db"
    conn = database.init_db(db_path)
    target = "https://target.example/job/123"
    _insert_job(
        conn,
        url=target,
        application_url=f"{target}?source=board",
        apply_status=None,
    )
    conn.commit()

    monkeypatch.setattr(launcher, "get_connection", lambda: database.get_connection(db_path))
    monkeypatch.setattr(launcher, "_load_blocked", lambda: (set(), []))
    monkeypatch.setattr("applypilot.config.is_manual_ats", lambda _: False)

    job = launcher.acquire_job(target_url=target, min_score=7, worker_id=9)

    assert job is not None
    assert job["url"] == target

    row = conn.execute("SELECT apply_status, agent_id FROM jobs WHERE url = ?", (target,)).fetchone()
    assert row[0] == "in_progress"
    assert row[1] == "worker-9"

    database.close_connection(db_path)
