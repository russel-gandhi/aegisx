---
phase: quick
plan: 260826-rsw
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/app/llm_router.py
  - backend/app/agents/a7_remediation.py
  - backend/tests/test_llm_router.py
  - backend/tests/test_a7_remediation.py
  - backend/README.md
autonomous: true
requirements: [REM-01, ORC-03]

estimate:
  tokens: 35000
  raw_tokens: 35000
  tasks: 2
  confidence: low

must_haves:
  truths:
    - "`select_provider('remediation')` returns `'groq_llama'`, while `'orchestrator'`, `'synthesis'`, `'compliance'`, `'narration'`, `'risk_assessment'`, `'incident'`, `'access'`, `'high_volume'` and `'fallback'` resolve exactly as they do today."
    - "A request built for any OpenAI-compatible provider with `json_output=True` carries `response_format` on the wire; the same request with `json_output=False` carries no such key, so every already-shipped narration/incident/access call is byte-identical to today's."
    - "A Groq request carrying `json_output=True` gets a completion-token budget sized for a four-field CAPA payload, not the one-sentence narration floor, so a reasoning-model truncation cannot masquerade as a malformed narrative."
    - "`synthesize_capa` returns within roughly its wall-clock ceiling on a hanging provider — not roughly twice it — and CAPA generation against a live provider completes in low single-digit seconds rather than 18s."
    - "A CAPA whose narrative came from the model carries the model's own four narrative strings and the provider-reported model id; a CAPA that fell back carries `'deterministic-fallback'` — and the fallback path now emits a warning log, so a plumbing regression is loud rather than silent."
    - "`A7_ELIGIBLE_CONFIDENCE` and the REM-01 eligibility gate are byte-identical to today, and `_deterministic_capa` still exists and still fires on genuine degradation."
    - "The backend suite reports 0 failed and at least 350 passed."
  artifacts:
    - "backend/app/llm_router.py: `_build_openai_compatible_request` accepting and honouring `json_output`, with the Groq completion cap sized by output shape"
    - "backend/tests/test_llm_router.py: request-body assertions proving `response_format` presence AND absence"
    - "backend/tests/test_a7_remediation.py: a respx-level test driving the real `call_llm` that asserts the outbound body carries JSON mode and that the response parses into the four narrative keys"
    - "backend/README.md: a numbered Bible-deviation entry recording the remediation routing move"
  key_links:
    - "`select_provider` returns the FIRST `PROVIDER_CONFIG` entry whose `use_for` contains the task, and `gemini_flash_thinking` is declared BEFORE `groq_llama`. `'remediation'` already lives in `gemini_flash_thinking['use_for']`, so merely APPENDING it to `groq_llama['use_for']` is a silent no-op: routing stays on Gemini, every test still passes, and the 18s latency is unchanged. It must be REMOVED from the Google entry in the same edit. This is the single difference from the narration fix, where `'narration'` was a brand-new key."
    - "`call_llm(json_output=...)` -> `_send_one` -> the request builder. `_send_one` currently forwards `json_output` ONLY to `_build_google_request`; the OpenAI-compatible branch drops it on the floor. Forwarding it is the whole prerequisite — without it, JSON mode is silently ignored and every CAPA quietly degrades to the template while still returning HTTP 200."
    - "Groq's `max_completion_tokens` -> reasoning tokens -> `finish_reason: 'length'` -> null/partial content -> `json.loads` failure -> `_deterministic_capa`. The 512 floor was sized for one narration sentence; a four-field CAPA plus reasoning tokens will overrun it, and the overrun surfaces ONLY as a generic-looking CAPA. Sizing the cap by output shape is what keeps this failure from being invisible."
    - "`asyncio.wait_for(ceiling)` around `call_llm` -> the router's internal cascade. `call_llm` reuses its `timeout` argument for the OpenRouter attempt, so a raw `timeout=N` alone permits ~2N. The outer `wait_for` is the binding ceiling — same reasoning as quick task 260826-p1q's Design Note 2."
    - "Provider switch -> respx mock endpoint + env var key name + response body shape. Per 260826-p1q's hard-won lesson, the key name is the SILENT one: `_send_one` raises `_MissingKeyError` before any HTTP call, so an unswept key name produces a test that passes while never exercising the real path. Here the exposure is narrow — `test_a7_remediation.py` monkeypatches `call_llm` in A7's own namespace and never mocks HTTP — but the new respx-level test must set `GROQ_API_KEY`, not a Google key."
