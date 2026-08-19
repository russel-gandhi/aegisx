# GxP Sentinel

## What This Is

GxP Sentinel is an agentic AI co-pilot for always-on, audit-ready GxP IT system management, built as a 20-day hackathon project. It lets a QA/Compliance or IT System Manager user ask natural-language questions about a GxP system's audit readiness, and answers with AI-generated findings that are independently, deterministically verified against real database records and OPA/Rego policy evaluation before being trusted — never presented as unverified LLM output.

## Core Value

**Deterministic evidence verification (C1) is the thesis of the product.** The winning idea is not "AI agents for GxP" — it's "we use AI to investigate, but we never blindly trust AI: every important conclusion is independently verified with deterministic evidence." The minimum viable proof of this is the demo loop: user asks "Is GXP-MFG-DEMO-01 audit ready?" → A0 routes → A2 Compliance Agent produces a claim (e.g. "URS traceability incomplete") → C1 Evidence Verification retrieves real evidence (URS record, test case, execution status), runs the deterministic rule check (e.g. ANNEX11-S4-DOC-001) against real DB/OPA state, and returns a VERIFIED (or INSUFFICIENT_EVIDENCE) finding with confidence. Remove C1 and the product becomes "a chatbot that reads compliance documents" — that destroys the differentiation. Everything else is supporting infrastructure around this hero loop.

## Business Context

- **Customer**: Hackathon judges evaluating a demo; longer-term, GxP IT System Managers, QA/Compliance staff, and Auditors at regulated life-sciences companies
- **Revenue model**: N/A — hackathon project, no monetization in scope
- **Success metric**: Judges see and believe the Finding → Evidence → Verification loop is real (backed by actual DB/OPA state, not LLM narrative) — plus, per the demo hierarchy, Blast Radius and Controlled Remediation working live
- **Strategy notes**: See `GxP-Sentinel-Project-Bible-v6.md` Section 16 (demo script) and `Sentinel-Build-Map.md` for the original stage/ticket breakdown (GSD roadmap will be independently derived, not a direct 1:1 mapping, per project decision)

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] User can ask a natural-language audit-readiness question about a GxP system and get a routed response (C2 Gateway → A0 Orchestrator → relevant A1–A6 agents)
- [ ] A2 Compliance Agent (at minimum) produces an `AgentFinding` claim from real system state
- [ ] C1 Evidence & Grounding Verifier fans in on findings, retrieves real DB record(s) + OPA evaluation result, and returns VERIFIED or INSUFFICIENT_EVIDENCE with a confidence score — never trusting the LLM's claim on its own
- [ ] OPA/Rego sidecar evaluates at least the rule(s) needed for the hero demo path (e.g. ANNEX11-S4-DOC-001) via `evaluate_opa_policy()`, with a documented `python_fallback_rules()` stub
- [ ] Verified finding is rendered showing CLAIM / EVIDENCE / RULE / DETERMINISTIC CHECK / CONFIDENCE, sourced from server-trusted data (not LLM-generated UI)
- [ ] Blast Radius: NetworkX evidence graph built from live Postgres state, traversable from a verified finding to affected tests/controls/systems
- [ ] Controlled Remediation: A7 Remediation Agent synthesizes an `ActionProposal`/CAPA narrative from already-verified findings; C3 Action Gateway routes it and holds GxP-relevant writes `PENDING` until human approval
- [ ] C2 Policy & Safety Gateway enforces RBAC (IT System Manager / QA-Compliance / Auditor) and injection detection deterministically (no LLM in the decision path) on the request path
- [ ] Hash-chained append-only audit trail records the finding/verification/approval events, with `verify_chain()` available
- [ ] Environment stands up via `docker-compose up -d postgres qdrant opa` and the FastAPI/Vite services per the Bible's fixed ports

### Out of Scope

