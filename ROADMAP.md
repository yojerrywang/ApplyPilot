# ApplyPilot Product Roadmap & PM Framework

This document outlines the high-level Epics (major milestones) for the ApplyPilot project and defines the strict Product Management framework used to orchestrate AI Developer Agents.

---

## 🧭 The Documentation Lifecycle (End-to-End)

To prevent AI hallucination and maintain a pristine codebase, all project momentum flows through a strict documentation lifecycle:

1. **`ROADMAP.md` (The "Why")**: Defines the massive, overarching Epics and the strategic vision. It is the north star.
2. **`BACKLOG.md` (The "What")**: The Roadmap Epics are broken down into specific, actionable P0/P1/P2/P3 tickets here. The AI pulls from this menu to execute localized Sprints.
3. **`CHANGELOG.md` (The "Done")**: When a Backlog ticket is completed via a git commit, it is recorded here so the history of shipped features is immutable.
4. **`README.md` (The "How")**: If a completed feature changes how a human interacts with the product (new CLI flags, config schemas, etc.), the README is updated to reflect the new reality.
5. **Feedback Loop**: As the `README.md` capabilities expand and users request new features based on the current product, those requests inform the next massive Epic in the `ROADMAP.md`.

*Note: You can instantly trigger steps 3, 4, and 5 by using the `/save_atp` custom workflow command.*

### ✅ Documentation Governance (Source of Truth Rules)

Use this order for every feature or fix:

1. **Plan in `ROADMAP.md`** (if strategic scope changes)
2. **Define execution in `BACKLOG.md`** (ticket + acceptance criteria)
3. **Implement code + tests**
4. **Record shipped behavior in `CHANGELOG.md`**
5. **Reflect user-facing behavior in `README.md`**
6. **Feed learnings back into `ROADMAP.md`** (new constraints, priorities, or epics)

Hard rules:
- `README.md` must describe only what is currently implemented.
- `CHANGELOG.md` entries must map to merged commits, not planned work.
- `BACKLOG.md` is the execution contract for AIs (no undocumented scope expansion).
- If docs conflict, precedence is: `CHANGELOG.md` + code > `README.md` > `BACKLOG.md` > `ROADMAP.md`.

---

## 🤖 AI Product Management Principles

When acting as the PM for the AI coding assistants on this repository, ruthlessly enforce these four rules:

1. **The "Definition of Done" (DoD) is Absolute**: AIs will rush to declare victory if the code compiles. You must provide strict Acceptance Criteria for every Backlog ticket (e.g., "Prove it works by writing a test suite that processes 10 fake DB rows").
2. **Force "Tracer Bullets" First**: Never let an AI write 500 lines of brittle automation code blindly. Force the AI to build a tiny, end-to-end slice of functionality (a Tracer Bullet) and prove it works before authorizing the full feature build-out.
3. **Maintain the Menu**: Do not give open-ended prompts. Say: *"Look at BACKLOG.md, read the first two P1 items, tell me your architecture plan, and wait for my approval before coding."*
4. **Instrument Telemetry**: Always demand the AI builds observability into the core systems (e.g., tracking the exact % of jobs where the LLM formatting fails). If a metric dips below your threshold, it becomes a P0 ticket for the next Sprint.

---

## 🗺️ Current Roadmap (Epics)

### 🟢 Epic 1: MVP Pipeline Stabilization (Completed)
- **Goal**: Fortify the entire 6-stage core pipeline against rate-limits, LLM hallucinations, and config tech-debt.
- **Status**: Shipped. (Data ingestion stabilized, OpenRouter LLM integrated, P0 backlog fixed).

### 🟡 Epic 2: Autonomous Application Testing & Hardening (In Progress)
- **Goal**: Ensure the Claude Code/Playwright auto-submission browser module is bulletproof, handles edge-cases, and successfully submits fake or real applications without human intervention.
- **Key Deliverables**: 
  - Tracer bullet tests against dummy job forms.
  - CAPTCHA failure rate telemetry and graceful aborts.
  - Form field matching stabilization.

### 🔴 Epic 3: User Authentication & Multi-Tenant SaaS (Planned)
- **Goal**: Migrate the single-user local SQLite architecture into a production-ready PostgreSQL multi-tenant backend with user accounts and session tokens.
- **Key Deliverables**:
  - `tenant_id` plumbing across all DB queries.
  - Stripe billing integration tiers (Proof vs Premium).
  - API key provisioning.

### 🔴 Epic 4: Advanced Telemetry & Dashboard (Planned)
- **Goal**: Give the user a beautiful, live-updating view of their funnel (Discovered -> Scored -> Tailored -> Applied -> Interviewing).
- **Key Deliverables**: 
  - Frontend dashboard enhancement.
  - Pipeline conversion rate tracking.
