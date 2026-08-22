---
phase: 04-evidence-impact
plan: 03
subsystem: api
tags: [fastapi, pydantic, react, vitest, evid-03]

# Dependency graph
requires:
  - phase: 04-evidence-impact
    plan: "04-01"
    provides: "app.routes.evidence_graph._system_exists helper; frontend/src/lib/api.ts's apiGet pattern; nine-entry routes.tsx baseline"
  - phase: 03-intelligence-retrieval
    provides: "app.agents.a2_compliance (A2_CHECKS, build_finding, narrate_gap) and app.agents.c1_verifier.verify_finding, both read-only Critical-review modules this plan consumes without modifying"
provides:
  - "GET /api/systems/{system_id}/assurance-cards -- assembles one AssuranceCard per failing A2 deterministic check, verified through C1 against real Postgres and real OPA"
  - "backend/app/schemas.py: DeterministicCheck/AssuranceCard/AssuranceCardsResponse Pydantic models"
  - "frontend/src/components/AssuranceCard.tsx -- reusable, presentational card component (CLAIM/EVIDENCE/RULE/DETERMINISTIC CHECK/CONFIDENCE + ALCOA+ + model attribution)"
  - "frontend/src/lib/api.ts: fetchAssuranceCards and its TS interfaces"
  - "/findings route (Evidence Investigation), tenth entry in routes.tsx"
affects: [04-05-blast-radius-traversal, 06-copilot-chat]

actuals:
  tokens: 9133
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Route calls A2's check functions and C1's verifier directly rather than the compiled LangGraph, to keep the per-check name (check_result['check']) that build_finding drops -- cheaper and more faithful to what the card shows (critical finding 3)"
    - "_assemble_card() is a pure, DB-free function taking three already-computed Phase 3 dicts (check_result, finding, verification_result) and returning a Pydantic model -- unit-testable without Postgres/OPA, and the single place the UNVERIFIED-vs-real-confidence distinction is documented and enforced"
    - "AssuranceCard.tsx is presentation-only (no fetch, no derived state) with a data-confidence attribute driving only border/badge colour -- the visual grade is always the server's own value, never a client computation"

key-files:
  created:
    - backend/app/routes/findings.py
    - backend/tests/test_routes_findings.py
    - frontend/src/components/AssuranceCard.tsx
    - frontend/src/pages/FindingInvestigation.tsx
    - frontend/src/__tests__/AssuranceCard.test.tsx
  modified:
    - backend/app/main.py
    - backend/app/schemas.py
    - frontend/src/lib/api.ts
    - frontend/src/routes.tsx
    - frontend/src/__tests__/routes.test.tsx

key-decisions:
  - "_assemble_card() extracted as a standalone, pure function (not inlined in the route handler) specifically so the UNIT test section could prove the confidence-source discipline (verification_result, never finding['confidence_score']) without touching Postgres or OPA -- the plan's own stated 'single most likely defect' warranted a test that runs in milliseconds, not only an integration test that would also catch it more slowly"
  - "Imported _system_exists from app.routes.evidence_graph rather than re-declaring the same query shape (plan's explicit instruction), keeping the 'system exists' probe defined in exactly one place across both Phase 4 routers"
  - "CONFIDENCE rendered as its own fifth ordered section (SectionLabel + badge) rather than folded into a top-of-card summary badge, after the initial draft's top badge created an ambiguous double-match against the plan's single ordered CLAIM/EVIDENCE/RULE/DETERMINISTIC CHECK/CONFIDENCE section list"

requirements-completed: [EVID-03]

