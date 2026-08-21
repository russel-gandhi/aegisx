# GxP Sentinel — Build Progress

Tracks Bible/Build-Map Stage 0–7 phase completion. Updated at each checkpoint (phase close-out, wave completion, or major blocker).

**Last updated:** 2026-08-21

---

## ✅ Phase 1 — Environment (Stage 0)
Docker Compose brings Postgres, Qdrant, OPA up healthy from one command; repo structure ready.
- [x] One-command Postgres bring-up
- [x] Repo scaffold + BRANCHING.md
- [x] Qdrant + OPA up healthy
- [x] Persistence proven across stop/start
- [x] **Verified: PASS** (`01-VERIFICATION.md`)

## ✅ Phase 2 — Foundation (Stage 1)
Full schema, seed data, policy layer, API skeleton, orchestration skeleton, frontend shell, WebSocket pattern.
- [x] Postgres schema (27 tables, 21 FKs) + seed data
- [x] All 10 Rego compliance rules (42/42 tests) — 2 real Bible bugs found & fixed
- [x] FastAPI skeleton (`/api/health`)
- [x] LangGraph StateGraph skeleton (11 stub nodes, correct topology)
- [x] Frontend shell (Vite/React/TS/Tailwind v4, 8 routes, React Flow)
- [x] WebSocket echo pattern (`/api/copilot/stream/{session_id}`)
- [x] CI workflow (GitHub Actions)
- [x] **Verified: PASS 8/8** (`02-VERIFICATION.md`)

## ◐ Phase 3 — Intelligence & Retrieval (Stage 2) — IN PROGRESS
MVP-scoped to the hero loop only: A0 Orchestrator → A2 Compliance Agent → C1 Evidence Verifier. (A1 RAG + A3–A6 are deferred v2-territory per ROADMAP.md.)

**Known blocker:** no LLM provider API keys configured (Gemini/DeepSeek/Groq/OpenRouter) — built with honest degraded-mode fallback + respx-mocked wire-contract tests; live LLM quality needs operator-supplied keys to verify.

- [x] Context, research, plan (6 plans / 5 waves)
- [ ] **Wave 1 (03-01)** — LLM router (`llm_router.py`) + Postgres client (`db.py`) — *in progress, resuming after interrupted session*
- [ ] Wave 2 (03-02) — hero tracer: one A2 check → real `AgentFinding` → C1 `calculate_confidence()`
- [ ] Wave 3 (03-03, 03-04 parallel) — A0 classification + fallback; remaining A2 checks + URS seed fixture
- [ ] Wave 4 (03-05) — C1 Critical-review coverage (unit/negative/edge/integration + contradiction fixture)
- [ ] Wave 5 (03-06) — hero-loop integration test + CI gate extension
- [ ] Phase verification

## ⏳ Phase 4 — Evidence & Impact (Stage 3)
NetworkX evidence graph from live Postgres state; Blast Radius traversal; verified finding renders as evidence card.
- [ ] Not started

## ⏳ Phase 5 — Safety & Remediation (Stage 4)
C2 RBAC + injection detection gateway (zero LLM in decision path); C3 write-approval gate (GxP-relevant writes PENDING until human approval); hash-chained audit trail with tamper detection.
- [ ] Not started

## ⏳ Phase 6 — Product Experience (Stage 5)
Command Centre dashboard, Ask GxP Copilot UI with live agent streaming, full Monitor→Investigate→Trust→Remediate→Audit loop walkable unaided.
- [ ] Not started

## ⏳ Phase 7 — Integration & Hardening (Stage 6)
Adversarial-input resilience on the demo path; one-command demo-state reset.
- [ ] Not started

## ⏳ Phase 8 — Freeze (Stage 7)
No new features — P0 bug fixes only, visual polish, timed rehearsal against 7-minute demo script, backup recording, final Bible-reconciliation review (SENT-7-05), submission packaging.
- [ ] Not started

---

## Open cross-phase items
- **SENT-7-05 Bible reconciliation** accumulating deviations from phases 2–3 (Rego `time.diff`/column fix, ALCOA 9-vs-8 constant, DeepSeek/OpenRouter model-string corrections, Gemini key-env-var alias) — review at Phase 8 per plan.
- **LLM provider API keys** — operator needs to supply `GEMINI_API_KEY` / `DEEPSEEK_API_KEY` / `GROQ_API_KEY` / `OPENROUTER_API_KEY` in `.env` before live-quality verification of A0/A2 is possible.
