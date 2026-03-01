# Branch Protection Baseline

Use this baseline for `main` (prod) and `dev` (integration):

## `main`
- Require pull requests before merging.
- Require at least 1 approving review.
- Dismiss stale approvals on new commits.
- Require status checks to pass before merging.
- Require check: `required-checks`.
- Restrict direct pushes.

## `dev`
- Require pull requests before merging (recommended for teams).
- Require status checks to pass before merging.
- Require check: `required-checks`.
- Restrict direct pushes (optional for solo maintainers).

## Notes
- The `required-checks` job is produced by `.github/workflows/ci.yml` and gates
  the Python matrix, lint, unit/integration, and E2E regression jobs.
- CODEOWNERS is defined at `.github/CODEOWNERS` for critical file review routing.
