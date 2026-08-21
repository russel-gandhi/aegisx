---
phase: 03-intelligence-retrieval
verified: 2026-08-21T00:00:00Z
status: passed
score: 9/9 must-haves verified
behavior_unverified: 0
overrides_applied: 0
---

# Phase 3: Intelligence & Retrieval Verification Report

**Phase Goal:** A real query enters A0, is classified and routed, fans out to real (non-stub) agents, and C1 produces a non-trivial confidence score sourced from real DB + OPA state — the backend hero loop is real, not mocked.
**Gate (Build-Map Stage 2):** "a real query enters A0, fans out to real (non-stub) A1–A6, C1 produces a non-trivial confidence score sourced from real DB + OPA state."
**Mode:** MVP-scoped — A0 Orchestrator + A2 Compliance + C1 real wiring are the v1-required tickets (SENT-2-01/2-02/2-12); A1/A3–A6 are v2-territory retained as context, built here only as genuinely-real-but-minimal fan-out targets, not first-class deliverables.
**Verified:** 2026-08-21 (live commands run in this session against the running Compose Postgres/OPA, not SUMMARY.md prose)
**Status:** passed
**Re-verification:** No — initial verification

## Method

Live services were confirmed reachable directly via TCP probe (`docker` CLI is not on PATH in this shell, consistent with every Phase-3 plan's own SUMMARY.md — Postgres 5432, Qdrant 6333, and OPA 8181 all confirmed OPEN). The full backend test suite was executed live in this session (`cd backend && ./.venv/Scripts/python -m pytest -q`), plus the specific reviewable-evidence keyword selectors each plan names, plus direct `asyncpg` queries against the live database to independently confirm the seeded rows the tests assert against. Source files were read directly to confirm wiring, deterministic-first boundaries, and the absence of over-mocking — not inferred from SUMMARY.md claims.

```
$ cd backend && ./.venv/Scripts/python -m pytest -q
112 passed, 1 warning in 53.88s
```

This matches the requested "expect 112 passed" exactly.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A0 classifies a real query via the router and narrows `active_agents` to the classified subset, which `route_specialists` fans out to (ORC-02) | ✓ VERIFIED | `pytest tests/test_a0_orchestrator.py::test_mocked_classification_narrows_active_agents -q` passes; source read of `app/agents/a0_orchestrator.py::classify_intent` confirms real `call_llm(task="orchestrator", json_output=True)` call, real JSON parse, real `FULL_AGENT_SET` validation. `route_specialists` in `graph/state.py` unchanged (byte-identical fan-out over `active_agents`). |
| 2 | A classification that overruns 2000ms is abandoned (cancelled, not raced) and `active_agents` reverts to the full six-agent set, proven by measured elapsed time (ORC-02, D-02) | ✓ VERIFIED | `pytest tests/test_a0_orchestrator.py -k timeout -q` → 2 passed. Source: `asyncio.wait_for(..., timeout=A0_TIMEOUT_SECONDS)` with `A0_TIMEOUT_SECONDS = 2.0`; `grep -c 'asyncio.wait_for' app/agents/a0_orchestrator.py` ≥ 1, `grep -c 'sleep'` (non-comment) = 0 — cancellation, not a blocking-delay approximation. |
| 3 | Every one of A1, A3, A4, A5, A6 runs a real deterministic Postgres check and a real router call, and returns its Bible failure behavior when that work cannot complete — none returns an unconditional empty finding list (phase gate: real, non-stub fan-out) | ✓ VERIFIED | `pytest tests/test_minimal_specialists.py -q` → 10 passed. `grep -cE 'return \{"findings": \[\]\}' app/graph/state.py` = 0 (independently re-confirmed). `SPECIALIST_CONFIG` in `minimal_specialists.py` has real `$1`-parameterized SQL per agent (verified via `grep -v '^\s*#' app/agents/minimal_specialists.py \| grep -cE "f\"SELECT\|f'SELECT"` = 0) and a real `run_specialist` driver calling `call_llm`. |
| 4 | A2 produces a real `AgentFinding` from live DB state via all three Bible-named checks (`verify_urs_approved`, `verify_periodic_eval_current`, `verify_test_traceability`) (ORC-03) | ✓ VERIFIED | `pytest tests/test_a2_compliance.py -q` → 11 passed. Live `asyncpg` query run in this session independently confirms `DOC-2026-URS-01` is `APPROVED`/`doc_type=URS` and `PE-2024-01` has `due_date_ns=1704067200000000000`/`status=PENDING` — the exact rows the tests and the hero loop assert against. `A2_CHECKS` tuple confirmed to hold all three functions. |
| 5 | C1 fans in and calls `calculate_confidence()` against the real DB record and real OPA evaluation — never a mock — returning a non-trivial grade for a true claim (EVID-01) | ✓ VERIFIED | `grep -v '^\s*#' app/agents/c1_verifier.py \| grep -c 'call_llm'` = 0 — C1 makes no model call, confirming the deterministic-only constraint. `test_negative_positive_control_truthful_claim_against_real_row_scores_medium` (no respx anywhere in `test_c1_verifier.py`, confirmed by grep) runs `verify_finding()` against the live pool and live OPA sidecar and asserts `MEDIUM`. |
| 6 | Feeding C1 an LLM-shaped claim that contradicts the real Postgres row and the real OPA evaluation returns `INSUFFICIENT_EVIDENCE`, proven live (EVID-02, D-04) | ✓ VERIFIED | `pytest tests/test_c1_verifier.py -k contradiction -q` and the full `-k "contradiction or boundary or ten_rules or fail_closed"` selector → 9 passed. `test_negative_evid02_contradiction_against_real_approved_urs_row` asserts a claim stating `DOC-2026-URS-01` is NOT approved (real row IS approved) grades `INSUFFICIENT_EVIDENCE` with `db_record_found=True`/`opa_corroborated=False`, run with no mocking of Postgres or OPA. |
| 7 | A fabricated `evidence_ids` record short-circuits to `INSUFFICIENT_EVIDENCE` without the policy engine being consulted (EVID-02) | ✓ VERIFIED | `test_negative_evid02_fabricated_evidence_short_circuits_before_opa_call` installs a call-counting wrapper around the real `evaluate_opa_policy` reference and asserts `calls["n"] == 0` after verification — proven by instrumentation, not source inspection. |
| 8 | All ten `policies/gxp_rules.rego` rule ids resolve through C1 against live Postgres + live OPA to a real grade, and C1 fails closed (all `INSUFFICIENT_EVIDENCE`) on both an OPA outage and a Postgres outage (EVID-01) | ✓ VERIFIED | `pytest tests/test_c1_verifier.py -k "ten_rules or fail_closed" -q` → part of the 9-test selector, all passing. `RULE_EVIDENCE_TABLES`/`RULE_OPA_INPUT` confirmed 10 entries each over an identical key set. The 03-04-discovered `build_opa_payload()` multi-input-key defect (rules 5/10) was found, tracked in `.planning/WINDOWS.md`, and fixed in 03-05 (`open_count: 0` confirmed live in this session) — not silently patched or left open. |
| 9 | The end-to-end hero loop — submitting "Is GXP-MFG-DEMO-01 audit ready?" through one `compiled_graph.ainvoke()` call — drives A0 → A2 → C1 to a verified finding sourced entirely from real Postgres/OPA state, discriminates against the healthy `BUS-IT-DEMO-02` system, and still closes with zero provider keys present (EVID-04, roadmap success criterion 5) | ✓ VERIFIED | `pytest tests/test_hero_loop.py -k hero -q` → 9 passed. Source-read confirms only the four LLM provider endpoints are respx-mocked; `respx.route(host="127.0.0.1", port=8181).pass_through()` is registered in every scenario so OPA stays live, and `app.db.DATABASE_URL`/`app.opa_client.OPA_URL` are never monkeypatched in this module (independently grepped). Provenance test reads `PE-2024-01` back from the live pool inside the test itself and matches `due_date_ns=1704067200000000000` — independently re-confirmed live in this session. Discrimination control against `BUS-IT-DEMO-02` grades everything `INSUFFICIENT_EVIDENCE`. Keyless run confirms `active_agents == FULL_AGENT_SET`, every `model_attribution == "deterministic-fallback"`, and the periodic-eval finding still grades `MEDIUM` (C1 makes no model call). |

**Score:** 9/9 truths verified (0 present-but-behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `backend/app/db.py` | asyncpg pool, degrade-don't-raise entry point | ✓ VERIFIED | `get_pool()`/`acquire_pool_or_none()`/`close_pool()` present; zero `print(` occurrences; `pytest tests/test_db.py` part of the 112-passing full suite |
| `backend/app/llm_router.py` | multi-provider router, `PROVIDER_CONFIG`, `call_llm()` | ✓ VERIFIED | `PROVIDER_CONFIG` has the 5 expected keys with the two corrected model strings (`deepseek-v4-pro`, `openrouter/auto`); never raises to caller; key-leakage tests pass |
| `backend/app/agents/a0_orchestrator.py` | real intent classification, hard 2000ms fallback | ✓ VERIFIED | `FULL_AGENT_SET`, `A0_TIMEOUT_SECONDS=2.0`, `classify_intent()`, `run_a0()` all present and wired into `graph/state.py::orchestrator_a0` |
| `backend/app/agents/a2_compliance.py` | all 3 Bible-named checks, multi-gap finding assembly | ✓ VERIFIED | `A2_CHECKS` tuple of 3; `run_a2` emits exactly 2 findings against the seeded `GXP-MFG-DEMO-01` state (URS check now passes since 03-04's fixture) |
| `backend/app/agents/c1_verifier.py` | deterministic-only confidence verifier | ✓ VERIFIED | Zero `call_llm` occurrences; `ALCOA_DIMENSION_COUNT=9`; `RULE_EVIDENCE_TABLES`/`RULE_OPA_INPUT` both 10-entry frozen maps; `build_opa_payload()`'s multi-input-key fix live-confirmed working for rules 5 and 10 |
| `backend/app/agents/minimal_specialists.py` | A1/A3-A6 minimal-but-real agents | ✓ VERIFIED | `SPECIALIST_CONFIG` keyed A1/A3/A4/A5/A6, each with real parameterized SQL + real router call + Bible failure behavior |
| `backend/app/graph/state.py` | 8 of 11 nodes now delegate to real agents; topology unchanged | ✓ VERIFIED | `len(graph.nodes) == 11`, node ids unchanged; `orchestrator_a0`/`system_knowledge_a1`/`compliance_a2`/`risk_a3`/`change_a4`/`incident_a5`/`access_a6`/`evidence_verifier_c1` all delegate; `remediation_a7`/`safety_gateway_c2`/`action_gateway_c3` deliberately still stub (Phase 5 territory, documented in module docstring) |
| `infra/postgres/seed/002_urs_fixture.sql` | additive APPROVED URS fixture (D-05) | ✓ VERIFIED | Live query confirms `DOC-2026-URS-01` exists, `status=APPROVED`, `doc_type=URS` |
| `backend/tests/test_hero_loop.py` | phase-gate EVID-04 evidence | ✓ VERIFIED | 9 tests, all live-DB/live-OPA/mocked-LLM-only, all passing |
| `backend/tests/test_c1_verifier.py` | SENT-2-12 Critical-review coverage | ✓ VERIFIED | 20 tests across UNIT/NEGATIVE/EDGE/INTEGRATION sections (4 section markers confirmed by grep), no respx anywhere in the file |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| A0's `active_agents` output | `route_specialists` conditional edge | data flow, no topology change | ✓ WIRED | `route_specialists` byte-identical to Phase 2; A0 output flows through unmodified |
| A2's `regulatory_citations`/`evidence_ids` | C1's OPA corroboration join key | `RULE_EVIDENCE_TABLES`/`RULE_OPA_INPUT` allowlists | ✓ WIRED | Confirmed via `test_integration_ten_rules_verify_finding_grades_and_at_least_eight_corroborate` and rule-5/rule-10-specific tests (all 10 rules resolve, post-03-05-fix) |
| `graph/state.py`'s 8 delegating node bodies | `app.agents.*` real implementations | direct `await`/import | ✓ WIRED | Confirmed by direct source read of `state.py` — every delegating body is a one-line `return await run_X(state)`, imports at module top level |
| C1's `calculate_confidence()` threshold ladder | 4 grade names | numeric comparison | ✓ WIRED | 3 threshold-boundary tests pass (`-k boundary`, 3+ selected); ladder one-liner independently re-run in prior sessions and reconfirmed by this session's full-suite pass |
| `verification_results[finding_id]['confidence']` | Phase 4's future Assurance Card UI contract | shape stability | ✓ WIRED | Shape (`confidence`/`db_record_found`/`opa_corroborated`/`opa_rule_ids`/`evidence_ids`) proven end-to-end through the full compiled graph in `test_hero_loop.py`, not just unit-isolated |
| `infra/apply-seed.sh` | every `*.sql` under `infra/postgres/seed/` | sorted-glob application | ✓ WIRED (indirect) | Not directly re-run this session (`docker` CLI unavailable, consistent with every plan's own SUMMARY.md); indirectly confirmed by the live database genuinely containing both `PE-2024-01` (001_seed.sql) and `DOC-2026-URS-01` (002_urs_fixture.sql) rows, queried directly in this session |

### Behavioral Spot-Checks / Live Execution

| Behavior | Command | Result | Status |
|---|---|---|---|
| Full backend suite | `cd backend && ./.venv/Scripts/python -m pytest -q` | 112 passed, 1 warning, 53.88s | ✓ PASS (matches requested expectation exactly) |
| EVID-04 reviewable evidence | `pytest tests/test_hero_loop.py -k hero -q` | 9 passed | ✓ PASS |
| ORC-02 timeout evidence | `pytest tests/test_a0_orchestrator.py -k timeout -q` | 2 passed | ✓ PASS |
| C1 Critical-review evidence | `pytest tests/test_c1_verifier.py -k "contradiction or boundary or ten_rules or fail_closed" -q` | 9 passed | ✓ PASS |
| A0 full module | `pytest tests/test_a0_orchestrator.py -q` | 11 passed | ✓ PASS |
| A2 full module | `pytest tests/test_a2_compliance.py -q` | 11 passed | ✓ PASS |
| Minimal specialists full module | `pytest tests/test_minimal_specialists.py -q` | 10 passed | ✓ PASS |
| Graph topology intact | `python -c "from app.graph.state import graph; ..."` | 11 nodes, ids unchanged | ✓ PASS |
| Live seeded-row cross-check (independent of the test suite) | direct `asyncpg` query via `get_pool()` in this session | `PE-2024-01`: due_date_ns=1704067200000000000/PENDING; `DOC-2026-URS-01`: APPROVED/URS; `BUS-IT-DEMO-02` exists | ✓ PASS — matches every literal the test suite asserts |
| Deterministic-first boundary | `grep -v '^\s*#' app/agents/c1_verifier.py \| grep -c call_llm` | 0 | ✓ PASS |
| No stub finding lists remain | `grep -cE 'return \{"findings": \[\]\}' app/graph/state.py` | 0 | ✓ PASS |
| Live services reachable | TCP probe 127.0.0.1:5432/6333/8181 | all OPEN | ✓ PASS |
| Debt markers | `grep -rn -E "TBD\|FIXME\|XXX"` over all Phase-3-modified files | none found | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|---|---|---|---|---|
| ORC-02 | 03-03 | A0 classifies, fans out to subset; 2000ms fallback | ✓ SATISFIED | `test_a0_orchestrator.py` 11/11, `-k timeout` measured-elapsed-time evidence |
| ORC-03 | 03-01, 03-02, 03-04 | A2 produces real findings via all 3 named checks | ✓ SATISFIED | `test_a2_compliance.py` 11/11, all 3 checks live-DB-backed |
| EVID-01 | 03-02, 03-05 | C1 calls `calculate_confidence()` against real DB + real OPA, never mocked | ✓ SATISFIED | `test_c1_verifier.py` 20/20, zero `respx` usage in the file, all 10 rules resolve |
| EVID-02 | 03-05 | Contradicting claim returns `INSUFFICIENT_EVIDENCE`, explicitly tested | ✓ SATISFIED | `test_negative_evid02_contradiction_against_real_approved_urs_row` + fabricated-evidence short-circuit test, both live |
| EVID-04 | 03-06 | End-to-end hero loop works | ✓ SATISFIED | `test_hero_loop.py` 9/9, `-k hero` selector, live Postgres + live OPA + mocked-LLM-only |

No orphaned requirements found — all 5 IDs mapped to Phase 3 in REQUIREMENTS.md (ORC-02, ORC-03, EVID-01, EVID-02, EVID-04) are claimed by plan frontmatter and independently confirmed above. Note: `REQUIREMENTS.md`'s own checkbox/traceability table still shows these as `[ ]`/"Pending" — this is the same tracking-metadata lag 02-VERIFICATION.md flagged for Phase 2, not a code gap; left unmodified per instructions for the orchestrator to update.

### Deterministic-First Constraint Check

`grep -v '^\s*#' backend/app/agents/c1_verifier.py | grep -c call_llm` → `0`. `grep -v '^\s*#' backend/app/graph/state.py | grep -cE 'httpx|asyncpg'` (re-derivable from source read) → `0` — the graph module itself makes no network/DB call; every such call lives in `app.agents.*` delegates. C2/A7/C3 remain deliberately stubbed pending Phase 5 (documented in `state.py`'s own module docstring, matching the ROADMAP's phase boundary). No LLM occupies C1 — confirmed both by grep and by every C1 test file using zero HTTP mocking of an LLM provider.

### Anti-Patterns Found

None. Grepped every file this phase created or modified for `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER`/"not yet implemented"/"coming soon" — zero matches. `.planning/WINDOWS.md`'s one tracked deviation (the `build_opa_payload()` multi-input-key defect, discovered in 03-04) is `fixed` (`open_count: 0`), not silently carried forward — confirmed live in this session, not from SUMMARY.md prose alone.

### Honesty of the Credential-Gap Claim

Every Phase-3 plan's SUMMARY.md states no live LLM provider API key was configured and that classification/narration quality (as opposed to wire-contract correctness and degraded-mode fallback) remains unproven this session. This session's `.env` was inspected (present, 538 bytes) but its contents were not read (would risk exposing key material in this report) — this verification does not depend on whether a key is now present, because every test file that exercises an LLM path explicitly monkeypatches or mocks provider keys/responses, so the suite's correctness does not depend on `.env`'s actual contents. The `backend/README.md` "Phase 3 backend hero loop" section states this limitation plainly and without softening, matching what 03-06-PLAN.md required. This verification does not independently re-confirm live-LLM narration quality — that remains, as every plan states, an operator follow-up outside this phase's automated gate.

### Human Verification Required

None. Every phase-gate claim in ROADMAP.md's 5 success criteria was either directly executed live in this session (full suite, targeted keyword selectors, direct DB queries) or confirmed via source inspection proving the test evidence is not over-mocked (no `respx` in `test_c1_verifier.py`; only the 4 LLM provider endpoints mocked in `test_hero_loop.py`, with an explicit OPA passthrough registered in every scenario).

### Gaps Summary

None. All 5 ROADMAP.md Phase 3 success criteria hold:

1. A0 classifies via Gemini and fans out via `Send` to a subset; 2000ms+ delay demonstrably falls back to the full set — proven by a measured-elapsed-time test, not inspection.
2. A2 produces real `AgentFinding`s from live DB state via all three named checks.
3. C1 fans in and calls `calculate_confidence()` against real DB + real OPA, returning a real grade for a true claim (`MEDIUM` for the periodic-evaluation finding, live-reconfirmed in this session).
4. Feeding C1 a claim that contradicts real DB/OPA truth returns `INSUFFICIENT_EVIDENCE` — the EVID-02 contradiction fixture runs against the genuinely `APPROVED` `DOC-2026-URS-01` row with neither Postgres nor OPA mocked.
5. The full hero loop — "Is GXP-MFG-DEMO-01 audit ready?" through one `compiled_graph.ainvoke()` — drives A0 → A2 → C1 to a verified finding sourced entirely from real DB/OPA state, discriminates against the healthy control system, and closes with zero provider keys present.

A real, non-trivial defect (`build_opa_payload()`'s multi-input-key lookup, discovered in 03-04) was found, tracked (not hidden), and fixed in 03-05, with the fix verified against live infrastructure and the tracking ledger closed. This is exactly the kind of finding a goal-backward verification should surface — and in this case the phase's own plans already surfaced and resolved it before this verification began, which is a positive signal about the executing sessions' rigor, not a substitute for this independent check.

The backend hero loop for Phase 3 is real, not mocked, in every layer except the LLM provider transport (as every plan explicitly and consistently discloses), and the phase goal is achieved.

---

*Verified: 2026-08-21*
*Verifier: Claude (gsd-verifier)*
