---
phase: quick
plan: 260825-wga
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/app/llm_router.py
  - backend/tests/test_llm_router.py
  - backend/tests/test_a0_orchestrator.py
  - backend/tests/test_a2_compliance.py
  - backend/tests/test_hero_loop.py
  - backend/tests/test_hero_tracer.py
  - backend/tests/test_minimal_specialists.py
  - backend/README.md
autonomous: true
requirements: [ORC-02, ORC-03]

estimate:
  tokens: 44000
  raw_tokens: 22000
  tasks: 3
  confidence: low

must_haves:
  truths:
    - "A Gemini call built by the router targets a model Google currently serves (no 404 'no longer available to new users')."
    - "The compliance/knowledge/change fast path is accepted by Google (no 400 'Request contains an invalid argument' from a zero thinking budget)."
    - "A Groq call built by the router targets a model present in the account's current /v1/models catalog (no 404 model_not_found)."
    - "The backend test suite fails on exactly the 13 pre-existing OPA-corroboration tests and nothing else."
  artifacts:
    - backend/app/llm_router.py
    - backend/README.md
    - backend/tests/test_llm_router.py
  key_links:
    - "PROVIDER_CONFIG['gemini_*']['model'] -> _build_google_request() URL path -> the respx route literal in 6 test files. This is the silent breaker: the model name is embedded in the request URL, so changing it un-matches every mocked Google route."
    - "PROVIDER_CONFIG['gemini_flash_fast']['thinking_budget'] -> generationConfig.thinkingConfig.thinkingBudget -> the single equality assertion in test_llm_router.py."
    - "_parse_google_response() returns entry['model'] as model_id -> finding['model_attribution'] in A2/A3/tracer assertions."
---

<objective>
Three PROVIDER_CONFIG values in `backend/app/llm_router.py` name provider models that
have been retired out from under this repo. All three were confirmed dead, and their
replacements confirmed live, against the real provider APIs using the keys already in
`backend/.env` during this session:

| Entry | Field | Current (dead) | Confirmed working |
|---|---|---|---|
| `gemini_flash_thinking` | `model` | retired Gemini 2.5 flash id | `gemini-3.6-flash` |
| `gemini_flash_fast` | `model` | retired Gemini 2.5 flash id | `gemini-3.6-flash` |
| `gemini_flash_fast` | `thinking_budget` | `0` (now HTTP 400) | `1` |
| `groq_llama` | `model` | retired Llama 3.3 70B id | `openai/gpt-oss-120b` |

Purpose: a human is blocked at a Phase 5 checkpoint waiting to verify LLM-backed
explainability text on assurance cards and CAPA proposals. Every Google and Groq call
the router makes currently 404s, so that text can never render. This unblocks it.

Output: corrected `PROVIDER_CONFIG`, a truthful module docstring, three new numbered
Bible deviations in `backend/README.md`, and a test suite that still passes at baseline.

**Why this is not a one-line change.** The Gemini model id is interpolated into the
request *path* by `_build_google_request()`
(`{base_url}/models/{model}:generateContent`). Six test files register respx routes
against that full URL as a hard-coded literal. Changing the config without changing
those literals makes every mocked Google route stop matching, and respx raises an
`AssertionError` for the unmatched request rather than anything `call_llm()` catches —
so the failure surfaces as a wall of unrelated-looking test errors. Task 2 exists
solely to keep that from happening, and is the same fix, not scope creep.

**Explicitly NOT touched** (deliberate, not oversight):
- `deepseek_r1` — the key is valid; the account returns HTTP 402 Insufficient Balance.
  That is billing, not code.
- `openrouter_fallback` — `openrouter/auto` returns HTTP 200 today.
- `backend/app/agents/minimal_specialists.py` — its three stale-name occurrences are
  deliberate literal transcriptions of the Bible's A1 abstain finding and A1 system
  prompt (already documented as such in its own docstring). Out of the declared scope
  and governed by SENT-7-05. Flagged here, not fixed.
- `backend/tests/test_schemas.py` and `backend/tests/test_c1_verifier.py` — their
  occurrences are inert fixture data for a free-text `model_attribution` field, not
  coupled to `PROVIDER_CONFIG`. They cannot fail from this change, and
  `test_c1_verifier.py` holds 4 of the 13 baseline failures, so editing it would
  muddy the baseline comparison in Task 3.
- No live-network test is added. The suite mocks providers via respx; the live
  verification recorded above is the proof these values work.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/phases/05-safety-remediation/deferred-items.md
