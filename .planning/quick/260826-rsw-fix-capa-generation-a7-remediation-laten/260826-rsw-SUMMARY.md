---
phase: quick
plan: 260826-rsw
subsystem: api
tags: [llm-router, groq, json-mode, a7-remediation, capa, asyncio-wait-for]

requires:
  - phase: quick/260826-p1q
    provides: "The narration-path cold-fix pattern this task mirrors: Groq routing via a dedicated use_for key, a total wall-clock ceiling via asyncio.wait_for wrapping call_llm (not merely call_llm's own timeout), and the three-part respx-sweep rule (endpoint URL, env var key name, response body shape) for repointing mocks"
provides:
  - "llm_router.py: _build_openai_compatible_request accepts and honours json_output, emitting response_format:{type:json_object} for Groq/DeepSeek/OpenRouter alike; Groq's max_completion_tokens sized by output shape via GROQ_MAX_COMPLETION_TOKENS_DEFAULT (512) / GROQ_MAX_COMPLETION_TOKENS_JSON (2048)"
  - "llm_router.py: 'remediation' moved from gemini_flash_thinking's use_for to groq_llama's (both halves of the edit, since select_provider returns the first match)"
  - "a7_remediation.py: synthesize_capa wraps call_llm in a 6.0s asyncio.wait_for total wall-clock ceiling (A7_REMEDIATION_CEILING_SECONDS), replacing the raw 20.0s per-attempt timeout with no cap"
  - "a7_remediation.py: module logger; warnings on ceiling breach and on parse failure (malformed JSON / missing narrative key), so a json_output plumbing regression is loud instead of silently degrading to the deterministic template"
  - "backend/README.md: Bible deviation entry recording the routing move, routed to SENT-7-05"
affects: [llm-router, a7-remediation-agent, backend-test-suite, capa-generation-latency]

actuals:
  tokens: 8570
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "json_output threaded through the OpenAI-compatible request builder identically to how the Google builder already honoured it -- a single boolean gate rather than a provider-specific branch, so DeepSeek and OpenRouter (A7's own cascade fallback) get JSON mode for free rather than needing a separate change later"
    - "Completion-token budget selected by json_output (output shape), not by a new call_llm parameter or a provider special-case -- narration's existing 512 floor is untouched byte-for-byte, and the structured-payload budget is a second named constant, not a magic number inlined at the call site"
    - "Routing-key MOVE, not append: when a task key already exists on an earlier PROVIDER_CONFIG entry, select_provider's first-match linear scan means the key must be removed from the old entry in the same edit that adds it to the new one, or the change is a silent no-op. A verification gate asserts both halves together."
    - "Total wall-clock ceiling via asyncio.wait_for wrapping the whole call_llm() invocation, not merely call_llm's own timeout parameter -- call_llm reuses that value for its internal OpenRouter cascade attempt, so a raw timeout=N alone permits ~2N worst case (identical reasoning to narration's fix, applied at a longer 6.0s ceiling for CAPA's four-field payload)"
    - "Parse-failure branches now log a warning naming the responding model_id and the exception, closing the exact gap that let a json_output plumbing bug degrade silently and indistinguishably from ordinary provider unavailability"

key-files:
  created: []
  modified:
    - backend/app/llm_router.py
    - backend/app/agents/a7_remediation.py
    - backend/tests/test_llm_router.py
    - backend/tests/test_a7_remediation.py
    - backend/README.md

