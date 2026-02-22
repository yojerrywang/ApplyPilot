# Codex Session Recovery Guide

This file is a lightweight handoff note so the project can be restarted with AI assistance at any time.

## Who I Am (Codex)

- Assistant name: GitHub Copilot (Codex).
- Model: GPT-5.3-Codex.
- Primary role in this repo: implementation-focused coding agent for architecture changes, refactors, security hardening, and CLI/data-path reliability fixes.

## Gemini AI (Companion Agent)

- Primary role: fast ideation, alternative design options, prompt iteration, and parallel tasking.
- Best use in this project: brainstorming filters/scoring heuristics, drafting docs, and proposing tradeoff options before code changes are finalized.

## Strengths by Agent

### Codex strengths
- Precise multi-file code edits in existing codebases.
- Safer refactors with focused scope and minimal collateral changes.
- End-to-end execution (implement + validate + summarize).
- Git/worktree operational support for parallel branch workflows.

### Gemini strengths
- Rapid generation of alternatives and design variants.
- Broad exploration of options for pipeline behavior/policy.
- Fast drafting of product-facing explanations and docs.

## Suggested Split of Work (for two-AI mode)

- Codex: core Python changes (`src/applypilot/**`), security fixes, DB/query hardening, tests.
- Gemini: backlog grooming, requirements wording, scoring/filter policy proposals, prompt copy tuning.

## Current Parallel Workflow Pattern

- Main worktree: `/Users/admin/Projects/ApplyPilot` on `dev`.
- Security worktree: `/Users/admin/Projects/ApplyPilot-security` on `security-hardening`.
- Use separate IDE windows, one per worktree, to avoid branch checkout collisions.

## Restart Checklist

1. Confirm worktrees:
   - `git -C /Users/admin/Projects/ApplyPilot worktree list`
2. Confirm active branches:
   - `git -C /Users/admin/Projects/ApplyPilot status --short --branch`
   - `git -C /Users/admin/Projects/ApplyPilot-security status --short --branch`
3. Re-open both IDE windows if needed.
4. Re-state active goals from `BACKLOG.md`.
5. Continue coding in the appropriate worktree branch.

## Reintegration Reminder

- Merge via PR (recommended): `security-hardening -> dev`.
- Or merge locally into `dev`, resolve conflicts, run tests, push.
- Remove temporary worktree after merge if no longer needed.
