---
phase: 03-intelligence-retrieval
plan: 06
subsystem: api
tags: [hero-loop, end-to-end, langgraph, respx, postgres, opa, evid-04, phase-gate]

requires:
  - phase: 03-intelligence-retrieval
    provides: "03-02's real A0/A2/C1 wiring, 03-03's real A1/A3-A6 minimal specialists, 03-04's A2 three-check completeness + URS fixture, 03-05's C1 Critical-review hardening and the build_opa_payload() multi-input-key fix that makes the traceability finding corroborate"
provides:
  - "backend/tests/test_hero_loop.py — 9 tests, the phase's reviewable EVID-04 evidence (`pytest tests/test_hero_loop.py -k hero -q`): a fully-mocked run against GXP-MFG-DEMO-01 driving A0->[A1-A6]->C1 with all four LLM providers mocked and Postgres+OPA live; a discrimination control against the healthy BUS-IT-DEMO-02 grading everything INSUFFICIENT_EVIDENCE; a keyless run proving the loop closes via A0/A2's degraded-mode fallback since C1 makes no model call; and a no-findings edge case proving C1 never fabricates a bare verified default"
  - "backend/README.md '## Phase 3 backend hero loop' section recording what the loop proves, which layers are live vs. mocked, and the explicit non-claim about live LLM quality with the operator's re-run instructions"
affects: [phase-4-assurance-cards]

actuals:
  tokens: 4800
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Body-content-routed respx side_effect for two PROVIDER_CONFIG entries sharing one URL: A0's classification call (gemini_flash_thinking) and A2/A4's narration calls (gemini_flash_fast) both resolve to the identical Gemini generateContent endpoint, so a single fixed mocked response cannot serve both — the side_effect inspects the outgoing request's systemInstruction text for A0_SYSTEM_PROMPT's own marker and branches accordingly"
    - "Mocking all four PROVIDER_CONFIG endpoints (Gemini, DeepSeek, Groq, OpenRouter) in one scenario so a fully-keyed hero-loop run exercises every specialist's own primary provider directly, rather than silently falling through the router's own cascade-to-openrouter-then-degrade path for lack of a matching mock route"

key-files:
  created:
    - backend/tests/test_hero_loop.py
  modified:
    - backend/README.md

key-decisions:
  - "Classified the fully-mocked scenario to the full six-agent set (rather than a narrower subset) so it exercises all four provider routes in one invocation, per <critical_findings>'s instruction to prove every specialist's primary provider rather than silently falling through cascades — A0's own subset-narrowing behavior is already covered by test_a0_orchestrator.py and not re-proven here."
  - "Kept test_hero_tracer.py in place unmodified rather than deleting or superseding it — 03-06-PLAN.md's files_modified lists only test_hero_loop.py and backend/README.md; the tracer remains its own narrower single-check regression suite."

requirements-completed: [EVID-04]

coverage:
  - id: D1
    description: "One compiled_graph.ainvoke() call on the literal hero query drives A0->A2->C1 and yields a finding graded MEDIUM or better from a real Postgres row and a real OPA evaluation"
    requirement: "EVID-04"
    verification:
      - kind: integration
        ref: "backend/tests/test_hero_loop.py#test_hero_fully_mocked_run_at_least_one_finding_verified_medium_or_better"
        status: pass
      - kind: integration
        ref: "backend/tests/test_hero_loop.py#test_hero_provenance_periodic_eval_matches_live_seeded_row"
        status: pass
    human_judgment: false
  - id: D2
    description: "The same invocation against the healthy BUS-IT-DEMO-02 system grades every finding INSUFFICIENT_EVIDENCE — the loop discriminates rather than always verifying (T-03-29)"
    requirement: "EVID-04"
    verification:
      - kind: integration
        ref: "backend/tests/test_hero_loop.py#test_hero_discrimination_control_healthy_system_grades_insufficient_evidence"
        status: pass
    human_judgment: false
  - id: D3
    description: "The same invocation with every provider key removed still closes end to end: A0 falls back to the full six-agent set, every finding's model_attribution is deterministic-fallback, and C1's grade is unchanged because it makes no model call (D-01)"
    requirement: "EVID-04"
    verification:
      - kind: integration
        ref: "backend/tests/test_hero_loop.py#test_hero_keyless_run_falls_back_to_full_agent_set_and_deterministic_fallback"
        status: pass
    human_judgment: false
  - id: D4
    description: "Real, not mocked, in every layer except the LLM provider transport: findings/verification_results shape proven, model attribution proven real-provider, C1 never fabricates a verified default for empty findings"
    requirement: "EVID-04"
    verification:
      - kind: integration
        ref: "backend/tests/test_hero_loop.py#test_hero_fully_mocked_run_verification_results_shape_and_four_grades"
        status: pass
      - kind: integration
        ref: "backend/tests/test_hero_loop.py#test_hero_fully_mocked_run_model_attribution_names_real_provider"
        status: pass
      - kind: unit
        ref: "backend/tests/test_hero_loop.py#test_hero_run_c1_with_no_findings_returns_empty_verification_mapping"
        status: pass
  - id: D5
    description: "The phase close-out record states what the loop proves, which layers are live vs. mocked, and the explicit non-claim about live LLM quality, without softening"
    requirement: "EVID-04"
    verification:
      - kind: other
        ref: "backend/README.md '## Phase 3 backend hero loop' section"
        status: pass
    human_judgment: false