@backend/app/llm_router.py
</context>

<tasks>

<task type="tracer">
  <name>Task 1: Correct PROVIDER_CONFIG and prove it through the router's own contract tests</name>
  <files>backend/app/llm_router.py, backend/tests/test_llm_router.py</files>
  <precondition>`backend/.venv/Scripts/python.exe` exists and `python -m pytest` runs from `backend/`.</precondition>
  <action>
FIRST, capture a fresh pre-edit baseline so Task 3 has something to diff against.
Run the suite once before touching anything and save the failing node IDs:
`cd backend && .venv/Scripts/python.exe -m pytest -q --tb=no -rf > "$SCRATCH/baseline.txt" 2>&1` (use the
session scratchpad directory, NOT the repo). Expect 13 failed / 294 passed per
`.planning/phases/05-safety-remediation/deferred-items.md`. If the count differs
materially from 13/294, STOP and report — the baseline has drifted and the
"no new failures" gate in Task 3 would be meaningless.

Then in `backend/app/llm_router.py`, edit only the `PROVIDER_CONFIG` dict and the
module docstring:

1. `gemini_flash_thinking["model"]` -> `"gemini-3.6-flash"`. Leave its
   `thinking_budget` at 512 (verified accepted).
2. `gemini_flash_fast["model"]` -> `"gemini-3.6-flash"`.
3. `gemini_flash_fast["thinking_budget"]` -> `1`. Google now rejects a zero budget
   with HTTP 400; 1 is the smallest verified-accepted value and preserves the
   entry's intent (minimum reasoning overhead for the latency-sensitive
   compliance/knowledge/change path).
4. `groq_llama["model"]` -> `"openai/gpt-oss-120b"`, taken from the account's live
   `GET /v1/models` catalog. Leave `rpm_limit` at 300 — it is the Bible's value and
   the new model's real rate limit was not measured; do not invent one.
5. Do not modify `deepseek_r1` or `openrouter_fallback` in any way.

Then repair the module docstring, which currently makes two claims that this edit
falsifies: it says there are "three corrections", and it asserts that
"thinking_budget" is among the keys "unchanged from the Bible". Rewrite it to say
six corrections, add the three new bullets pointing at the new README deviation
numbers 10/11/12, and drop `thinking_budget` from the unchanged-keys sentence.
Keep the existing bullets for deviations 4-6 intact.

Then update `backend/tests/test_llm_router.py` so its contract tests describe the
new config. Six respx routes and two assertions reference the old Gemini id via the
full URL literal `.../v1beta/models/<old-id>:generateContent` — repoint all six to
the new id, and update the `model_id` equality assertion in
`test_call_llm_parses_mocked_gemini_response`. In
`test_call_llm_compliance_task_uses_zero_thinking_budget`, the asserted budget is now
1, not 0 — change the assertion AND rename the test so the name is not a lie; use a
name describing a minimum (not zero) budget. Also update the module-level
`OPENAI_COMPATIBLE_SUCCESS_BODY["model"]` and the matching `result.model_id`
assertion in `test_call_llm_parses_mocked_openai_compatible_response` to the new Groq
id — those two move together because `_parse_openai_compatible_response()` prefers the
echoed body value, so leaving the body stale would keep the assertion green while
mocking a response no real provider would now send. Leave the `openrouter/auto` and
`deepseek-v4-pro` strings in this file untouched.

Do not add a code comment naming either retired model id in `PROVIDER_CONFIG` or in
the test file; the retirement is documented in the README deviations and the module
docstring, which is where Task 3's greps expect it.
  </action>
  <verify>
    <automated>cd backend &amp;&amp; .venv/Scripts/python.exe -m pytest tests/test_llm_router.py -q</automated>
    <automated>cd backend &amp;&amp; grep -n '"model":' app/llm_router.py | grep -Ec 'gemini-2\.5-flash|llama-3\.3-70b-versatile'  # must print 0</automated>
    <automated>cd backend &amp;&amp; grep -c 'gemini-3\.6-flash' app/llm_router.py  # must print 2</automated>
    <automated>cd backend &amp;&amp; grep -Ec 'gemini-2\.5-flash|llama-3\.3-70b-versatile' tests/test_llm_router.py  # must print 0</automated>
  </verify>
  <done>