key-decisions:
  - "response_format applies to all three OpenAI-compatible providers (Groq, DeepSeek, OpenRouter), while reasoning_effort/max_completion_tokens stay Groq-gated -- reasoning_effort is a Groq gpt-oss vendor extension that OpenRouter may reject with a 4xx, but response_format is the standard OpenAI-compatible field and OpenRouter is A7's own cascade fallback: gating it on Groq alone would mean the fallback silently loses JSON mode and returns prose"
  - "6.0s ceiling rather than narration's 3.0s -- a four-field CAPA needs more generation room than one sentence; live measurement (below) shows this ceiling has wide headroom on the happy path (0.978s direct probe, 1.447s full generate-capa route)"
  - "2048-token Groq completion cap for JSON output, sized as a starting estimate (roughly 400-600 content tokens plus reasoning-token headroom) and confirmed by live measurement rather than left as an assumption -- the live probe used only 264 completion tokens against the cap"
  - "The routing-move verification gate asserts BOTH that remediation now resolves to groq_llama AND that orchestrator/synthesis still resolve to gemini_flash_thinking, in the same assertion block -- a half-done edit (key present on both entries) cannot pass silently"

patterns-established:
  - "Cosmetic-honesty sweep on provider-attribution test fixtures: when a routing move lands, every fake response fixture standing in for the old provider (model_id/provider strings) gets corrected in the same commit, not deferred, even where the test's pass/fail behavior does not depend on the exact string"

requirements-completed: [REM-01, ORC-03]

coverage:
  - id: D1
    description: "select_provider('remediation') returns 'groq_llama'; select_provider('orchestrator') and select_provider('synthesis') still return 'gemini_flash_thinking'; every other task key (compliance, narration, risk_assessment, incident, access, high_volume, fallback) resolves exactly as before"
    requirement: "ORC-03"
    verification:
      - kind: unit
        ref: "backend/tests/test_llm_router.py::test_select_provider_routes_remediation_to_groq_not_google"
        status: pass
      - kind: unit
        ref: "backend/app/llm_router.py select_provider() routing smoke check (python -c, all 7 task keys asserted in one block)"
        status: pass
    human_judgment: false
  - id: D2
    description: "_build_openai_compatible_request emits response_format:{type:json_object} when json_output=True and omits the key entirely when False, for all three providers (Groq, DeepSeek, OpenRouter) that share the builder -- proving absence protects every already-shipped narration/incident/access call, not just proving presence for the new path"
    requirement: "ORC-03"
    verification:
      - kind: unit
        ref: "backend/tests/test_llm_router.py::test_build_openai_compatible_request_carries_response_format_when_json_output_true (parametrized: groq_llama, deepseek_r1, openrouter_fallback)"
        status: pass
      - kind: unit
        ref: "backend/tests/test_llm_router.py::test_build_openai_compatible_request_omits_response_format_when_json_output_false (parametrized: groq_llama, deepseek_r1, openrouter_fallback)"
        status: pass
      - kind: unit
        ref: "backend/app/llm_router.py json-mode plumbing smoke check (python -c)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Groq's completion-token cap is 512 without JSON output (byte-identical to before) and a larger structured-payload budget with it; OpenRouter never carries reasoning_effort or a completion cap in either state"
    requirement: "ORC-03"
    verification:
      - kind: unit
        ref: "backend/tests/test_llm_router.py::test_build_openai_compatible_request_groq_completion_cap_differs_by_json_output"
        status: pass
      - kind: unit
        ref: "backend/tests/test_llm_router.py::test_build_openai_compatible_request_openrouter_never_carries_groq_vendor_fields (parametrized: True, False)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Driving synthesize_capa through the REAL call_llm against a mocked Groq endpoint: the captured request body carries JSON mode, and the returned proposal's four narrative values are the model's own strings (not the template), attributed to the provider-reported model id -- proving the plumbing at A7's own call site, not merely at the router unit level"
    requirement: "REM-01"
    verification:
      - kind: integration
        ref: "backend/tests/test_a7_remediation.py::test_respx_synthesize_capa_through_real_call_llm_reaches_groq_with_json_mode"
        status: pass
      - kind: integration
        ref: "backend/tests/test_llm_router.py::test_call_llm_remediation_task_reaches_groq_with_json_mode_on_the_wire"
        status: pass
      - kind: unit
        ref: "backend/tests/test_a7_remediation.py::test_synthesize_capa_calls_call_llm_with_remediation_task_and_json_output"
        status: pass
    human_judgment: false
  - id: D5
    description: "Null message content (Groq reasoning-model truncation shape), malformed JSON, and a wall-clock ceiling breach on a hanging provider all fall back to the deterministic CAPA with 'deterministic-fallback' attribution, each now emitting a logged warning naming the failure; a ceiling breach returns in roughly the ceiling, not roughly twice it. A7_ELIGIBLE_CONFIDENCE, its fail-closed gate, _deterministic_capa, and run_a7 are all unchanged."
    requirement: "REM-01"
    verification:
      - kind: integration
        ref: "backend/tests/test_a7_remediation.py::test_respx_null_content_groq_truncation_falls_back_and_logs_a_warning"
        status: pass
      - kind: unit
        ref: "backend/tests/test_a7_remediation.py::test_malformed_json_narrative_falls_back_to_deterministic_capa"
        status: pass
      - kind: unit
        ref: "backend/tests/test_a7_remediation.py::test_ceiling_breach_returns_deterministic_fallback_within_roughly_the_ceiling"
        status: pass
      - kind: unit
        ref: "backend/tests/test_a7_remediation.py AST gates (test_a7_never_imports_the_verifier, test_a7_is_the_only_module_permitted_a_model_call_in_this_phase) -- unchanged, still pass"
        status: pass
    human_judgment: false
  - id: D6
    description: "A live generate-capa against a C1-eligible seeded finding completes in low single-digit seconds (versus the 18s baseline) with a model-authored, non-template narrative, and a direct call_llm probe's reported completion-token usage sits clear of the 2048 cap"
    requirement: "ORC-03"
    verification:
      - kind: manual_procedural
        ref: "Live smoke against GXP-MFG-DEMO-01 finding A2-ANNEX11-S11-PE-001-PE-2024-01: generate-capa completed in 1.447s with a model-authored narrative; direct probe completed in 0.978s using 264/2048 completion tokens (finish_reason=stop). See Performance section below."
        status: pass
    human_judgment: true
    rationale: "A live-provider timing and content-quality measurement depends on the actual key/network/model state of this environment at run time; it is recorded as evidence here but is not a repeatable CI assertion the way the mocked tests above are."

