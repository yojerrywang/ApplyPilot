# ApplyPilot Roadmap (2026)

This roadmap is synced with `docs/SAAS-PLAN-1M-ARR.md`.
It defines what we ship, in order, to reach **$1M ARR** with sustainable margins.

## Strategic Objective

Build an outcomes-first job search SaaS with clear spend control:

- Target: **$1,000,000 ARR**
- Gross margin: **>= 65%** (company level)
- Active paid users at target: **~400** (blended ARPU around `$210/month`)
- Core promise: **more interviews, faster, with less effort and controlled spend**

## Product Positioning

ApplyPilot is not "mass apply for volume."
It is a multi-track, automated pipeline that optimizes for:

1. Match quality (targeting)
2. Reliable daily execution (throughput)
3. Submission quality and verification
4. Measurable funnel outcomes (callbacks, screens, interviews)

## Documentation Lifecycle

Use this order for every strategic or execution change:

1. `ROADMAP.md` defines strategic direction.
2. `BACKLOG.md` defines executable tickets with acceptance criteria.
3. Code + tests implement the ticket.
4. `CHANGELOG.md` records merged behavior changes.
5. `README.md` documents user-facing behavior that exists now.

Source-of-truth precedence:
- code + `CHANGELOG.md` > `README.md` > `BACKLOG.md` > `ROADMAP.md`

## KPI Scorecard and Guardrails

North-star KPI:
- Interview outcomes per verified submission cohort.

Operating KPIs:
- Verified submissions per user per week
- Callback rate
- Recruiter screen rate
- Interview rate
- Apply success rate (submitted vs attempted)
- Cost per verified submission
- Cost per callback
- Time-to-first-callback

Business guardrails:
- CAC payback <= 8 weeks
- LTV:CAC >= 3.0
- Refund rate <= 5%
- Loaded COGS target `$60-$75/user/month` (red line at `$85+`)

## Roadmap Phases

### Phase 0: Current Baseline (Completed / In Progress)

Status summary:
- Core pipeline is functional.
- Daily multi-track harness exists (`scripts/applypilot-daily.sh`).
- Tailoring quality and apply-result parsing were recently hardened.
- End-to-end testing and SaaS economics controls are still incomplete.

Exit criteria:
- Baseline reliability metrics available per run.

### Phase 1: Cost and Reliability Controls (Weeks 1-3)

Goal:
- Prevent cost runaway and increase unattended run reliability.

Deliverables:
- Hard scoring/apply quotas per track/day.
- Discovery throttle enforcement by config.
- Budget-aware runner output (daily cost and volume summary).
- Retry/backoff/timeout hardening for long runs.

Exit criteria:
- Predictable max daily spend.
- >= 95% run completion without manual intervention.

### Phase 2: Outcome Instrumentation (Weeks 4-6)

Goal:
- Measure real job-funnel performance, not just pipeline activity.

Deliverables:
- Funnel attribution (`submitted -> callback -> screen -> interview`) by role and source.
- Sub-Epic: Inbox Scanning / Email Integration to close the telemetry loop autonomously (detect recruiter emails).
- Weekly cohort reporting and trend views.
- Quality telemetry for failed/invalid submissions.

Exit criteria:
- Every submission tied to a track + source + cohort.
- Weekly callback and screen rates visible in one report reliably (without user self-reporting).

### Phase 3: Onboarding and Multi-Track Data Model (Weeks 7-10)

Goal:
- Improve targeting quality through better candidate data and role-specific tailoring.

Deliverables:
- Master resume intake flow.
- Clarifying-question enrichment workflow.
- Role-track configuration (`3-5` tracks) with constrained fact reuse.
- Claim-to-evidence and formatting quality gates before apply.

Exit criteria:
- Lower hallucination/format failure rate.
- Higher callback rate versus baseline cohorts.

### Phase 4: SaaS Foundation & API-First Apply (Weeks 11-14)

Goal:
- Move from single-user local workflow to multi-tenant SaaS primitives, while rescuing gross margins from Playwright cloud-compute costs.

Deliverables:
- Auth + tenant model (`tenant_id` plumbing).
- Hosted database and worker architecture.
- Pivot mass-submissions to API-First Apply Engine (direct to ATS endpoints). Reserve browser automation for Power tier.
- Billing with weekly plans and usage-based overage.
- Introduce `Alumni Mode` ($5/mo) to monetize successful churn.
- Budget policies and per-tenant usage limits.
- Backlog mapping: `BACKLOG.md` tickets `#19-#22`.

Exit criteria:
- One hosted environment can support multiple isolated users safely.
- Billing and usage controls enforce margin guardrails.

### Phase 5: Growth Loop and Referral Engine (Weeks 15-18)

Goal:
- Reduce CAC and create compounding acquisition.

Deliverables:
- Double-sided referral credits with fraud controls.
- Channel attribution and CAC by source.
- In-product activation nudges (first successful run, first verified submission).

Exit criteria:
- Referral-driven share of new paid users >= 25% (target by month 6).
- CAC for referred users materially lower than paid channels.

### Phase 6: Managed Tier and Reliability Ops (Weeks 19-24)

Goal:
- Support heavy users profitably while improving trust.

Deliverables:
- Priority processing / managed queue for Power users.
- SLA-backed support workflows.
- Automatic rollback/kill-switch on high error or spend spikes.

Exit criteria:
- Heavy users remain margin-positive.
- Support burden per paying user remains inside budget.

## Seasonal GTM Operating Plan

Use seasonal targets instead of a flat monthly plan:

- Jan-Jun: prioritize growth (`~95-120` new paid users/month).
- Jul-Sep: prioritize efficiency (`~90-105` new paid users/month).
- Oct-Dec: prioritize retention and CAC discipline (`~40-85` new paid users/month).

Execution notes:
- Build an active-user buffer before Q4.
- Shift Q4 budget from paid acquisition to referral and retention loops.

## Risks and Mitigations

1. Runaway LLM spend from high discovery/scoring volume
- Mitigation: hard quotas, budget gates, overage pricing.

2. High churn from job-seeker lifecycle dynamics
- Mitigation: weekly plans, optionality segment, retention loops.

3. Support load growth from automation edge cases
- Mitigation: tiered SLA, diagnostics, managed tier pricing.

4. Weak callback outcomes despite high throughput
- Mitigation: strict targeting improvements and channel-level ROI pruning.

## Decision Rule for Scaling

Scale acquisition only when the last 4 weeks all hold:

1. Gross margin >= 65%
2. Callback trend is flat-to-up
3. CAC payback <= 8 weeks
4. Support/refund metrics are inside guardrails
