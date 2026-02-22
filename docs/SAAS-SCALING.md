# SaaS scaling: 1,000 users

This doc outlines how to run ApplyPilot as a multi-tenant service for ~1,000 users, with rough compute and cost estimates and suggested price points. It assumes you will comply with AGPL (offer source for the version you run) and add your own features/updates/fixes.

**Quick numbers (premium $50–100/mo, daily use, product + marketing costs):**

| Reg users | Paid | Revenue/mo | Costs/mo | Profit/mo |
|-----------|------|------------|----------|-----------|
| 1,000     | 100  | **\$10,000** | **\$5,000** | **\$5,000** |

Easy rule of thumb: **every 1k registered users with 100 paid** → **\$10k revenue**, **\$5k costs**, **\$5k profit** (50% margin). Assumes ~\$100 ARPU and costs scaled for 100 paying users; **costs include product, marketing, and support** (email, chatbot, community). **Important:** The \$5k cost assumes **no full team** — your time or 1–2 people. A proper team (PM, dev, ops, product marketing) adds ~\$25–40k/mo and needs ~5–8k users / 500–800 paid to work (see §4.6).

**Sanity check (100 paid → $10k / $5k / $5k):**

| Line | Check |
|------|--------|
| **Revenue** | 100 × \$100/mo = **\$10,000**. Holds if ARPU is \$100. If ARPU is \$50, revenue halves → \$5k; then \$5k costs = **no profit**. So **\$100 ARPU (or close) is required**. |
| **Product cost** | 100 users × 22 runs/mo = 2,200 runs. LLM ≈ **\$350**. Compute **~\$500–1,200**. Product total **~\$900–1,600**. |
| **Marketing** | **~\$2,500–3,500** (acquisition). |
| **Support & success** | Proactive: email notifications, CRM, nurturing (leads, free, paid); reactive: email, chatbot, community. **~\$300–600** (tools + your time) or more if part-time. Part of the \$5k cost bucket. |
| **Total cost** | Product ~\$1.2k + marketing ~\$3k + support ~\$500 = **~\$4.7k**; round to **\$5k**. Profit **~\$5k**. **Sanity check passes** — the \$5k cost bucket includes support. |
| **Risks** | (1) **ARPU below \$100** → profit drops. (2) **Conversion below 10%** → fewer paid, same cost base. (3) **Support heavier than expected** (e.g. \$1k+) → shrink margin unless you trim marketing or increase revenue. |

**Verdict:** The rule of thumb is **sane** if you get **~\$100 ARPU** and **~10% reg→paid**, and you keep **support & success in the \$300–600 range** (proactive email/CRM + reactive; tools + your/part-time time). Support is explicitly part of the \$5k costs.

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

### 4.4 Support and customer success (budget)

Support can be **proactive as well as reactive**. Budget for both: nurturing (email, CRM, outreach) and answering (email, chatbot, community).

**Proactive — email, CRM, nurturing**

| Category | What it covers | Ballpark (monthly) |
|----------|----------------|--------------------|
| **Email notifications & sequences** | Transactional (run done, apply status) + lifecycle (welcome, proof-tier tips, upgrade nudge, re-engagement). Tool: SendGrid, Postmark, Customer.io, Resend, etc. | $50 – $200 (sending) + **time** to write and tune sequences |
| **CRM / lead & user nurturing** | Track leads, free users, paid users; segments (trial started, ran first run, didn’t convert, churned). Outreach: “Need help with your first run?”, “You have 2 runs left on proof — here’s how to get the most,” “New jobs in your search this week.” Tools: HubSpot, Clay, Loops, or lightweight DB + your own emails | $0 – $300 (tools) + **time** to run segments and copy |
| **Outreach** | Proactive check-ins for stuck trials, at-risk paid, or power users (feedback, testimonials). Can be manual or semi-automated from CRM segments | **Time** (5–10 hrs/mo) or part-time **~\$200–500** |

