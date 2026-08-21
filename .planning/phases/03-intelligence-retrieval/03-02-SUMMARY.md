---
phase: 03-intelligence-retrieval
plan: 02
requirements-completed: [ORC-03, EVID-01, EVID-04]
---

# Plan 03-02 Summary: Hero Tracer — Real A2/C1 Wired End to End

## Result

Wired the phase's tracer: ONE path through every layer of the hero loop
(graph orchestration, LLM router, Postgres evidence, OPA policy evaluation,
deterministic confidence scoring), on real state, proven by a single
end-to-end test suite. Invoking `compiled_graph.ainvoke()` with the query
"Is GXP-MFG-DEMO-01 audit ready?" now produces one real `AgentFinding`
sourced from the live seeded `PE-2024-01` row, and C1 scores it `MEDIUM`
from that real Postgres record plus the real OPA `ANNEX11-S11-PE-001`
violation set — with and without a provider key present. Full backend
suite: **50/50 passing.**

## Execution note — resumed from an uncommitted worktree

This plan's implementation already existed, complete and untested, in the
git worktree at `.claude/worktrees/agent-ac442c7d2c1a5cc26` from an earlier
session that stopped before the verification/close-out step. This session
copied those files into the main working tree, installed the two
declared-but-missing dependencies (`asyncpg==0.31.0`, `respx==0.23.1` —
present in `requirements.txt` but not in the venv), ran the full
verification loop, completed Task 2 (the README deviation entry, not yet
written), and closed out the plan.

**Environment note:** this session's shell has no `docker` CLI on PATH, so
`infra/health-check.sh`'s container-health check reports RED even though
Postgres (5432), Qdrant (6333), and OPA (8181) were confirmed live and
reachable directly via `node -e "require('net')..."` / `fetch()` — the
services were already running (started in an earlier session/host
context). Seed data (`PE-2024-01`) was already present from a prior
`infra/apply-seed.sh` run. `DATABASE_URL` is not set in `.env` directly;
it was constructed for the test run from `.env`'s `POSTGRES_USER` /
`POSTGRES_PASSWORD` / `POSTGRES_DB` values, matching `db.py`'s own default
construction.

## Task 1 — End-to-end tracer

- `backend/app/agents/__init__.py` — package marker.
- `backend/app/agents/a2_compliance.py` — `A2_SYSTEM_PROMPT` (Bible Section
  6, transcribed verbatim), `verify_periodic_eval_current()` (Python
  arithmetic against `periodic_evaluations.due_date_ns` vs.
  `time.time_ns()` — no model consulted), `narrate_gap()` (routes through
  `call_llm(task="compliance")`, falls back to a deterministic template
  sentence on router degradation), `build_finding()`, `run_a2()`
  (degrades to the Bible's A2 failure-behavior finding when Postgres is
  unreachable).
- `backend/app/agents/c1_verifier.py` — `ALCOA_DIMENSION_COUNT = 9` (D-06),
  `calculate_confidence()` (transcribed from Bible Section 2 with only that
  constant corrected), `RULE_EVIDENCE_TABLES` and `RULE_OPA_INPUT` (both
  complete 10-entry frozen allowlists over the same rule-id key set — table
  names never come from request data), `fetch_evidence_record()`,
  `build_opa_payload()` (single data-driven assembly, no per-rule
  branching), `verify_finding()` (calls the real `evaluate_opa_policy()`,
  never a second Python copy of the Rego logic), `run_c1()`.
- `backend/app/graph/state.py` — the single wave-2 edit: `compliance_a2`
  and `evidence_verifier_c1` now delegate to `app.agents.run_a2()` /
  `run_c1()`. The other nine node bodies, both `TypedDict`s,
  `route_specialists`, and the graph-assembly block are untouched. Module
  docstring updated to record that real evidence/policy work now lives in
  `app.agents` and that C2/C1/C3 remain permanently closed to model
  occupancy.
- `backend/tests/test_hero_tracer.py` — 3 tests: success path (respx-mocked
  Gemini, asserts `finding_id`, citations, evidence ids, `model_attribution
  == "gemini-2.5-flash"`, `claim` equals the mocked text, and
  `verification_results` scores `MEDIUM` with both `db_record_found` and
  `opa_corroborated` true); degraded path (no provider key anywhere in the
  environment, same finding id and `MEDIUM` score, `model_attribution ==
  "deterministic-fallback"`, no exception); evidence provenance (reads the
  `PE-2024-01` row back out through a fresh connection and asserts its
  `due_date_ns` matches the seed file's literal, proving the score came
  from the live row and not a fixture).