---

<objective>
CAPA generation takes 18s. `synthesize_capa` routes `task="remediation"` to
`gemini_flash_thinking` (thinking_budget=512) with `call_llm`'s `timeout=20.0` and no
wall-clock ceiling — the same class of problem quick task 260826-p1q just fixed for A2
narration, on the one call site that fix did not cover.

The fix is the same shape (route to Groq, bound the wall clock), but it cannot simply be
copied, because A7 differs from narration in two ways that each hide a silent failure:

1. A7 asks for **strict JSON** (`json_output=True`, four required string keys, parsed with
   `json.loads`). `_build_openai_compatible_request` — the builder Groq, DeepSeek and
   OpenRouter all share — does not accept `json_output` at all. Only the Google builder
   honours it. Repointing A7 at Groq without fixing this means JSON mode is silently
   ignored, Groq returns prose, `json.loads` raises, and every CAPA degrades to the generic
   `_deterministic_capa` template — HTTP 200, well-formed response, quietly worthless output.
2. `'remediation'` is **already** a task key on the Google entry. `select_provider` returns
   the first matching entry and Google is declared first, so appending the key to Groq
   without removing it from Google changes nothing at all, while looking exactly like a fix.

Purpose: make the demo's remediation step feel instant without moving one byte of
compliance judgement off the deterministic path. A7 synthesizes narrative prose from
findings C1 has *already* verified; nothing here touches what gets verified or how.

Output: JSON mode wired through the OpenAI-compatible request builder for all three
providers that share it, a completion-token budget sized by output shape, remediation
routed to Groq under a hard wall-clock ceiling, a parse-failure warning so a future
plumbing regression is loud, and tests that prove the request body actually carries JSON
mode rather than merely that a mock returned parseable text.

## What this plan explicitly does NOT touch

`A7_ELIGIBLE_CONFIDENCE` and the REM-01 eligibility gate in `synthesize_capa` stay
byte-identical — this is latency and provider work, not remediation-logic work. C1's
`verify_finding()` and `calculate_confidence()` are not read, imported, or referenced.
`_deterministic_capa` keeps existing and keeps firing on genuine degradation; the only
change to its role is that it stops firing *silently* on a plumbing bug. The A7 system
prompt, the four `CAPA_NARRATIVE_FIELDS`, `_capa_due_date`, `A7_DEFAULT_OWNER`,
`_build_capa_payload`, `_compose_justification` and `run_a7`'s D-03 gate are all untouched.
No frontend, no streaming, no pre-warming, no new dependency.

## Design decisions and why

**Design Note 1 — the routing change is a MOVE, not an ADD.**
`gemini_flash_thinking["use_for"]` is `["orchestrator", "synthesis", "remediation"]` and it
is the first entry in `PROVIDER_CONFIG`. `select_provider` scans linearly and returns the
first match. The narration fix appended a *new* key to Groq and that was sufficient; here
the key already exists upstream, so it must be removed from the Google entry and added to
the Groq entry in the same edit. `"orchestrator"` and `"synthesis"` stay on Google
untouched — A0's intent classification and C3's synthesis are not in scope. A verification
gate asserts both halves so a half-done edit cannot pass.

**Design Note 2 — the completion cap is selected by output shape, not by a new parameter.**
`json_output` is already threaded from `call_llm` to `_send_one` and is already the signal
the Google builder branches on. Reusing it to select the Groq completion budget keeps the
public `call_llm` signature unchanged and gives the correct behaviour for free: narration
(`json_output=False`) keeps the existing 512 floor byte-for-byte, so the shipped narration
path carries zero regression risk, while A7 (`json_output=True`) gets a budget sized for
four narrative fields. 2048 is the starting value: a four-field CAPA is roughly 400-600
content tokens, and `openai/gpt-oss-120b` charges reasoning tokens against the same budget
even at `reasoning_effort="low"`, so the remainder is deliberate headroom, not slack. Task 2
measures actual usage against a live call and records it, so a later tuning decision rests
on evidence rather than on this estimate.