duration: 45min
completed: 2026-08-21
status: complete
---

# Phase 3 Plan 6: Hero-Loop End-to-End Integration Test (EVID-04) Summary

**One `compiled_graph.ainvoke()` call on "Is GXP-MFG-DEMO-01 audit ready?" now provably drives A0 -> A2 -> C1 to a verified finding sourced entirely from real Postgres and real OPA state, discriminates against the healthy demo system, and still closes end to end with zero provider keys configured — closing the Phase 3 gate.**

## Performance

- **Duration:** 45 min (approx)
- **Completed:** 2026-08-21T14:56:00Z (approx)
- **Tasks:** 2
- **Files modified:** 2 (1 created, 1 modified)

## Accomplishments

- `backend/tests/test_hero_loop.py` (new, 9 tests): a fully-mocked scenario (6 test functions) drives one `compiled_graph.ainvoke()` call against the seeded, unhealthy `GXP-MFG-DEMO-01` with all four `PROVIDER_CONFIG` endpoints (Gemini, DeepSeek, Groq, OpenRouter) mocked and Postgres/OPA fully live — A0 classifies to the full six-agent set, fans out to A1-A6, and A2's periodic-evaluation and traceability findings are graded `MEDIUM` from the real seeded `PE-2024-01` row (provenance-checked back against the live database) and a real OPA evaluation; every emitted finding's `model_attribution` names a real provider model id.
- A discrimination-control scenario runs the identical query against the healthy `BUS-IT-DEMO-02` system and asserts every finding grades `INSUFFICIENT_EVIDENCE` — proving the loop refuses as well as verifies (T-03-29), not a mechanism that always trusts.
- A keyless scenario removes every provider key and asserts A0 falls back to the full Bible-ordered six-agent set, every finding's `model_attribution` is the literal `deterministic-fallback` marker, and the periodic-evaluation finding still grades `MEDIUM` — proving C1's confidence score is independent of LLM availability (D-01), since C1 makes no model call at all.
- A ninth, lightweight test calls `run_c1({"findings": []})` directly and asserts an empty `verification_results` mapping, proving C1 never fabricates a bare verified default for a finding that was never actually verified.
- Resolved the plan's flagged routing hazard (`<critical_findings>`): A0's classification call and A2/A4's narration calls both resolve to the identical Gemini `generateContent` URL (same `model`, same `base_url` across the `gemini_flash_thinking`/`gemini_flash_fast` `PROVIDER_CONFIG` entries) — a single fixed respx response would have fed A0's classification JSON into a narration prompt or vice versa. `_gemini_side_effect()` inspects the outgoing request body's `systemInstruction` text for `A0_SYSTEM_PROMPT`'s own marker and branches to the correct response shape.
- `backend/README.md` gained `## Phase 3 backend hero loop`: the runnable command, seed/service preconditions, the three named scenarios, which layers are live vs. mocked, and an explicit, unsoftened non-claim that live LLM classification/narration quality remains unproven — naming all four provider env vars and the operator's exact re-run commands.

## Task Commits

Each task was committed atomically:

1. **Task 1: Hero-loop integration test — one query, real database, real policy engine, three graded outcomes** - `03199aa` (test)
2. **Task 2: Phase close-out record — what the hero loop proves, and the one claim it does not make** - `718c46a` (docs)

**Plan metadata:** _pending — added in the final metadata commit alongside this SUMMARY.md_

## Files Created/Modified

