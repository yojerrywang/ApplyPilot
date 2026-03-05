# Backlog

## P0 (Next)
- Add robust LinkedIn job-description fallback for standalone `tailor` when scrape fails (accept pasted JD text/file as direct input).
- Add provider fallback chain in runtime (`openai -> gemini -> local`) when 429/5xx occurs.
- Add secret hygiene guardrails:
  - redact API keys in logs/console
  - refuse committing env/token/credentials files
  - document key rotation workflow.

## P1
- Add batch URL UX for standalone mode with per-job status report (`queued/ok/failed`) and retry list output.
- Add `tailor-doc` direct pipeline mode (`--from-tailor-out DIR`) to auto-render every tailored txt into doc+pdf.
- Add optional Drive folder auto-creation by date/company.

## P2
- Add Gmail draft creation command for follow-up emails tied to generated resumes.
- Add Calendar follow-up reminder command (5-7 day post-apply reminders).
- Add resume quality metrics report (keyword coverage, section length, banned phrase score).

### ✅ Unify location filter schema across pipeline (P0)
- Support one canonical schema (`get_location_preferences()`) and maintain backward compatibility for `location_reject_non_remote` as either list or bool.

### ✅ Enforce `exclude_titles` during discovery (P0)
- Apply case-insensitive title filtering in discovery ingestion paths to actively discard unwanted jobs before database insertion.

### ✅ Expose Session ID filtering in CLI (P1)
- Allow users to specifically target jobs discovered in a specific run via `applypilot run/apply/status --session-id`.

### ✅ Scope Session ID across downstream pipeline stages (P1)
- Ensure `applypilot run --session-id` scopes `enrich`, `score`, `tailor`, and `cover` stage execution in sequential and streaming modes.
- Ensure pending-work polling and run summary stats respect the same session scope.

### ✅ Fix targeted apply URL acquisition for fresh jobs (P0)
- Ensure `applypilot apply --url URL` can acquire jobs with `apply_status = NULL` (fresh, never-attempted rows).

### ✅ Correct semantic dedupe identity to company + title (P1)
- Persist `company` in the jobs schema and discovery ingestors.
- Deduplicate by normalized `company + title` (fallback to `site` when company is missing), prioritized by highest fit score and recency.

## Completed (operational-hardening-suite)

### ✅ Add filter transparency in status/dashboard (P2 #5)
- Added persisted counters for `filtered_by_location`, `filtered_by_title`, and `deduped`.
- Surfaced counters in `applypilot status` and HTML dashboard.

### ✅ Add `applypilot doctor` for config validation (P2 #6)
- Added doctor command covering profile/search/env schema validation, blocked-pattern sanity checks, and runtime readiness probes.
- Fails fast on hard errors and prints actionable remediation guidance.

### ✅ Recover stale apply locks
- Added stale `in_progress` recovery in the apply launcher with configurable timeout (`stale_lock_minutes`).
- Added tests validating stale-lock recovery and automatic reacquisition flow.

### ✅ Expand E2E regression coverage
- Added end-to-end tests for `run --stream`, `apply --url` targeting, and failed→retry→applied lifecycle.

### ✅ CI branch gating artifact
- Added `required-checks` CI gate job and branch-protection baseline docs for `dev` + `main`.

### ✅ Track isolation via `APPLYPILOT_DIR` (MVP)
- CLI/runtime already support `APPLYPILOT_DIR` so each role can run with isolated `profile.json`, `searches.yaml`, logs, and SQLite DB.
- Daily harness uses this pattern to run isolated track directories (for example, `~/.applypilot_pm`, `~/.applypilot_swe`).

## P1 — Pipeline Efficiency and Cost Controls

### 3) Keep broad discovery, then cheap filters before expensive LLM stages
- Goal: Preserve and harden pipeline ordering: discover → dedupe → enrich → score → tailor/cover → apply.
- Scope:
  - Ensure dedupe always runs before enrich/score in all execution modes.
  - Add a guardrail test for stage ordering.
  - Add optional caps (e.g., max jobs per run) before scoring.
- Acceptance criteria:
  - No LLM stages execute on jobs excluded by dedupe/filters.
  - Stage-order tests pass in sequential + streaming modes.