**Design Note 3 — `response_format` applies to all three OpenAI-compatible providers;
`reasoning_effort` and `max_completion_tokens` stay Groq-gated.**
These are different kinds of field and must not share a gate. `reasoning_effort` is a Groq
gpt-oss vendor extension — 260826-p1q gated it strictly on `provider == "groq"` precisely
because `openrouter/auto` may reject an unrecognized field, and that gate stays exactly as
it is. `response_format: {"type": "json_object"}` is the standard OpenAI-compatible field
that DeepSeek and OpenRouter both accept, so gating it on Groq alone would mean the
OpenRouter cascade — the fallback A7 relies on when Groq is down — silently loses JSON mode
and returns prose. Applying it to the whole OpenAI-compatible branch is what makes the
cascade actually usable for A7. Accepted consequence, stated so a reviewer does not later
"fix" it: if `openrouter/auto` ever rejects the field, that is a 4xx, which `call_llm`
already turns into a logged non-cascading degraded response, which `synthesize_capa`
already handles — a loud, attributable failure on a path that was already a last resort.

**Design Note 4 — the ceiling is a total wall-clock budget, and that deliberately narrows
the cascade.**
`call_llm` reuses its `timeout` value for the OpenRouter cascade attempt, so a raw
`timeout=6.0` alone permits a ~12s worst case. The real ceiling is
`asyncio.wait_for(call_llm(...), 6.0)` in `synthesize_capa`. On a Groq **timeout** the outer
`wait_for` fires first and the cascade gets no second attempt — a 6s budget is a 6s budget.
On a Groq **fast failure** (missing key, 429, 5xx — all sub-millisecond) `call_llm`'s
cascade still runs normally inside the remaining budget. 6.0s rather than narration's 3.0s
because four JSON fields need more generation time than one sentence; 260826-p1q measured
narration at 0.56-0.82s live, so an expected CAPA call lands well under this and the ceiling
should never fire on a healthy path. It exists for the hang, and even at its worst it is
three times faster than today's measured 18s.

**Design Note 5 — silence is the actual bug being fixed.**
A malformed or truncated narrative currently falls back to `_deterministic_capa` with no
signal whatsoever: the route returns 200, the proposal is well-formed, and the CAPA is
generic. That is exactly how a `json_output` plumbing regression would hide. A7 gains a
module logger and a warning on the parse-failure branch naming the model id and the reason.
The behaviour is unchanged — the fallback still fires, REM-01 is unaffected — but a future
regression leaves a trace. This is the smallest change that satisfies "no longer fire
SILENTLY on a json_output plumbing bug" and is not a licence to restructure the fallback.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@CLAUDE.md
@.claude/CLAUDE.md

# The sibling fix this mirrors. Read both in full before editing: they document the
# reasoning-token hazard, the missing-key silent-test-pass pitfall, and the
# wall-clock-ceiling-vs-raw-timeout distinction that all apply again here.
@.planning/quick/260826-p1q-research-and-permanently-fix-cold-path-l/260826-p1q-PLAN.md
@.planning/quick/260826-p1q-research-and-permanently-fix-cold-path-l/260826-p1q-SUMMARY.md

@backend/app/llm_router.py
@backend/app/agents/a7_remediation.py
@backend/app/agents/a2_compliance.py
@backend/app/routes/actions.py
@backend/tests/test_llm_router.py
@backend/tests/test_a7_remediation.py
@backend/tests/conftest.py
</context>

<tasks>