- Full 7+ page frontend polish, agent visualizations, FSM animations, Trust Centre, ALCOA+ scoring UI, guided demo mode — Tier 3 polish per the user's own demo hierarchy; only build after Tier 1 (verification loop) and Tier 2 (Blast Radius, Remediation) are solid
- Multi-provider LLM routing across all 6 agents (Gemini/DeepSeek/Groq/OpenRouter) as a v1 requirement — a single working provider path is enough to prove the C1 loop; full router is nice-to-have, not core value
- Supplier intelligence, inspection simulator — explicitly called out by the user as "nobody notices," deferred
- Full A1, A3–A6 agent breadth (System Knowledge/RAG, Risk, Change, Incident, Access) beyond what's needed to support the hero finding — only A2 Compliance is required for the minimum killer demo; others are Tier 2+/expansion
- Direct 1:1 mapping of ROADMAP.md phases onto Sentinel-Build-Map.md's SENT-\<stage\>-\<number\> tickets — user chose to let GSD re-derive phases independently from requirements; Build-Map remains a reference, not the roadmap source

## Context

- This repository is currently a specification vault (Obsidian vault), not a codebase — no application source, build tooling, or tests exist yet
- Four governing documents exist and inform all planning: `GxP-Sentinel-Project-Bible-v6.md` (source of truth, ~3,300 lines, Sections 1–17), `Sentinel-Build-Map.md` (original Stage 0–7 ticket breakdown, reference only per this project's phase-derivation decision), `GSD_Core_Reference.md` (GSD workflow reference), `Refined_MetaPrompt.md` (planning meta-prompt with evidence-tagging discipline)
- Architecture is fixed by the Bible and must not be redesigned: deterministic-first isolation of generative models from compliance/RBAC/injection decisions (Section 1.3 decision table is binding); LangGraph request flow `C2 → A0 → [A1…A6 parallel via Send] → C1 → A7 → C3`
- Fixed local ports: Postgres 5432, Qdrant 6333, OPA 8181, FastAPI 8000, Vite frontend 3000
- 15 mandatory agentic-coding rules exist in Bible Section 16.11 (see CLAUDE.md) governing how Claude Code should work in this repo — explicit contracts before implementation, tests with implementation, stronger review for Critical-labeled components (C1, C2, C3, hash-chain, Rego rules, Blast Radius, ALCOA+, evidence graph), no silent scope expansion, no generated regulatory citations (must come from Bible Section 14's citation map)

## Constraints

- **Timeline**: 20-day hackathon, full runway available as of project start — but scope must stay demo-hierarchy-ordered (Tier 1 before Tier 2 before Tier 3) so a credible demo exists at any cut point
- **Architecture**: Deterministic-first is non-negotiable — no LLM may ever evaluate a compliance threshold, RBAC decision, or prompt-injection judgment; those run in Python, Rego, or NetworkX only (Bible Section 1.3)
- **Source of truth**: When any planning artifact disagrees with `GxP-Sentinel-Project-Bible-v6.md`, the Bible wins; drift must be reconciled explicitly
- **Regulatory citations**: Annex 11 / 21 CFR 11 / ICH Q9 citations must come from the Bible's Section 14 citation map, never from model recall
- **Critical-path review**: C1, C2, C3, hash-chain, Rego rules, Blast Radius, ALCOA+, and the evidence graph require unit + negative + edge-case + integration test coverage, not a smoke test

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Full v1 build per the Bible (not a reduced demo slice) | User chose to plan the full system, ordered by the Tier 1/2/3 demo hierarchy so any cut point still demos well | — Pending |
| GSD roadmap phases re-derived independently from REQUIREMENTS.md rather than mapped 1:1 onto Sentinel-Build-Map.md stages | User's explicit choice; Build-Map remains a reference for ticket-level contracts | — Pending |
| Skip GSD's domain research step | Stack and architecture are already fully decided and justified in the Bible; research would be redundant | — Pending |
| Core value = C1 Evidence Verification + Finding→Evidence→Verification loop, not the full agentic system | User's explicit differentiation thesis: "we use AI to investigate, but we do not blindly trust AI" | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Business Context check — customer, revenue model, success metric still accurate?
4. Audit Out of Scope — reasons still valid?
5. Update Context with current state

---
*Last updated: 2026-08-19 after initialization*