**Reactive — when they ask**

| Category | What it covers | Ballpark (monthly) |
|----------|----------------|--------------------|
| **Email support** | Help desk (Zendesk, Help Scout, Intercom), templates, your or part-time time to answer | $100 – $400 (tools) + **time** (or \$300–800 part-time) |
| **Chatbot / AI deflect** | Bot answers FAQs, “how do I…”, status checks; escalate to human when needed | $50 – $200 (API/tool); can cut reactive volume 20–40% |
| **Community support** | Discord, Reddit, X — monitor, answer, triage bugs/feedback | **Time** (5–15 hrs/mo) or \$200–600 part-time |

**Rule of thumb:** At 1,000 users and 100 paid, plan **\$300–1,200/month** for support + success (proactive + reactive): email/CRM tools, sequences, and either your time or part-time for outreach and replies. Proactive nurturing improves conversion (proof → paid) and retention (paid → renew), so it pays back; treat it as part of the same budget as reactive support.

### 4.5 Total cost (ballpark)

**With 200 paying users running daily/near-daily** (4,400 runs/month, thousands of apply jobs/month):

| Item | Low | High |
|------|-----|-----|
| Compute (API, run workers, apply workers, DB, Redis) | $700 | $1,800 |
| LLM (Gemini 2.0 Flash) | $700 | $1,300 |
| Storage / egress / misc | $30 | $80 |
| **Marketing / distribution** | **$1,000** | **$3,000** |
| **Support & success** (proactive: email/CRM nurturing, outreach; reactive: email, chatbot, community) | **$300** | **$1,200** |
| **Total** | **~$2,730** | **~$7,380** |

So **~\$2,700–7,400/month** to run 1,000 users with **200 paying users who run it all the time**, including marketing and support/success. Product + infra **~\$1,400–3,200**; marketing **~\$1,000–3,000**; support & success (proactive nurturing + reactive) **~\$300–1,200**. Per paying user: **~\$14–37/month** all-in.

### 4.6 Team: who does the work

Running this properly usually means **a small team**, not a solo founder doing everything. The **\$5k cost** number above assumes **your time** or part-time/contract (no full salaries). If you need dedicated roles, add people cost.

| Role | What they do | Cost (ballpark) |
|------|--------------|------------------|
| **Product manager** | Roadmap, prioritization, user research, specs, coordination with dev/ops/marketing | \$6k–12k/mo (FT) or \$2k–4k (part-time/contract) |
| **Product dev** | Multi-tenant build, queue, workers, billing, product features, fixes | \$8k–18k/mo (FT) or \$3k–8k (part-time/contract) |
| **Product ops** | Infra, run/apply workers, monitoring, incidents, cost control, reliability | \$6k–12k/mo (FT) or \$2k–5k (part-time/contract) |
| **Product marketing** | Positioning, proof tier → paid conversion, content, campaigns, CRM/email, community | \$5k–12k/mo (FT) or \$2k–4k (part-time/contract) |

**Implication:** A **full team of four** (PM + dev + ops + marketing) at the low end is **~\$25k–35k/month** in people cost. At **1k users, 100 paid, \$10k revenue**, that’s **not enough** — you’d be deep in the red.

So you have two paths:

1. **Lean until scale:** One person (you) or 1–2 people (e.g. you + one dev or one marketing/support) doing most of it, with part-time or contract help. Keep **people cost** in the **\$5k** bucket (e.g. \$0 if it’s your time, or \$2k–5k for one part-time). The **1k users, 100 paid, \$10k / \$5k / \$5k** model assumes this.
2. **Team when revenue supports it:** Add PM, dev, ops, marketing as you grow. Rough rule: **people cost ~\$25–40k/mo** for a small team → you need **~\$50–80k/mo revenue** to cover product + marketing + support + team and still have margin. That’s **~500–800 paid users** at \$100 ARPU, i.e. **~5,000–8,000 reg users** at 10% conversion. So: **the 10k/5k/5k thumb is a “solo or tiny team” stage; a full team needs ~5–8k users and ~500–800 paid** to make sense.