<task type="tracer" tdd="true">
  <name>Task 1: Wire JSON mode through the OpenAI-compatible builder, move remediation to Groq, and bound A7's wall clock</name>
  <files>backend/app/llm_router.py, backend/app/agents/a7_remediation.py, backend/tests/test_llm_router.py, backend/tests/test_a7_remediation.py</files>
  <precondition>`cd backend && .venv/Scripts/python.exe -m pytest -q` currently reports 350 passed, 0 failed (the post-260826-p1q baseline). Capture this number before making any edit; every later verification compares against it.</precondition>
  <behavior>
    - A request built for a Groq entry with JSON output requested carries `response_format` set to the JSON-object form; the same request without JSON output requested carries no `response_format` key at all.
    - The same presence/absence holds for the DeepSeek and OpenRouter entries, which share the builder.
    - A Groq request with JSON output requested carries a completion-token budget sized for a structured payload; a Groq request without it carries the existing 512 floor, unchanged.
    - The OpenRouter entry carries neither `reasoning_effort` nor a completion cap, with or without JSON output — those gates are unchanged.
    - `select_provider("remediation")` returns the Groq entry key. `select_provider("orchestrator")` and `select_provider("synthesis")` still return the Google thinking entry. `"compliance"`, `"narration"`, `"risk_assessment"`, `"incident"`, `"access"`, `"high_volume"` and `"fallback"` are all unchanged.
    - Driving `synthesize_capa` through the REAL `call_llm` against a mocked Groq endpoint: the captured outbound request body carries JSON mode, and the returned proposal's four narrative values are the model's own strings, attributed to the provider-reported model id — not the template.
    - A Groq response with null message content (the reasoning-model truncation shape) yields the deterministic fallback rather than raising, and emits a warning naming the failure.
    - A response whose text is not valid JSON, and a response missing one of the four required keys, both yield the deterministic fallback with `"deterministic-fallback"` attribution and a warning.
    - A provider call that exceeds the wall-clock ceiling returns the deterministic fallback in roughly the ceiling, not roughly twice it.
    - Every existing eligibility assertion still holds: ineligible and unrecognised confidence grades still return `(None, "not-eligible")`, and each of HIGH/MEDIUM/LOW still yields a proposal.
  </behavior>
  <action>
Work in `backend/`. Four production edits, then targeted test additions.

**1a. `app/llm_router.py` — move the remediation task key.** In `PROVIDER_CONFIG`, delete
`"remediation"` from `gemini_flash_thinking["use_for"]` (leaving `"orchestrator"` and
`"synthesis"` in place) and append it to `groq_llama["use_for"]` alongside the narration key
260826-p1q added. Both halves are mandatory and must land together — see Design Note 1 for
why appending alone is a no-op that still passes every test. Do not add a new
`PROVIDER_CONFIG` entry and do not touch any other entry's `use_for`. Leave `select_provider`
itself completely alone: its first-match linear scan is the mechanism being used, not a
thing to work around. Update the module docstring's Bible-transcription note, which
currently claims `use_for` is unchanged from the Bible — that claim is already inaccurate
after 260826-p1q's narration key and becomes materially wrong here; record the remediation
move as a new numbered deviation reference in the same style as the existing entries and
route it to SENT-7-05, matching how Deviations 4-6 and 10-12 are referenced.

**1b. `app/llm_router.py` — accept and honour JSON output in the shared builder.** Add a
`json_output: bool` parameter to `_build_openai_compatible_request`, positioned to match
`_build_google_request`'s existing signature order, and update its one caller in `_send_one`
to forward the value it already receives. When the flag is set, add the standard
OpenAI-compatible `response_format` field with the JSON-object type to the body, for every
provider this builder serves — Groq, DeepSeek and OpenRouter alike, per Design Note 3. When
the flag is clear, add nothing, so every already-shipped call site produces a byte-identical
body. Leave the existing `provider == "groq"` gate around `reasoning_effort` exactly where it
is and exactly as narrow as it is.

**1c. `app/llm_router.py` — size the Groq completion budget by output shape.** Inside the
existing Groq-gated block, select the completion-token cap from the JSON-output flag: the
current 512 when it is clear, and a larger structured-payload budget of 2048 when it is set.
Name both values as module-level constants rather than inlining the integers, so the pair is
greppable and tunable from one place. Extend the existing comment there to record why the
budget scales: reasoning tokens are charged against this cap, a four-field CAPA is several
times a narration sentence, and an overrun surfaces only as a generic-looking CAPA rather
than as an error (Design Note 2). Do not touch `reasoning_effort`, and do not add
`reasoning_format` — the existing comment already records that it is unsupported for these
models.

**1d. `app/agents/a7_remediation.py` — ceiling, logging, docstrings.** Add `import asyncio`
and `import logging` at the top of the module and create a module logger in the same house
style as `llm_router.py`. Do not import anything else; the AST gate in
`tests/test_a7_remediation.py` asserts this module never reaches the verifier, and that gate
must keep passing untouched.