## Epic 5 — Multi-Track Autonomous Job-Hunting Agent Loop

### 11) Master Fact Bank Intake Flow (P1)
- Goal: Create an onboarding/intake loop to build the canonical `master_facts.json` instead of a flat profile.
- Scope:
  - Enhance parsing to extract hard facts (metrics, tools, dates) vs soft claims.
  - Implement initial probing questions to the user for missing metrics (e.g., "You mentioned AWS, what was the monthly spend?").
- Acceptance criteria:
  - `applypilot init` (or a dedicated `ingest` command) generates a highly structured `master_facts.json` containing immutable facts.

### 12) Native Role-Track Schema & DB Plumbing (P0)
- Goal: Move from env-var pseudo-tracks to first-class in-app role tracks.
- Scope:
  - Define `role_tracks.yaml` (tracks, include/exclude titles, budgets, scoring thresholds).
  - Update jobs table schema to persist `role_track` on discovered/scored/tailored rows.
  - Add CLI/runtime selection so runs can target one or more tracks without duplicating directories.
- Acceptance criteria:
  - Jobs are stamped with `role_track` and visible in status/dashboard queries.
  - Runs can be scoped by track without requiring separate home directories.

### 13) Track-Aware Discovery & Scoring (P0)
- Goal: Route jobs into their respective tracks and filter out noise cheaply.
- Scope:
  - Update discovery to partition incoming jobs by track.
  - Score in two passes: cheap rule filter first, then LLM scoring only on survivors within the track quota.
- Acceptance criteria:
  - Discovery output cleanly isolates into configured tracks.
  - A track with a quota of N only passes N jobs to the expensive LLM tailor stage.

### 14) Track Budget Policies & Throttle Configs (P0)
- Goal: Treat application matching as a paid performance channel with strict ROI controls.
- Scope:
  - Add native Python limits for daily throughput per track (e.g., `score_budget: 300`, `tailor_budget: 15`).
  - Add logic to halt/pause tracks if 21-day lagging interview conversion drops below a threshold.
  - Explore Batch API for scoring and tailoring to instantly drop token costs by 50%.
- Acceptance criteria:
  - You can configure a hard $15/week spending cap by limiting maximum jobs scored and tailored per day, and the engine correctly stops processing when the cap is hit.

### 15) Resume Quality Gates & Claim-to-Evidence Validation (P0)
- Goal: Block "usable but weak" resumes from being automatically applied to preserve interview conversion rates.
- Scope:
  - Enforce strict resume header structure (Full name, proper contact info).
  - Enforce minimum keyword matching (e.g., must hit 6-10 JD keywords).
  - Enforce quantification (e.g., at least 5 bullets must contain a numeric metric).
  - Implement Claim-to-Evidence mapping in tailor prompts to prevent hallucinated projects/skills.
  - Fail closed: if validation fails, discard the tailored resume and block application.
- Acceptance criteria:
  - The pipeline intentionally crashes/discards a payload if the resume lacks metrics, has a broken header, or hallucinates skills.

## P3 — Quality, DX and Dependencies

### 7) Harden init/config flow
- Goal: Fewer failed runs due to missing or invalid config.
- Scope:
  - Validate `profile.json`, `searches.yaml`, and `.env` (required keys, types, non-empty where needed).
  - Provide clear error messages and, where possible, defaults or remediation hints.
  - Consider `applypilot doctor` (see P2) to run these checks on demand.
- Acceptance criteria:
  - Invalid or incomplete setup is caught early with actionable messages.

### 8) Observability: logging and verbose mode
- Goal: Make discovery, scoring, and apply stages debuggable without reading code.
- Scope:
  - Add structured logging (or a single `--verbose` flag) for key stages: discovery counts per source, score distribution, apply success/fail reasons.
  - Ensure logs don’t leak PII or API keys.
- Acceptance criteria:
  - Users and contributors can trace why jobs were included, scored, or skipped.

### 9) Tests for core pipeline logic
- Goal: Protect refactors and build confidence in scoring, tailoring, and dedupe.
- Scope:
  - Unit or integration tests for: dedupe semantics, score threshold behavior, tailor output structure (e.g. resume_facts preserved).
  - Tests can use fixtures or small canned jobs/profiles.