**Summary:** It takes a team of PM, dev, ops, and product marketing to run this properly. The economics in this doc assume you’re in the **lean stage** (your time or 1–2 people). Once you add a full team, you need to **scale to roughly 5–8k users and 500–800 paid** for the numbers to work, or raise/fund the gap.

### 4.7 Indie founder: how one person can support as many users as possible

If you want to stay a **solo indie founder**, build and operate so that **one person can support as many users as possible** without burning out. Below: what to build, what to automate, and what to avoid.

**Product — self-serve everything**

| What to build | Why it reduces your load |
|---------------|---------------------------|
| **Frictionless onboarding** | Clear steps: upload resume → set searches → run. No “talk to us” or custom setup. Users get to value without you. |
| **In-app usage and limits** | Dashboard: runs left, applications this month, queue status. Hard caps per plan (runs/month, apply/day) so users see limits and don’t email “why did it stop?” |
| **Billing and account** | Stripe (or similar) self-serve: upgrade, downgrade, cancel, download invoice. No manual invoicing or “cancel for me.” |
| **Good defaults** | Sensible search defaults, one-click “recommended” config. Fewer “how do I set this up?” questions. |

**Support — deflect and scale**

| What to build / do | Why it reduces your load |
|---------------------|---------------------------|
| **FAQ + chatbot first** | Public FAQ and an AI chatbot that answers “how do I…”, “run failed”, “where’s my resume?” Escalate to you only when the bot can’t answer. Cuts 30–50% of inbound. |
| **Docs and status** | Short docs: “First run,” “Understanding your score,” “Apply failed — what to do.” Status page for outages. Users fix their own issues before emailing. |
| **Email with templates** | Reply with saved replies (macros): “Check your resume format,” “That site is blocked because…,” “Your run is queued.” Aim for 24–48h reply, not same-day; set that expectation. |
| **Community as peer support** | Discord or Reddit where users help each other. You monitor and step in for bugs, abuse, or escalations only. Reduces “how do I” in your inbox. |
| **Async only** | No phone, no live chat, no “book a call.” Everything async (email, community). You batch replies 1–2x per day. |

**Proactive — automate, don’t hand-hold**

| What to build / do | Why it reduces your load |
|---------------------|---------------------------|
| **Email sequences** | Welcome, “Run your first discovery,” “You have X runs left on proof,” upgrade nudge. Automated; no manual outreach per user. |
| **In-app nudges** | “Your run finished — 12 jobs above your score.” “3 applications submitted today.” Fewer “is it working?” emails. |
| **CRM on rules** | Segment by: signed up, first run done, proof runs left, churned. Trigger sequences from segments. No manual “who should I email today.” |

**Ops — automate and monitor**

| What to build / do | Why it reduces your load |
|---------------------|---------------------------|
| **Infra as code** | Workers, queues, DB, scaling defined in code. Redeploy and scale without manual server tweaks. |
| **Alerting** | Alerts when queue backs up, errors spike, or a job source is down. You fix before users flood support. |
| **Managed services** | Use managed DB, managed Redis, hosted queue where possible. Fewer 3am pages and “is the server up?” |
| **Per-user / per-tenant caps** | Rate limits and run/apply caps so one heavy user doesn’t blow cost or block others. Protects you and keeps behavior predictable. |

**Indie marketing in 2026: hub + spoke**

Best practice for one person: **one main site (hub) + a small set of angle-specific product pages (spokes)**. Same product, same signup, different entry points.