coverage:
  - id: D1
    description: "_assemble_card() reads confidence from the verification result and never from the finding's own UNVERIFIED placeholder, proven directly against hand-built dicts with no Postgres/OPA involved"
    requirement: "EVID-03"
    verification:
      - kind: unit
        ref: "backend/tests/test_routes_findings.py#test_unit_assemble_card_reads_confidence_from_verification_not_finding"
        status: pass
      - kind: unit
        ref: "backend/tests/test_routes_findings.py#test_unit_assemble_card_no_record_yields_insufficient_evidence"
        status: pass
    human_judgment: false
  - id: D2
    description: "GET /api/systems/GXP-MFG-DEMO-01/assurance-cards returns exactly two cards (verify_periodic_eval_current, verify_test_traceability), verify_urs_approved absent because it passes; the periodic-evaluation card grades MEDIUM with evidence_ids == ['PE-2024-01'], db_record_found and opa_corroborated both true, and that evidence id resolves to a real periodic_evaluations row (provenance check)"
    requirement: "EVID-03"
    verification:
      - kind: integration
        ref: "backend/tests/test_routes_findings.py#test_integration_gxp_demo_returns_exactly_two_cards"
        status: pass
      - kind: integration
        ref: "backend/tests/test_routes_findings.py#test_integration_gxp_demo_check_names_are_exactly_the_two_failing_checks"
        status: pass
      - kind: integration
        ref: "backend/tests/test_routes_findings.py#test_integration_periodic_evaluation_card_grades_medium_with_real_evidence"
        status: pass
      - kind: integration
        ref: "backend/tests/test_routes_findings.py#test_integration_periodic_evaluation_evidence_id_resolves_to_a_real_row"
        status: pass
      - kind: manual_procedural
        ref: "Live uvicorn fetch (node) against GET /api/systems/GXP-MFG-DEMO-01/assurance-cards returned the exact predicted two-card body (MEDIUM/MEDIUM, PE-2024-01 evidence)"
        status: pass
    human_judgment: false
  - id: D3
    description: "GET /api/systems/BUS-IT-DEMO-02/assurance-cards returns 200 with every card graded INSUFFICIENT_EVIDENCE (discrimination control); no card anywhere carries the literal UNVERIFIED placeholder; an unknown system_id 404s"
    requirement: "EVID-03"
    verification:
      - kind: integration
        ref: "backend/tests/test_routes_findings.py#test_negative_bus_it_demo_all_cards_grade_insufficient_evidence"
        status: pass
      - kind: integration
        ref: "backend/tests/test_routes_findings.py#test_negative_no_card_anywhere_carries_the_unverified_placeholder"
        status: pass
      - kind: integration
        ref: "backend/tests/test_routes_findings.py#test_negative_unknown_system_returns_404"
        status: pass
      - kind: manual_procedural
        ref: "Live uvicorn fetch confirmed BUS-IT-DEMO-02 cards all INSUFFICIENT_EVIDENCE and NO-SUCH-SYSTEM returned 404"
        status: pass
    human_judgment: false
  - id: D4
    description: "An unreachable Postgres returns 503 rather than fabricating a card; an unreachable OPA still returns 200 with every card failing closed to INSUFFICIENT_EVIDENCE"
    requirement: "EVID-03"
    verification:
      - kind: integration
        ref: "backend/tests/test_routes_findings.py#test_edge_postgres_unreachable_returns_503"
        status: pass
      - kind: integration
        ref: "backend/tests/test_routes_findings.py#test_edge_opa_unreachable_all_cards_grade_insufficient_evidence"
        status: pass
    human_judgment: false
  - id: D5
    description: "AssuranceCard.tsx renders all five EVID-03 labels plus the ALCOA+ nine-dimension grid, sets data-confidence for visual distinction of an INSUFFICIENT_EVIDENCE grade, renders an explicit no-evidence message for an empty evidence_ids, and makes no network call in isolation"
    requirement: "EVID-03"
    verification:
      - kind: unit
        ref: "frontend/src/__tests__/AssuranceCard.test.tsx#AssuranceCard component (6 tests)"
        status: pass
    human_judgment: false
  - id: D6
    description: "/findings is the tenth route: two stubbed cards render two card regions, a zero-card response renders an explicit all-checks-passing message, a rejected fetch renders a visible error message"
    requirement: "EVID-03"
    verification:
      - kind: unit
        ref: "frontend/src/__tests__/AssuranceCard.test.tsx#/findings page (3 tests)"
        status: pass
      - kind: unit
        ref: "frontend/src/__tests__/routes.test.tsx#route table (ten entries, /findings heading)"
        status: pass
      - kind: manual_procedural
        ref: "Live vite dev server: GET http://localhost:3000/findings returned HTTP 200 (scripted fetch check, not a human browser click-through)"
        status: pass
    human_judgment: true
    rationale: "As with 04-01's own D4, full visual browser confirmation (card layout, colour distinction, selector switch) was verified by scripted checks (fetch status 200, all 44 vitest assertions, build/lint clean) rather than a human clicking through the rendered page in this session."

duration: 25min
completed: 2026-08-22
status: complete
---

# Phase 4 Plan 03: Assurance Card Summary