- `backend/tests/test_hero_loop.py` - New: 9 tests (fully-mocked run x6, discrimination control x1, keyless run x1, no-findings edge case x1), all invoking the real compiled graph, real Postgres, and real OPA; only the LLM provider transport is mocked.
- `backend/README.md` - New `## Phase 3 backend hero loop` section, placed after `## C1 Critical-review coverage (SENT-2-12)`.

## Decisions Made

- Classified the fully-mocked scenario to the full six-agent set rather than a narrower subset — see `key-decisions` in frontmatter.
- Left `test_hero_tracer.py` unmodified — out of this plan's declared `files_modified`, and its narrower single-check coverage remains valid alongside this file's broader phase-gate evidence.

## Deviations from Plan

None — plan executed exactly as written. Both tasks' `<verify>` and `<acceptance_criteria>` blocks passed on the first implementation attempt with no upstream drift discovered.

## Known Stubs

None — every scenario in `test_hero_loop.py` drives the real compiled graph against real Postgres and real OPA; the only mocked layer is the LLM provider transport, as the plan requires.

## Threat Flags

None beyond what 03-06-PLAN.md's own `<threat_model>` already anticipated (T-03-29 through T-03-32, all mitigated as designed — the discrimination control, the README's unsoftened non-claim, the read-only-against-the-database suite plus the post-run `infra/verify-seed.sh`-equivalent check, and placeholder-only mocked provider keys).

## Issues Encountered

**Environment: `docker` CLI unavailable in this worktree's shell.** Same situation every prior Phase-3 plan recorded: `docker`/`docker-compose` are not on `PATH` in this session's shell, so `bash infra/verify-seed.sh` itself could not be invoked literally (it exits with every check reporting `<none>` since `dc exec` has no `docker`/`docker-compose` binary to resolve). Postgres (5432) and OPA (8181) were confirmed live and reachable directly (`node -e "require('net')..."`), already seeded. Verified equivalently by re-running the substance of `verify-seed.sh`'s checks directly via `asyncpg` against the live database both before and after the full test-suite run — all PASS both times, equivalent to `SEED OK`, confirming the hero-loop suite (which is read-only against the database) mutated nothing. `backend/.venv` also does not exist inside this git worktree (gitignored); resolved by invoking the main checkout's `backend/.venv/Scripts/python.exe` interpreter directly with the worktree's `backend/` as the working directory, matching every prior Phase-3 plan's established workaround.

## User Setup Required

None — no external service configuration required for this plan's own deliverable. The pre-existing credential gap for live LLM narration/classification quality (noted in every prior Phase-3 plan's summary, and restated explicitly in this plan's new README section) is unchanged: no live LLM provider key is configured, so every claim graded in `test_hero_loop.py` came from a mocked provider response or a deterministic template. Setting `GEMINI_API_KEY` (and optionally `DEEPSEEK_API_KEY`/`GROQ_API_KEY`/`OPENROUTER_API_KEY`) and re-running `pytest tests/test_hero_loop.py -q` against a live provider remains the outstanding operator follow-up, tracked since plan 03-01's `user_setup`.

## Next Phase Readiness

- Phase 3's gate is closed: EVID-04 is proven end to end, with the discrimination control (T-03-29) and the keyless-run independence guarantee (D-01) both explicitly tested, not assumed.
- Full backend suite: 112/112 passing (`pytest -q` from `backend/`, live Postgres + OPA required) — 103 from prior Phase-3 plans plus this plan's 9 new tests.
- `verification_results`' shape (`confidence`/`db_record_found`/`opa_corroborated`/`opa_rule_ids`/`evidence_ids`) is now proven end-to-end through the full graph, not just unit-tested in isolation — Phase 4's Assurance Card UI can read this shape with confidence it reflects real composed behavior, not just C1's own contract in isolation.
- The operator credential-gap follow-up (set live provider keys, re-run against a real model) remains open and is now recorded in exactly one place (`backend/README.md`'s new section) rather than scattered across five plans' summaries.

STATE.md and ROADMAP.md were not modified — left for the orchestrator, per this plan's instruction.

---
*Phase: 03-intelligence-retrieval*
*Completed: 2026-08-21*

## Self-Check: PASSED

All claimed files found on disk (`backend/tests/test_hero_loop.py`, `backend/README.md`, this SUMMARY.md). Both task commits (`03199aa`, `718c46a`) confirmed present in `git log`. Full backend suite re-confirmed 112/112 passing after both commits.