In `synthesize_capa`, below the eligibility gate and the prompt construction — both of which
stay byte-identical:
  - lower the `call_llm` `timeout` argument from 20.0 to the new ceiling value;
  - wrap the whole `await call_llm(...)` in `asyncio.wait_for` at the same ceiling inside a
    `try` / `except asyncio.TimeoutError`, and on timeout return the same
    `(_deterministic_capa(...), "deterministic-fallback")` pair the existing `degraded`
    branch returns, after logging a warning;
  - in the existing `except (json.JSONDecodeError, KeyError, TypeError)` branch, log a
    warning naming the responding model id and the exception before returning the fallback,
    so a plumbing regression leaves a trace (Design Note 5). Keep the caught exception tuple
    and the returned value exactly as they are — a null-content Groq response arrives here as
    an empty string and is already handled by `json.loads` raising, so no new branch is
    needed.
Define the ceiling as a named module constant set to 6.0 rather than inlining the float in
two places. Do not restructure anything else in this function, and do not alter
`A7_ELIGIBLE_CONFIDENCE`, the gate that reads it, `_deterministic_capa`, or `run_a7`.

Update the `synthesize_capa` docstring: its second paragraph currently states remediation is
routed to `gemini_flash_thinking`, which this task makes false. Replace that with the Groq
routing, the total-wall-clock-ceiling contract, and Design Note 4's stated consequence for
the cascade — mirroring the paragraph `a2_compliance.narrate_gap`'s docstring already
carries, so the two read as one deliberate pattern rather than two ad-hoc fixes. Extend
`_deterministic_capa`'s docstring to note that its trigger conditions now also include the
wall-clock ceiling firing.

**1e. `tests/test_llm_router.py` — request-shape coverage.** This file's existing
compliance/orchestrator routing assertions and its existing Groq parse test must keep passing
untouched; their continuing to pass is the proof this change was surgical. Add:
  - routing assertions extending `test_select_provider_routes_by_task` to cover the moved key
    in both directions — remediation now resolves to the Groq entry, and orchestrator and
    synthesis still resolve to the Google thinking entry;
  - direct unit tests of `_build_openai_compatible_request` over the Groq, DeepSeek and
    OpenRouter entries, asserting `response_format` is present with the JSON-object type when
    JSON output is requested and that the key is absent from the body otherwise. Assert
    absence explicitly, not just presence — absence is what protects the shipped narration
    and incident paths;
  - a Groq-entry test asserting the completion cap differs between the two flag states and
    that the flag-clear value is still 512;
  - an OpenRouter-entry test asserting no `reasoning_effort` and no completion cap in either
    flag state;
  - an end-to-end `call_llm(task="remediation", ..., json_output=True)` test under respx with
    `GROQ_API_KEY` set, asserting the mocked Groq chat-completions route was called (proving
    the routing move landed) and that the captured request body carries JSON mode. Follow the
    file's existing convention of decoding `route.calls.last.request.content` for body
    assertions.

**1f. `tests/test_a7_remediation.py` — the proof that matters.** Keep the file's existing
`call_llm`-monkeypatching approach for the eligibility, payload-shape, due-date and
prompt-labelling tests; those are provider-agnostic by design and must not be rewritten. Two
mechanical corrections and four additions:
  - correct the fake success response's `model_id`/`provider` values from the Google strings
    to the Groq ones, together with the one attribution assertion that reads them, so the
    fixture stops implying a provider this module no longer uses. This is cosmetic honesty,
    not behaviour;
  - update the module docstring, which describes the fake as standing in for a Google request
    body;
  - add an assertion that `synthesize_capa` invokes `call_llm` with the remediation task and
    with JSON output requested, read from the fake's already-captured kwargs — this is the
    guard against a future edit dropping the flag at the call site;
  - add the respx-level test the constraint requires: set `GROQ_API_KEY`, do NOT monkeypatch
    `call_llm`, mock the Groq chat-completions endpoint to return an OpenAI-shaped body whose
    message content is the four-key CAPA JSON, call `synthesize_capa` with an eligible
    confidence, and assert three things together — the captured outbound request body carries
    JSON mode, the returned proposal's four narrative values are the model's strings rather
    than the template's, and the attribution is the provider-reported model id. All three in
    one test: any one alone can pass while the plumbing is broken. Copy the OpenAI-shaped
    body helper from `tests/test_routes_actions.py` rather than inventing one, and set the
    Groq key rather than a Google key — with the wrong key name `_send_one` raises before any
    HTTP call, respx stays silent, and the test passes while proving nothing;
  - add a null-content test in the same respx style (message content null, finish reason
    length) asserting the deterministic fallback with its fallback attribution and a captured
    warning record, proving a reasoning-model truncation is handled and is not silent;
  - add a ceiling test using a monkeypatched `call_llm` that sleeps well past the ceiling,
    asserting the deterministic fallback is returned and that elapsed wall time is comfortably
    under twice the ceiling — the property Design Note 4 exists to guarantee.