| Layer | What it is | Purpose |
|-------|------------|---------|
| **Home** | Main website root (e.g. applypilot.com). Can be a short “what we do” plus links to angle pages and “Start free,” or the main product story if you only want one hero. | Brand, direct traffic, “learn more” from ads or content. |
| **Main product page** | Your default product pitch: what it does, how it works, proof tier, pricing, FAQ. (This can *be* the home, or live at /product or /apply.) | Default destination when you don’t know the visitor’s angle. |
| **Angle pages (spokes)** | Separate URLs, same layout as the main product page but **different hero headline and first screen copy**. E.g. /get-interviews (urgent), /optionality (employed), /apply-at-scale (volume). Same “How it works,” pricing, and **one shared signup**. | Match the message to where they came from (ad, Reddit, SEO) so they see themselves in the copy. |
| **Blog / content** | Articles, guides, “how to get more callbacks,” etc. Each post can link to the main product page or the angle page that fits the topic. | SEO and long-term traffic; one piece of content keeps working. |
| **Shared signup** | One flow (e.g. “Start with proof — free”) from every page. Optional: tag signup with the page they came from (e.g. `?from=optionality`) so you can see which angles convert. | One funnel to build and maintain; you only optimize a few pages. |

So: **yes — main website home page plus a bunch of custom product pages with different angles** is the right pattern. You’re not building a different product per page; you’re changing the **first screen** (and maybe one section) so it speaks to that segment. One person can run **1 home + 1 main product (or home = product) + 3–5 angle pages + a handful of blog posts**. Paid and SEO send people to the page that fits; everyone ends up at the same signup.

**Marketing — content and community, not high-touch**

| What to do | Why it scales for one person |
|------------|------------------------------|
| **Content and SEO** | Blog, guides, “how to get more interviews.” One piece of content can attract many signups over time. No per-lead work. |
| **Community and word of mouth** | Discord, Reddit, testimonials. Users and advocates share; you nurture the community, not each lead. |
| **Paid with simple funnels** | One landing page, one signup flow, simple ad creatives. No custom demos or sales calls. See **docs/landing-page.html** for a concrete example (hero, how it works, proof CTA, pricing, FAQ). |
| **Custom product pages per angle** | You can run **multiple landing pages** for different segments or channels — same product, same signup, different headline and angle. E.g. “Get more interviews in 2 weeks” (unemployed/urgent), “Keep your options open without the grind” (employed/optionality), “Apply to 200 jobs without burning out” (volume). One person can maintain a few variants; paid traffic and SEO can point to the page that fits the audience. |
| **Avoid** | Outbound sales, “book a demo,” custom enterprise deals. Those don’t scale for one person. |

**What to avoid as an indie**

- **No phone or live chat** — Async only.
- **No “we’ll set it up for you”** — Everything self-serve; say no to custom onboarding.
- **No unbounded free tier** — Proof tier has clear run/apply limits so abuse doesn’t blow cost.
- **No promise of same-day reply** — Set “we reply within 24–48h” and batch your support.
- **No custom integrations or one-off features** — Build for the many; say no to “can you add X for me?”

**Rough ceiling for one person**

With the above: **~1,000–3,000 registered users, ~100–300 paid**, is a reasonable range before support, ops, or marketing start to need part-time help. When you hit the ceiling, hire or contract for the **first bottleneck** (often support or ops), not a full team. Stay indie by automating and deflecting first; add help only where you can’t scale yourself.

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
- **Costs:** Product (compute + LLM) **~\$1,400–3,200/month** when 200 paying users run **daily/near-daily**; **marketing** ~\$1,000–3,000/month; **support & success** (proactive: email/CRM nurturing, outreach; reactive: email, chatbot, community) ~\$300–1,200/month. **Total ~\$2,700–7,400/month** — budget for product, marketing, and support. Paying users will run it all the time, so plan for heavy use.
- **User segments**: (1) Unemployed/underemployed — want to win, need proof it works; (2) Employed — want optionality. Both need a try-before-commit proof tier, then premium pricing for heavy use.
- **Pricing**: **Proof tier** (free or nominal) so users get real proof; **Premium \$50–100/month** for heavy use. Assume **paying users run daily** — plan capacity and costs for 20–25 runs/month per paying user.
- **Marketing**: Allocate 20–40% of revenue or \$1,000–3,000/month; content + community + targeted paid; target CAC payback under 12 months. Premium pricing keeps unit economics workable with real acquisition spend and daily use.
- Build order: tenant model + auth → queue + run workers → apply workers → billing and limits.

