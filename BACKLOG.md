# Backlog

## Completed (security-hardening)

### ✅ Credential and local data hardening
- Removed password collection from setup profile flow.
- Removed plaintext password embedding from auto-apply prompt generation.
- Parameterized blocked-site and blocked-pattern SQL filtering in apply job acquisition.
- Tightened local file permissions for sensitive artifacts on non-Windows systems.

## Completed (P0 & P1)

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

### 12) Track Isolation via `APPLYPILOT_DIR` & DB Updates (P0)
- Goal: Support isolated pseudo-tracks immediately using environment variables, then native DB scaffolding.
- Scope:
  - Ensure the CLI and codebase respect an `APPLYPILOT_DIR` environment variable to completely isolate `profile.json`, `searches.yaml`, and the SQLite DB per role (e.g., `~/.applypilot_pm`).
  - Native Phase: Define `role_tracks.yaml` (tracks, include/exclude titles, budgets) and update jobs table schema to persist `role_track`.
- Acceptance criteria:
  - Running `APPLYPILOT_DIR=~/.applypilot_pm applypilot run` completely isolates the run from the default `~/.applypilot` directory.

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

## Notes
- Prioritize P0 items first; they directly address current filtering confusion and wasted downstream compute.
- Keep changes backward-compatible where possible to avoid breaking existing user configs.
