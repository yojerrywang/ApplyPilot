<!-- logo here -->

# ApplyPilot

**Applied to 1,000 jobs in 2 days. Fully autonomous. Open source.**

[![PyPI version](https://img.shields.io/pypi/v/applypilot?color=blue)](https://pypi.org/project/applypilot/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-green.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/Pickle-Pixel/ApplyPilot?style=social)](https://github.com/Pickle-Pixel/ApplyPilot)




https://github.com/user-attachments/assets/7ee3417f-43d4-4245-9952-35df1e77f2df


---

## What It Does

ApplyPilot is a 6-stage autonomous job application pipeline. It discovers jobs across 5+ boards, scores them against your resume with AI, tailors your resume per job, writes cover letters, and **submits applications for you**. It navigates forms, uploads documents, answers screening questions, all hands-free.

Four commands. That's it.

```bash
pip install applypilot
pip install --no-deps python-jobspy    # separate install (broken numpy pin in metadata)
pip install pydantic tls-client requests markdownify regex  # jobspy runtime deps skipped by --no-deps
applypilot init          # one-time setup: resume, profile, preferences, API keys
applypilot run           # discover > dedupe > enrich > score > tailor > cover letters
applypilot run -w 4      # same but parallel (4 threads for discovery/enrichment)
applypilot apply         # autonomous browser-driven submission
applypilot apply -w 3    # parallel apply (3 Chrome instances)
applypilot apply --dry-run  # fill forms without submitting
applypilot doctor        # preflight checks (env/profile/search/db/runtime)
```

---

## Two Paths

### Full Pipeline (recommended)
**Requires:** Python 3.11+, Node.js (for npx), Gemini API key (free), Claude Code CLI, Chrome

Runs all 6 stages, from job discovery to autonomous application submission. This is the full power of ApplyPilot.

### Discovery + Tailoring Only
**Requires:** Python 3.11+, Gemini API key (free)

Runs stages 1-5: discovers jobs, scores them, tailors your resume, generates cover letters. You submit applications manually with the AI-prepared materials.

### Standalone Tailoring + Google Docs (manual apply speedrun)
**Requires:** Python 3.11+, LLM API key (Gemini/OpenAI/local), Google OAuth credentials

Paste one or more job URLs, generate tailored resumes, and optionally push outputs to
Google Docs for human edit + PDF export.

---

## The Pipeline

| Stage | What Happens |
|-------|-------------|
| **1. Discover** | Scrapes 5 job boards (Indeed, LinkedIn, Glassdoor, ZipRecruiter, Google Jobs) + 48 Workday employer portals + 30 direct career sites. Automatically assigns a `session_id` to group batches. |
| **2. Dedupe** | Removes semantic duplicates by normalized company + title (fallback to site + title when company is unavailable), prioritizing the highest fit score and most recent discovery. |
| **3. Enrich** | Fetches full job descriptions via JSON-LD, CSS selectors, or AI-powered extraction |
| **4. Score** | AI rates every job 1-10 based on your resume and preferences. Only high-fit jobs proceed |
| **5. Tailor** | AI rewrites your resume per job: reorganizes, emphasizes relevant experience, adds keywords. Never fabricates |
| **6. Cover Letter** | AI generates a targeted cover letter per job |
| **7. Auto-Apply** | Claude Code navigates application forms, fills fields, uploads documents, answers questions, and submits |

Each stage is independent. Run them all or pick what you need.

---

## 🎯 The Multi-Track "Shotgun" Strategy (Beta)

ApplyPilot is transitioning from a single-persona resume builder into a **Multi-Track Autonomous Application Engine**. You should not apply to PM roles and Content roles with the same global configuration, as this leads to LLM hallucination and weak narratives.

**The Multi-Track Playbook:**
1. Maintain discrete "Role Tracks" (e.g. `pm`, `swe`, `content_mgr`).
2. Use shipped safeguards now (validator checks, preserved-fact checks, apply result parsing), then add stricter keyword/metric quotas as Epic 5 work lands.
3. Use the nightly supervisor harness to cycle through isolated environments automatically.

**Running the MVP Harness Today:**
Before native SQLite track scaffolding is built, you can emulate this isolation using `APPLYPILOT_DIR`.
1. Create isolated folders: `~/.applypilot_pm`, `~/.applypilot_swe`, etc.
2. Place your track-specific `profile.json` (e.g., using `youremail+pm@gmail.com`), `searches.yaml`, and `.env` inside each.
3. Run the built-in `scripts/applypilot-daily.sh` to sequentially discover/score, and horizontally auto-apply across all tracks.

**Estimated Cost Modeling (Running 5 Roles, 5 Days/Week):**
Current harness defaults in `scripts/applypilot-daily.sh` are `MAX_SCORE=400`, `--min-score 8`, and `--limit 10` across `5` tracks.
- **OpenAI scoring + tailoring (gpt-5-mini style baseline):** about `$12/week` at those caps.
- **Claude apply agent:** typically `$17-$90/week` depending on model and per-application token usage.
- **Total API envelope:** roughly `$30-$140/week`, plus cloud hosting.
Treat this as a planning range, not a fixed guarantee. Actual cost depends on model selection, retries, and ATS complexity.

---

## ApplyPilot vs The Alternatives

| Feature | ApplyPilot | AIHawk | Manual |
|---------|-----------|--------|--------|
| Job discovery | 5 boards + Workday + direct sites | LinkedIn only | One board at a time |
| AI scoring | 1-10 fit score per job | Basic filtering | Your gut feeling |
| Resume tailoring | Per-job AI rewrite | Template-based | Hours per application |
| Auto-apply | Full form navigation + submission | LinkedIn Easy Apply only | Click, type, repeat |
| Supported sites | Indeed, LinkedIn, Glassdoor, ZipRecruiter, Google Jobs, 46 Workday portals, 28 direct sites | LinkedIn | Whatever you open |
| License | AGPL-3.0 | MIT | N/A |

---

## Requirements

| Component | Required For | Details |
|-----------|-------------|---------|
| Python 3.11+ | Everything | Core runtime |
| Node.js 18+ | Auto-apply | Needed for `npx` to run Playwright MCP server |
| Gemini API key | Scoring, tailoring, cover letters | Free tier (15 RPM / 1M tokens/day) is enough |
| Chrome/Chromium | Auto-apply | Auto-detected on most systems |
| Claude Code CLI | Auto-apply | Install from [claude.ai/code](https://claude.ai/code) |

**Gemini API key is free.** Get one at [aistudio.google.com](https://aistudio.google.com). OpenAI and local models (Ollama/llama.cpp) are also supported.

### Optional

| Component | What It Does |
|-----------|-------------|
| CapSolver API key | Solves CAPTCHAs during auto-apply (hCaptcha, reCAPTCHA, Turnstile, FunCaptcha). Without it, CAPTCHA-blocked applications just fail gracefully |

> **Note:** python-jobspy is installed separately with `--no-deps` because it pins an exact numpy version in its metadata that conflicts with pip's resolver. It works fine with modern numpy at runtime.

---

## Configuration

All generated by `applypilot init`:

### `profile.json`
Your personal data in one structured file: contact info, work authorization, compensation, experience, skills, resume facts (preserved during tailoring), and EEO defaults. Powers scoring, tailoring, and form auto-fill.

### `searches.yaml`
Job search queries, target titles, locations, boards. Run multiple searches with different parameters.

### `.env`
API keys and runtime config: `GEMINI_API_KEY`, `OPENAI_API_KEY`, `LLM_URL`, `LLM_MODEL`,
`LLM_PROVIDER`, `CAPSOLVER_API_KEY` (optional).

#### LLM provider selection
- Auto-detect (default): Gemini > OpenAI > local URL
- Force provider explicitly:
  - `LLM_PROVIDER=gemini`
  - `LLM_PROVIDER=openai`
  - `LLM_PROVIDER=local`

## Security & Privacy Notes

- ApplyPilot no longer stores a job-site login password in `profile.json`.
- Auto-apply prompts do not embed a plaintext account password.
- On macOS/Linux, `applypilot init` now applies restrictive permissions to local secrets (`.env`, `profile.json`) and app data directories.
- If a site requires login credentials, prefer your browser password manager/autofill over putting credentials in project files.

### Package configs (shipped with ApplyPilot)
- `config/employers.yaml` - Workday employer registry (48 preconfigured)
- `config/sites.yaml` - Direct career sites (30+), blocked sites, base URLs, manual ATS domains
- `config/searches.example.yaml` - Example search configuration

---

## How Stages Work

### Discover
Queries Indeed, LinkedIn, Glassdoor, ZipRecruiter, Google Jobs via JobSpy. Scrapes 48 Workday employer portals (configurable in `employers.yaml`). Hits 30 direct career sites with custom extractors. Automatically tags the batch with a `session_id`.

### Dedupe
Scans the database and automatically purges semantic duplicates (jobs that have different URLs but the same normalized company + title; falls back to site + title when company is unavailable), keeping the one with the highest fit score and most recent discovery.

### Enrich
Visits each job URL and extracts the full description. 3-tier cascade: JSON-LD structured data, then CSS selector patterns, then AI-powered extraction for unknown layouts.

### Score
AI scores every job 1-10 against your profile. 9-10 = strong match, 7-8 = good, 5-6 = moderate, 1-4 = skip. Only jobs above your threshold proceed to tailoring.

### Tailor
Generates a custom resume per job: reorders experience, emphasizes relevant skills, incorporates keywords from the job description. Your `resume_facts` (companies, projects, metrics) are preserved exactly. The AI reorganizes but never fabricates.

### Cover Letter
Writes a targeted cover letter per job referencing the specific company, role, and how your experience maps to their requirements.

### Auto-Apply
Claude Code launches a Chrome instance, navigates to each application page, detects the form type, fills personal information and work history, uploads the tailored resume and cover letter, answers screening questions with AI, and submits. A live dashboard shows progress in real-time.

If a worker crashes mid-run, stale `in_progress` locks are now auto-recovered and returned to the retry queue after a timeout (`stale_lock_minutes` in defaults).

The Playwright MCP server is configured automatically at runtime per worker. No manual MCP setup needed.

```bash
# Utility modes (no Chrome/Claude needed)
applypilot apply --mark-applied URL    # manually mark a job as applied
applypilot apply --mark-failed URL     # manually mark a job as failed
applypilot apply --reset-failed        # reset all failed jobs for retry
applypilot apply --gen --url URL       # generate prompt file for manual debugging
applypilot doctor                      # validate config/runtime readiness
```

```

---

## AI Assistant Workflows & Shortcuts

If you use an AI coding assistant (like Claude Code, Cursor, Windsurf, or Github Copilot), ApplyPilot includes custom instruction files (`CLAUDE.md`, `.cursorrules`) that teach your AI how to use custom workflow shortcuts.

Workflows are defined as markdown instructions in the `.agents/workflows/` directory.

### Available AI Shortcuts
You can type these phrases directly to your AI assistant:
- **"save atp"** (or `/save_atp`): Auto-instructs the AI to review the git diff, update `CHANGELOG.md`/`README.md`/`BACKLOG.md`, and generate a clean git commit.
- **"commit"** (or `/commit`): Identical to `save atp`.

You can create your own custom AI shortcuts by dropping a new `.md` file into `.agents/workflows/`.

For end-to-end documentation governance (Roadmap → Backlog → Changelog → README feedback loop), see `ROADMAP.md`.

---

## CLI Reference

```
applypilot init                         # First-time setup wizard
applypilot google-auth                  # Authorize Google Drive/Docs
applypilot run [stages...]              # Run pipeline stages (or 'all')
applypilot run --workers 4              # Parallel discovery/enrichment
applypilot run --stream                 # Concurrent stages (streaming mode)
applypilot run --min-score 8            # Override score threshold
applypilot run --dry-run                # Preview without executing
applypilot apply                        # Launch auto-apply
applypilot apply --workers 3            # Parallel browser workers
applypilot apply --dry-run              # Fill forms without submitting
applypilot apply --continuous           # Run forever, polling for new jobs
applypilot apply --headless             # Headless browser mode
applypilot apply --url URL              # Apply to a specific job
applypilot run --session-id "xyz"       # Target a specific discovery batch
applypilot apply --session-id "xyz"     # Auto-apply to a specific batch
applypilot status --session-id "xyz"    # Stats for a specific batch
applypilot status                       # Pipeline statistics
applypilot doctor                       # Validate profile/search/env/db/runtime
applypilot dashboard                    # Open HTML results dashboard
applypilot tailor URL [URL ...]         # Standalone tailoring from explicit URLs
applypilot tailor ... --resume FILE_OR_DRIVE_ID
applypilot tailor ... --gdoc --drive-folder-id FOLDER_ID
applypilot tailor-doc --template-doc-id DOC_ID --tailored-txt PATH
```

When `--session-id` is provided to `applypilot run`, downstream stages (`enrich`, `score`, `tailor`, `cover`) and run summary stats are scoped to that batch.
`applypilot status` and `applypilot dashboard` now include transparency counters for filtered-by-location, filtered-by-title, and deduped jobs.

---

## Recommended workflow and operating tips

- **Start with discovery + tailoring only.** Run `applypilot run` and submit applications yourself at first. Once you’re happy with scoring and tailored resumes, enable auto-apply with `applypilot apply`.
- **Tune the score threshold.** Use `applypilot run --min-score 8` (or `7`) so only strong matches get tailored. Adjust after reviewing a few batches.
- **Use parallel workers when scaling.** Once your searches and profile are stable, use `applypilot run -w 4` and `applypilot apply -w 3` to speed up discovery and submissions.
- **Keep `profile.json` and resume facts accurate.** Better profile data improves scoring and tailoring. The AI preserves your resume facts and does not fabricate; keep them truthful.
- **Dry-run before real apply.** Use `applypilot apply --dry-run` to watch form-filling without submitting, and to catch issues early.
- **CAPTCHAs.** If auto-apply hits many CAPTCHAs, adding a CapSolver API key can help; otherwise those applications fail gracefully.

---

## Google Docs Resume Workflow

1. Authorize once:
```bash
PYTHONPATH=src .venv/bin/python -m applypilot google-auth
```

2. Generate tailored text from explicit job URLs:
```bash
PYTHONPATH=src .venv/bin/python -m applypilot tailor \
  "https://www.linkedin.com/jobs/view/4376778099/" \
  --resume "GOOGLE_DRIVE_FILE_ID_OR_NAME" \
  --out "./tmp_outputs/live_tailor"
```

3. Optional: upload tailored text files to Drive as Google Docs:
```bash
PYTHONPATH=src .venv/bin/python -m applypilot tailor \
  "URL_1" "URL_2" \
  --resume "GOOGLE_DRIVE_FILE_ID_OR_NAME" \
  --gdoc \
  --drive-folder-id "FOLDER_ID"
```

4. Fill a formatted Google Doc template and export PDF:
```bash
PYTHONPATH=src .venv/bin/python -m applypilot tailor-doc \
  --template-doc-id "DOC_TEMPLATE_ID" \
  --tailored-txt "./tmp_outputs/live_tailor/SomeRole.txt" \
  --output-name "Tailored Resume - Review" \
  --pdf-out "./tmp_outputs/live_tailor/Tailored_Resume_Review.pdf"
```

### Supported template placeholders
- `{{NAME}}`, `{{TITLE}}`, `{{CONTACT}}`, `{{PHONE}}`, `{{EMAIL}}`
- `{{SUMMARY}}`, `{{SKILLS}}`, `{{EXPERIENCE}}`, `{{PROJECTS}}`, `{{SERVICE}}`, `{{EDUCATION}}`

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, coding standards, and PR guidelines.
Branch protection baseline and required-check guidance live in [.github/BRANCH_PROTECTION.md](.github/BRANCH_PROTECTION.md).

---

## License

ApplyPilot is licensed under the [GNU Affero General Public License v3.0](LICENSE).

You are free to use, modify, and distribute this software. If you deploy a modified version as a service, you must release your source code under the same license.