- Acceptance criteria:
  - CI runs tests; critical path changes are covered.

### 10) JobSpy / dependency story
- Goal: Reduce install friction and confusion.
- Scope:
  - Document the current `--no-deps` + manual jobspy (and runtime deps) flow in an Install or Troubleshooting section.
  - Investigate upstream fix or optional extra (e.g. `pip install applypilot[jobspy]`) so one command works where possible.
- Acceptance criteria:
  - Install instructions are clear; medium-term path to simpler install is documented or implemented.

## Epic 6 — Telemetry, API-First Apply & Churn Management (SaaS Milestones)

### 16) Inbox Telemetry Scanner / Webhook (P0)
- Goal: Close the telemetry gap for the `Callback Rate` and `Interview Rate` metrics.
- Scope:
  - Build a secure script (or extension proxy) to scan the authenticated Gmail/Outlook inbox for recruiter responses tied to jobs in the database.
  - Automatically update `jobs.interview_status` without manual user reporting.
- Acceptance criteria:
  - The pipeline can definitively prove 100% of the callbacks generated without the user having to log into a dashboard.

### 17) API-First Apply Engine (Greenhouse/Lever) (P1)
- Goal: Stop burning $119/week on cloud Playwright compute for standard SaaS users.
- Scope:
  - Reverse-engineer standard Greenhouse/Lever POST endpoints.
  - Bypass Playwright GUI flows entirely for 80% of jobs; submit JSON directly.
  - Only route jobs to the Playwright Claude Code fallback if the API fails or the form is complex (e.g., Workday).
- Acceptance criteria:
  - Apply latency drops from 60 seconds/job to 2 seconds/job for Greenhouse links.
  - Cloud server resources drop significantly.

### 18) Alumni Mode Tracker ($5/mo Segment) (P2)
- Goal: Monetize churn when a user successfully gets hired.
- Scope:
  - Add `is_alumni_mode` flag to user tenant/profile.
  - Discovery script runs weekly instead of daily.
  - Score jobs but skip `tailor` and `apply` completely.
  - Fire a single summary email with the top 3 high-paying jobs.
- Acceptance criteria:
  - Alumni users consume < 5% of standard LLM tokens but remain active in the system.

## Epic 7 — SaaS Platform Foundation (Phase 4)

### 19) Tenant Auth & Access Model (P0)
- Goal: Introduce account-level isolation required for hosted multi-user operation.
- Scope:
  - Add users, tenants, memberships, and session/auth tables.
  - Enforce tenant scoping in all read/write paths.
- Acceptance criteria:
  - Cross-tenant data access is blocked by default and validated in tests.

### 20) Hosted Database Migration (P0)
- Goal: Replace single-user local SQLite as the system of record for SaaS mode.
- Scope:
  - Define Postgres schema and migration path from local SQLite.
  - Add migration tooling and rollback-safe rollout process.
- Acceptance criteria:
  - Hosted environment runs end-to-end on Postgres with tenant-safe queries.

### 21) Billing, Plans, and Entitlements (P0)
- Goal: Enforce weekly plans and usage-based overage in product.
- Scope:
  - Integrate billing provider for subscriptions, payment state, and webhooks.
  - Map plan entitlements (tracks, submissions, support level) into runtime checks.
- Acceptance criteria:
  - Plan limits and overage billing are enforced automatically before run execution.

### 22) Usage Metering and Budget Kill-Switches (P0)
- Goal: Keep contribution margin healthy under heavy usage.
- Scope:
  - Meter per-tenant scoring/tailoring/apply usage and estimated cost.
  - Add daily/weekly budget guardrails with pause/stop controls.
- Acceptance criteria:
  - Runs stop or throttle when tenant budget thresholds are exceeded, with clear audit logs.

## Notes
- Prioritize P0 items first; they directly address current filtering confusion and wasted downstream compute.
- Keep changes backward-compatible where possible to avoid breaking existing user configs.

## Testing Backlog
- Unit tests for `doc_template.py` parsing + placeholder mapping.
- Integration test for Drive copy -> Docs replace -> PDF export path.
- Regression test for `llm.py` provider detection with env loaded after import.
- Regression test for Google Docs download/export in `download_file()`.
