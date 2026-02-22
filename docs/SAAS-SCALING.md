# SaaS scaling: 1,000 users

This doc outlines how to run ApplyPilot as a multi-tenant service for ~1,000 users, with rough compute and cost estimates and suggested price points. It assumes you will comply with AGPL (offer source for the version you run) and add your own features/updates/fixes.

---

## 1. Architecture overview

Today ApplyPilot is single-tenant: one `APPLYPILOT_DIR` (profile, DB, resume, searches) per machine. To support 1,000 users you need:

| Concern | Current | For 1,000 users |
|--------|---------|------------------|
| **Identity** | None | Auth (e.g. Supabase Auth, Auth0, Clerk) + tenant ID per user/org |
| **Config per user** | `~/.applypilot/` on one machine | Profile, resume, searches, API keys stored per tenant (DB or object storage) |
| **Database** | SQLite per dir | **PostgreSQL** (or similar) with `tenant_id` on all tables; one schema, many tenants |
| **Pipeline execution** | Single process, optional `-w N` | **Job queue** (Redis + Celery, or SQS + workers, or Inngest, etc.) so `run` and `apply` are async jobs per tenant |
| **LLM** | One `GEMINI_API_KEY` in `.env` | Per-tenant API keys **or** one pool key with rate limits and cost attribution (e.g. tenant_id in logs) |
| **Apply (Chrome)** | Local Chrome + Claude Code | Isolated **apply workers**: each worker = VM/container with Chrome + Claude Code, pulling “apply” jobs from the queue for any tenant; store tailored resume/cover in object storage and pass URLs |

High-level flow:

1. **API / web app**: user signs in → tenant_id; user triggers “run pipeline” or “run apply” → enqueue job(s) with tenant_id.
2. **Run workers**: pick “run” jobs, load tenant config (profile, searches) and tenant-specific DB connection (or same DB with `tenant_id` filter), execute discover → dedupe → enrich → score → tailor → cover (and optionally pdf); write results to tenant’s rows; optionally store tailored PDFs in object storage.
3. **Apply workers**: pick “apply” jobs, load job + tailored resume/cover (from DB or object storage), launch Chrome + Claude Code for that tenant’s apply, report status back to DB.

You’ll need to refactor:

- **Config**: replace single `APPLYPILOT_DIR` with “config loader” that takes `tenant_id` and returns paths or in-memory config (profile, resume text, searches, optional per-tenant LLM key).
- **Database**: replace single SQLite with a DB layer that uses PostgreSQL and `tenant_id`; reuse existing schema as far as possible (add `tenant_id`, isolate all queries).
- **Pipeline**: keep stage logic; entrypoints become “run for tenant X” and “apply for job Y (tenant X)”.

---

## 2. Assumptions for cost and compute

Rough inputs (tune to your product):

- **1,000 registered users**; **~20% “active” per month** → 200 users running the pipeline at least once.
- **Runs per active user per month**: 4 (e.g. weekly).
- **Jobs per run**: discover ~250, after dedupe ~180, after score (min 7) **~50** jobs that get score + tailor + cover.
- **Apply**: 25% of active users use auto-apply; 15 applications per run → 50 users × 4 runs × 15 = **3,000 applications/month**, ~3–5 min each → **150–250 worker-hours/month** of Chrome+Claude.

Token usage per “full” run (50 jobs scored + tailored + cover), from current code:

- **Score**: ~50 × (≈4.5k input + 0.5k output) ≈ 250k tokens.
- **Tailor**: ~50 × (≈9k input + 2k output) ≈ 550k tokens.
- **Cover**: ~50 × (≈5k input + 1k output) ≈ 300k tokens.
- **Enrichment (AI fallback)**: variable; assume ~10% of jobs use it, 5 × (≈8k + 4k) ≈ 60k tokens.
- **Total per run** ≈ **1.1M tokens** (round to **1.2M** with retries/overhead).

So:

- **Pipeline runs/month**: 200 × 4 = **800 runs** → 800 × 1.2M ≈ **960M tokens/month** (~1B).
- **Apply**: 3,000 applications × 3–5 min → **150–250 Chrome-hours/month**.

---

## 3. Compute and infra (ballpark)

- **API / app**: 2–4 small instances (e.g. 1 vCPU, 2 GB RAM) behind a load balancer, or one 2 vCPU / 4 GB; handle auth, enqueue jobs, serve dashboard/status.
- **Run workers**: 4–8 workers (e.g. 1 vCPU, 2 GB RAM each); I/O and CPU for discover/enrich, plus LLM calls; scale with queue depth.
- **Apply workers**: each Chrome + Claude Code is heavy (2–4 GB RAM, 1 vCPU per concurrent browser). 5–10 concurrent apply workers → 5–10 × (2–4 GB) = 10–40 GB RAM and 5–10 vCPUs for apply; can be a few larger VMs or a pool of medium instances.
- **PostgreSQL**: 1 instance (e.g. 2 vCPU, 4–8 GB RAM); 1,000 users and ~50–200 jobs per run × 200 users × 4 runs = 40k–160k new rows/month plus history → storage on the order of tens of GB in year one.
- **Redis** (if used for queue): 1 small instance (e.g. 1 GB).
- **Object storage**: tailored PDFs and cover letters; 800 runs × 50 files × ~200 KB ≈ 8 GB/month growth (S3/GCS pricing is cheap).