`tests/test_llm_router.py` passes with zero failures. The `"model":` lines of
`PROVIDER_CONFIG` contain neither retired id; `deepseek-v4-pro` and `openrouter/auto`
are still present and unchanged. The module docstring no longer claims
`thinking_budget` is unchanged from the Bible. A baseline file of pre-edit failures
exists in the scratchpad.
  </done>
</task>

<task type="auto">
  <name>Task 2: Repoint the five dependent test files' mocked Google routes</name>
  <files>backend/tests/test_a0_orchestrator.py, backend/tests/test_a2_compliance.py, backend/tests/test_hero_loop.py, backend/tests/test_hero_tracer.py, backend/tests/test_minimal_specialists.py</files>
  <action>
Each of these files hard-codes the Gemini request URL, which embeds the model id.
After Task 1 the router posts to a different path, so every one of these routes now
fails to match. Update the model id inside each URL literal, leaving the rest of each
URL (`https://generativelanguage.googleapis.com/v1beta/models/...:generateContent`)
exactly as-is:

- `test_a0_orchestrator.py` — one module-level `GEMINI_URL` constant. Its
  `thinkingBudget == 512` assertion is for the orchestrator/thinking entry and stays
  at 512; do not touch it.
- `test_a2_compliance.py` — one module-level `GEMINI_ENDPOINT` constant, plus a
  `finding["model_attribution"]` equality assertion in the mocked-run comparison.
  That attribution is derived from `LLMResponse.model_id`, which for Google is
  `entry["model"]`, so it must move to the new id. The degraded-run branch of the
  same test asserts a deterministic-fallback attribution — leave that alone.
- `test_hero_loop.py` — one module-level `GEMINI_URL` constant, plus the mocked Groq
  response body's echoed model string, which should become the new Groq id so the
  mock still resembles a real Groq response. Leave the `deepseek-v4-pro` and
  `openrouter/auto` echoes alone.
- `test_hero_tracer.py` — two separate inline URL literals (not a shared constant;
  find both), plus one `finding["model_attribution"]` assertion.
- `test_minimal_specialists.py` — one module-level `GEMINI_URL` constant, plus the
  `model_attribution` assertion in the A3-DeepSeek-timeout-downgrades-to-Gemini test
  (derived from `model_id`, so it moves). CRITICAL: leave the `model_attribution`
  assertion in the A1 abstain test alone. That one mirrors a hard-coded literal in
  `_a1_abstain_finding()` in `minimal_specialists.py`, which this plan does not
  touch; changing the assertion would break a currently-passing test. Exactly one
  occurrence of the old Gemini id must survive in this file.

Note that `test_hero_loop.py` and `test_hero_tracer.py` contain 4 of the 13
pre-existing baseline failures. Those tests will still fail after this edit, for the
same unrelated OPA-corroboration reason. That is expected; do not attempt to fix them.
  </action>
  <verify>
    <automated>cd backend &amp;&amp; grep -Ec 'gemini-2\.5-flash|llama-3\.3-70b-versatile' tests/test_a0_orchestrator.py tests/test_a2_compliance.py tests/test_hero_loop.py tests/test_hero_tracer.py  # each must print 0</automated>
    <automated>cd backend &amp;&amp; grep -c 'gemini-2\.5-flash' tests/test_minimal_specialists.py  # must print exactly 1 (the A1 abstain assertion)</automated>
    <automated>cd backend &amp;&amp; .venv/Scripts/python.exe -m pytest tests/test_a0_orchestrator.py tests/test_a2_compliance.py tests/test_minimal_specialists.py -q</automated>
  </verify>
  <done>
`test_a0_orchestrator.py`, `test_a2_compliance.py` and `test_minimal_specialists.py`
pass with zero failures. `test_hero_loop.py` and `test_hero_tracer.py` fail only on
the 4 node IDs already listed in `deferred-items.md` — no unmatched-route
`AssertionError` appears anywhere in the output.
  </done>
</task>

<task type="auto">
  <name>Task 3: Record deviations 10-12 and confirm the suite against baseline</name>
  <files>backend/README.md</files>
  <action>
`backend/README.md`'s "Bible deviations (backend tier)" section currently ends at
Deviation 9. Append three new entries — 10, 11, 12 — following the exact structure the
existing entries use (**Bible says:** / **Implemented:** / **Why:** / **Evidence:** /
**Scope:**, each routed to **SENT-7-05**). One Bible field per deviation, matching the
existing granularity of deviations 4/5/6:

- **Deviation 10** — both Google entries' `model` corrected from the retired Gemini
  2.5 flash id to `gemini-3.6-flash`. Why: Google's API returns 404 naming the
  replacement model directly in the error body ("no longer available to new users").
- **Deviation 11** — `gemini_flash_fast["thinking_budget"]` corrected from the Bible's
  `0` to `1`. Why: a zero budget is now rejected with HTTP 400 "Request contains an
  invalid argument"; 1 is the smallest accepted value and preserves the field's intent
  of minimum reasoning overhead on the latency-sensitive path. Note explicitly that
  this makes the module docstring's former "thinking_budget is unchanged from the
  Bible" claim obsolete.
- **Deviation 12** — `groq_llama["model"]` corrected from the retired Llama 3.3 70B id
  to `openai/gpt-oss-120b`. Why: the id returns 404 `model_not_found`, and the
  account's live `GET /v1/models` catalog contains no Llama models at all. Note that
  `rpm_limit` is left at the Bible's 300 because the new model's real limit was not
  measured.

For **Evidence:** on all three, cite live verification against the real provider APIs
using the keys in `backend/.env`, dated 2026-08-25 — not a docs fetch. These are the
first deviations in this file backed by live calls rather than documentation, so say
so plainly.

Do NOT edit deviations 1-9. Do NOT add a deviation for `deepseek_r1`'s HTTP 402 —
that is an account balance issue, not a code deviation.

Then run the full suite and diff against the Task 1 baseline.
  </action>
  <verify>
    <automated>cd backend &amp;&amp; grep -c '^### Deviation' README.md  # must print 12</automated>
    <automated>cd backend &amp;&amp; .venv/Scripts/python.exe -m pytest -q --tb=no -rf 2>&amp;1 | tail -25</automated>
  </verify>
  <done>
README.md contains 12 numbered deviations, 1-9 byte-identical to before. The full
suite reports the SAME 13 failing node IDs as the Task 1 baseline file and the same
294 passing — compare the failing node-ID SETS, not just the counts. If any node ID
appears in the new failure set that is not in the baseline set, this task is NOT done:
report the new failure rather than closing.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| backend -> external LLM provider APIs | Outbound only; API keys cross this boundary in request headers |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-quick-01 | Information Disclosure | `llm_router.call_llm()` failure logging | high | accept (already mitigated) | No change to logging or key-resolution paths in this plan. The two existing leak tests (`test_call_llm_never_logs_the_key_value_on_failure`, `test_leak_key_absent_from_log_on_missing_key_path`) remain in the suite and must stay green — they are covered by Task 1's `pytest tests/test_llm_router.py` gate. |
| T-quick-02 | Tampering | new model identifier strings | medium | mitigate | Both replacement ids were read from the providers' own authoritative surfaces (Google's 404 error body naming its successor; Groq's live `GET /v1/models` catalog) and confirmed with real 200-returning calls, not from model recall — per CLAUDE.md Rule 13's posture on generated claims. |
| T-quick-SC | Tampering | npm/pip/cargo installs | n/a | n/a | No package is installed or upgraded by this plan. No package-legitimacy gate applies. |
</threat_model>

<verification>
1. `cd backend && .venv/Scripts/python.exe -m pytest -q --tb=no -rf` — 13 failed / 294
   passed, and the 13 failing node IDs are set-identical to the Task 1 baseline.
2. Neither retired model id appears in any `"model":` line of `PROVIDER_CONFIG`.
3. Exactly one occurrence of the old Gemini id survives across the six edited test
   files (the A1 abstain assertion in `test_minimal_specialists.py`).
4. `deepseek_r1` and `openrouter_fallback` are byte-identical to their pre-plan state:
   `cd backend && git diff app/llm_router.py` shows no change inside either entry.
5. README deviations 1-9 are unmodified: `cd backend && git diff README.md` shows only
   additions at the end of the deviations section.
</verification>

<success_criteria>
- Router-built Gemini requests target `gemini-3.6-flash` with a non-zero thinking
  budget on both Google entries.
- Router-built Groq requests target `openai/gpt-oss-120b`.
- `deepseek_r1` and `openrouter_fallback` untouched.
- Full backend suite: no failure that was not already failing at baseline.
- The module docstring and README deviations 10-12 truthfully describe all six
  corrections, leaving the SENT-7-05 reconciliation trail complete.
</success_criteria>

<output>
Commit with `fix(llm-router): retarget retired Gemini and Groq model ids`.
No SUMMARY.md required (quick task).
</output>
