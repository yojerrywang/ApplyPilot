# Backlog

## Completed (security-hardening)

### ✅ Credential and local data hardening
- Removed password collection from setup profile flow.
- Removed plaintext password embedding from auto-apply prompt generation.
- Parameterized blocked-site and blocked-pattern SQL filtering in apply job acquisition.
- Tightened local file permissions for sensitive artifacts on non-Windows systems.

## P0 — Filters Consistency + Enforcement

### 1) Unify location filter schema across pipeline
- Problem: Discovery uses `location_accept` / `location_reject_non_remote`, while apply prompt uses `location.accept_patterns`.
- Goal: Support one canonical schema and maintain backward compatibility.
- Scope:
  - Add centralized config helpers in `config.py` to read normalized location filters.
  - Update discovery (`jobspy.py`, `workday.py`, `smartextract.py`) and apply prompt generation to use the shared helper.
  - Add migration note in docs and examples.
- Acceptance criteria:
  - Both old and new config styles work.
  - Discovery and apply behavior are consistent for the same config.

### 2) Enforce `exclude_titles` during discovery
- Problem: `exclude_titles` exists in `searches.example.yaml` but is not currently enforced.
- Goal: Filter out excluded titles before scoring/tailoring.
- Scope:
  - Apply case-insensitive title filtering in discovery ingestion paths.
  - Log filtered counts by source/stage.
  - Add tests for exclusion matching and edge cases.
- Acceptance criteria:
  - Jobs matching excluded title patterns are not inserted or are excluded before downstream stages.
  - `status`/logs expose filtered counts.

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

### 4) Expose Session ID filtering in CLI
- Goal: Allow users to specifically target jobs discovered in a specific run (e.g. `applypilot run --session-id 20260221_222415`).
- Scope:
  - Add `--session-id` flat to `cli.py` commands (`run`, `apply`, `status`).
  - Update `database.py` query conditions to filter by `session_id` if provided.
- Acceptance criteria:
  - CLI can process and target single historical discovery runs.
  - Pipeline stages flow seamlessly for that specific session batch.

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

## Notes
- Prioritize P0 items first; they directly address current filtering confusion and wasted downstream compute.
- Keep changes backward-compatible where possible to avoid breaking existing user configs.