Rough **compute-only** (cloud list prices, before discounts):

- API: ~$40–80/month.
- Run workers: ~$80–160/month.
- Apply workers (Chrome): ~$200–400/month (e.g. 3× 4 vCPU / 16 GB or equivalent).
- PostgreSQL: ~$50–100/month (managed).
- Redis: ~$15–30/month.
- **Total compute/infra**: **~$400–800/month**.

---

## 4. Cost estimates

### 4.1 LLM (Gemini 2.0 Flash–style pricing)

Using rough **Google Gemini 2.0 Flash** list pricing (check current):

- Input: ~\$0.075 / 1M tokens; output: ~\$0.30 / 1M tokens.
- Per run: ~900k input + 300k output → ~\$0.068 + \$0.09 ≈ **\$0.16/run**.
- 800 runs/month → **~\$130/month** LLM.

If you use **OpenAI** (e.g. gpt-4o-mini): input ~\$0.15/1M, output ~\$0.60/1M → ~\$0.30/run → **~\$240/month** for 800 runs.

So: **LLM in the $130–250/month range** for the usage above.

### 4.2 CapSolver (optional)

If you enable CAPTCHA solving for apply: 3,000 applications × low solve rate (e.g. 10%) = 300 solves; at ~\$2–3/1k solves → **~\$1–2/month** (can be higher if many sites use CAPTCHAs).

### 4.3 Total cost (ballpark)

| Item | Low | High |
|------|-----|-----|
| Compute (API, run workers, apply workers, DB, Redis) | $400 | $800 |
| LLM (Gemini 2.0 Flash) | $130 | $250 |
| Storage / egress / misc | $20 | $50 |
| **Total** | **~$550** | **~$1,100** |

So **~\$600–1,100/month** to run for 1,000 users with 200 active and the usage above. Per active user that’s **~\$3–5.50/month** in hard costs.

---

## 5. Price points that make sense

- You need to cover **costs + margin + support + growth**. Aim for **3–5×** markup on variable cost (LLM + compute share) for a sustainable SaaS.
- **Per active user** cost is ~\$3–5.50; **per registered user** (if 20% active) ~\$0.60–1.10.

Suggested positioning (monthly):

| Tier | Price (approx) | Target | Rationale |
|------|----------------|--------|-----------|
| **Free** | $0 | Trial / light use | 1 run/month or 5 jobs/run; no auto-apply; converts to paid. |
| **Pro** | **$19–29** | Most individuals | 4–8 runs/month, e.g. 50–100 jobs/run, auto-apply included; clear margin. |
| **Team / power** | **$49–79** | Heavy or shared | Higher run/job limits, maybe team seats or API access. |

If 200 active users pay **$24/month** on average:

- Revenue: 200 × \$24 = **\$4,800/month**.
- Cost: ~\$600–1,100 → **~\$3,700–4,200 gross margin** before sales, support, and your time.

So **\$19–29/month** for the main tier is a reasonable range; you can start at **\$24** and adjust after you see real usage and support load.

---

## 6. What to build first (order of operations)

1. **Multi-tenant data model**: tenant_id everywhere; migrate from “one SQLite per dir” to one PostgreSQL schema with tenant_id; config loader by tenant.
2. **Auth**: sign-up, login, API keys or session tokens; associate every request with a tenant.
3. **Job queue**: enqueue “run pipeline (tenant_id)” and “apply (job_id, tenant_id)”; run workers and apply workers consume from the queue.
4. **Run workers**: refactor pipeline to “run for tenant” (load config by tenant, write to tenant rows); no UI change needed beyond “start run.”
5. **Apply workers**: refactor apply to run in worker pool with tenant-isolated Chrome/profile; store outputs in object storage and pass URLs.
6. **Billing**: usage metering (runs, applications, or tokens) and Stripe (or similar) for Free vs Pro vs Team; enforce limits per plan.
7. **Observability**: per-tenant and per-stage logging, error rates, LLM token usage; use this to tune limits and pricing.

---

## 7. Summary

- **Setup for 1,000 users**: multi-tenant DB (PostgreSQL), auth, job queue, run workers, apply workers (Chrome pool), per-tenant config and storage.
- **Compute**: ~\$400–800/month; **LLM**: ~\$130–250/month; **total ~\$600–1,100/month** at 200 active users and 800 runs/month.
- **Price**: **\$19–29/month** for the main tier is a sensible target; **\$24** is a good starting point.
- Build order: tenant model + auth → queue + run workers → apply workers → billing and limits.

All numbers are estimates; measure real usage and adjust costs and pricing as you ship.
