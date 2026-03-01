from pathlib import Path

from applypilot import database


def test_init_db_includes_session_id_column(tmp_path):
    db_path = tmp_path / "test.db"
    conn = database.init_db(db_path)

    cols = [row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()]

    assert "session_id" in cols
    assert "company" in cols
    database.close_connection(db_path)


def test_remove_semantic_duplicates_keeps_highest_score(tmp_path):
    db_path = tmp_path / "dupes.db"
    conn = database.init_db(db_path)

    conn.execute(
        "INSERT INTO jobs (url, title, site, discovered_at, fit_score) VALUES (?, ?, ?, ?, ?)",
        ("https://a", "Backend Engineer", "ExampleSite", "2026-01-01T00:00:00Z", 6),
    )
    conn.execute(
        "INSERT INTO jobs (url, title, site, discovered_at, fit_score) VALUES (?, ?, ?, ?, ?)",
        ("https://b", "Backend Engineer", "ExampleSite", "2026-01-02T00:00:00Z", 9),
    )
    conn.execute(
        "INSERT INTO jobs (url, title, site, discovered_at, fit_score) VALUES (?, ?, ?, ?, ?)",
        ("https://c", "Data Engineer", "ExampleSite", "2026-01-02T00:00:00Z", 8),
    )
    conn.commit()

    removed = database.remove_semantic_duplicates(conn)
    remaining_urls = {row[0] for row in conn.execute("SELECT url FROM jobs").fetchall()}

    assert removed == 1
    assert "https://b" in remaining_urls
    assert "https://a" not in remaining_urls
    assert "https://c" in remaining_urls
    database.close_connection(db_path)


def test_remove_semantic_duplicates_uses_company_and_title(tmp_path):
    db_path = tmp_path / "dupes-company.db"
    conn = database.init_db(db_path)

    conn.execute(
        "INSERT INTO jobs (url, title, company, site, discovered_at, fit_score) VALUES (?, ?, ?, ?, ?, ?)",
        ("https://a", "Backend Engineer", "Acme", "Indeed", "2026-01-01T00:00:00Z", 7),
    )
    conn.execute(
        "INSERT INTO jobs (url, title, company, site, discovered_at, fit_score) VALUES (?, ?, ?, ?, ?, ?)",
        ("https://b", "Backend Engineer", "Acme", "LinkedIn", "2026-01-02T00:00:00Z", 9),
    )
    conn.execute(
        "INSERT INTO jobs (url, title, company, site, discovered_at, fit_score) VALUES (?, ?, ?, ?, ?, ?)",
        ("https://c", "Backend Engineer", "Globex", "Indeed", "2026-01-02T00:00:00Z", 8),
    )
    conn.commit()

    removed = database.remove_semantic_duplicates(conn)
    remaining_urls = {row[0] for row in conn.execute("SELECT url FROM jobs").fetchall()}

    assert removed == 1
    assert remaining_urls == {"https://b", "https://c"}
    database.close_connection(db_path)
