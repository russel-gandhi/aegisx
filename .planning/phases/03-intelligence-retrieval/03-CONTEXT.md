# Phase 3: Intelligence & Retrieval - Context

**Gathered:** 2026-08-21
**Status:** Ready for planning
**Mode:** Auto-generated (operator away for several hours; user-facing/architectural phase, but scope is already tightly bounded by ROADMAP.md's MVP framing — grey areas resolved by Claude's discretion per explicit prior instruction to keep executing autonomously)

<domain>
## Phase Boundary

A real query enters A0, is classified and routed, fans out to real (non-stub) agents, and C1 produces a non-trivial confidence score sourced from real DB + OPA state — the backend hero loop is real, not mocked. (Build-Map Stage 2, Gate: "a real query enters A0, fans out to real (non-stub) A1–A6, C1 produces a non-trivial confidence score sourced from real DB + OPA state.")

**ROADMAP.md scopes this phase as MVP** (`**Mode:** mvp`) to exactly: A0 Orchestrator (SENT-2-01), A2 Compliance agent (SENT-2-02, highest demo visibility), and C1 real wiring (SENT-2-12, Critical review). Requirements for this phase: **ORC-02, ORC-03, EVID-01, EVID-02, EVID-04** only.

A1 (System Knowledge/RAG), A3–A6 (Risk/Change/Incident/Access), and the Qdrant ingestion/hybrid-retrieval/fusion/reranking/parent-context stack (SENT-2-03 through SENT-2-11) are explicitly **v2-territory retained as context, not new v1 requirements** per ROADMAP.md. Do not build these as first-class deliverables in this phase — the hero loop only needs A0 → A2 → C1 to work end to end. If a plan needs a placeholder for A1/A3–A6 so A0's `Send` fan-out and `route_specialists` can be exercised meaningfully, those four agents should exist as genuinely-real-but-minimal LLM-backed agents (not fake stubs — the Bible forbids stub agents in this phase's gate), but their `AgentFinding` quality bar is lower than A2's.

</domain>

<decisions>
## Implementation Decisions

### Credential gap — LLM provider API keys (BLOCKING for live execution, not for code correctness)

No LLM provider API keys (Gemini, DeepSeek, Groq, OpenRouter — Bible Section 8's multi-provider router) are configured anywhere in this repo. `.env.example` only has Postgres credentials. This is a genuine gap only the operator can close — a fabricated or guessed key is not an option.

**Resolution:** Build the multi-provider LLM router and every agent as fully real, production-shaped code — real HTTP calls to real provider endpoints, real Pydantic response parsing, no `if DEMO_MODE: return canned_response` shortcuts. Every agent's Bible-mandated degraded-mode fallback (abstain / downgrade model / rule-only, per CLAUDE.md and Bible Section 1.3/agent contracts) is treated as first-class behavior, not an afterthought — because without live keys, the degraded path is the only path this session can prove end-to-end. `.env.example` gains placeholder entries (`GEMINI_API_KEY=`, `DEEPSEEK_API_KEY=`, `GROQ_API_KEY=`, `OPENROUTER_API_KEY=`) with clear comments that they are required for live LLM calls and the system runs in explicit degraded/abstain mode without them.

Plans MUST include a live-mocked-HTTP test path (e.g. `respx`/`httpx` mock transport or an injectable HTTP client) proving the real request/response contract against each provider's actual API shape, and a separate degraded-mode test proving the fallback fires cleanly (no exception, explicit `INSUFFICIENT_EVIDENCE` or documented abstain marker) when no key is present or the call fails. This satisfies "real, not mocked" for the code path while being honest that a live network call to a paid LLM API was not exercised in this autonomous session.

**Human follow-up required:** obtain and set `GEMINI_API_KEY` / `DEEPSEEK_API_KEY` / `GROQ_API_KEY` / `OPENROUTER_API_KEY` in `.env`, then re-run the phase's live-LLM verification steps (flagged in each plan's `<human-check>` or deferred verification) to confirm real classification/generation quality, not just wire-format correctness.

### A0 Orchestrator scope
- Intent classification via Gemini 2.5 Flash (per Bible), fan-out via `Send` to a subset of A1–A6.
- 2000ms timeout fallback to the full `["A1".."A6"]` set is a hard, explicitly-tested requirement (ROADMAP success criterion 1) — implement with a real async timeout (e.g. `asyncio.wait_for`), not a sleep-based approximation.

### A2 Compliance Agent scope
- Highest demo visibility; must produce a real `AgentFinding` from live DB state via the three named verification functions (`verify_urs_approved`, `verify_periodic_eval_current`, `verify_test_traceability`) matching the Bible's Section 2 schema.
- These three functions are themselves deterministic DB queries — the LLM's role is synthesis/narrative framing of findings already computed deterministically, consistent with Bible Section 1.3 (LLM never evaluates the compliance threshold itself).

### C1 Evidence & Grounding Verifier scope
- Critical-review ticket (SENT-2-12). Fans in from A2 (and whichever other agents ran), calls `calculate_confidence()` against the real DB record and real OPA evaluation — never a mock of either.
- Must demonstrably return `INSUFFICIENT_EVIDENCE` when an LLM claim contradicts DB/OPA truth — this contradiction case needs an explicit, engineered test fixture (a claim that says the opposite of what the seeded data / Rego evaluation shows).
- Per CLAUDE.md Rule 6, C1 needs unit + negative + edge-case + integration coverage, not a smoke test — same bar as phase 2's Rego bundle.

