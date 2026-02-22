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

## P2 — Observability and UX

### 5) Add filter transparency in status/dashboard
- Goal: Make filtering decisions visible.
- Scope:
  - Add counters for `filtered_by_location`, `filtered_by_title`, and `deduped`.
  - Surface counters in `status` and dashboard.
- Acceptance criteria:
  - Users can explain why discovered jobs did or did not progress.

### 6) Add `applypilot doctor` for config validation
- Goal: Validate env/config before long runs.
- Scope:
  - Check required keys, conflicting schema usage, and malformed patterns.
  - Print actionable fixes.
- Acceptance criteria:
  - Invalid setup is detected up-front with clear remediation.

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

## Notes
- Prioritize P0 items first; they directly address current filtering confusion and wasted downstream compute.
- Keep changes backward-compatible where possible to avoid breaking existing user configs.