duration: ~55min
completed: 2026-08-26
status: complete
---

# Quick Task 260826-rsw: Fix CAPA Generation (A7 Remediation) Latency Summary

**Groq-routed A7 remediation under a 6s wall-clock ceiling, with JSON mode wired through the shared OpenAI-compatible request builder for Groq/DeepSeek/OpenRouter alike and a shape-sized completion-token budget -- cutting live CAPA generation from an 18s baseline to 1.447s measured.**

## Performance

- **Duration:** ~55 min (includes four full-suite baseline/verification runs at 240-570s each, plus a live smoke measurement against a running Postgres/OPA stack)
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- **Task 1 -- JSON mode plumbing, routing move, wall-clock ceiling.** `_build_openai_compatible_request` now accepts and honours `json_output`, adding the standard `response_format: {"type": "json_object"}` field for every OpenAI-compatible provider it serves (Groq, DeepSeek, OpenRouter) when set, and omitting it entirely when clear -- proven both ways so every already-shipped narration/incident/access call stays byte-identical. Groq's `max_completion_tokens` is now selected by output shape via two named module constants: `GROQ_MAX_COMPLETION_TOKENS_DEFAULT` (512, unchanged) without JSON output, `GROQ_MAX_COMPLETION_TOKENS_JSON` (2048) with it. `"remediation"` was moved -- both halves, in the same edit -- from `gemini_flash_thinking["use_for"]` to `groq_llama["use_for"]`, alongside the `"narration"` key 260826-p1q already added there; `select_provider`'s first-match linear scan meant an append-only change would have been a silent no-op, so a verification gate asserts both the addition and the removal together. `a7_remediation.synthesize_capa` now wraps its `call_llm` invocation in `asyncio.wait_for(A7_REMEDIATION_CEILING_SECONDS)` (6.0s), replacing the prior raw 20.0s per-attempt timeout with no total ceiling, and gained a module logger: a ceiling breach and a parse failure (malformed JSON / missing narrative key / null-content truncation) both now log a warning naming the failure, closing the gap where a `json_output` plumbing regression would have degraded silently and indistinguishably from ordinary provider unavailability. `A7_ELIGIBLE_CONFIDENCE`, its gate, `_deterministic_capa`, and `run_a7` are all untouched.
- **Task 2 -- Sweep, live proof, and Bible-deviation record.** Swept `test_routes_actions.py`, `test_ws_broadcast.py`, and `test_graph_gateways.py` for remediation-path assumptions: all three confirmed green, unedited -- `_delete_all_provider_keys` already included `GROQ_API_KEY`, and the two live-call test files already tolerate a proposal-or-degraded outcome by design. A live smoke test (services up, a real `GROQ_API_KEY` present in this environment) measured a real `generate-capa` request against a C1-eligible seeded finding (`A2-ANNEX11-S11-PE-001-PE-2024-01`, `GXP-MFG-DEMO-01`) at **1.447s** end to end, with a model-authored, non-template narrative -- versus the 18s baseline. A direct `call_llm(task="remediation", json_output=True)` probe against the same live key completed in 0.978s, reporting `completion_tokens=264` against the 2048 cap (`finish_reason="stop"`, no truncation), confirming the budget is not truncating rather than merely assuming it. Recorded the routing move as a new numbered Bible deviation (Deviation 10) in `backend/README.md`, routed to SENT-7-05, and noted -- without fixing, per Rule 7 -- that the code docstring's own Deviations 10-12 references and 260826-p1q's narration-key addition have no corresponding README headings, a pre-existing documentation gap.

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire JSON mode through the OpenAI-compatible builder, move remediation to Groq, and bound A7's wall clock** - `65a9614` (feat)
2. **Task 2: Sweep the wider suite for remediation-path assumptions, prove the latency against a live call, and record the Bible deviation** - `23737a4` (docs)

