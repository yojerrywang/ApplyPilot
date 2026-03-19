"""Bridge module: ApplyPilot → Resume-Matcher integration.

Queries top-scored jobs from ApplyPilot's SQLite, sends them to
Resume-Matcher's API for tailoring, and stores the results back.

Usage:
    from applypilot.bridge import run_bridge
    run_bridge(min_score=8, limit=50)

Or via CLI:
    applypilot bridge --min-score 8 --limit 50
"""

import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from applypilot.config import (
    APP_DIR, TAILORED_DIR, COVER_LETTER_DIR, RESUME_PDF_PATH, load_env,
)
from applypilot.database import get_connection, init_db

log = logging.getLogger(__name__)

# Resume-Matcher API base URL (local dev server)
RM_BASE_URL = os.environ.get("RESUME_MATCHER_URL", "http://localhost:8000")
RM_API_PREFIX = "/api/v1"

# Directory for proof/review reports
PROOF_DIR = APP_DIR / "proof_reports"

# Timeout for Resume-Matcher API calls (tailoring can be slow)
RM_TIMEOUT = float(os.environ.get("RM_TIMEOUT", "120"))


class ResumeMatcher:
    """Client for Resume-Matcher's local API."""

    def __init__(self, base_url: str = RM_BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")
        self.api = f"{self.base_url}{RM_API_PREFIX}"
        self._client = httpx.Client(timeout=httpx.Timeout(RM_TIMEOUT, connect=10.0))
        self._master_resume_id: str | None = None

    def health_check(self) -> dict:
        """Check if Resume-Matcher is running and healthy."""
        resp = self._client.get(f"{self.api}/health")
        resp.raise_for_status()
        return resp.json()

    def status(self) -> dict:
        """Get Resume-Matcher status including master resume info."""
        resp = self._client.get(f"{self.api}/status")
        resp.raise_for_status()
        return resp.json()

    def upload_resume(self, resume_path: str | Path) -> str:
        """Upload a resume file (PDF/DOCX) and return the resume_id."""
        path = Path(resume_path)
        if not path.exists():
            raise FileNotFoundError(f"Resume not found: {path}")

        content_type = "application/pdf" if path.suffix == ".pdf" else (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

        with open(path, "rb") as f:
            resp = self._client.post(
                f"{self.api}/resumes/upload",
                files={"file": (path.name, f, content_type)},
            )
        resp.raise_for_status()
        data = resp.json()
        resume_id = data["resume_id"]
        log.info("Uploaded resume %s → id=%s (status=%s)", path.name, resume_id, data.get("processing_status"))

        # Wait for processing to complete
        self._wait_for_ready(resume_id)
        return resume_id

    def _wait_for_ready(self, resume_id: str, max_wait: int = 60) -> None:
        """Poll until resume processing_status is 'ready'."""
        for _ in range(max_wait // 2):
            resp = self._client.get(f"{self.api}/resumes", params={"resume_id": resume_id})
            resp.raise_for_status()
            data = resp.json()
            status = data.get("data", {}).get("raw_resume", {}).get("processing_status", "")
            if status == "ready":
                return
            if status == "failed":
                raise RuntimeError(f"Resume processing failed for {resume_id}")
            time.sleep(2)
        raise TimeoutError(f"Resume {resume_id} still processing after {max_wait}s")

    def get_master_resume_id(self) -> str | None:
        """Get the master resume ID from Resume-Matcher, if one exists."""
        resp = self._client.get(f"{self.api}/resumes/list", params={"include_master": True})
        resp.raise_for_status()
        resumes = resp.json().get("resumes", [])
        for r in resumes:
            if r.get("is_master"):
                return r["resume_id"]
        return None

    def ensure_master_resume(self, resume_path: str | Path) -> str:
        """Ensure a master resume is uploaded. Returns the resume_id."""
        if self._master_resume_id:
            return self._master_resume_id

        existing = self.get_master_resume_id()
        if existing:
            log.info("Master resume already uploaded: %s", existing)
            self._master_resume_id = existing
            return existing

        log.info("No master resume found, uploading %s", resume_path)
        self._master_resume_id = self.upload_resume(resume_path)
        return self._master_resume_id

    def upload_job(self, job_description: str, resume_id: str | None = None) -> str:
        """Upload a job description and return the job_id."""
        payload = {
            "job_descriptions": [job_description],
        }
        if resume_id:
            payload["resume_id"] = resume_id

        resp = self._client.post(f"{self.api}/jobs/upload", json=payload)
        resp.raise_for_status()
        data = resp.json()
        job_ids = data.get("job_id", [])
        if not job_ids:
            raise RuntimeError("No job_id returned from Resume-Matcher")
        return job_ids[0]

    def tailor_resume(self, resume_id: str, job_id: str) -> dict:
        """Tailor a resume for a job description. Returns the full response."""
        payload = {
            "resume_id": resume_id,
            "job_id": job_id,
        }
        resp = self._client.post(f"{self.api}/resumes/improve", json=payload)
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        self._client.close()


def _get_job_description(job: dict) -> str:
    """Extract the best available job description text."""
    return job.get("full_description") or job.get("description") or ""


def _safe_filename(text: str, max_len: int = 50) -> str:
    """Create a filesystem-safe filename from text."""
    import re
    safe = re.sub(r'[^\w\s-]', '', text or 'unknown').strip()
    safe = re.sub(r'[-\s]+', '_', safe)
    return safe[:max_len]


def run_bridge(
    min_score: int = 8,
    limit: int = 50,
    resume_path: str | Path | None = None,
    rm_url: str | None = None,
    dry_run: bool = False,
) -> dict:
    """Run the bridge: pull top jobs from ApplyPilot, tailor via Resume-Matcher.

    Args:
        min_score: Minimum fit_score to include (default 8).
        limit: Maximum jobs to process in this batch.
        resume_path: Path to master resume PDF. Defaults to ~/.applypilot/resume.pdf.
        rm_url: Resume-Matcher API URL. Defaults to http://localhost:8000.
        dry_run: If True, only show what would be processed.

    Returns:
        Summary dict with counts of processed, succeeded, failed jobs.
    """
    load_env()
    init_db()

    if resume_path is None:
        resume_path = RESUME_PDF_PATH

    TAILORED_DIR.mkdir(parents=True, exist_ok=True)
    COVER_LETTER_DIR.mkdir(parents=True, exist_ok=True)
    PROOF_DIR.mkdir(parents=True, exist_ok=True)

    conn = get_connection()

    # Query jobs that are scored high but not yet tailored via Resume-Matcher
    # We look for jobs with high scores that haven't been tailored yet
    jobs = conn.execute(
        """
        SELECT url, title, company, full_description, description, fit_score,
               score_reasoning, application_url, site
        FROM jobs
        WHERE fit_score >= ?
          AND full_description IS NOT NULL
          AND tailored_resume_path IS NULL
          AND COALESCE(tailor_attempts, 0) < 5
        ORDER BY fit_score DESC, discovered_at DESC
        LIMIT ?
        """,
        (min_score, limit),
    ).fetchall()

    if not jobs:
        log.info("No eligible jobs found (min_score=%d, limit=%d)", min_score, limit)
        return {"processed": 0, "succeeded": 0, "failed": 0, "skipped": 0}

    log.info("Found %d jobs to tailor (fit_score >= %d)", len(jobs), min_score)

    if dry_run:
        for job in jobs:
            log.info("  [DRY RUN] %s @ %s (score=%d)", job["title"], job["company"] or job["site"], job["fit_score"])
        return {"processed": 0, "succeeded": 0, "failed": 0, "skipped": len(jobs)}

    # Connect to Resume-Matcher
    rm = ResumeMatcher(base_url=rm_url or RM_BASE_URL)

    try:
        # Health check
        health = rm.health_check()
        if health.get("status") not in ("healthy", "degraded"):
            raise RuntimeError(f"Resume-Matcher unhealthy: {health}")
        log.info("Resume-Matcher connected: %s", health.get("status"))

        # Ensure master resume is uploaded
        master_id = rm.ensure_master_resume(resume_path)
        log.info("Master resume ID: %s", master_id)

        succeeded = 0
        failed = 0
        now = datetime.now(timezone.utc).isoformat()

        for i, job in enumerate(jobs):
            url = job["url"]
            title = job["title"] or "Unknown"
            company = job["company"] or job["site"] or "Unknown"
            jd_text = _get_job_description(dict(job))

            if not jd_text or len(jd_text.strip()) < 50:
                log.warning("[%d/%d] Skipping %s @ %s — JD too short", i + 1, len(jobs), title, company)
                conn.execute(
                    "UPDATE jobs SET tailor_attempts = COALESCE(tailor_attempts, 0) + 1 WHERE url = ?",
                    (url,),
                )
                conn.commit()
                failed += 1
                continue

            log.info("[%d/%d] Tailoring: %s @ %s (score=%d)", i + 1, len(jobs), title, company, job["fit_score"])

            try:
                # Upload job description to Resume-Matcher
                rm_job_id = rm.upload_job(jd_text, resume_id=master_id)

                # Tailor resume for this job
                result = rm.tailor_resume(master_id, rm_job_id)

                # Extract tailored content
                data = result.get("data", {})
                tailored_resume_id = data.get("resume_id")
                cover_letter = data.get("cover_letter")
                resume_preview = data.get("resume_preview", {})
                markdown_improved = data.get("markdownImproved")

                # Build filename
                safe_name = _safe_filename(f"{company}_{title}")
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

                # Save tailored resume as plain text (prefer markdown, fall back to structured→text)
                resume_content = markdown_improved if markdown_improved else _resume_to_text(resume_preview)
                resume_filename = f"{safe_name}_{timestamp}.txt"
                resume_path_out = TAILORED_DIR / resume_filename
                resume_path_out.write_text(resume_content, encoding="utf-8")

                # Save cover letter if available
                cover_path_out = None
                if cover_letter:
                    cover_filename = f"{safe_name}_{timestamp}_cover.txt"
                    cover_path_out = COVER_LETTER_DIR / cover_filename
                    cover_path_out.write_text(cover_letter, encoding="utf-8")

                # Save proof report (JD, original, tailored, diff, stats)
                import json as _json
                proof_report = {
                    "job_url": url,
                    "title": title,
                    "company": company,
                    "fit_score": job["fit_score"],
                    "score_reasoning": job["score_reasoning"],
                    "application_url": job["application_url"],
                    "job_description": jd_text[:3000],
                    "original_markdown": data.get("markdownOriginal"),
                    "tailored_markdown": markdown_improved,
                    "tailored_structured": resume_preview,
                    "cover_letter": cover_letter,
                    "diff_summary": data.get("diff_summary"),
                    "detailed_changes": data.get("detailed_changes"),
                    "refinement_stats": data.get("refinement_stats"),
                    "improvements": data.get("improvements"),
                    "warnings": data.get("warnings"),
                    "tailored_at": now,
                    "rm_resume_id": tailored_resume_id,
                }
                proof_filename = f"{safe_name}_{timestamp}_proof.json"
                proof_path = PROOF_DIR / proof_filename
                proof_path.write_text(_json.dumps(proof_report, indent=2, default=str), encoding="utf-8")

                # Update ApplyPilot database
                conn.execute(
                    """
                    UPDATE jobs
                    SET tailored_resume_path = ?,
                        tailored_at = ?,
                        tailor_attempts = COALESCE(tailor_attempts, 0) + 1,
                        cover_letter_path = ?,
                        cover_letter_at = ?
                    WHERE url = ?
                    """,
                    (
                        str(resume_path_out),
                        now,
                        str(cover_path_out) if cover_path_out else None,
                        now if cover_path_out else None,
                        url,
                    ),
                )
                conn.commit()

                # Log refinement stats if available
                stats = data.get("refinement_stats")
                if stats:
                    log.info(
                        "  Refinement: keywords_injected=%d, ai_phrases_removed=%d, match=%d%%→%d%%",
                        stats.get("keywords_injected", 0),
                        len(stats.get("ai_phrases_removed", [])),
                        int(stats.get("initial_match_percentage", 0)),
                        int(stats.get("final_match_percentage", 0)),
                    )

                succeeded += 1
                log.info("  ✓ Saved: %s", resume_path_out.name)

            except Exception as e:
                log.error("  ✗ Failed: %s — %s", title, e)
                conn.execute(
                    "UPDATE jobs SET tailor_attempts = COALESCE(tailor_attempts, 0) + 1 WHERE url = ?",
                    (url,),
                )
                conn.commit()
                failed += 1

            # Small delay between API calls to be nice to the LLM
            if i < len(jobs) - 1:
                time.sleep(1)

    finally:
        rm.close()

    summary = {
        "processed": len(jobs),
        "succeeded": succeeded,
        "failed": failed,
        "skipped": 0,
    }
    log.info("Bridge complete: %d processed, %d succeeded, %d failed", len(jobs), succeeded, failed)
    return summary


def _resume_to_text(resume_data: dict) -> str:
    """Convert ResumeData JSON to plain text resume format."""
    lines = []

    # Personal info
    pi = resume_data.get("personalInfo", {})
    if pi.get("name"):
        lines.append(pi["name"])
    if pi.get("title"):
        lines.append(pi["title"])
    contact = []
    for field in ("email", "phone", "location", "linkedin", "github", "website"):
        if pi.get(field):
            contact.append(pi[field])
    if contact:
        lines.append(" | ".join(contact))
    lines.append("")

    # Summary
    if resume_data.get("summary"):
        lines.append("SUMMARY")
        lines.append(resume_data["summary"])
        lines.append("")

    # Work experience
    if resume_data.get("workExperience"):
        lines.append("EXPERIENCE")
        for exp in resume_data["workExperience"]:
            lines.append(f"{exp.get('title', '')} — {exp.get('company', '')}")
            if exp.get("location"):
                lines.append(f"  {exp['location']}")
            if exp.get("years"):
                lines.append(f"  {exp['years']}")
            for bullet in exp.get("description", []):
                lines.append(f"  • {bullet}")
            lines.append("")

    # Projects
    if resume_data.get("personalProjects"):
        lines.append("PROJECTS")
        for proj in resume_data["personalProjects"]:
            header = proj.get("name", "")
            if proj.get("role"):
                header += f" — {proj['role']}"
            lines.append(header)
            if proj.get("years"):
                lines.append(f"  {proj['years']}")
            for bullet in proj.get("description", []):
                lines.append(f"  • {bullet}")
            lines.append("")

    # Education
    if resume_data.get("education"):
        lines.append("EDUCATION")
        for edu in resume_data["education"]:
            lines.append(f"{edu.get('degree', '')} — {edu.get('institution', '')}")
            if edu.get("years"):
                lines.append(f"  {edu['years']}")
            if edu.get("description"):
                lines.append(f"  {edu['description']}")
            lines.append("")

    # Skills / Additional
    additional = resume_data.get("additional", {})
    if additional.get("technicalSkills"):
        lines.append("SKILLS")
        lines.append(", ".join(additional["technicalSkills"]))
        lines.append("")
    if additional.get("languages"):
        lines.append("LANGUAGES")
        lines.append(", ".join(additional["languages"]))
        lines.append("")
    if additional.get("certificationsTraining"):
        lines.append("CERTIFICATIONS")
        lines.append(", ".join(additional["certificationsTraining"]))
        lines.append("")

    return "\n".join(lines)