### Resolved: RESEARCH.md Open Questions (decided autonomously, operator away)

**Open Question 1 — `verify_urs_approved` positive-path fixture:** Seed one additional minimal `documents` row with `doc_type='URS'` in an additive seed-data task (extends, does not replace, phase 2's `infra/postgres/seed/001_seed.sql` — follow the same idempotent `INSERT ... ON CONFLICT` style already established there). A Critical-adjacent agent (A2 feeds C1, a Critical ticket) should not ship with an untested positive path when a one-row fixture closes the gap cheaply.

**Open Question 2 — ALCOA 8-vs-9 constant in `calculate_confidence()`:** Use **9**, not the Bible's literal `8`. Rationale: CLAUDE.md itself states "ALCOA+ 9-dimension scoring (16.12)" as a settled project fact, and `app.schemas.ALCOAScore` (already shipped, phase 2) has 9 boolean fields — both independent sources agree on 9, against the Bible's one stale `8` literal in the `calculate_confidence()` formula. Implement as `(9 - alcoa_score) * 10` where `alcoa_score` is the count of true fields in the 9-field `ALCOAScore`. Record this as a Bible deviation in a `BIBLE-DEVIATIONS.md`-style file for this phase (same pattern as `policies/BIBLE-DEVIATIONS.md`), routed to SENT-7-05, preserving every other constant/threshold in the formula unchanged. This is a genuine correction (stale literal vs. the project's own explicitly-stated 9-dimension model), not a redesign.

### Claude's Discretion
- Exact module/file layout under `backend/app/` for the LLM router, A0/A2/C1 implementations, and any minimal A1/A3–A6 placeholders — follow the existing `backend/app/graph/state.py` skeleton from phase 2 and extend it rather than restructuring.
- Whether A1/A3–A6 get a shared minimal implementation pattern or individually tailored ones — keep them genuinely functional (real LLM call + degraded fallback) but proportionate to their v2-territory status; do not over-invest relative to A0/A2/C1.
- Retry/backoff policy for provider calls, exact Pydantic model field names not already fixed by the Bible.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/graph/state.py` — the LangGraph `StateGraph` skeleton from phase 2: `AgentState`/`AgentFinding`/`ActionProposal` TypedDicts, eleven stub nodes (C2, A0, A1-A6, C1, A7, C3), fixed topology `C2 → A0 → [A1..A6 via Send] → C1 → A7 → C3`. This phase replaces the A0/A2/C1 stub node bodies with real implementations; A1/A3-A6/A7/C2/C3 stub bodies stay largely as-is except where A0's fan-out needs a genuinely-real minimal agent to route to.
- `backend/app/opa_client.py` — `evaluate_opa_policy()` / `python_fallback_rules()`, already live-wired to the real OPA container from phase 2. C1 consumes this directly.
- `policies/gxp_rules.rego` + the 10 rule IDs, seeded gap records in Postgres (phase 2) — C1's real DB+OPA evidence source.
- `backend/app/schemas.py` — Bible Section 4.3 Pydantic models from phase 2; extend with any Section 2 (`AgentFinding`) schema pieces not yet present.
- `backend/tests/conftest.py` — shared fixtures (`client`, `opa_base_url`, `pinned_now_ns`) from phase 2, extend as needed.

### Established Patterns
- Deterministic-first: LLM never evaluates a compliance threshold, RBAC decision, or injection judgment (Bible Section 1.3) — carried over from phase 2's LangGraph skeleton documentation.
- Pinned-clock, offset-based date fixtures (not wall-clock-relative) — established in phase 2's Rego and DB tests, reuse for any date-dependent A2/C1 fixtures.
- Bible deviations get written to a `BIBLE-DEVIATIONS.md`-style file and routed to SENT-7-05 — reuse for any Section 2/8 corrections found the same way phase 2 found Section 3.3/4.1 corrections.

### Integration Points
- A0/A2/C1 land inside `backend/app/graph/` alongside the existing skeleton.
- The multi-provider LLM router (Bible Section 8) is new — likely `backend/app/llm_router.py` or similar, consumed by A0/A2/C1/A1/A3-A6.

</code_context>

<specifics>
## Specific Ideas

None beyond the Bible/Build-Map ticket contracts (SENT-2-01, SENT-2-02, SENT-2-12) and the ROADMAP.md MVP scope narrowing. The hero loop — "Is GXP-MFG-DEMO-01 audit ready?" driving A0 → A2 → C1 to a verified finding — is the concrete acceptance target (ROADMAP success criterion 5).

</specifics>

<deferred>
## Deferred Ideas

- Full A1 System Knowledge / RAG agent with Qdrant hybrid retrieval (dense + BM25 sparse → fusion → cross-encoder rerank → parent-context expansion) — explicitly v2-territory per ROADMAP.md, deferred to a later milestone/phase, not built as a first-class deliverable here.
- Full A3 (Risk), A4 (Change), A5 (Incident), A6 (Access) agents beyond whatever minimal real implementation is needed to exercise A0's fan-out — same v2-territory deferral.
- Live-LLM-quality verification (does Gemini's classification actually route sensibly, does the synthesis read well) — deferred to the operator, who needs to supply API keys first.

</deferred>
