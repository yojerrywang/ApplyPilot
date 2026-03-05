"""ApplyPilot CLI — the main entry point."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from applypilot import __version__
from applypilot.google.auth import get_credentials as _get_google_creds
from applypilot.google.drive import (
    download_file as _drive_download,
    find_file_by_name as _drive_find,
    upload_file as _drive_upload,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)

app = typer.Typer(
    name="applypilot",
    help="AI-powered end-to-end job application pipeline.",
    no_args_is_help=True,
)
console = Console()
log = logging.getLogger(__name__)

# Valid pipeline stages (in execution order)
VALID_STAGES = ("discover", "dedupe", "enrich", "score", "tailor", "cover", "pdf")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bootstrap() -> None:
    """Common setup: load env, create dirs, init DB."""
    from applypilot.config import load_env, ensure_dirs
    from applypilot.database import init_db

    load_env()
    ensure_dirs()
    init_db()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"[bold]applypilot[/bold] {__version__}")
        raise typer.Exit()


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", "-V",
        help="Show version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """ApplyPilot — AI-powered end-to-end job application pipeline."""


@app.command()
def init() -> None:
    """Run the first-time setup wizard (profile, resume, search config)."""
    from applypilot.wizard.init import run_wizard

    run_wizard()


@app.command()
def run(
    stages: Optional[list[str]] = typer.Argument(
        None,
        help=(
            "Pipeline stages to run. "
            f"Valid: {', '.join(VALID_STAGES)}, all. "
            "Defaults to 'all' if omitted."
        ),
    ),
    min_score: int = typer.Option(7, "--min-score", help="Minimum fit score for tailor/cover stages."),
    workers: int = typer.Option(1, "--workers", "-w", help="Parallel threads for discovery/enrichment stages."),
    stream: bool = typer.Option(False, "--stream", help="Run stages concurrently (streaming mode)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview stages without executing."),
    session_id: Optional[str] = typer.Option(None, "--session-id", help="Process only jobs from a specific session batch."),
) -> None:
    """Run pipeline stages: discover, dedupe, enrich, score, tailor, cover, pdf."""
    _bootstrap()

    from applypilot.pipeline import run_pipeline

    stage_list = stages if stages else ["all"]

    # Validate stage names
    for s in stage_list:
        if s != "all" and s not in VALID_STAGES:
            console.print(
                f"[red]Unknown stage:[/red] '{s}'. "
                f"Valid stages: {', '.join(VALID_STAGES)}, all"
            )
            raise typer.Exit(code=1)

    # Gate AI stages behind Tier 2
    llm_stages = {"score", "tailor", "cover"}
    if any(s in stage_list for s in llm_stages) or "all" in stage_list:
        from applypilot.config import check_tier
        check_tier(2, "AI scoring/tailoring")

    result = run_pipeline(
        stages=stage_list,
        min_score=min_score,
        dry_run=dry_run,
        stream=stream,
        workers=workers,
        session_id=session_id,
    )

    if result.get("errors"):
        raise typer.Exit(code=1)


@app.command()
def apply(
    limit: Optional[int] = typer.Option(None, "--limit", "-l", help="Max applications to submit."),
    workers: int = typer.Option(1, "--workers", "-w", help="Number of parallel browser workers."),
    min_score: int = typer.Option(7, "--min-score", help="Minimum fit score for job selection."),
    model: str = typer.Option("haiku", "--model", "-m", help="Claude model name."),
    continuous: bool = typer.Option(False, "--continuous", "-c", help="Run forever, polling for new jobs."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview actions without submitting."),
    headless: bool = typer.Option(False, "--headless", help="Run browsers in headless mode."),
    url: Optional[str] = typer.Option(None, "--url", help="Apply to a specific job URL."),
    session_id: Optional[str] = typer.Option(None, "--session-id", help="Apply only jobs discovered in a specific session batch."),
    gen: bool = typer.Option(False, "--gen", help="Generate prompt file for manual debugging instead of running."),
    mark_applied: Optional[str] = typer.Option(None, "--mark-applied", help="Manually mark a job URL as applied."),
    mark_failed: Optional[str] = typer.Option(None, "--mark-failed", help="Manually mark a job URL as failed (provide URL)."),
    fail_reason: Optional[str] = typer.Option(None, "--fail-reason", help="Reason for --mark-failed."),
    reset_failed: bool = typer.Option(False, "--reset-failed", help="Reset all failed jobs for retry."),
) -> None:
    """Launch auto-apply to submit job applications."""
    _bootstrap()

    from applypilot.config import check_tier, PROFILE_PATH as _profile_path
    from applypilot.database import get_connection

    # --- Utility modes (no Chrome/Claude needed) ---

    if mark_applied:
        from applypilot.apply.launcher import mark_job
        mark_job(mark_applied, "applied")
        console.print(f"[green]Marked as applied:[/green] {mark_applied}")
        return

    if mark_failed:
        from applypilot.apply.launcher import mark_job
        mark_job(mark_failed, "failed", reason=fail_reason)
        console.print(f"[yellow]Marked as failed:[/yellow] {mark_failed} ({fail_reason or 'manual'})")
        return

    if reset_failed:
        from applypilot.apply.launcher import reset_failed as do_reset
        count = do_reset()
        console.print(f"[green]Reset {count} failed job(s) for retry.[/green]")
        return

    # --- Full apply mode ---

    # Check 1: Tier 3 required (Claude Code CLI + Chrome)
    check_tier(3, "auto-apply")

    # Check 2: Profile exists
    if not _profile_path.exists():
        console.print(
            "[red]Profile not found.[/red]\n"
            "Run [bold]applypilot init[/bold] to create your profile first."
        )
        raise typer.Exit(code=1)

    # Check 3: Tailored resumes exist (skip for --gen with --url)
    if not (gen and url):
        conn = get_connection()
        ready = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE tailored_resume_path IS NOT NULL AND applied_at IS NULL"
        ).fetchone()[0]
        if ready == 0:
            console.print(
                "[red]No tailored resumes ready.[/red]\n"
                "Run [bold]applypilot run score tailor[/bold] first to prepare applications."
            )
            raise typer.Exit(code=1)

    if gen:
        from applypilot.apply.launcher import gen_prompt, BASE_CDP_PORT
        target = url or ""
        if not target:
            console.print("[red]--gen requires --url to specify which job.[/red]")
            raise typer.Exit(code=1)
        prompt_file = gen_prompt(target, min_score=min_score, model=model)
        if not prompt_file:
            console.print("[red]No matching job found for that URL.[/red]")
            raise typer.Exit(code=1)
        mcp_path = _profile_path.parent / ".mcp-apply-0.json"
        console.print(f"[green]Wrote prompt to:[/green] {prompt_file}")
        console.print(f"\n[bold]Run manually:[/bold]")
        console.print(
            f"  claude --model {model} -p "
            f"--mcp-config {mcp_path} "
            f"--permission-mode bypassPermissions < {prompt_file}"
        )
        return

    from applypilot.apply.launcher import main as apply_main

    effective_limit = limit if limit is not None else (0 if continuous else 1)

    console.print("\n[bold blue]Launching Auto-Apply[/bold blue]")
    console.print(f"  Limit:    {'unlimited' if continuous else effective_limit}")
    console.print(f"  Workers:  {workers}")
    console.print(f"  Model:    {model}")
    console.print(f"  Headless: {headless}")
    console.print(f"  Dry run:  {dry_run}")
    if url:
        console.print(f"  Target:   {url}")
    if session_id:
        console.print(f"  Session:  {session_id}")
    console.print()

    apply_main(
        limit=effective_limit,
        target_url=url,
        min_score=min_score,
        headless=headless,
        model=model,
        dry_run=dry_run,
        continuous=continuous,
        workers=workers,
        session_id=session_id,
    )


@app.command()
def google_auth() -> None:
    """Run the Google Workspace OAuth2 flow to authorize Drive/Gmail access."""
    console.print("\n[bold blue]Google Workspace Authorization[/bold blue]")
    try:
        creds = _get_google_creds()
        console.print("[green]Successfully authorized![/green]")
        console.print(f"Token saved to: [dim]~/.applypilot/google_token.json[/dim]\n")
    except Exception as e:
        console.print(f"[red]Authorization failed:[/red] {e}")
        raise typer.Exit(code=1)


@app.command()
def tailor(
    urls: list[str] = typer.Argument(..., help="List of job URLs to tailor for."),
    resume: Optional[str] = typer.Option(None, "--resume", "-r", help="Resume path or Google Drive file ID/name."),
    out: Optional[Path] = typer.Option(None, "--out", "-o", help="Output directory for tailored resumes."),
    gdoc: bool = typer.Option(False, "--gdoc", help="Upload tailored .txt outputs to Google Drive as Google Docs."),
    drive_folder_id: Optional[str] = typer.Option(None, "--drive-folder-id", help="Google Drive folder ID for uploaded files."),
) -> None:
    """Standalone tailoring: generate tailored resumes for specific URLs."""
    _bootstrap()
    
    from applypilot.tools.tailor_standalone import StandaloneTailor
    from pathlib import Path
    
    resume_path = None
    if resume:
        # Check if local file
        if Path(resume).exists():
            resume_path = Path(resume)
        else:
            # Try Google Drive
            console.print(f"  [cyan]Fetching master resume from Google Drive:[/cyan] {resume}")
            try:
                # Resolve ID or Name
                file_id = resume
                if not re.match(r"^[a-zA-Z0-9-_]{25,}$", resume):
                    # Looks like a name, try to find it
                    found = _drive_find(resume)
                    if found:
                        file_id = found["id"]
                        console.print(f"  [dim]Found file ID: {file_id}[/dim]")
                    else:
                        console.print(f"[red]Could not find file '{resume}' on Google Drive.[/red]")
                        raise typer.Exit(code=1)
                
                from applypilot.config import CONFIG_DIR
                dest = CONFIG_DIR / "resume_drive.txt"
                resume_path = _drive_download(file_id, dest)
                console.print(f"  [green]Downloaded to {resume_path}[/green]")
            except Exception as e:
                console.print(f"[red]Google Drive error:[/red] {e}")
                console.print("Make sure you ran [bold]applypilot google-auth[/bold] first.")
                raise typer.Exit(code=1)

    runner = StandaloneTailor(out_dir=out, resume_path=resume_path)
    out_dir = runner.run(urls)

    if gdoc:
        txt_files = sorted(Path(out_dir).glob("*.txt"))
        if not txt_files:
            console.print("[yellow]No tailored .txt outputs found to upload.[/yellow]")
            return

        console.print(f"  [cyan]Uploading {len(txt_files)} file(s) to Google Drive as Docs...[/cyan]")
        uploaded = 0
        for txt in txt_files:
            try:
                _drive_upload(txt, folder_id=drive_folder_id, as_google_doc=True)
                uploaded += 1
            except Exception as e:
                console.print(f"[yellow]Upload failed for {txt.name}:[/yellow] {e}")

        console.print(f"  [green]Uploaded {uploaded}/{len(txt_files)} as Google Docs.[/green]")


@app.command()
def status() -> None:
    """Show pipeline statistics from the database."""
    _bootstrap()

    from applypilot.database import get_stats

    stats = get_stats()

    console.print("\n[bold]ApplyPilot Pipeline Status[/bold]\n")

    # Summary table
    summary = Table(title="Pipeline Overview", show_header=True, header_style="bold cyan")
    summary.add_column("Metric", style="bold")
    summary.add_column("Count", justify="right")

    summary.add_row("Total jobs discovered", str(stats["total"]))
    summary.add_row("With full description", str(stats["with_description"]))
    summary.add_row("Pending enrichment", str(stats["pending_detail"]))
    summary.add_row("Enrichment errors", str(stats["detail_errors"]))
    summary.add_row("Scored by LLM", str(stats["scored"]))
    summary.add_row("Pending scoring", str(stats["unscored"]))
    summary.add_row("Tailored resumes", str(stats["tailored"]))
    summary.add_row("Pending tailoring (7+)", str(stats["untailored_eligible"]))
    summary.add_row("Cover letters", str(stats["with_cover_letter"]))
    summary.add_row("Ready to apply", str(stats["ready_to_apply"]))
    summary.add_row("Applied", str(stats["applied"]))
    summary.add_row("Apply errors", str(stats["apply_errors"]))

    console.print(summary)

    # Score distribution
    if stats["score_distribution"]:
        dist_table = Table(title="\nScore Distribution", show_header=True, header_style="bold yellow")
        dist_table.add_column("Score", justify="center")
        dist_table.add_column("Count", justify="right")
        dist_table.add_column("Bar")

        max_count = max(count for _, count in stats["score_distribution"]) or 1
        for score, count in stats["score_distribution"]:
            bar_len = int(count / max_count * 30)
            if score >= 7:
                color = "green"
            elif score >= 5:
                color = "yellow"
            else:
                color = "red"
            bar = f"[{color}]{'=' * bar_len}[/{color}]"
            dist_table.add_row(str(score), str(count), bar)

        console.print(dist_table)

    # By site
    if stats["by_site"]:
        site_table = Table(title="\nJobs by Source", show_header=True, header_style="bold magenta")
        site_table.add_column("Site")
        site_table.add_column("Count", justify="right")

        for site, count in stats["by_site"]:
            site_table.add_row(site or "Unknown", str(count))

        console.print(site_table)

    console.print()


@app.command()
def dashboard() -> None:
    """Generate and open the HTML dashboard in your browser."""
    _bootstrap()

    from applypilot.view import open_dashboard

    open_dashboard()


@app.command("tailor-doc")
def tailor_doc(
    template_doc_id: str = typer.Option(..., "--template-doc-id", help="Google Doc template ID containing placeholders like {{SUMMARY}}."),
    tailored_txt: Path = typer.Option(..., "--tailored-txt", help="Path to tailored resume .txt output."),
    output_name: Optional[str] = typer.Option(None, "--output-name", help="Name for the generated Google Doc."),
    pdf_out: Optional[Path] = typer.Option(None, "--pdf-out", help="Local PDF output path."),
    drive_folder_id: Optional[str] = typer.Option(None, "--drive-folder-id", help="Drive folder for the generated Google Doc."),
) -> None:
    """Fill a Google Doc template from tailored text and export PDF for human review."""
    _bootstrap()
    from applypilot.tools.doc_template import render_template_to_doc_and_pdf

    if not tailored_txt.exists():
        console.print(f"[red]Tailored text not found:[/red] {tailored_txt}")
        raise typer.Exit(code=1)

    final_name = output_name or tailored_txt.stem
    final_pdf = pdf_out or (Path.cwd() / f"{final_name}.pdf")

    try:
        doc_id, pdf_path = render_template_to_doc_and_pdf(
            template_doc_id=template_doc_id,
            tailored_txt_path=tailored_txt,
            output_doc_name=final_name,
            output_pdf_path=final_pdf,
            drive_folder_id=drive_folder_id,
        )
    except Exception as e:
        console.print(f"[red]Template render failed:[/red] {e}")
        raise typer.Exit(code=1)

    console.print("[green]Template render complete.[/green]")
    console.print(f"Google Doc: https://docs.google.com/document/d/{doc_id}/edit")
    console.print(f"PDF: {pdf_path}")


if __name__ == "__main__":
    app()
