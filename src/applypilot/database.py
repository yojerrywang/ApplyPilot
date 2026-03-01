"""ApplyPilot database layer: schema, migrations, stats, and connection helpers.

Single source of truth for the jobs table schema. All columns from every
pipeline stage are created up front so any stage can run independently
without migration ordering issues.
"""

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from applypilot.config import DB_PATH

# Thread-local connection storage — each thread gets its own connection
# (required for SQLite thread safety with parallel workers)
_local = threading.local()


# Filter / dedupe transparency counters persisted across runs.
COUNTER_KEYS: tuple[str, ...] = ("filtered_by_location", "filtered_by_title", "deduped")
_COUNTER_SCOPE_ALL = "__all__"


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Get a thread-local cached SQLite connection with WAL mode enabled.

    Each thread gets its own connection (required for SQLite thread safety).
    Connections are cached and reused within the same thread.

    Args:
        db_path: Override the default DB_PATH. Useful for testing.

    Returns:
        sqlite3.Connection configured with WAL mode and row factory.
    """
    path = str(db_path or DB_PATH)

    if not hasattr(_local, 'connections'):
        _local.connections = {}

    conn = _local.connections.get(path)
    if conn is not None:
        try:
            conn.execute("SELECT 1")
            return conn
        except sqlite3.ProgrammingError:
            pass

    conn = sqlite3.connect(path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.row_factory = sqlite3.Row
    _local.connections[path] = conn
    return conn


def close_connection(db_path: Path | str | None = None) -> None:
    """Close the cached connection for the current thread."""
    path = str(db_path or DB_PATH)
    if hasattr(_local, 'connections'):
        conn = _local.connections.pop(path, None)
        if conn is not None:
            conn.close()


def init_db(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Create the full jobs table with all columns from every pipeline stage.

    This is idempotent -- safe to call on every startup. Uses CREATE TABLE IF NOT EXISTS
    so it won't destroy existing data.

    Schema columns by stage:
      - Discovery:  url, title, company, salary, description, location, site, strategy, discovered_at
      - Enrichment: full_description, application_url, detail_scraped_at, detail_error
      - Scoring:    fit_score, score_reasoning, scored_at
      - Tailoring:  tailored_resume_path, tailored_at, tailor_attempts
      - Cover:      cover_letter_path, cover_letter_at, cover_attempts
      - Apply:      applied_at, apply_status, apply_error, apply_attempts,
                   agent_id, last_attempted_at, apply_duration_ms, apply_task_id,
                   verification_confidence
      - Metrics:    transparency_counters table for filtered/deduped counts

    Args:
        db_path: Override the default DB_PATH.

    Returns:
        sqlite3.Connection with the schema initialized.
    """
    path = db_path or DB_PATH

    # Ensure parent directory exists
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    conn = get_connection(path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            -- Discovery stage (smart_extract / job_search)
            url                   TEXT PRIMARY KEY,
            title                 TEXT,
            company               TEXT,
            salary                TEXT,
            description           TEXT,
            location              TEXT,
            site                  TEXT,
            strategy              TEXT,
            session_id            TEXT,
            discovered_at         TEXT,

            -- Enrichment stage (detail_scraper)
            full_description      TEXT,
            application_url       TEXT,
            detail_scraped_at     TEXT,
            detail_error          TEXT,

            -- Scoring stage (job_scorer)
            fit_score             INTEGER,
            score_reasoning       TEXT,
            scored_at             TEXT,

            -- Tailoring stage (resume tailor)
            tailored_resume_path  TEXT,
            tailored_at           TEXT,
            tailor_attempts       INTEGER DEFAULT 0,

            -- Cover letter stage
            cover_letter_path     TEXT,
            cover_letter_at       TEXT,
            cover_attempts        INTEGER DEFAULT 0,

            -- Application stage
            applied_at            TEXT,
            apply_status          TEXT,
            apply_error           TEXT,
            apply_attempts        INTEGER DEFAULT 0,
            agent_id              TEXT,
            last_attempted_at     TEXT,
            apply_duration_ms     INTEGER,
            apply_task_id         TEXT,
            verification_confidence TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS transparency_counters (
            scope        TEXT NOT NULL,
            counter_name TEXT NOT NULL,
            value        INTEGER NOT NULL DEFAULT 0,
            updated_at   TEXT NOT NULL,
            PRIMARY KEY (scope, counter_name)
        )
    """)
    conn.commit()

    # Run migrations for any columns added after initial schema
    ensure_columns(conn)

    return conn


# Complete column registry: column_name -> SQL type with optional default.
# This is the single source of truth. Adding a column here is all that's needed
# for it to appear in both new databases and migrated ones.
_ALL_COLUMNS: dict[str, str] = {
    # Discovery
    "url": "TEXT PRIMARY KEY",
    "title": "TEXT",
    "company": "TEXT",
    "salary": "TEXT",
    "description": "TEXT",
    "location": "TEXT",
    "site": "TEXT",
    "strategy": "TEXT",
    "session_id": "TEXT",
    "discovered_at": "TEXT",
    # Enrichment
    "full_description": "TEXT",
    "application_url": "TEXT",
    "detail_scraped_at": "TEXT",
    "detail_error": "TEXT",
    # Scoring
    "fit_score": "INTEGER",
    "score_reasoning": "TEXT",
    "scored_at": "TEXT",
    # Tailoring
    "tailored_resume_path": "TEXT",
    "tailored_at": "TEXT",
    "tailor_attempts": "INTEGER DEFAULT 0",
    # Cover letter
    "cover_letter_path": "TEXT",
    "cover_letter_at": "TEXT",
    "cover_attempts": "INTEGER DEFAULT 0",
    # Application
    "applied_at": "TEXT",
    "apply_status": "TEXT",
    "apply_error": "TEXT",
    "apply_attempts": "INTEGER DEFAULT 0",
    "agent_id": "TEXT",
    "last_attempted_at": "TEXT",
    "apply_duration_ms": "INTEGER",
    "apply_task_id": "TEXT",
    "verification_confidence": "TEXT",
}


def ensure_columns(conn: sqlite3.Connection | None = None) -> list[str]:
    """Add any missing columns to the jobs table (forward migration).

    Reads the current table schema via PRAGMA table_info and compares against
    the full column registry. Any missing columns are added with ALTER TABLE.

    This makes it safe to upgrade the database from any previous version --
    columns are only added, never removed or renamed.

    Args:
        conn: Database connection. Uses get_connection() if None.

    Returns:
        List of column names that were added (empty if schema was already current).
    """
    if conn is None:
        conn = get_connection()

    existing = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
    added = []

    for col, dtype in _ALL_COLUMNS.items():
        if col not in existing:
            # PRIMARY KEY columns can't be added via ALTER TABLE, but url
            # is always created with the table itself so this is safe
            if "PRIMARY KEY" in dtype:
                continue
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} {dtype}")
            added.append(col)

    if added:
        conn.commit()

    return added


def increment_counter(
    counter_name: str,
    amount: int = 1,
    session_id: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> None:
    """Increment a transparency counter for the given scope.

    Args:
        counter_name: Counter key (recommended: values from COUNTER_KEYS).
        amount: Positive increment amount.
        session_id: Optional session scope. Uses global scope if omitted.
        conn: Optional DB connection.
    """
    if amount <= 0:
        return

    if conn is None:
        conn = get_connection()

    now = datetime.now(timezone.utc).isoformat()
    scope = session_id or _COUNTER_SCOPE_ALL

    conn.execute(
        """
        INSERT INTO transparency_counters (scope, counter_name, value, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(scope, counter_name) DO UPDATE
            SET value = value + excluded.value,
                updated_at = excluded.updated_at
        """,
        (scope, counter_name, amount, now),
    )
    conn.commit()


def get_transparency_counters(
    conn: sqlite3.Connection | None = None,
    session_id: str | None = None,
) -> dict[str, int]:
    """Fetch transparency counters globally or for a single session."""
    if conn is None:
        conn = get_connection()

    counters = {name: 0 for name in COUNTER_KEYS}

    if session_id:
        rows = conn.execute(
            """
            SELECT counter_name, value
            FROM transparency_counters
            WHERE scope = ?
            """,
            (session_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT counter_name, SUM(value) AS total
            FROM transparency_counters
            GROUP BY counter_name
            """
        ).fetchall()

    for row in rows:
        name = row[0]
        value = int(row[1] or 0)
        if name in counters:
            counters[name] = value

    return counters


def get_stats(conn: sqlite3.Connection | None = None, session_id: str | None = None) -> dict:
    """Return job counts by pipeline stage.

    Provides a snapshot of how many jobs are at each stage, useful for
    dashboard display and pipeline progress tracking.

    Args:
        conn: Database connection. Uses get_connection() if None.
        session_id: Optional session identifier to filter stats by batch.

    Returns:
        Dictionary with keys:
            total, by_site, pending_detail, with_description,
            scored, unscored, tailored, untailored_eligible,
            with_cover_letter, applied, score_distribution
    """
    if conn is None:
        conn = get_connection()

    stats: dict = {}

    where_clause = " WHERE session_id = ?" if session_id else ""
    where_and = " session_id = ? AND " if session_id else ""
    params = (session_id,) if session_id else ()

    # Total jobs
    stats["total"] = conn.execute(f"SELECT COUNT(*) FROM jobs{where_clause}", params).fetchone()[0]

    # By site breakdown
    rows = conn.execute(
        f"SELECT site, COUNT(*) as cnt FROM jobs{where_clause} GROUP BY site ORDER BY cnt DESC", params
    ).fetchall()
    stats["by_site"] = [(row[0], row[1]) for row in rows]

    # Enrichment stage
    stats["pending_detail"] = conn.execute(
        f"SELECT COUNT(*) FROM jobs WHERE {where_and}detail_scraped_at IS NULL", params
    ).fetchone()[0]

    stats["with_description"] = conn.execute(
        f"SELECT COUNT(*) FROM jobs WHERE {where_and}full_description IS NOT NULL", params
    ).fetchone()[0]

    stats["detail_errors"] = conn.execute(
        f"SELECT COUNT(*) FROM jobs WHERE {where_and}detail_error IS NOT NULL", params
    ).fetchone()[0]

    # Scoring stage
    stats["scored"] = conn.execute(
        f"SELECT COUNT(*) FROM jobs WHERE {where_and}fit_score IS NOT NULL", params
    ).fetchone()[0]

    stats["unscored"] = conn.execute(
        f"SELECT COUNT(*) FROM jobs "
        f"WHERE {where_and}full_description IS NOT NULL AND fit_score IS NULL", params
    ).fetchone()[0]

    # Score distribution
    dist_rows = conn.execute(
        f"SELECT fit_score, COUNT(*) as cnt FROM jobs "
        f"WHERE {where_and}fit_score IS NOT NULL "
        f"GROUP BY fit_score ORDER BY fit_score DESC", params
    ).fetchall()
    stats["score_distribution"] = [(row[0], row[1]) for row in dist_rows]

    # Tailoring stage
    stats["tailored"] = conn.execute(
        f"SELECT COUNT(*) FROM jobs WHERE {where_and}tailored_resume_path IS NOT NULL", params
    ).fetchone()[0]

    stats["untailored_eligible"] = conn.execute(
        f"SELECT COUNT(*) FROM jobs "
        f"WHERE {where_and}fit_score >= 7 AND full_description IS NOT NULL "
        f"AND tailored_resume_path IS NULL", params
    ).fetchone()[0]

    stats["tailor_exhausted"] = conn.execute(
        f"SELECT COUNT(*) FROM jobs "
        f"WHERE {where_and}COALESCE(tailor_attempts, 0) >= 5 "
        f"AND tailored_resume_path IS NULL", params
    ).fetchone()[0]

    # Cover letter stage
    stats["with_cover_letter"] = conn.execute(
        f"SELECT COUNT(*) FROM jobs WHERE {where_and}cover_letter_path IS NOT NULL", params
    ).fetchone()[0]

    stats["cover_exhausted"] = conn.execute(
        f"SELECT COUNT(*) FROM jobs "
        f"WHERE {where_and}COALESCE(cover_attempts, 0) >= 5 "
        f"AND (cover_letter_path IS NULL OR cover_letter_path = '')", params
    ).fetchone()[0]

    # Application stage
    stats["applied"] = conn.execute(
        f"SELECT COUNT(*) FROM jobs WHERE {where_and}applied_at IS NOT NULL", params
    ).fetchone()[0]

    stats["apply_errors"] = conn.execute(
        f"SELECT COUNT(*) FROM jobs WHERE {where_and}apply_error IS NOT NULL", params
    ).fetchone()[0]

    stats["ready_to_apply"] = conn.execute(
        f"SELECT COUNT(*) FROM jobs "
        f"WHERE {where_and}tailored_resume_path IS NOT NULL "
        f"AND applied_at IS NULL "
        f"AND application_url IS NOT NULL", params
    ).fetchone()[0]

    counters = get_transparency_counters(conn=conn, session_id=session_id)
    stats["filtered_by_location"] = counters["filtered_by_location"]
    stats["filtered_by_title"] = counters["filtered_by_title"]
    stats["deduped"] = counters["deduped"]

    return stats


def store_jobs(conn: sqlite3.Connection, jobs: list[dict],
               site: str, strategy: str) -> tuple[int, int]:
    """Store discovered jobs, skipping duplicates by URL.

    Args:
        conn: Database connection.
        jobs: List of job dicts with keys: url, title, salary, description, location.
        site: Source site name (e.g. "RemoteOK", "Dice").
        strategy: Extraction strategy used (e.g. "json_ld", "api_response", "css_selectors").

    Returns:
        Tuple of (new_count, duplicate_count).
    """
    now = datetime.now(timezone.utc).isoformat()
    import os
    session_id = os.environ.get("APPLYPILOT_SESSION_ID")
    new = 0
    existing = 0

    for job in jobs:
        url = job.get("url")
        if not url:
            continue
        try:
            conn.execute(
                "INSERT INTO jobs (url, title, company, salary, description, location, site, strategy, session_id, discovered_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (url, job.get("title"), job.get("company"), job.get("salary"), job.get("description"),
                 job.get("location"), site, strategy, session_id, now),
            )
            new += 1
        except sqlite3.IntegrityError:
            existing += 1

    conn.commit()
    return new, existing