Follow the suite's conventions throughout: plain `def test_*` with `asyncio.run()` inside, no
pytest-asyncio, no asyncio primitive at module scope.
  </action>
  <verify>
    <automated>cd backend && .venv/Scripts/python.exe -m pytest tests/test_llm_router.py tests/test_a7_remediation.py -q</automated>
    <automated>cd backend && .venv/Scripts/python.exe -c "from app.llm_router import select_provider as s; assert s('remediation')=='groq_llama', s('remediation'); assert s('orchestrator')=='gemini_flash_thinking'; assert s('synthesis')=='gemini_flash_thinking'; assert s('compliance')=='gemini_flash_fast'; assert s('narration')=='groq_llama'; assert s('risk_assessment')=='deepseek_r1'; assert s('fallback')=='openrouter_fallback'; print('routing ok')"</automated>
    <automated>cd backend && .venv/Scripts/python.exe -c "from app.llm_router import PROVIDER_CONFIG as P, _build_openai_compatible_request as b; g=P['groq_llama']; o=P['openrouter_fallback']; on=b(g,'k','p','s',True); off=b(g,'k','p','s',False); assert on['json']['response_format']=={'type':'json_object'}; assert 'response_format' not in off['json']; assert off['json']['max_completion_tokens']==512; assert on['json']['max_completion_tokens']>512; oo=b(o,'k','p','s',True); assert oo['json']['response_format']=={'type':'json_object'}; assert 'reasoning_effort' not in oo['json']; assert 'max_completion_tokens' not in oo['json']; print('json-mode plumbing ok')"</automated>
    <automated>cd backend && .venv/Scripts/python.exe -m pytest -q</automated>
  </verify>
  <done>`select_provider` resolves remediation to the Groq entry while orchestrator, synthesis and every other pre-existing task mapping is unchanged. The shared OpenAI-compatible builder emits `response_format` when and only when JSON output is requested, for all three providers that share it, and the Groq completion cap is 512 without it and larger with it. Driving `synthesize_capa` through the real `call_llm` against a mocked Groq endpoint yields a CAPA whose four narrative fields are the model's own, from a request body that carried JSON mode. Null content, malformed JSON, a missing key and a ceiling breach all fall back deterministically and all log. `A7_ELIGIBLE_CONFIDENCE`, its gate, `_deterministic_capa` and `run_a7` are unchanged, and the AST gate still passes. The full suite reports 0 failed and at least 350 passed.</done>
</task>

<task type="auto">
  <name>Task 2: Sweep the wider suite for remediation-path assumptions, prove the latency against a live call, and record the Bible deviation</name>
  <files>backend/tests/test_routes_actions.py, backend/tests/test_ws_broadcast.py, backend/tests/test_graph_gateways.py, backend/README.md</files>
  <action>
**2a. Sweep — confirm, then fix only what actually breaks.** A survey done during planning
says the blast radius is small, but confirm each site rather than trusting the survey:
  - `tests/test_a7_remediation.py` monkeypatches `call_llm` inside A7's own namespace and
    mocks no HTTP at all, so Task 1 already covers it fully;
  - `tests/test_graph_gateways.py`'s A7 tests call `_delete_all_provider_keys`, whose tuple
    already includes the Groq key, so those degrade before any HTTP attempt exactly as they
    did before and need no edit. Verify the tuple really does include it before concluding
    this — a live key reaching an empty `respx.mock` context raises respx's own
    all-mocked assertion, which is how this would surface;
  - `tests/test_routes_actions.py` and `tests/test_ws_broadcast.py` drive `generate-capa`
    end-to-end with neither respx nor key deletion, so they issue real provider calls today
    and will now issue them to a different provider. Both already tolerate either a proposal
    or the documented `reason` path, so they are expected to pass unchanged — and to get
    substantially faster. Run them explicitly and confirm.
