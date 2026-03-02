# Changelog

All notable changes to ApplyPilot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Created `scripts/applypilot-daily.sh` MVP harness to execute pipeline concurrently across pseudo-tracks using `APPLYPILOT_DIR`.
- Enforced strict LLM token budgets in bash harness (`MAX_SCORE=400`, `--min-score 8`) to structurally cap API spend.
- Added YAML configuration sanity checking to bash harness to block runs if `results_per_site` exceeds 40.
- Drafted `docs/SAAS-PLAN-1M-ARR.md` outlining pricing, unit economics, and 90-day execution milestones.
- Formalized Epic 6 in `ROADMAP.md` and `BACKLOG.md` introducing Inbox Telemetry Scanning, an API-First apply engine switch, and the new $5/mo Alumni mode tracker.
- Architectural Epic 5 (Multi-Track Agent Loop) tickets added to `ROADMAP.md` and `BACKLOG.md` introducing strict resume quality gates (header verification, metric quotas, claim-to-evidence validation).
- Native `dedupe` pipeline stage to automatically remove semantic duplicate jobs (same title and company) prioritizing by fit score and recency. Run manually via `applypilot run dedupe`.
- Session ID tracking (`APPLYPILOT_SESSION_ID`) to group discovered jobs by run batch. Auto-generated via CLI or overrideable via environment variables.
- Custom AI coding assistant workflow instructions (`CLAUDE.md`, `.cursorrules`, `.agents/workflows/`) explicitly documented to enable smart automation triggers like `save atp`.
- OpenRouter local LLM integration for scoring phase with JSON validation and graceful retries.
- Comprehensive markdown `walkthrough.md` logic detailing pipeline execution strategies and anti-fabrication validator fixes.
- **Title exclusion enforcement**: Jobs matching `exclude_titles` from `searches.yaml` are actively discarded during discovery before database entry.
- `applypilot doctor` command to validate profile/search/env schema, blocked URL patterns, DB readiness, and Tier 2/3 runtime prerequisites before long runs.
- Persisted transparency counters (`filtered_by_location`, `filtered_by_title`, `deduped`) stored in SQLite and exposed to CLI/HTML reporting.
- Stale apply-lock recovery for rows stuck in `apply_status='in_progress'` beyond a configurable timeout (`stale_lock_minutes`).
- Expanded E2E regression coverage for `run --stream`, `apply --url`, and failure→retry→applied lifecycle.
- Branch governance artifacts: `.github/CODEOWNERS`, `.github/BRANCH_PROTECTION.md`, and `required-checks` CI gate job.

### Changed
- **LLM Provider Migration**: Switched default recommended inference from local Ollama to OpenRouter API (using `google/gemini-2.0-flash-exp:free` or similar models).
  - *Context:* The initial direct Gemini API implementation experienced instability, prompting a shift to local Ollama models (e.g., `gemma2:2b`, `deepseek-r1:32b`, `llama3.1:8b`). However, local edge models either failed strict JSON validation/anti-fabrication checks during the resume tailoring stage or were far too slow for the massive context size (entire resume + full job description). OpenRouter provides the speed and reliability of robust API models while circumventing direct provider limitations.
- **Session-scoped pipeline execution**: `applypilot run --session-id` now scopes downstream stages (`enrich`, `score`, `tailor`, `cover`) and pending-work polling to that batch in both sequential and streaming modes.
- **Session-scoped dedupe execution**: `dedupe` stage now accepts optional `session_id` scope in both sequential and streaming pipeline paths.
- **Dedupe identity correction**: Semantic dedupe now keys by normalized `company + title` (with fallback to `site` when company is unavailable) and the `jobs` schema now persists `company`.
- **Discovery ingestion consistency**: custom discovery inserters now persist `session_id`, aligning JobSpy/Workday/SmartExtract rows with batch-scoped downstream stages and stats.
- **Status/dashboard observability**: `applypilot status` and HTML dashboard now surface filter/dedupe transparency counters.

### Fixed
- **Location filter backward compatibility**: Fixed bug where legacy list-based `reject_non_remote` configurations were parsed incorrectly by discovery scrapers.
- **Discover stage session wiring**: Fixed `discover` stage invocation path to accept and propagate `session_id` correctly.
- **Target URL apply selection**: Fixed `applypilot apply --url` lookup to include jobs where `apply_status` is `NULL` (not only non-`in_progress` non-null statuses).
- **SmartExtract ingest path**: restored missing filtered-store helper wiring and config imports so location/title filtering and DB inserts run correctly.
- **Hiring.Cafe title filtering**: fixed excluded-title lookup path and added filtered-title metric tracking for discovered rows.