def get_jobs_by_stage(conn: sqlite3.Connection | None = None,
                      stage: str = "discovered",
                      min_score: int | None = None,
                      limit: int = 1000,
                      session_id: str | None = None) -> list[dict]:
    """Fetch jobs filtered by pipeline stage.

    Args:
        conn: Database connection. Uses get_connection() if None.
        stage: One of "discovered", "enriched", "scored", "tailored", "applied".
        min_score: Minimum fit_score filter (only relevant for scored+ stages).
        limit: Maximum number of rows to return.
        session_id: Optional session identifier to filter stats by batch.

    Returns:
        List of job dicts.
    """
    if conn is None:
        conn = get_connection()

    conditions = {
        "discovered": "1=1",
        "pending_detail": "detail_scraped_at IS NULL",
        "enriched": "full_description IS NOT NULL",
        "pending_score": "full_description IS NOT NULL AND fit_score IS NULL",
        "scored": "fit_score IS NOT NULL",
        "pending_tailor": (
            "fit_score >= ? AND full_description IS NOT NULL "
            "AND tailored_resume_path IS NULL AND COALESCE(tailor_attempts, 0) < 5"
        ),
        "tailored": "tailored_resume_path IS NOT NULL",
        "pending_apply": (
            "tailored_resume_path IS NOT NULL AND applied_at IS NULL "
            "AND application_url IS NOT NULL"
        ),
        "applied": "applied_at IS NOT NULL",
    }

    where = conditions.get(stage, "1=1")
    params: list = []

    if "?" in where and min_score is not None:
        params.append(min_score)
    elif "?" in where:
        params.append(7)  # default min_score

    if min_score is not None and "fit_score" not in where and stage in ("scored", "tailored", "applied"):
        where += " AND fit_score >= ?"
        params.append(min_score)

    if session_id:
        where += " AND session_id = ?"
        params.append(session_id)

    query = f"SELECT * FROM jobs WHERE {where} ORDER BY fit_score DESC NULLS LAST, discovered_at DESC"
    if limit > 0:
        query += " LIMIT ?"
        params.append(limit)

    rows = conn.execute(query, params).fetchall()

    # Convert sqlite3.Row objects to dicts
    if rows:
        columns = rows[0].keys()
        return [dict(zip(columns, row)) for row in rows]
    return []