Fix anything that actually fails by the three-part rule 260826-p1q established — endpoint
URL, env var key name, and response body shape change together — never by widening a mock to
skip assertion of mocked routes. If nothing fails, change nothing: a green sweep is a
finding, and it belongs in the SUMMARY rather than in a diff.

**2b. Live latency and truncation proof.** 260826-p1q recorded that a live `GROQ_API_KEY`
exists in this environment. With services up, issue a single real `generate-capa` against a
C1-eligible seeded finding on GXP-MFG-DEMO-01 and record: the wall-clock time; whether the
returned proposal's narrative is model-authored or the template (the template's
corrective-action wording is fixed and easy to recognise); and the model id the proposal
carries. Then make one direct `call_llm` invocation with the remediation task and JSON output
requested, and read the provider's reported token usage off the raw response to confirm the
completion did not hit the cap — a completion at or near the cap means truncation and means
2048 is too small, which is exactly the silent failure this plan exists to prevent. Record
the measured numbers. Do not read, print, or commit the key value itself; only timing,
content shape and usage counts. If no live key is available, say so plainly in the SUMMARY
and mark this step not-run rather than inventing numbers — the automated gates in Task 1
still stand on their own.

**2c. `backend/README.md` — record the deviation.** Bible Section 8.1 assigns remediation to
the Google thinking entry; this plan moves it. Add one new numbered entry under the existing
"Bible deviations (backend tier)" section, matching the surrounding heading and
what/why format, recording the routing move, the JSON-mode plumbing that made it possible,
and the wall-clock ceiling, and routing the reconciliation to SENT-7-05. Number it after the
highest existing heading in the file. Note in the SUMMARY, but do NOT fix here, that the
deviations `llm_router.py`'s docstring references as 10-12 have no corresponding README
headings and that 260826-p1q's narration key was never recorded either — that backfill is a
pre-existing documentation gap and belongs to SENT-7-05, not to this task (Rule 7).
  </action>
  <verify>
    <automated>cd backend && .venv/Scripts/python.exe -m pytest tests/test_routes_actions.py tests/test_ws_broadcast.py tests/test_graph_gateways.py -q</automated>
    <automated>cd backend && .venv/Scripts/python.exe -m pytest -q</automated>
    <human-check>A real generate-capa against a C1-eligible seeded finding returns in low single-digit seconds (versus the 18s baseline) with a model-authored, non-template narrative, and the live token usage shows the completion did not hit the cap.</human-check>
  </verify>
  <done>Every test file that touches the remediation path has been checked and either needed no change or was fixed by the endpoint/key/body rule. The full backend suite reports 0 failed and at least 350 passed. A live generate-capa is measurably faster than the 18s baseline, returns a model-authored CAPA, and its token usage confirms the completion budget is not truncating. The routing move is recorded as a numbered Bible deviation in `backend/README.md`.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| FastAPI → Groq API | The CAPA prompt embeds a finding's `claim`, citations and evidence ids — partially model-authored text — and the response becomes stored CAPA narrative. |