### Security
- Removed collection/storage of job-site account password from `applypilot init` profile flow.
- Removed plaintext password from auto-apply prompt instructions to reduce credential exposure.
- Parameterized blocked-site and blocked-pattern SQL filters in apply job acquisition to avoid config-driven query interpolation.
- Hardened local permissions on non-Windows systems: sensitive files (`.env`, `profile.json`) use `600`, app data directories use `700`.

## [0.2.0] - 2026-02-17

### Added
- **Parallel workers for discovery/enrichment** - `applypilot run --workers N` enables
  ThreadPoolExecutor-based parallelism for Workday scraping, smart extract, and detail
  enrichment. Default is sequential (1); power users can scale up.
- **Apply utility modes** - `--gen` (generate prompt for manual debugging), `--mark-applied`,
  `--mark-failed`, `--reset-failed` flags on `applypilot apply`
- **Dry-run mode** - `applypilot apply --dry-run` fills forms without clicking Submit
- **5 new tracking columns** - `agent_id`, `last_attempted_at`, `apply_duration_ms`,
  `apply_task_id`, `verification_confidence` for better apply-stage observability
- **Manual ATS detection** - `manual_ats` list in `config/sites.yaml` skips sites with
  unsolvable CAPTCHAs (e.g. TCS iBegin)
- **Qwen3 `/no_think` optimization** - automatically saves tokens when using Qwen models
- **`config.DEFAULTS`** - centralized dict for magic numbers (`min_score`, `max_apply_attempts`,
  `poll_interval`, `apply_timeout`, `viewport`)

### Fixed
- **Config YAML not found after install** - moved `config/` into the package at
  `src/applypilot/config/` so YAML files (employers, sites, searches) ship with `pip install`
- **Search config format mismatch** - wizard wrote `searches:` key but discovery code
  expected `queries:` with tier support. Aligned wizard output and example config
- **JobSpy install isolation** - removed python-jobspy from package dependencies due to
  broken numpy==1.26.3 exact pin in jobspy metadata. Installed separately with `--no-deps`
- **Scoring batch limit** - default limit of 50 silently left jobs unscored across runs.
  Changed to no limit (scores all pending jobs in one pass)
- **Missing logging output** - added `logging.basicConfig(INFO)` so per-job progress for
  scoring, tailoring, and cover letters is visible during pipeline runs

### Changed
- **Blocked sites externalized** - moved from hardcoded sets in launcher.py to
  `config/sites.yaml` under `blocked:` key
- **Site base URLs externalized** - moved from hardcoded dict in detail.py to
  `config/sites.yaml` under `base_urls:` key
- **SSO domains externalized** - moved from hardcoded list in prompt.py to
  `config/sites.yaml` under `blocked_sso:` key
- **Prompt improvements** - screening context uses `target_role` from profile,
  salary section includes `currency_conversion_note` and dynamic hourly rate examples
- **`acquire_job()` fixed** - writes `agent_id` and `last_attempted_at` to proper columns
  instead of misusing `apply_error`
- **`profile.example.json`** - added `currency_conversion_note` and `target_role` fields

## [0.1.0] - 2026-02-17

### Added
- 6-stage pipeline: discover, enrich, score, tailor, cover letter, apply
- Multi-source job discovery: Indeed, LinkedIn, Glassdoor, ZipRecruiter, Google Jobs
- Workday employer portal support (46 preconfigured employers)
- Direct career site scraping (28 preconfigured sites)
- 3-tier job description extraction cascade (JSON-LD, CSS selectors, AI fallback)
- AI-powered job scoring (1-10 fit scale with rationale)
- Resume tailoring with factual preservation (no fabrication)
- Cover letter generation per job
- Autonomous browser-based application submission via Playwright
- Interactive setup wizard (`applypilot init`)
- Cross-platform Chrome/Chromium detection (Windows, macOS, Linux)
- Multi-provider LLM support (Gemini, OpenAI, local models via OpenAI-compatible endpoints)
- Pipeline stats and HTML results dashboard
- YAML-based configuration for employers, career sites, and search queries
- Job deduplication across sources
- Configurable score threshold filtering
- Safety limits for maximum applications per run
- Detailed application results logging