def remove_semantic_duplicates(
    conn: sqlite3.Connection | None = None,
    session_id: str | None = None,
) -> int:
    """Remove semantic duplicates (same title and company) from the database.

    Keeps the one with the highest fit_score or most recent discovery date.
    
    Args:
        conn: Target connection. Uses default if None.

    Returns:
        Number of duplicate rows deleted.
    """
    if conn is None:
        conn = get_connection()

    session_filter = "AND session_id = ?" if session_id else ""
    params = (session_id,) if session_id else ()

    query = f"""
    WITH RankedJobs AS (
        SELECT url,
               ROW_NUMBER() OVER (
                   PARTITION BY
                       LOWER(TRIM(COALESCE(NULLIF(company, ''), NULLIF(site, '')))),
                       LOWER(TRIM(title))
                   ORDER BY 
                       COALESCE(fit_score, 0) DESC, 
                       discovered_at DESC
               ) as rn
        FROM jobs
        WHERE title IS NOT NULL
          AND TRIM(title) != ''
          AND COALESCE(NULLIF(company, ''), NULLIF(site, '')) IS NOT NULL
          {session_filter}
    )
    SELECT url FROM RankedJobs WHERE rn > 1;
    """
    
    rows = conn.execute(query, params).fetchall()
    urls_to_delete = [row[0] for row in rows]
    
    if not urls_to_delete:
        return 0

    placeholders = ','.join('?' * len(urls_to_delete))
    delete_query = f"DELETE FROM jobs WHERE url IN ({placeholders})"
    
    cursor = conn.execute(delete_query, urls_to_delete)
    conn.commit()

    removed = cursor.rowcount
    if removed > 0:
        increment_counter("deduped", amount=removed, session_id=session_id, conn=conn)

    return removed
