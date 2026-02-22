# SaaS scaling: 1,000 users

This doc outlines how to run ApplyPilot as a multi-tenant service for ~1,000 users, with rough compute and cost estimates and suggested price points. It assumes you will comply with AGPL (offer source for the version you run) and add your own features/updates/fixes.

**Quick numbers (premium $50–100/mo, daily use, product + marketing costs):**

| Reg users | Paid | Revenue/mo | Costs/mo | Profit/mo |
|-----------|------|------------|----------|-----------|
| 1,000     | 100  | **\$10,000** | **\$5,000** | **\$5,000** |

Easy rule of thumb: **every 1k registered users with 100 paid** → **\$10k revenue**, **\$5k costs**, **\$5k profit** (50% margin). Assumes ~\$100 ARPU (e.g. all at \$100/mo or mix of \$50/\$100) and costs scaled for 100 paying users running daily.

**Sanity check (100 paid → $10k / $5k / $5k):**

| Line | Check |
|------|--------|
| **Revenue** | 100 × \$100/mo = **\$10,000**. Holds if ARPU is \$100 (all on \$100 plan or mix that averages there). If ARPU is \$50, revenue halves → \$5k; then \$5k costs = **no profit**. So **\$100 ARPU (or close) is required** for this rule of thumb. |
| **Product cost** | 100 users × 22 runs/mo = 2,200 runs. LLM: 2,200 × \$0.16 ≈ **\$350**. Compute (fewer run/apply workers than 200-user case): **~\$500–1,200**. Product total **~\$900–1,600**. |
| **Marketing** | To hit **\$5k total cost**: \$5k − \$1k to \$5k − \$1.6k → **~\$3,400–4,000** on marketing. So the thumb assumes **~\$3.5k/mo** acquisition spend (35% of revenue). Plausible for growth; if you spend less (e.g. \$1.5–2k), total cost **~\$2.5–3.5k** → **profit ~\$6.5–7.5k**. |
| **Profit** | \$10k − \$5k = **\$5k**. Mid-case: product ~\$1.2k + marketing ~\$3.8k = \$5k. **Sanity check passes** — numbers are consistent. |
| **Risks** | (1) **ARPU below \$100** → revenue and profit drop fast. (2) **Conversion below 10%** (e.g. 80 paid) → \$8k revenue, ~\$4.5k costs → ~\$3.5k profit. (3) **Heavier use** (more apply or more jobs/run) → product cost can reach \$2k; still fine if marketing is \$3k. |

**Verdict:** The rule of thumb is **sane** as long as you actually get **~\$100 ARPU** and **~10% reg→paid**. If ARPU or conversion is lower, profit shrinks; if you spend less on marketing, profit goes up.

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

- **1,000 registered users**; **~20% paying or heavy-active per month** → 200 users you need to support at “paid” usage levels.
- **Paying users run it a lot.** Once someone has paid, they’re motivated to get results — they’ll run **daily or near-daily** (new jobs, new applications). Plan for **heavy use as the norm** for paid tiers, not the exception.
- **Runs per paying user per month**: **20–25** (e.g. weekdays or 5–6×/week) for premium; trial/proof users might do 1–2 runs total.
- **Jobs per run**: discover ~250, after dedupe ~180, after score (min 7) **~50** jobs that get score + tailor + cover.
- **Apply**: Most paying users use auto-apply; **~20 applications per run** → 200 users × 22 runs × 20 = **~88,000 applications/month** at 3–5 min each → **~4,400–7,300 Chrome-hours/month**. (If only half use apply that often: **~2,200–3,600 hours/month**.)

Token usage per “full” run (50 jobs scored + tailored + cover), from current code:

- **Score**: ~50 × (≈4.5k input + 0.5k output) ≈ 250k tokens.
- **Tailor**: ~50 × (≈9k input + 2k output) ≈ 550k tokens.
- **Cover**: ~50 × (≈5k input + 1k output) ≈ 300k tokens.
- **Enrichment (AI fallback)**: variable; assume ~10% of jobs use it, 5 × (≈8k + 4k) ≈ 60k tokens.
- **Total per run** ≈ **1.1M tokens** (round to **1.2M** with retries/overhead).

So for **200 paying users, daily/near-daily use**:

- **Pipeline runs/month**: 200 × 22 = **4,400 runs** → 4,400 × 1.2M ≈ **5.3B tokens/month**.
- **Apply**: **~2,200–7,300 Chrome-hours/month** depending on what % of paying users run apply every run (scale apply worker pool to handle peak).

---

## 3. Compute and infra (ballpark)

**Sized for 200 paying users running daily/near-daily** (4,400 runs/month, 2,200–7,300 apply-hours/month):

