"""Standalone Tailoring logic: Job URLs -> Tailored Resumes/PDFs."""

import logging
import re
import time
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn

from applypilot.config import CONFIG_DIR, load_profile, load_env, TAILORED_DIR
from applypilot.enrichment.detail import scrape_detail_page
from applypilot.scoring.tailor import tailor_resume
from applypilot.scoring.pdf import convert_to_pdf
from applypilot.llm import get_client

from playwright.sync_api import sync_playwright

log = logging.getLogger(__name__)
console = Console()

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

class StandaloneTailor:
    """Standalone tailoring runner."""
    def __init__(self, out_dir: Path | None = None, resume_path: Path | None = None):
        load_env()
        self.profile = load_profile()
        self.out_dir = out_dir or (TAILORED_DIR / f"standalone_{int(time.time())}")
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.resume_path = resume_path or (CONFIG_DIR / "resume.txt")
        self.resume_text = self.resume_path.read_text(encoding="utf-8")
        
    def run(self, inputs: list[str | dict]):
        """Run the tailoring flow for a list of URLs or pre-parsed job dicts."""
        console.print(f"  [bold cyan]Starting Standalone Tailor[/bold cyan] for {len(inputs)} job(s)")
        console.print(f"  Output folder: [dim]{self.out_dir}[/dim]\n")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=UA)
            page = context.new_page()
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                overall_task = progress.add_task("[cyan]Processing job(s)...", total=len(inputs))
                
                for item in inputs:
                    try:
                        if isinstance(item, str):
                            url_str = item
                            progress.update(overall_task, description=f"[cyan]Scraping[/cyan] {url_str[:40]}...")
                            result = scrape_detail_page(page, url_str)
                            if result["status"] not in ("ok", "partial"):
                                progress.print(f"  [red]FAILED SCRAPE:[/red] {url_str} - {result.get('error')}")
                                continue

                            job = {
                                "url": url_str,
                                "title": str(result.get("title") or "Unknown Position"),
                                "site": str(result.get("site") or "Direct Site"),
                                "location": result.get("location") or "Unknown",
                                "full_description": result.get("full_description"),
                            }
                        else:
                            job = item
                            url_str = job.get("url", "local_file")

                        job_title = str(job.get("title") or "Unknown Position")
                        job_site = str(job.get("site") or "Direct Site")

                        # If title wasn't extracted by scraper, use page title as fallback.
                        if (not job_title or job_title == "Unknown Position") and isinstance(item, str):
                            job_title = str(page.title() or "Unknown Position")
                            job["title"] = job_title

                        safe_title = re.sub(r"[^\w\s-]", "", job_title)[:50].strip().replace(" ", "_")
                        safe_site = re.sub(r"[^\w\s-]", "", job_site)[:20].strip().replace(" ", "_")
                        prefix = f"{safe_site}_{safe_title}"

                        progress.update(overall_task, description=f"[cyan]Tailoring[/cyan] {job_title[:30]}...")
                        tailored_text, report = tailor_resume(self.resume_text, job, self.profile)

                        txt_path = self.out_dir / f"{prefix}.txt"
                        txt_path.write_text(tailored_text, encoding="utf-8")

                        if report["status"] == "approved":
                            progress.update(overall_task, description="[cyan]Converting to PDF[/cyan]...")
                            try:
                                convert_to_pdf(txt_path)
                            except Exception as e:
                                progress.print(f"  [yellow]PDF generation error:[/yellow] {e}")

                        progress.print(f"  [green]DONE:[/green] {job['title']} ([dim]{prefix}[/dim])")
                    except Exception as e:
                        progress.print(f"  [red]ERROR:[/red] {item} - {e}")
                    finally:
                        progress.advance(overall_task)
                    
            browser.close()
            
        console.print(f"\n  [bold green]Success![/bold green] All files are in: {self.out_dir}\n")
        return self.out_dir
