# ApplyPilot SaaS Plan to $1M ARR

## 1) Goal
Build a sustainable SaaS business that reaches **$1,000,000 ARR** with healthy gross margins while supporting heavy users.

Core promise:
- **More interviews, faster, with less effort and controlled spend**
- Not "mass apply for volume"; outcome is callback/interview lift

## 2) Business Model
### 2.1 Pricing (weekly billing + usage caps)
- **Starter**: `$29/week`
  - Includes `20` verified auto-submissions/week
  - Up to `2` role tracks
- **Pro**: `$59/week`
  - Includes `60` verified auto-submissions/week
  - Up to `5` role tracks
- **Power**: `$119/week`
  - Includes `150` verified auto-submissions/week
  - Browser-driven (Playwright) submit fallback for complex forms
  - Priority queue/support
- **Alumni (Monetize Churn)**: `$5/month`
  - Zero applies. Weekly digest of top 3 high-ROI jobs to tempt them back into the active funnel.
- **Overage**: `$0.85` per verified submission

Why weekly:
- Better fit for job-search cycles (2-3 week feedback loop)
- Lower trial barrier for unemployed users
- Faster payback and tighter spend control

### 2.2 Discount/Access policy
- Offer a temporary "laid-off relief" entry path (short-term discounted Starter) with hard usage caps.
- Keep full automation and high caps in paid tiers only.

## 3) Unit Economics Targets
Use strict targets, then tune pricing/caps to stay above margin floors.

### 3.1 Gross margin targets
- **Company target gross margin**: `>= 65%`
- **Plan floor**:
  - Starter: `>= 65%`
  - Pro: `>= 65%`
  - Power: `>= 60%`

### 3.2 Cost controls (must-have)
- Daily role/run budgets and max scoring quotas
- No cover-letter generation by default
- `min_score >= 8` for tailoring/apply spend
- Discovery throttles (`results_per_site`, query limits, title excludes)
- Hard per-user/per-day apply caps
- Overage billing for heavy usage

### 3.3 COGS model (loaded)
Loaded COGS includes:
- LLM spend (OpenAI scoring/tailoring + Claude apply agent)
- Infrastructure (Railway compute/db/storage/logging)
- Support + refunds + payment processing reserve

*Crucial Architecture Pivot for COGS*: To hit our 65%+ margin target at scale, Phase 4 must transition away from Playwright-driven browser automation (expensive compute, highly brittle) toward an **API-first Apply Engine** (integrating directly with ATS endpoints like Greenhouse/Lever). We reserve the Playwright fallback exclusively for `$119/week Power` users on complex Workday forms.

Planning number until real telemetry is stable:
- **Blended loaded COGS target**: `$60-$75/user/month`
- **Red line**: if loaded COGS rises above `$85/user/month` for 2 consecutive weeks, auto-tighten limits and/or reprice.

## 4) Revenue Math to $1M ARR
- `$1,000,000 ARR` = `$83,333 MRR`
- At blended ARPU of about `$210/month`, paid active users required:
  - `83,333 / 210 ~= 397` → **~400 paid actives**

Steady-state rule of thumb:
- Maintain **~400 active paid users**
- Replace churn + add growth users monthly (see seasonality model)

## 5) Seasonality Model
Hiring demand and conversion vary by season; treat acquisition targets as seasonal, not flat.

### 5.1 Monthly acquisition targets (steady-state around 400 actives)
- **Jan-Jun**: add `95-120` new paid/month
- **Jul-Sep**: add `90-105` new paid/month
- **Oct-Dec**: add `40-85` new paid/month (higher churn, lower hiring velocity)

### 5.2 Operating approach by season
- **Q1-Q2**: scale acquisition, expand role tracks, optimize conversion
- **Q3**: efficiency and targeting focus amid higher competition
- **Q4**: retention + referral heavy, reduce paid CAC burn, protect margin