- **API / app**: 2–4 small instances (e.g. 1 vCPU, 2 GB RAM) behind a load balancer; handle auth, enqueue jobs, serve dashboard/status.
- **Run workers**: **8–16 workers** (e.g. 1 vCPU, 2 GB RAM each) so the queue drains in reasonable time with 4,400 runs/month; I/O and CPU for discover/enrich, plus LLM calls.
- **Apply workers**: Each Chrome + Claude Code is heavy (2–4 GB RAM, 1 vCPU per concurrent browser). At **~3,000–5,000 apply-hours/month** you need **~5–15 concurrent apply workers** (depending on peak vs spread). Plan **~$400–1,200/month** for apply worker capacity (e.g. 5–15× medium instances or a smaller pool of larger ones).
- **PostgreSQL**: 1 instance (e.g. 2–4 vCPU, 8 GB RAM); 200 users × 22 runs × ~200 job rows/run → high write volume and storage growth; tens to low hundreds of GB in year one.
- **Redis** (if used for queue): 1 instance (e.g. 1–2 GB).
- **Object storage**: 4,400 runs × 50 files × ~200 KB ≈ **~44 GB/month** growth (still cheap on S3/GCS).

Rough **compute-only** (cloud list prices, before discounts), **with daily-use load**:

- API: ~$40–80/month.
- Run workers: ~$160–320/month.
- Apply workers (Chrome): ~$400–1,200/month.
- PostgreSQL: ~$80–150/month (managed, larger).
- Redis: ~$15–30/month.
- **Total compute/infra**: **~$700–1,800/month** (scale apply workers up if apply-hours trend toward the high end).

---

## 4. Cost estimates

### 4.1 LLM (Gemini 2.0 Flash–style pricing)

Using rough **Google Gemini 2.0 Flash** list pricing (check current):

- Input: ~\$0.075 / 1M tokens; output: ~\$0.30 / 1M tokens.
- Per run: ~900k input + 300k output → ~\$0.068 + \$0.09 ≈ **\$0.16/run**.
- **At daily use**: 4,400 runs/month → **~\$700/month** LLM.

If you use **OpenAI** (e.g. gpt-4o-mini): ~\$0.30/run → **~\$1,320/month** for 4,400 runs.

So: **LLM in the $700–1,300/month range** when 200 paying users run daily. This is the main variable cost; premium pricing ($50–100/month) is what makes it viable.

### 4.2 CapSolver (optional)

If you enable CAPTCHA solving for apply: tens of thousands of applications × low solve rate (e.g. 10%) → **~\$20–80/month** at daily-use volume (can be higher if many sites use CAPTCHAs).

### 4.3 Marketing and distribution (budget)

You need to budget for **acquisition** so trial users find the product and convert to paid. Typical approaches:

| Category | What it covers | Ballpark (monthly) |
|----------|----------------|--------------------|
| **Paid acquisition** | Google/Meta/LinkedIn ads, job-board partnerships, sponsored posts | $500 – $3,000+ |
| **Content & SEO** | Blog, guides, “how to get more interviews,” tooling; SEO for job-search terms | $200 – $1,000 (time or freelancer) |
| **Community & word of mouth** | Reddit, Discord, X, Indie Hackers; testimonials, case studies (“applied to 200 jobs, 5 interviews”) | $0 – $500 (time or small incentives) |
| **Partnerships / affiliates** | Career coaches, outplacement, bootcamps; rev share or flat fee per signup | $100 – $1,000 |
| **Tools & ops** | Email (Mailchimp/SendGrid), analytics, landing page, A/B tests | $50 – $200 |

**Rule of thumb:** Many early-stage B2C/self-serve SaaS allocate **20–40% of revenue** to marketing, or a **fixed monthly budget** (e.g. $1,000–2,500) until you have reliable CAC and LTV. Target **CAC payback** under 12 months; at $50–100/month, that means CAC of **\$600–1,200 per paying customer** is acceptable if retention is good.

**For ApplyPilot specifically:** Proof-led positioning (trial → proof it works → premium) works well with **content + community** (low CAC) and **targeted paid** (job seekers, “job search automation,” “apply to more jobs”). Budget **\$1,500–3,000/month** for marketing/distribution as you scale to 1,000 users and 200 paying; adjust once you measure CAC and conversion from proof → paid.

### 4.4 Total cost (ballpark)

**With 200 paying users running daily/near-daily** (4,400 runs/month, thousands of apply jobs/month):

| Item | Low | High |
|------|-----|-----|
| Compute (API, run workers, apply workers, DB, Redis) | $700 | $1,800 |
| LLM (Gemini 2.0 Flash) | $700 | $1,300 |
| Storage / egress / misc | $30 | $80 |
| **Marketing / distribution** | **$1,000** | **$3,000** |
| **Total** | **~$2,430** | **~$6,180** |

So **~\$2,400–6,200/month** to run 1,000 users with **200 paying users who run it all the time**, including marketing. Product + infra is **~\$1,400–3,200** at this usage; the rest is acquisition. Per paying user: **~\$12–31/month** all-in (product + marketing share).

---

## 5. User segments and positioning

**Typical use cases:**

