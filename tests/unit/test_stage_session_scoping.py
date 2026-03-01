from pathlib import Path

from applypilot import database
from applypilot.enrichment import detail
from applypilot.scoring import cover_letter, scorer, tailor


def _insert_job(
    conn,
    *,
    url: str,
    session_id: str,
    title: str = "Role",
    site: str = "Indeed",
    full_description: str | None = "description",
    fit_score: int | None = None,
    tailored_resume_path: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO jobs (
            url, title, site, session_id, discovered_at,
            full_description, fit_score, tailored_resume_path
        ) VALUES (?, ?, ?, ?, datetime('now'), ?, ?, ?)
        """,
        (
            url,
            title,
            site,
            session_id,
            full_description,
            fit_score,
            tailored_resume_path,
        ),
    )


def test_run_scoring_respects_session_id(monkeypatch, tmp_path):
    db_path = tmp_path / "score.db"
    resume_path = tmp_path / "resume.txt"
    resume_path.write_text("Resume", encoding="utf-8")
    conn = database.init_db(db_path)

    _insert_job(conn, url="https://a.example/job", session_id="batch-a", fit_score=None)
    _insert_job(conn, url="https://b.example/job", session_id="batch-b", fit_score=None)
    conn.commit()

    monkeypatch.setattr(scorer, "get_connection", lambda: database.get_connection(db_path))
    monkeypatch.setattr(scorer, "RESUME_PATH", resume_path)
    monkeypatch.setattr(
        scorer,
        "score_job",
        lambda resume_text, job: {"score": 8, "keywords": "python", "reasoning": "match"},
    )
    monkeypatch.setattr(scorer.time, "sleep", lambda _: None)

    result = scorer.run_scoring(session_id="batch-a")

    assert result["scored"] == 1
    row_a = conn.execute("SELECT fit_score FROM jobs WHERE session_id = 'batch-a'").fetchone()[0]
    row_b = conn.execute("SELECT fit_score FROM jobs WHERE session_id = 'batch-b'").fetchone()[0]
    assert row_a == 8
    assert row_b is None

    database.close_connection(db_path)


def test_run_tailoring_respects_session_id(monkeypatch, tmp_path):
    db_path = tmp_path / "tailor.db"
    resume_path = tmp_path / "resume.txt"
    resume_path.write_text("Resume", encoding="utf-8")
    conn = database.init_db(db_path)

    _insert_job(
        conn,
        url="https://a.example/job",
        session_id="batch-a",
        fit_score=9,
        tailored_resume_path=None,
    )
    _insert_job(
        conn,
        url="https://b.example/job",
        session_id="batch-b",
        fit_score=9,
        tailored_resume_path=None,
    )
    conn.commit()

    monkeypatch.setattr(tailor, "get_connection", lambda: database.get_connection(db_path))
    monkeypatch.setattr(tailor, "RESUME_PATH", resume_path)
    monkeypatch.setattr(tailor, "TAILORED_DIR", tmp_path / "tailored")
    monkeypatch.setattr(tailor, "load_profile", lambda: {})
    monkeypatch.setattr(
        tailor,
        "tailor_resume",
        lambda resume_text, job, profile: ("TAILORED RESUME", {"status": "approved", "attempts": 1}),
    )
    from applypilot.scoring import pdf as pdf_mod

    monkeypatch.setattr(pdf_mod, "convert_to_pdf", lambda txt_path: Path(txt_path).with_suffix(".pdf"))

    result = tailor.run_tailoring(min_score=7, session_id="batch-a")

    assert result["approved"] == 1
    row_a = conn.execute("SELECT tailored_resume_path FROM jobs WHERE session_id = 'batch-a'").fetchone()[0]
    row_b = conn.execute("SELECT tailored_resume_path FROM jobs WHERE session_id = 'batch-b'").fetchone()[0]
    assert row_a is not None
    assert row_b is None

    database.close_connection(db_path)


def test_run_cover_letters_respects_session_id(monkeypatch, tmp_path):
    db_path = tmp_path / "cover.db"
    resume_path = tmp_path / "resume.txt"
    resume_path.write_text("Resume", encoding="utf-8")
    conn = database.init_db(db_path)

    _insert_job(
        conn,
        url="https://a.example/job",
        session_id="batch-a",
        fit_score=8,
        tailored_resume_path=str(tmp_path / "tailored-a.txt"),
    )
    _insert_job(
        conn,
        url="https://b.example/job",
        session_id="batch-b",
        fit_score=8,
        tailored_resume_path=str(tmp_path / "tailored-b.txt"),
    )
    conn.commit()

    monkeypatch.setattr(cover_letter, "get_connection", lambda: database.get_connection(db_path))
    monkeypatch.setattr(cover_letter, "RESUME_PATH", resume_path)
    monkeypatch.setattr(cover_letter, "COVER_LETTER_DIR", tmp_path / "cover")
    monkeypatch.setattr(cover_letter, "load_profile", lambda: {})
    monkeypatch.setattr(cover_letter, "generate_cover_letter", lambda resume, job, profile: "Cover letter")
    from applypilot.scoring import pdf as pdf_mod

    monkeypatch.setattr(pdf_mod, "convert_to_pdf", lambda txt_path: Path(txt_path).with_suffix(".pdf"))

    result = cover_letter.run_cover_letters(min_score=7, session_id="batch-a")

    assert result["generated"] == 1
    row_a = conn.execute("SELECT cover_letter_path FROM jobs WHERE session_id = 'batch-a'").fetchone()[0]
    row_b = conn.execute("SELECT cover_letter_path FROM jobs WHERE session_id = 'batch-b'").fetchone()[0]
    assert row_a is not None
    assert row_b is None

    database.close_connection(db_path)


def test_detail_scraper_respects_session_id(monkeypatch, tmp_path):
    db_path = tmp_path / "detail.db"
    conn = database.init_db(db_path)
    conn.execute(
        "INSERT INTO jobs (url, title, site, session_id, discovered_at, detail_scraped_at) VALUES (?, ?, ?, ?, datetime('now'), NULL)",
        ("https://a.example/job", "Role A", "Indeed", "batch-a"),
    )
    conn.execute(
        "INSERT INTO jobs (url, title, site, session_id, discovered_at, detail_scraped_at) VALUES (?, ?, ?, ?, datetime('now'), NULL)",
        ("https://b.example/job", "Role B", "Indeed", "batch-b"),
    )
    conn.commit()

    scraped_urls: list[str] = []

    def fake_scrape_site_batch(conn_arg, site, jobs, delay=0, max_jobs=None):
        scraped_urls.extend(url for url, _ in jobs)
        return {"processed": len(jobs), "ok": len(jobs), "partial": 0, "error": 0, "tiers": {1: len(jobs), 2: 0, 3: 0}}

    monkeypatch.setattr(detail, "scrape_site_batch", fake_scrape_site_batch)

    stats = detail._run_detail_scraper(conn, workers=1, session_id="batch-a")

    assert stats["processed"] == 1
    assert scraped_urls == ["https://a.example/job"]
    database.close_connection(db_path)
