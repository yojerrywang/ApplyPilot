"""Hiring.Cafe job discovery via Playwright interception.

Hiring.Cafe has strict anti-bot protections (Cloudflare 405/429) for standard API
requests. This module uses Playwright to launch a headless browser, navigate to
the site, and intercept the raw JSON API responses to bypass these protections.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
import urllib.parse

from playwright.async_api import async_playwright

from applypilot.config import load_search_config
from applypilot.database import get_connection, store_jobs

log = logging.getLogger(__name__)


async def _run_search(
    page,
    query: str,
    remote_only: bool,
    hours_old: int,
) -> list[dict]:
    """Execute a single search query on Hiring.Cafe and intercept the results."""
    jobs_collected = []
    
    # We will hook into the response event to catch the API data
    async def handle_response(response):
        if "api/search-jobs" in response.url and response.request.method == "POST":
            try:
                data = await response.json()
                if isinstance(data, dict):
                    # Check for results/hits/jobs arrays
                    for key in ["results", "jobs", "data", "items"]:
                        if key in data and isinstance(data[key], list):
                            jobs_collected.extend(data[key])
                            return
                    if "hits" in data and isinstance(data["hits"], dict) and "hits" in data["hits"]:
                        jobs_collected.extend([h.get("_source", h) for h in data["hits"]["hits"]])
            except Exception as e:
                log.debug(f"Failed to parse hiring.cafe response from {response.url}: {e}")

    page.on("response", handle_response)
    
    # Construct search state query parameters
    # Hiring.cafe stores state in the URL search params encoded as JSON string
    days_old = max(1, min(61, hours_old // 24))
    
    search_state = {
        "searchQuery": query,
        "dateFetchedPastNDays": days_old,
    }
    
    if remote_only:
        search_state["workplaceTypes"] = ["Remote"]
        search_state["locations"] = []  # Remote overrides specific locations
        
    encoded_state = urllib.parse.quote(json.dumps(search_state))
    url = f"https://hiring.cafe/?searchState={encoded_state}"
    
    log.info(f"Navigating to Hiring.Cafe for query: '{query}'")
    
    try:
        # Go to the search URL directly with the encoded search state
        await page.goto(url, wait_until="networkidle")
        
        # Wait for the main job board to load and the API call to complete
        try:
            # Wait for either the search results container or the "no results" message
            await page.wait_for_selector('main, [class*="no-results"]', timeout=15000)
            # Give the background API requests a few more seconds to finish arriving
            await page.wait_for_timeout(3000)
        except Exception:
            log.warning(f"Timeout waiting for Hiring.cafe results for '{query}'. Site may be slow.")
            
    except Exception as e:
        log.error(f"Playwright navigation failed for '{query}': {e}")
        
    finally:
        # Remove the listener so it doesn't leak to the next search
        page.remove_listener("response", handle_response)
        
    return jobs_collected


def _map_job(raw_job: dict) -> dict | None:
    """Map a Hiring.Cafe JSON job object to the standard database schema."""
    try:
        title = raw_job.get("title") or raw_job.get("jobTitle")
        company = raw_job.get("companyName") or raw_job.get("company")
        url = raw_job.get("url") or raw_job.get("jobUrl")
        
        if not title or not company or not url:
            return None
            
        desc = raw_job.get("description", "")
        if not desc and "descriptionHtml" in raw_job:
            desc = raw_job["descriptionHtml"]
            
        # Parse compensation
        min_salary, max_salary = None, None
        curr = raw_job.get("currency", "USD")
        
        # Try minCompensationLowEnd/HighEnd first (standard hiring.cafe fields)
        if raw_job.get("minCompensationLowEnd"):
            min_salary = float(raw_job.get("minCompensationLowEnd"))
        if raw_job.get("maxCompensationHighEnd"):
            max_salary = float(raw_job.get("maxCompensationHighEnd"))
            
        # Try alternate "salary" nested object
        if raw_job.get("salary") and isinstance(raw_job["salary"], dict):
            s = raw_job["salary"]
            min_salary = float(s.get("min", s.get("low", min_salary)) or min_salary)
            max_salary = float(s.get("max", s.get("high", max_salary)) or max_salary)
            curr = s.get("currency", curr)

        # Work types
        remote = False
        workplace_types = raw_job.get("workplaceTypes", [])
        if "Remote" in workplace_types or ("remote" in str(raw_job.get("location", "")).lower()):
            remote = True
            
        # Format location
        locations = raw_job.get("locations", [])
        location_str = "Remote" if remote else ""
        if locations and isinstance(locations, list):
            loc_names = [l.get("formatted_address", "") for l in locations if isinstance(l, dict)]
            if loc_names:
                location_str = " | ".join(loc_names)
        elif raw_job.get("location"):
            location_str = str(raw_job.get("location"))

        now = datetime.now(timezone.utc).isoformat()
        
        return {
            "title": title,
            "company": company,
            "location": location_str,
            "url": url,
            "description": desc,
            "is_remote": remote,
            "min_salary": min_salary,
            "max_salary": max_salary,
            "currency": curr,
            "source": "hiring.cafe",
            "date_posted": raw_job.get("datePosted", raw_job.get("publishedAt", "")),
            "created_at": now,
        }
    except Exception as e:
        log.warning(f"Failed to map Hiring.Cafe job: {e}")
        return None


async def _crawl_async(queries: list[dict], remote_only: bool, hours_old: int) -> dict:
    """Run all searches asynchronously via Playwright."""
    stats = {"new": 0, "existing": 0}
    conn = get_connection()
    
    async with async_playwright() as p:
        # Launch with specific arguments that make headless chrome look more legit
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ]
        )
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            color_scheme="dark",
            locale="en-US",
            timezone_id="America/Los_Angeles",
        )
        
        # Add a realistic evasion script
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            })
        """)
        
        page = await context.new_page()
        
        for q in queries:
            query = q["query"]
            log.info(f"Hiring.Cafe search: '{query}'")
            
            raw_jobs = await _run_search(page, query, remote_only, hours_old)
            
            if not raw_jobs:
                log.info(f"  No jobs found for '{query}'")
                continue
                
            log.info(f"  Found {len(raw_jobs)} raw jobs")
            
            mapped_jobs = []
            for raw in raw_jobs:
                job = _map_job(raw)
                if job:
                    mapped_jobs.append(job)
                    
            if mapped_jobs:
                new, existing = store_jobs(conn, mapped_jobs)
                stats["new"] += new
                stats["existing"] += existing
                log.info(f"  Stored {new} new, {existing} existing.")
                
            # Random delay between searches to be polite
            await page.wait_for_timeout(2000)
            
        await browser.close()
        
    return stats


def run_discovery() -> dict:
    """Main entry point for Hiring.Cafe Playwright job discovery."""
    cfg = load_search_config()
    queries = cfg.get("queries", [])
    if not queries:
        log.warning("No search queries configured for Hiring.Cafe.")
        return {"new": 0, "existing": 0}

    # Extract defaults
    defaults = cfg.get("defaults", {})
    hours_old = defaults.get("hours_old", 72)
    
    # Are we exclusively searching remote?
    locations = cfg.get("locations", [])
    remote_only = len(locations) == 1 and locations[0].get("remote", False)
    
    stats = asyncio.run(_crawl_async(queries, remote_only, hours_old))
    
    log.info(f"Hiring.Cafe complete: {stats['new']} new, {stats['existing']} existing.")
    return stats