_Note: this quick task's own docs commit for STATE.md is created separately by the orchestrator, per the executor's constraint not to touch STATE.md/ROADMAP.md here. This SUMMARY.md is committed directly by this executor because it is a worktree-isolated artifact that would otherwise be lost when the worktree is removed._

## Files Created/Modified

- `backend/app/llm_router.py` - `json_output` threaded into `_build_openai_compatible_request`; two named Groq completion-cap constants; `"remediation"` moved from `gemini_flash_thinking` to `groq_llama`'s `use_for`; module docstring updated.
- `backend/app/agents/a7_remediation.py` - `asyncio`/`logging` imports, module logger, `A7_REMEDIATION_CEILING_SECONDS` constant; `synthesize_capa`'s `call_llm` invocation wrapped in `asyncio.wait_for`; warnings on ceiling breach and parse failure; docstrings updated.
- `backend/tests/test_llm_router.py` - Routing-move assertion (both directions); `_build_openai_compatible_request` presence/absence/cap/vendor-field-gating unit tests (Groq, DeepSeek, OpenRouter); end-to-end `call_llm(task="remediation", json_output=True)` respx test.
- `backend/tests/test_a7_remediation.py` - Fixture `model_id`/`provider` corrected Google->Groq; new call-kwargs guard test; respx-level real-`call_llm` test proving JSON mode reaches the wire; null-content-truncation test; ceiling-breach test.
- `backend/README.md` - New Deviation 10 entry recording the routing move, the JSON-mode plumbing, the wall-clock ceiling, and the live measurement; noted the pre-existing Deviation-10-12/narration-key documentation gap without fixing it.

## Decisions Made

