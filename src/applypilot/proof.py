"""Proof/review system for bridge-tailored resumes.

Shows side-by-side comparison of original vs tailored resume,
job description context, diff stats, and refinement details.
"""

import json
import logging
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from applypilot.config import APP_DIR

log = logging.getLogger(__name__)
console = Console()

PROOF_DIR = APP_DIR / "proof_reports"


def list_proofs(limit: int = 20) -> list[dict]:
    """List available proof reports, newest first."""
    if not PROOF_DIR.exists():
        return []

    reports = []
    for f in sorted(PROOF_DIR.glob("*_proof.json"), reverse=True)[:limit]:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            data["_file"] = str(f)
            data["_filename"] = f.name
            reports.append(data)
        except (json.JSONDecodeError, OSError):
            continue
    return reports


def show_proof_list(limit: int = 20) -> None:
    """Display a table of all proof reports."""
    reports = list_proofs(limit)

    if not reports:
        console.print("[yellow]No proof reports found.[/yellow]")
        console.print("Run [bold]applypilot bridge[/bold] first to tailor jobs via Resume-Matcher.")
        return

    table = Table(
        title=f"Proof Reports ({len(reports)} found)",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("#", style="dim", width=3)
    table.add_column("Score", justify="center", width=5)
    table.add_column("Company", width=20)
    table.add_column("Title", width=35)
    table.add_column("Changes", justify="right", width=8)
    table.add_column("Skills+", justify="right", width=7)
    table.add_column("Skills-", justify="right", width=7)
    table.add_column("KW Match", justify="right", width=9)
    table.add_column("AI Removed", justify="right", width=10)
    table.add_column("Date", width=10)

    for i, r in enumerate(reports):
        diff = r.get("diff_summary") or {}
        stats = r.get("refinement_stats") or {}
        tailored_at = (r.get("tailored_at") or "")[:10]

        kw_match = ""
        init_pct = stats.get("initial_match_percentage")
        final_pct = stats.get("final_match_percentage")
        if init_pct is not None and final_pct is not None:
            kw_match = f"{int(init_pct)}→{int(final_pct)}%"

        ai_removed = len(stats.get("ai_phrases_removed", []))

        table.add_row(
            str(i + 1),
            str(r.get("fit_score", "?")),
            (r.get("company") or "?")[:20],
            (r.get("title") or "?")[:35],
            str(diff.get("total_changes", "?")),
            str(diff.get("skills_added", "?")),
            str(diff.get("skills_removed", "?")),
            kw_match,
            str(ai_removed),
            tailored_at,
        )

    console.print(table)
    console.print(f"\nView details: [bold]applypilot proof --show 1[/bold]")


def show_proof_detail(index: int) -> None:
    """Show detailed proof report for a specific job."""
    reports = list_proofs(100)

    if not reports:
        console.print("[yellow]No proof reports found.[/yellow]")
        return

    if index < 1 or index > len(reports):
        console.print(f"[red]Invalid index {index}. Valid range: 1-{len(reports)}[/red]")
        return

    r = reports[index - 1]

    # Header
    console.print()
    console.print(Panel(
        f"[bold]{r.get('title', '?')}[/bold] @ {r.get('company', '?')}\n"
        f"Score: {r.get('fit_score', '?')} | {r.get('application_url', 'no URL')}",
        title="Proof Report",
        border_style="blue",
    ))

    # Score reasoning
    if r.get("score_reasoning"):
        console.print(Panel(r["score_reasoning"], title="Score Reasoning", border_style="dim"))

    # Job Description (truncated)
    jd = r.get("job_description", "")
    if jd:
        jd_display = jd[:1500] + ("..." if len(jd) > 1500 else "")
        console.print(Panel(jd_display, title="Job Description (truncated)", border_style="yellow"))

    # Diff Summary
    diff = r.get("diff_summary")
    if diff:
        diff_table = Table(title="Diff Summary", show_header=True, header_style="bold green")
        diff_table.add_column("Metric")
        diff_table.add_column("Value", justify="right")
        diff_table.add_row("Total changes", str(diff.get("total_changes", 0)))
        diff_table.add_row("Skills added", str(diff.get("skills_added", 0)))
        diff_table.add_row("Skills removed", str(diff.get("skills_removed", 0)))
        diff_table.add_row("Descriptions modified", str(diff.get("descriptions_modified", 0)))
        diff_table.add_row("Certifications added", str(diff.get("certifications_added", 0)))
        diff_table.add_row("[bold red]High-risk changes[/bold red]", str(diff.get("high_risk_changes", 0)))
        console.print(diff_table)

    # Refinement Stats
    stats = r.get("refinement_stats")
    if stats:
        ref_table = Table(title="Refinement Stats", show_header=True, header_style="bold magenta")
        ref_table.add_column("Metric")
        ref_table.add_column("Value", justify="right")
        ref_table.add_row("Passes completed", str(stats.get("passes_completed", 0)))
        ref_table.add_row("Keywords injected", str(stats.get("keywords_injected", 0)))
        ref_table.add_row("Alignment violations fixed", str(stats.get("alignment_violations_fixed", 0)))
        init_pct = stats.get("initial_match_percentage", 0)
        final_pct = stats.get("final_match_percentage", 0)
        ref_table.add_row("Keyword match", f"{int(init_pct)}% → {int(final_pct)}%")

        ai_phrases = stats.get("ai_phrases_removed", [])
        if ai_phrases:
            ref_table.add_row("AI phrases removed", ", ".join(ai_phrases))

        console.print(ref_table)

    # Detailed changes
    changes = r.get("detailed_changes")
    if changes:
        console.print(Panel.fit("[bold]Detailed Changes[/bold]", border_style="cyan"))
        for change in changes[:20]:
            field = change.get("field_path", change.get("field", "?"))
            change_type = change.get("change_type", "?")
            confidence = change.get("confidence", "")
            old_val = change.get("original_value", change.get("old_value", ""))
            new_val = change.get("new_value", "")
            conf_tag = f" [dim]({confidence})[/dim]" if confidence else ""

            if change_type == "modified":
                console.print(f"  [yellow]~[/yellow] {field}{conf_tag}")
                if old_val and new_val and str(old_val) != str(new_val):
                    console.print(f"    [red]- {_truncate(str(old_val), 120)}[/red]")
                    console.print(f"    [green]+ {_truncate(str(new_val), 120)}[/green]")
            elif change_type == "added":
                console.print(f"  [green]+[/green] {field}: {_truncate(str(new_val), 120)}{conf_tag}")
            elif change_type == "removed":
                console.print(f"  [red]-[/red] {field}: {_truncate(str(old_val), 120)}{conf_tag}")

    # Improvements / suggestions
    improvements = r.get("improvements")
    if improvements:
        console.print(Panel.fit("[bold]Improvement Suggestions[/bold]", border_style="green"))
        for imp in improvements[:10]:
            section = imp.get("section", "")
            suggestion = imp.get("suggestion", imp.get("description", ""))
            console.print(f"  [{section}] {_truncate(str(suggestion), 150)}")

    # Warnings
    warnings = r.get("warnings")
    if warnings:
        for w in warnings:
            console.print(f"  [yellow]⚠ {w}[/yellow]")

    # Original vs Tailored side-by-side summary
    orig = r.get("original_markdown")
    tailored = r.get("tailored_markdown")
    tailored_struct = r.get("tailored_structured")

    if orig:
        orig_lines = len(orig.splitlines())
        console.print(f"\n  Original resume: {orig_lines} lines")
    if tailored:
        tailored_lines = len(tailored.splitlines())
        console.print(f"  Tailored resume: {tailored_lines} lines")
    elif tailored_struct:
        console.print(f"  Tailored resume: structured JSON (use --full to see)")

    # Cover letter
    cl = r.get("cover_letter")
    if cl:
        console.print(Panel(cl, title="Cover Letter", border_style="green"))

    console.print()


def show_proof_full(index: int) -> None:
    """Show the full original vs tailored resume text."""
    reports = list_proofs(100)
    if index < 1 or index > len(reports):
        console.print(f"[red]Invalid index. Valid: 1-{len(reports)}[/red]")
        return

    r = reports[index - 1]

    console.print(Panel(
        f"[bold]{r.get('title', '?')}[/bold] @ {r.get('company', '?')}",
        title="Full Resume Comparison",
        border_style="blue",
    ))

    orig = r.get("original_markdown")
    if orig:
        console.print(Panel(orig[:3000], title="ORIGINAL Resume", border_style="red"))

    tailored = r.get("tailored_markdown")
    tailored_struct = r.get("tailored_structured")
    if tailored:
        console.print(Panel(tailored[:3000], title="TAILORED Resume", border_style="green"))
    elif tailored_struct:
        from applypilot.bridge import _resume_to_text
        text = _resume_to_text(tailored_struct)
        console.print(Panel(text[:3000], title="TAILORED Resume (from structured)", border_style="green"))

    console.print()


def _truncate(text: str, max_len: int = 120) -> str:
    """Truncate text with ellipsis."""
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."
