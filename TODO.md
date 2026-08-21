# AegisX AI — Build Progress

Tracks Bible/Build-Map Stage 0–7 phase completion. Updated at each checkpoint (phase close-out, wave completion, or major blocker).

**Last updated:** 2026-08-21

## ▶ Next up

Phase 3 is closed and verified. Next: start **Phase 4 — Evidence & Impact (Stage 3)** — NetworkX evidence graph from live Postgres state, Blast Radius traversal, verified finding renders as an evidence card. No context/plan artifacts exist yet for Phase 4; the normal GSD flow is discuss-phase → plan-phase → execute-phase.

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

## ✅ Phase 3 — Intelligence & Retrieval (Stage 2)
MVP-scoped to the hero loop only: A0 Orchestrator → A2 Compliance Agent → C1 Evidence Verifier. (A1 RAG + A3–A6 are deferred v2-territory per ROADMAP.md, though minimal-but-real fan-out targets were built in Wave 3.)

**Resolved:** LLM provider API keys (Gemini/DeepSeek/Groq/OpenRouter) are now configured in `.env`; local Postgres auth also fixed (`.env` wasn't being loaded — see `ee9ced5`).

- [x] Context, research, plan (6 plans / 5 waves)
- [x] **Wave 1 (03-01)** — LLM router (`llm_router.py`) + Postgres client (`db.py`), 47/47 tests passing. Found & fixed 2 real Windows asyncpg/pytest event-loop bugs; recorded 3 Bible deviations (deepseek-reasoner retired, openrouter model string, Gemini key-env alias).
- [x] **Wave 2 (03-02)** — hero tracer: one A2 check → real `AgentFinding` → C1 `calculate_confidence()`, 50/50 passing.
- [x] **Wave 3 (03-03, 03-04 parallel)** — A0 real classifier + 2000ms fallback, A1/A3-A6 minimal-but-real specialists; A2 full three deterministic checks + URS seed fixture. 83/83 passing after merge (resolved a real test-assertion conflict between the two plans). Found & fixed a latent `opa_client.py` datetime-serialization bug (Deviation 8).
- [x] **Wave 4 (03-05)** — C1 Critical-review coverage: 20 new unit/negative/edge/integration tests (CLAUDE.md Rule 6), all 10 Rego rules exercised, EVID-02 contradiction fixture against live Postgres+OPA. Fixed the `build_opa_payload()` multi-input-key defect (`.planning/WINDOWS.md` id 1, now closed). 103/103 passing.
- [x] **Wave 5 (03-06)** — hero-loop integration test: one real `compiled_graph.ainvoke()` on the literal hero query, driving A0→A2→C1 against live Postgres + live OPA (LLM providers mocked); keyless-run fallback proven closes the loop via deterministic fallback attribution. 9 new tests, 112/112 passing.
- [x] **Phase verification: PASS 9/9** (`03-VERIFICATION.md`) — requirements ORC-02, ORC-03, EVID-01, EVID-02, EVID-04 all confirmed satisfied by live-tested behavior, not just present code; deterministic-first boundary confirmed intact (zero `call_llm` references in `c1_verifier.py`).

## ◐ Phase 4 — Evidence & Impact (Stage 3) — NEXT
NetworkX evidence graph from live Postgres state; Blast Radius traversal; verified finding renders as evidence card.
- [ ] Context, research, plan
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