1. **Unemployed or underemployed** — They want to win and get a positive outcome. Stakes are high; they need results and proof the product works before they commit.
2. **Already employed** — They want optionality: better role, raise, or escape hatch. Lower urgency but willing to pay for quality and automation.

**Implications for pricing:**

- **Try before committing:** People need to see it work for *them* (their resume, their searches, their results) before they’ll pay serious money. Offer a clear **proof tier**: enough runs and applications to get real feedback (e.g. interviews, callbacks) so they can believe it works.
- **Premium once it works:** If it works, value is high — and **they’ll run it all the time**. People who paid are trying to get a job or optionality; they’ll run discover + apply **daily or near-daily**. So **design capacity and limits for daily use**; pricing at **$50 or $100/month** is justified and expected to support that usage.

---

## 6. Price points that make sense

- **Proof tier (trial):** Let users try with enough capacity to get real proof — e.g. 1–2 full runs, 20–30 applications, so they can see scores, tailored resumes, and maybe an interview. Free or nominal ($5–10 one-time or first month). Goal: conversion to paid once they see it work.
- **Premium tier:** **$50–100/month.** For users who are all-in: multiple discover + apply runs per week or per day, high job limits, full auto-apply. This is the main revenue tier.
- **Optional middle tier:** e.g. **$29–39/month** for 2–3 runs/week if you want a step between trial and power users.

Suggested positioning (monthly):

| Tier | Price (approx) | Target | Rationale |
|------|----------------|--------|-----------|
| **Proof / trial** | $0 or one-time $5–10 | Try before committing | 1–2 full runs, 20–30 applications; enough to see it work and get proof (callbacks, interviews). Converts to paid. |
| **Pro** (optional) | **$29–39** | Moderate use | 2–3 runs/week, capped applications; for people who want more than trial but not daily use. |
| **Premium** | **$50–100** | Serious / daily use | Multiple discover + apply runs per week or per day; high job limits; full auto-apply. Main revenue tier. |

**Unit economics at premium (including marketing, with daily use):**

- If 150 paying users are on **$50/month** and 50 on **$100/month**: 150 × \$50 + 50 × \$100 = **\$12,500/month** revenue.
- **Costs:** Product (compute + LLM with 4,400 runs/month) **~\$1,400–3,200/month**; marketing/distribution **~\$1,000–3,000/month** → total **~\$2,400–6,200/month**.
- **Gross margin** after product + marketing: **~\$6,300–10,100/month** — premium pricing makes the math work even when paying users run job searches daily and you spend on acquisition.

Start with a clear **proof tier** and a single **premium** at **$50 or $75**; add **$100** (or a higher cap) for heaviest users once you see real usage.

---

## 7. What to build first (order of operations)

1. **Multi-tenant data model**: tenant_id everywhere; migrate from “one SQLite per dir” to one PostgreSQL schema with tenant_id; config loader by tenant.
2. **Auth**: sign-up, login, API keys or session tokens; associate every request with a tenant.
3. **Job queue**: enqueue “run pipeline (tenant_id)” and “apply (job_id, tenant_id)”; run workers and apply workers consume from the queue.
4. **Run workers**: refactor pipeline to “run for tenant” (load config by tenant, write to tenant rows); no UI change needed beyond “start run.”
5. **Apply workers**: refactor apply to run in worker pool with tenant-isolated Chrome/profile; store outputs in object storage and pass URLs.
6. **Billing**: usage metering (runs, applications, or tokens) and Stripe (or similar) for Free vs Pro vs Team; enforce limits per plan.
7. **Observability**: per-tenant and per-stage logging, error rates, LLM token usage; use this to tune limits and pricing.

---

## 8. Summary

- **Setup for 1,000 users**: multi-tenant DB (PostgreSQL), auth, job queue, run workers, apply workers (Chrome pool), per-tenant config and storage.
- **Costs:** Product (compute + LLM) **~\$1,400–3,200/month** when 200 paying users run **daily/near-daily**; **marketing/distribution** ~\$1,000–3,000/month. **Total ~\$2,400–6,200/month** — budget for both. Paying users will run it all the time, so plan for heavy use.
- **User segments**: (1) Unemployed/underemployed — want to win, need proof it works; (2) Employed — want optionality. Both need a try-before-commit proof tier, then premium pricing for heavy use.
- **Pricing**: **Proof tier** (free or nominal) so users get real proof; **Premium \$50–100/month** for heavy use. Assume **paying users run daily** — plan capacity and costs for 20–25 runs/month per paying user.
- **Marketing**: Allocate 20–40% of revenue or \$1,000–3,000/month; content + community + targeted paid; target CAC payback under 12 months. Premium pricing keeps unit economics workable with real acquisition spend and daily use.
- Build order: tenant model + auth → queue + run workers → apply workers → billing and limits.

All numbers are estimates; measure real usage, CAC, and conversion and adjust costs and pricing as you ship.