## 6) CAC, LTV, and Payback Guardrails
Track contribution-margin LTV, not top-line revenue only.

Targets:
- **CAC payback**: `<= 8 weeks`
- **LTV:CAC**: `>= 3.0`
- **Refund rate**: `<= 5%`
- **Support cost/user/month**: within planned envelope (track by tier)

If any metric breaches threshold for 2 straight weeks:
- tighten quotas,
- reduce low-quality channels,
- increase price floor or reduce included usage,
- route heavy users to overage/managed tier.

## 7) Referral System (for CAC reduction)
Implement a simple double-sided referral loop:
- Referrer gets credit after referred user completes first paid week.
- Referred user gets one-week discount or credit.
- Fraud controls: payment method uniqueness, device/IP checks, delay unlock until successful charge.

Referral KPI targets:
- `>= 25%` of new paid users via referral by month 6
- Referred-user CAC at least `40%` lower than paid channels

## 8) Product KPI Scorecard
North star is interview outcomes. To accurately measure this, we cannot rely on users voluntarily reporting success. We must build an **Inbox Scanner** (OAuth or Chrome Extension) to detect inbound recruiter emails, closing the telemetry loop automatically.

### 8.1 Funnel KPIs
- Verified submissions/user/week
- Callback rate (callbacks / verified submissions) via Inbox Scanner
- Recruiter screen rate
- Interview rate
- Offer rate

### 8.2 Efficiency KPIs
- Cost per verified submission
- Cost per callback
- Cost per interview
- Time from signup to first callback

### 8.3 Reliability KPIs
- Apply success rate (submitted vs attempted)
- Invalid/failed submission rate
- Automation error rate
- Median support response time

## 9) Positioning
Primary value proposition:
- "Autonomous job search for ICs: daily role-matched applications with measurable interview lift."

Proof promise:
- Verified submissions + funnel tracking by role/channel
- Spend controls and transparent logs
- Measurable 2-3 week cohort reporting

## 10) 90-Day Execution Plan
### Phase 1 (Weeks 1-3): Cost + reliability baseline
- Ship budget controls in runner and scoring quotas
- Enforce apply caps and overage accounting
- Add per-user cost and token telemetry

### Phase 2 (Weeks 4-6): Outcome instrumentation
- Cohort dashboard: submitted -> callback -> screen -> interview
- Role/channel attribution and weekly reports
- Referral MVP

### Phase 3 (Weeks 7-10): Conversion and retention
- Improve onboarding (resume intake + enrichment Q&A)
- Better role-track targeting and match quality
- Launch weekly billing tiers and pricing gates

### Phase 4 (Weeks 11-13): GTM hardening
- Channel tests (content/community/paid)
- CAC and payback optimization
- Publish proof case studies and benchmark reports

## 11) Risks and Mitigations
- **Risk**: runaway LLM costs from unbounded discovery/scoring
  - **Mitigation**: hard quotas, query limits, budget-aware schedulers
- **Risk**: cloud browser scaling kills gross margins
  - **Mitigation**: pivot to API-first apply engine; reserve Playwright for Power tier only.
- **Risk**: "Ghosting" on telemetry (users don't report interviews)
  - **Mitigation**: Inbox integration to parse recruiter emails automatically.
- **Risk**: high churn after users get jobs
  - **Mitigation**: Churn is a feature, not a bug. Monetize it via `$5/mo Alumni Mode` (opportunistic tracking) instead of fighting to keep them in the $59/wk tier.
- **Risk**: support load from heavy users
  - **Mitigation**: tiered support SLA, managed tier pricing, in-product diagnostics
- **Risk**: poor channel quality hurts callback rate
  - **Mitigation**: source-level ROI tracking and strict pruning

## 12) Decision Rule (simple)
Scale only when all are true for 4 consecutive weeks:
- Gross margin `>= 65%`
- Callback rate trend is stable or improving
- CAC payback `<= 8 weeks`
- Support/refund metrics inside threshold