- `backend/tests/test_graph_topology.py` — the one pre-existing test
  asserting the old stub literal `{"verified": True}` for
  `verification_results` was narrowed to assert the real dict shape
  (`isinstance(..., dict)`) instead, since C1 is no longer a stub; its
  docstring points at `test_hero_tracer.py` for the real behavioral
  assertions. All other topology tests are unchanged.

All acceptance-criteria checks pass, run against the live-infra test
environment described above:

- `pytest tests/test_hero_tracer.py -x -q` → 3 passed.
- `pytest tests/test_graph_topology.py -x -q` → 11 passed.
- The `calculate_confidence()` one-liner (9-dimension constant, both
  complete 10-entry rule maps over an identical key set, the three
  `MEDIUM`/policy-contradiction/missing-record branches) → prints `ok`.
- `grep -v '^\s*#' backend/app/graph/state.py | grep -cE 'httpx|asyncpg'` →
  `0`.
- `grep -c 'run_a2'` / `'run_c1'` in `state.py` → `4` each (import + Send
  fan-out reference + node registration + docstring mention).
- `graph.nodes` still lists all eleven original node ids, unchanged.
- `grep -v '^\s*#' backend/app/agents/c1_verifier.py | grep -c 'call_llm'`
  → `0`.
- No f-string/`%`-interpolated `SELECT` anywhere in `backend/app/agents/`
  → `0`.

Full suite: `pytest -q` from `backend/` → **50 passed**.

## Task 2 — ALCOA deviation record + AgentFinding contract

Appended **Deviation 7** to `backend/README.md`'s "Bible deviations
(backend tier)" section (Bible's literal `8` → implemented `9`, why —
`.claude/CLAUDE.md` and `app.schemas.ALCOAScore`'s nine named fields agree
against the one stale literal, concrete consequence — the Bible's constant
would let a 9-true finding score above 100 with no threshold able to
express it, evidence — the tracer's live `MEDIUM` result for a 6-of-9
finding, scope — only the one constant changed). Routed to **SENT-7-05**.

Added `## AgentFinding conventions (Phase 3)` reproducing the plan's
interface-contract table (`finding_id` format, `claim`, `regulatory_citations`
sourced only from `policies/gxp_rules.rego` per CLAUDE.md Rule 13,
`confidence_score` starting `UNVERIFIED`, `evidence_ids`, `alcoa_score`,
`model_attribution`) plus the `verification_results` value shape, so plans
03-03 through 03-06 read the contract from the repository.

All README grep checks pass: `Deviation 7` (1), `AgentFinding conventions
(Phase 3)` heading (1), `SENT-7-05` (5 occurrences total across all seven
deviations), `contemporaneous` (2), `enduring` (1), `UNVERIFIED` (1),
Deviations 1-6 still present (6).

## Artifacts

| Artifact | Status |
|---|---|
| `backend/app/agents/__init__.py` | Created |
| `backend/app/agents/a2_compliance.py` | Created |
| `backend/app/agents/c1_verifier.py` | Created |
| `backend/app/graph/state.py` | Modified — `compliance_a2`/`evidence_verifier_c1` now delegate |
| `backend/tests/test_hero_tracer.py` | Created — 3 tests |
| `backend/tests/test_graph_topology.py` | Modified — 1 assertion narrowed |
| `backend/README.md` | Extended — Deviation 7, `## AgentFinding conventions (Phase 3)` |

Full backend suite: 50/50 passing (`pytest -q` from `backend/`, live
Postgres + OPA required for `test_hero_tracer.py` / `test_db.py` /
`test_opa_client.py`).

STATE.md and ROADMAP.md were not modified — left for the orchestrator.

## Follow-up for the operator

Same credential gap as 03-01: no live LLM provider key is configured, so
`test_hero_tracer.py`'s success path exercises A2's real request
construction and response parsing against a respx-mocked Gemini response,
not a live model call. Setting `GEMINI_API_KEY` and re-running proves the
narration reads well in practice; the deterministic-fallback path already
proves the system degrades correctly without one.