See `key-decisions` in frontmatter. The most consequential: `response_format` is applied to all three OpenAI-compatible providers (not gated to Groq like `reasoning_effort`/`max_completion_tokens`), because OpenRouter is A7's own cascade fallback -- gating JSON mode to Groq alone would mean the fallback silently loses it and returns prose exactly when the primary provider is already failing.

## Deviations from Plan

None - plan executed as written. The plan's own Design Notes 1-5 anticipated and were followed exactly: the routing move was a remove-and-add in the same edit (Design Note 1), the completion cap is selected by `json_output` rather than a new parameter (Design Note 2), `response_format` applies broadly while `reasoning_effort`/`max_completion_tokens` stay Groq-gated (Design Note 3), the ceiling is a total wall-clock budget via `asyncio.wait_for` rather than a raw `timeout` (Design Note 4), and the parse-failure branch now logs (Design Note 5).

## Issues Encountered

- **Stale worktree fork base.** This worktree's branch had diverged from `main` before quick task 260826-p1q's four commits (the narration cold-path fix this task mirrors) landed on `main` -- the worktree's copies of `llm_router.py` and `a7_remediation.py` were pre-p1q (no `"narration"` key, no `json_output` threading in the OpenAI-compatible builder, no null-content coercion). Confirmed via `git merge-base HEAD main` equalling the worktree's own `HEAD`, then resolved with `git merge --ff-only main` before any edit, per this executor's own pre-flight instruction. Fast-forwarded cleanly; re-verified the merged-but-unedited state against the full suite (350 passed) before making any change, so the subsequent 365-passed result is attributable entirely to this task's own edits.
- **`infra/health-check.sh` reported all three services RED** despite Postgres and OPA both being genuinely reachable (confirmed directly via `node -e` socket/fetch checks, and by the full test suite's own real DB/OPA integration tests passing). The script specifically requires Docker Compose-managed containers with health labels; this environment's services are evidently running by another mechanism. Used direct port/HTTP checks instead for the Task 2 live-smoke pre-flight, matching how the test suite itself already reaches these services.
- **No `.venv` inside this worktree** (gitignored, not carried into git worktrees, consistent with 260826-p1q's own prior finding). Invoked the main checkout's `backend/.venv/Scripts/python.exe` directly by absolute path for every test run and the live probe script, with `cwd` set to the worktree's own `backend/` directory so Python resolves the `app` package from there rather than from the main checkout.

## User Setup Required

None - no external service configuration required. `backend/requirements.txt` shows no diff (confirmed via `git diff --stat`) -- zero new dependencies.

## Next Phase Readiness

- Full backend suite: **365 passed, 0 failed** (baseline 350 + 15 new tests: 4 in `test_a7_remediation.py`, 11 in `test_llm_router.py` counting parametrized instances as their base function definitions).
- CAPA generation's cold-path story now matches narration's: routed to Groq, bounded by a 6.0s total wall-clock ceiling, with a live measurement (1.447s full route, 0.978s direct probe) showing wide headroom under both the ceiling and the 2048-token completion cap.
- `A7_ELIGIBLE_CONFIDENCE`, the REM-01 eligibility gate, `_deterministic_capa`, and `run_a7`'s D-03 gate are all byte-identical to before this task -- proven, not merely asserted, by the AST gates and the unchanged eligibility-parametrized tests continuing to pass.
- No blockers for later phases. The pre-existing README deviation-numbering gap (code docstring references Deviations 10-12 and the narration-key addition with no corresponding README headings) remains open, routed to SENT-7-05, and was deliberately not backfilled here (Rule 7 scope boundary).

## Self-Check: PASSED

All 5 files modified verified present via the git diff stat above (`backend/app/llm_router.py`, `backend/app/agents/a7_remediation.py`, `backend/tests/test_llm_router.py`, `backend/tests/test_a7_remediation.py`, `backend/README.md`). Both task commits (`65a9614`, `23737a4`) verified present in `git log --oneline`.

---
*Phase: quick*
*Completed: 2026-08-26*