| Groq response → `action_proposals` row | Model prose is persisted and read back verbatim on every later request; it is never re-generated. |
| `PROVIDER_CONFIG` → every agent | One shared routing table; an edit intended for A7 can silently redirect A0 or C3. |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-rsw-01 | Tampering | Groq CAPA narrative | medium | mitigate | The four narrative fields are prose only. `due_date` and `owner` remain computed in Python and are never parsed from model output, and `regulatory_citations`/`evidence_ids` are copied from the already-verified finding. The prompt keeps labelling the finding as untrusted data to summarise, not instructions to follow — the existing `test_prompt_labels_finding_text_as_untrusted` gate is untouched and must keep passing. |
| T-rsw-02 | Tampering | Silent degradation via ignored `json_output` | high | mitigate | This is the plan's whole premise. Presence AND absence of `response_format` are asserted at the builder, an end-to-end respx test proves the flag reaches the wire from A7's own call site, and the parse-failure branch now logs — so the degradation is loud instead of invisible. |
| T-rsw-03 | Denial of service | Hanging provider on the remediation path | high | mitigate | `asyncio.wait_for` at a 6.0s total wall-clock ceiling with immediate deterministic fallback; the prior 20s raw timeout could reach ~40s across the cascade. |
| T-rsw-04 | Elevation of privilege | Routing edit leaking beyond A7 | medium | mitigate | A verification gate asserts all nine task keys resolve as intended, in both directions, so removing the key from the Google entry cannot silently move orchestrator or synthesis with it. |
| T-rsw-05 | Repudiation | CAPA model attribution after the provider switch | low | mitigate | `_parse_openai_compatible_response` keeps preferring the provider-reported model id over the config string, so a stored proposal still names the model that actually authored it. Test fixtures are corrected to the real provider rather than loosened. |
| T-rsw-06 | Information disclosure | Provider key in logs | low | mitigate | The new warnings name only the model id and the failure reason. `test_llm_router.py`'s existing key-absent-from-log gates are untouched and must keep passing. The live measurement in Task 2 is explicitly forbidden from reading or printing the key. |
| T-rsw-SC | Tampering | npm/pip/cargo installs | high | mitigate | Not applicable: this plan adds zero dependencies to `backend/requirements.txt`. No package-manager install task exists, so no legitimacy checkpoint is required. If an executor finds itself reaching for `pip install`, that is a signal the approach has drifted — stop and re-read Design Note 3. |
</threat_model>

<verification>
1. `cd backend && .venv/Scripts/python.exe -m pytest -q` — 0 failed, at least 350 passed.
   The 350 baseline is the post-260826-p1q number; do not compare against the older 337.
2. The routing gate and the JSON-mode plumbing gate from Task 1's `<verify>` both print their
   ok lines.
3. `backend/requirements.txt` shows no diff.
4. Manual live smoke (services up): a real `generate-capa` against a C1-eligible seeded
   finding returns in low single-digit seconds with a model-authored narrative, and the
   direct `call_llm` probe's reported completion usage sits clear of the cap.
</verification>

<success_criteria>
- `json_output` is honoured by the OpenAI-compatible request builder for Groq, DeepSeek and
  OpenRouter, and is provably absent from the body when not requested, so no already-shipped
  call site changed shape.
- Remediation resolves to Groq — the key removed from the Google entry as well as added to
  the Groq one — with orchestrator, synthesis and all seven other task keys unchanged.
- The Groq completion budget is selected by output shape, leaving narration's 512 floor
  untouched, and the chosen structured-payload value is confirmed against live token usage
  rather than assumed.
- `synthesize_capa` is bounded by a 6.0s total wall-clock ceiling, and falls back
  deterministically — with a warning — on timeout, degradation, null content, malformed JSON,
  and a missing narrative key.
- REM-01 is untouched: `A7_ELIGIBLE_CONFIDENCE` and its fail-closed gate are byte-identical,
  A7 still never imports the verifier, and `_deterministic_capa` still exists and still fires
  on genuine degradation.
- The request body carrying JSON mode is proven at the A7 call site through the real
  `call_llm`, not merely inferred from a mock that happened to return parseable text.
- Zero new dependencies. Backend suite: 0 failed, at least 350 passed.
</success_criteria>

<output>
Create `.planning/quick/260826-rsw-fix-capa-generation-a7-remediation-laten/260826-rsw-SUMMARY.md` when done.

Record in it: the measured CAPA generation time before and after, and the live completion
token usage against the 2048 cap, so the budget can be re-tuned on evidence rather than on
this plan's estimate; the observed Groq remediation latency, so the 6.0s ceiling can be
re-tuned the same way narration's 3.0s was; the final pass count against the 350 baseline;
which sweep sites in Task 2a needed a change and which were confirmed green untouched; and
the pre-existing README deviation-numbering gap noted in 2c, so the next person inherits a
complete map rather than rediscovering it.
</output>