All numbers are estimates; measure real usage, CAC, and conversion and adjust costs and pricing as you ship.

---

## 9. Is it still worth it? Other considerations

**With the full cost picture (product + marketing + support/success):**

- The **100 paid → $10k rev, $5k cost, $5k profit** thumb still holds *if* you hit ~$100 ARPU and ~10% reg→paid. The $5k cost bucket already includes support & success (proactive + reactive). So **yes, the economics can still be worth it** — you’re not “discovering” that support kills the model; it’s in the number.
- The real question is **execution and risk**. Below are other considerations that affect “worth it” beyond the P&L.

**Other considerations**

| Area | What to think about |
|------|---------------------|
| **Job-board ToS and fragility** | Scraping and automation often violate or sit in a gray area of Indeed, LinkedIn, Glassdoor, etc. They can block IPs, change markup, add CAPTCHAs, or send C&Ds. Your discovery and apply flows depend on surfaces you don’t control. Plan for breakage and legal risk; have a view on “what if one major source goes away.” |
| **Compliance and data** | You’re storing resumes, PII, and sometimes application history. Consider GDPR/CCPA, where you host data, retention, and how you handle “delete my account.” One serious incident can cost more than months of profit. |
| **AGPL and your fork** | You must offer source for the version you run. That’s workable but means your customizations are visible. If you want to sell the company later, some acquirers are skittish about AGPL. Know your long-term intent. |
| **Competition and moat** | Other tools do “apply to more jobs” or “AI resume.” Your moat is full pipeline + many sources + auto-apply. If a well-funded player or a job board builds something similar, you need a plan (niche, speed, community, integration). |
| **Team** | Doing this properly usually means PM, dev, ops, product marketing (see §4.6). The 10k/5k/5k model assumes **lean** (you or 1–2 people). A full team adds **~\$25–40k/mo** people cost → you need **~\$50–80k revenue** (roughly **5–8k users, 500–800 paid**) for it to pencil, or you fund the gap. |
| **Personal capacity and runway** | If you’re lean: building and running this is a full job (product, infra, marketing, support/success). How many months can you run at a loss or low profit? What’s your “quit” threshold (e.g. after 12 months we need $X profit or we stop)? |
| **Support/success load** | Proactive nurturing (email, CRM, outreach) plus reactive (tickets, community) can balloon if you get a lot of confused or angry users. Plan tooling and part-time help *before* you’re overwhelmed; it’s harder to fix once trust is damaged. |
| **Churn and retention** | Job seekers churn when they get a job (success!) or give up. If most paid users leave after 2–3 months, LTV is low and CAC payback gets tight. Think about: “employed, want optionality” as a more stable segment, and product hooks that keep people (e.g. “new jobs weekly,” light ongoing value) even after they’re employed. |
| **Pricing and willingness to pay** | $50–100/mo is meaningful for someone unemployed. Test willingness to pay early; if you can’t get ~$100 ARPU, the 10k/5k/5k model doesn’t hold. Consider a lower tier with caps so you still get *some* revenue from price-sensitive users. |

**Summary**

- **Still worth it on paper:** Full costs (including support & success) are in the model; $5k profit per 1k users at 100 paid is still the target.
- **Worth it in practice** depends on: (1) your tolerance for platform/legal risk, (2) **whether you’re lean (solo/1–2) or building a team** — team adds ~\$25–40k/mo and requires ~5–8k users / 500–800 paid to work, (3) whether you can get and keep ~$100 ARPU and ~10% conversion, and (4) how you’ll handle churn and competition. Nail those before scaling spend.