**`GET /api/systems/{id}/assurance-cards` assembles CLAIM/EVIDENCE/RULE/DETERMINISTIC CHECK/CONFIDENCE from already-verified Phase 3 output, rendered by a reusable, presentation-only `AssuranceCard` React component on a new `/findings` route -- zero new verification logic written**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-08-22T22:47:00+05:30 (approx, after fast-forwarding onto main's 04-01 merge)
- **Completed:** 2026-08-22T23:06:32+05:30
- **Tasks:** 2
- **Files modified:** 10 (5 created, 5 modified) across backend and frontend

## Accomplishments
- `backend/app/routes/findings.py` runs A2's three deterministic checks (`A2_CHECKS`, in the Bible's own order) against live Postgres, narrates each failing one, verifies each resulting finding through C1's `verify_finding()` against real Postgres and real OPA, and assembles one `AssuranceCard` per failing check via a pure `_assemble_card()` helper -- `c1_verifier.py` and `a2_compliance.py` are untouched.
- The card's `confidence` field is read exclusively from C1's verification result, never from the finding's own `UNVERIFIED` placeholder -- proven by a dedicated unit test against hand-built dicts (no DB/OPA) and reconfirmed by a negative integration test scanning every card from both seeded systems for the literal placeholder string.
- `GET /api/systems/GXP-MFG-DEMO-01/assurance-cards` returns exactly two cards (periodic evaluation, test traceability), both `MEDIUM`, matching the plan's `<critical_findings>` predictions exactly, including a provenance check that the periodic-evaluation card's evidence id resolves to a real `periodic_evaluations` row. `BUS-IT-DEMO-02` grades every card `INSUFFICIENT_EVIDENCE` (the discrimination control).
- Two fail-closed edge paths: an unreachable Postgres 503s instead of fabricating a card; an unreachable OPA still 200s but every card grades `INSUFFICIENT_EVIDENCE`, proving C1's fail-closed contract survives the card assembly layer.
- `AssuranceCard.tsx`, a purely-presentational component, renders CLAIM / EVIDENCE / RULE / DETERMINISTIC CHECK / CONFIDENCE in that fixed order, followed by the ALCOA+ nine-dimension grid and the model attribution line; a `data-confidence` attribute drives only border/badge colour, so the visual distinction is always the server's own grade.
- `/findings` (`Evidence Investigation`), the tenth route, fetches and renders one card per finding with real loading/error/all-checks-passing states, placed immediately after `/copilot` per D-04 (ready for Phase 6's Copilot chat to embed the same component).

## Task Commits

Each task was committed atomically:

1. **Task 1: `GET /api/systems/{id}/assurance-cards`** - `921e47e` (feat)
2. **Task 2: `AssuranceCard` component and the Evidence Investigation route** - `b6b7f4c` (feat)

**Plan metadata:** this summary's own commit (docs)

_Note: Both tasks were written test-first (TDD) -- `test_routes_findings.py` was confirmed failing (`ModuleNotFoundError: No module named 'app.routes.findings'`) before `app/routes/findings.py` existed; `AssuranceCard.test.tsx` was confirmed failing (Vite import-resolution error) before `AssuranceCard.tsx` existed._

## Files Created/Modified
- `backend/app/routes/findings.py` - `_assemble_card()`, `GET /api/systems/{system_id}/assurance-cards`
- `backend/app/schemas.py` - `DeterministicCheck`/`AssuranceCard`/`AssuranceCardsResponse`
- `backend/app/main.py` - registers the third router (`findings_router`)
- `backend/tests/test_routes_findings.py` - unit (2) + negative (3) + edge (2) + integration (6) = 13 tests
- `frontend/src/lib/api.ts` - `DeterministicCheckData`/`AssuranceCardData`/`AssuranceCardsResponse`, `fetchAssuranceCards`
- `frontend/src/components/AssuranceCard.tsx` - presentational card component
- `frontend/src/pages/FindingInvestigation.tsx` - `/findings` page, system selector, loading/error/empty states
- `frontend/src/routes.tsx` - tenth entry, `/findings`, immediately after `/copilot`
- `frontend/src/__tests__/routes.test.tsx` - length assertion 9→10, `expectedHeadings['/findings']`
- `frontend/src/__tests__/AssuranceCard.test.tsx` - 6 component tests + 3 page tests

## Decisions Made
- **`_assemble_card()` extracted as a standalone pure function:** lets the UNIT test section prove the confidence-source discipline (verification result, never the finding's placeholder -- the plan's own stated most-likely defect) in milliseconds against hand-built dicts, independent of the slower integration tests that also happen to catch it.
- **Imported `_system_exists` from `app.routes.evidence_graph`** rather than re-declaring the same query shape, per the plan's explicit instruction -- the "system exists" probe now has exactly one definition across both Phase 4 routers.
- **CONFIDENCE rendered as its own fifth ordered section**, not folded into a top-of-card badge: an initial draft placed a summary badge at the top of the card, which satisfied the "5 labels present" test but violated the plan's explicit ordered-section instruction and created an ambiguous double match for a single `getByText(/CONFIDENCE/i)` assertion. Restructured before running the tests to keep the five sections in the exact plan-specified order.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Worktree lacked `.env`, `backend/.venv`, and `frontend/node_modules`**
- **Found during:** Session start, before Task 1
- **Issue:** This worktree was created fresh and had none of plan 04-01's runtime setup (worktrees don't share untracked files with the main checkout, per 04-01-SUMMARY.md's own "Issues Encountered"). `bash infra/health-check.sh` reported all three services RED because `docker compose` needs `.env` to resolve `POSTGRES_PASSWORD` for project interpolation, even though the containers themselves (started from the main checkout) were already healthy.
- **Fix:** Copied `.env` from the main checkout (`../../../.env`, resolved to the repo root two levels above the worktrees directory) -- not created new, matching 04-01's own precedent. Created `backend/.venv` and ran `pip install -r requirements.txt`; ran `npm install` in `frontend/`.
- **Files modified:** None tracked (`.env` is gitignored; `.venv`/`node_modules` are gitignored directories, not committed).
- **Verification:** `bash infra/health-check.sh` reported `ALL HEALTHY`; `bash infra/verify-seed.sh` reported `SEED OK`; full backend suite (130 tests, pre-existing baseline) passed before Task 1 began.
- **Committed in:** N/A (environment setup only, no tracked file changes).

**Total deviations:** 1 auto-fixed (Rule 3, environment setup only -- no code or test behavior changed).
**Impact on plan:** None on the plan's actual deliverable; this was the same one-time worktree bootstrap step 04-01 already documented and worked around.

## Issues Encountered
- This worktree's branch (`worktree-agent-a02dc049362dbf837`) had diverged from `main` by five commits (04-01's plan/summary docs plus its two task commits) at session start -- the phase 04 plan files did not exist in the worktree yet. Since the worktree's own HEAD was a strict ancestor of `main` (verified via `git merge-base --is-ancestor`) and the working tree was clean, fast-forwarded (`git merge --ff-only main`) rather than requesting a rebase or cherry-pick, bringing in 04-01's merged deliverables (`evidence_graph.py`, its routes, and the four planning docs this plan's `<context>` requires) with no destructive operation.
- No other blockers. Both tasks' full acceptance criteria (backend full suite 143/143, frontend full suite 44/44, build and lint clean, live-server-verified endpoint bodies) passed on first implementation attempt for Task 1 and after one presentational-ordering fix for Task 2 (caught before running tests, not a test failure).

## User Setup Required

None -- no external service configuration required beyond what 04-01 already established (Docker Desktop running `postgres`/`qdrant`/`opa`, and a repo-root `.env` copied into this worktree, both already covered by the project's standard `infra/health-check.sh` / `infra/apply-seed.sh` setup path).

## Next Phase Readiness

- `AssuranceCard.tsx` is a self-contained, reusable component (props: `{ card: AssuranceCardData }`, no fetch, no derived state) ready for Phase 6's Copilot chat to drop in directly per D-04, with no second implementation needed.
- A placeholder comment in `FindingInvestigation.tsx` marks exactly where plan 04-05 attaches the per-card Blast Radius link; no traversal logic was built here.
- `c1_verifier.py` and `a2_compliance.py` remain exactly as Phase 3 left them -- this plan added zero new verification logic anywhere (CLAUDE.md Rule 7).
- The one open item, matching 04-01's own precedent: a human has not yet visually clicked through `http://localhost:3000/findings` in a browser to confirm card layout and colour distinction -- verified instead by 44/44 passing component/page tests, a clean production build, clean lint, and a live scripted fetch (HTTP 200) against the running dev server in this session.

---
*Phase: 04-evidence-impact*
*Completed: 2026-08-22*

## Self-Check: PASSED

All created files verified present on disk (`backend/app/routes/findings.py`,
`backend/tests/test_routes_findings.py`, `frontend/src/components/AssuranceCard.tsx`,
`frontend/src/pages/FindingInvestigation.tsx`, `frontend/src/__tests__/AssuranceCard.test.tsx`,
this SUMMARY.md) and both task commits (`921e47e`, `b6b7f4c`) verified present in `git log`.
