# backend/

FastAPI + LangGraph application tier (D-01).

## What lands here

- The FastAPI app entrypoint and route modules (`/api/*`)
- The LangGraph `StateGraph` implementing the fixed request topology: `C2 → A0 → [A1…A6 in parallel via Send] → C1 → A7 → C3`
- Pydantic schemas (`AgentFinding`, `ActionProposal`, `AgentState`, and the rest of Section 4.3)
- The OPA client module (`evaluate_opa_policy()` and its `python_fallback_rules()` stub)
- The six domain agents (A1 System Knowledge, A2 Compliance, A3 Risk, A4 Change, A5 Incident, A6 Access) plus A0 Orchestrator and A7 Remediation
- The C1 Evidence & Grounding Verifier, C2 Policy & Safety Gateway, and C3 Action Gateway modules

## Owning tickets (Stage 1)

| Ticket | Contract |
|---|---|
| SENT-1-05 | FastAPI skeleton + Pydantic schemas — all Section 4.3 types importable, `/api/health` live |
| SENT-1-06 | LangGraph `StateGraph` skeleton — compiles with stub node returns, edges match the C2→A0→[A1-A6]→C1→A7→C3 topology exactly |
| SENT-1-04 | OPA Docker sidecar wired to the app — `evaluate_opa_policy()` calls the real REST endpoint |

## Deterministic-first constraint (Bible Section 1.3)

No LLM call in this tier may ever evaluate a compliance threshold, an RBAC decision, or a prompt-injection judgment. Those checks run in Python, Rego (via the OPA client), or NetworkX only — never inside a generative model call. See `CLAUDE.md` and Bible Section 1.3's decision table before choosing an implementation method for any check that lands in this tier.

This tier is intentionally empty until Stage 1 (ROADMAP Phase 2) begins.

## Local setup (Stage 1)

### Environment

Create a **project-local** virtual environment before installing anything. This machine's bare `pip` on `PATH` resolves to `C:\Anaconda3` — a global environment shared across unrelated projects — so the bare `pip`/`python -m pip` outside a venv must never be used to install this project's dependencies.

```bash
python -m venv backend/.venv
backend/.venv/Scripts/python -m pip install -r backend/requirements.txt
```

Note `python`, not `python3` — that is what resolves on this machine. `backend/.venv/` is gitignored; it must never appear in `git status`.

### Run

From inside `backend/`:

```bash
backend/.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
```

### Test

From inside `backend/`:

```bash
backend/.venv/Scripts/python -m pytest -x
```

### Health check

`GET /api/health` returns `200` with the exact body `{"status": "ok"}`. With the server running per the command above, verify against the live process (this machine uses `node -e "fetch(...)"` rather than `curl`, matching the convention `infra/health-check.sh` established — `curl` is unreliable under Windows Git Bash):

```bash
node -e "fetch('http://127.0.0.1:8000/api/health').then(r=>r.json().then(j=>{console.log(r.status, JSON.stringify(j))}))"
```

### Why the backend runs host-side this phase

The backend runs as a host-side process (`uvicorn` invoked directly), not as a `docker-compose.yml` service, for the duration of this phase — see `02-RESEARCH.md` Open Question 1. This means `docker-compose.yml` needs no change for this plan, and no BRANCHING.md §5 shared-file PR is triggered by standing up the FastAPI skeleton.

## Bible deviations (backend tier)

This section records every point where `backend/app/opa_client.py` departs from the literal text of `AegisX-AI-Project-Bible-v6.md` Section 3.4 (lines 548-579). **Per CLAUDE.md ("when bible content and a ticket contract disagree, the bible wins" / "drift is reconciled explicitly"), this section is input to the final bible-reconciliation review, ticket `SENT-7-05`.** No rule logic, threshold, or regulatory citation is affected — `opa_client.py` calls into the deterministic Rego policy engine, it does not itself evaluate any compliance decision (Bible Section 1.3).

**What was NOT changed:** the async POST shape, the `{"input": payload}` request body, the 2.0-second timeout, the non-2xx status check, and the `response.json().get("result", [])` extraction are all preserved exactly as Section 3.4 specifies.

### Deviation 1 — Configurable `OPA_URL` environment variable

**Bible says:** `evaluate_opa_policy()` hardcodes `http://localhost:8181/v1/data/sentinel/gxp/violation`.

**Implemented:** The URL is read from the `OPA_URL` environment variable, defaulting to `http://127.0.0.1:8181/v1/data/sentinel/gxp/violation` — the identical path, with `127.0.0.1` in place of `localhost` to sidestep IPv6-first resolution that makes `localhost` intermittently slow to connect on Windows.

**Why:** In normal operation the behaviour is identical to the Bible's hardcoded value. The fallback branch (see Deviation 2) cannot be exercised at all without pointing the client somewhere that does not answer, and stopping the shared OPA container mid-suite to force that would disrupt sibling test runs and the live Compose stack. `OPA_URL` is the first backend environment variable this project has; it deliberately requires no `.env.example` change, since its default is already correct for normal local operation (this keeps this plan clear of the BRANCHING.md §5 shared-file protocol).

### Deviation 2 — `httpx.HTTPStatusError` also routes to the fallback

**Bible says:** The `except httpx.RequestError as e:` clause is the only failure branch.

**Implemented:** `except (httpx.RequestError, httpx.HTTPStatusError) as e:` — both exception classes route to `python_fallback_rules()`.

**Why:** The Bible's own `response.raise_for_status()` call raises `httpx.HTTPStatusError` on a non-2xx response, and `HTTPStatusError` is not a subclass of `RequestError` — under the Bible's literal text it would escape the `try`/`except` entirely and crash whichever agent called this function. An OPA that answers with a 500 or a 400 is exactly as unusable to the caller as one that does not answer at all, so both branches now degrade to the same fallback. (`httpx.TimeoutException` already inherits from `RequestError` and needs no separate branch.)

### Deviation 3 — Logging instead of `print()`

**Bible says:** The failure branch calls `print(f"OPA unreachable: {e}. Executing Python fallback rules.")`.

**Implemented:** A module-level `logging.getLogger(__name__)` at `warning` level, including the exception text and the URL that failed.

**Why:** A server process writing diagnostics to stdout loses them the moment it runs anywhere other than a developer's terminal. `backend/tests/test_opa_client.py` asserts the warning is actually emitted via `caplog`, so a fallback that silently swallows a failure without leaving a trace fails the test suite.

### Deviation 4 — `deepseek_r1["model"]` corrected from a retired model name

**Bible says:** `PROVIDER_CONFIG["deepseek_r1"]["model"]` is `"deepseek-reasoner"` (Section 8.1).

**Implemented:** `"deepseek-v4-pro"`.

**Why:** DeepSeek has retired the `deepseek-reasoner` legacy alias; it does not appear anywhere in DeepSeek's current API documentation, only `deepseek-v4-flash`/`deepseek-v4-pro` do. A live call against the Bible's literal model name would fail with a 400/404 once a real key is supplied. Out of MVP scope this phase — A3 (the only agent that selects `deepseek_r1`) is v2-territory per 03-CONTEXT.md and is not exercised by A0/A2/C1.

**Evidence:** `[VERIFIED: api-docs.deepseek.com — fetched during 03-RESEARCH.md's research session]`. See `.planning/phases/03-intelligence-retrieval/03-RESEARCH.md` Pitfall 1.

**Scope:** `backend/app/llm_router.py`'s `PROVIDER_CONFIG["deepseek_r1"]` only. Routed to **SENT-7-05**.

### Deviation 5 — `openrouter_fallback["model"]` corrected to OpenRouter's actual model string

**Bible says:** `PROVIDER_CONFIG["openrouter_fallback"]["model"]` is `"auto"` (Section 8.1).

**Implemented:** `"openrouter/auto"`.

**Why:** OpenRouter's own API expects the fully-qualified model string `openrouter/auto` for its auto-routing feature; a bare `"auto"` is not a valid model identifier against OpenRouter's `/chat/completions` endpoint.

**Evidence:** `[VERIFIED: 03-RESEARCH.md Pitfall 3]`.

**Scope:** `backend/app/llm_router.py`'s `PROVIDER_CONFIG["openrouter_fallback"]` only. Routed to **SENT-7-05**.

### Deviation 6 — Google provider entries accept `GEMINI_API_KEY` as well as `GOOGLE_API_KEY`

**Bible says:** `PROVIDER_CONFIG["gemini_flash_thinking"]["api_key_env"]` and `["gemini_flash_fast"]["api_key_env"]` are both the single string `"GOOGLE_API_KEY"` (Section 8.1).

**Implemented:** `api_key_env` is a tuple `("GEMINI_API_KEY", "GOOGLE_API_KEY")` for both Google entries; `GEMINI_API_KEY` is checked first, `GOOGLE_API_KEY` is accepted as a fallback alias when the first is unset.

**Why:** `.env.example` (Phase 3, D-01) introduces `GEMINI_API_KEY=` as the four provider-key placeholders' naming convention — matching Google AI Studio's own developer-facing key name (`aistudio.google.com/apikey` issues keys under that name) rather than the Bible's more generic `GOOGLE_API_KEY`. Accepting both avoids a silent mismatch where an operator sets the variable `.env.example` documents and the router looks for a different one.

**Scope:** `backend/app/llm_router.py`'s `PROVIDER_CONFIG["gemini_flash_thinking"]` and `["gemini_flash_fast"]` `api_key_env` fields only; no other provider's key-resolution behavior changed. Routed to **SENT-7-05**.

### Deviation 7 — `calculate_confidence()`'s ALCOA dimension count corrected from 8 to 9

**Bible says:** `calculate_confidence()` (Section 2, the "C1" entry) hardcodes the literal `8` as its ALCOA dimension count: `score -= (8 - alcoa_score) * 10`.

**Implemented:** `backend/app/agents/c1_verifier.py`'s `ALCOA_DIMENSION_COUNT = 9`, substituted for that literal `8` and nothing else in the formula.

**Why:** Two independent in-project sources agree on 9 against the Bible's one stale literal. `.claude/CLAUDE.md` states "ALCOA+ 9-dimension scoring (16.12) extends C1" as settled project fact, and `app.schemas.ALCOAScore` (shipped in Phase 2, `backend/app/schemas.py`) has nine boolean fields: `attributable`, `legible`, `contemporaneous`, `original`, `accurate`, `complete`, `consistent`, `enduring`, `available`. Under the Bible's literal `8`, a finding with all nine dimensions true would compute a starting-score deduction of `(8 - 9) * 10 = -10`, i.e. `score = 100 - (-10) = 110` — a value above 100 that the formula's own threshold ladder (`> 80` HIGH, `>= 50` MEDIUM, `> 0` LOW, else `INSUFFICIENT_EVIDENCE`) cannot express or distinguish from any other HIGH score.

**Evidence:** `[VERIFIED: backend/tests/test_hero_tracer.py]` — the tracer's live end-to-end assertion against the real `PE-2024-01` Postgres row and the real OPA `ANNEX11-S11-PE-001` evaluation yields `MEDIUM` for a 6-of-9-true `ALCOAScore()` finding (`attributable`/`contemporaneous`/`original` False, the other six True): `100 - (9 - 6) * 10 = 70`, which falls in `score >= 50` → `MEDIUM`. This is exactly what the corrected 9-dimension arithmetic predicts.

**Scope:** Only `ALCOA_DIMENSION_COUNT` changed. The starting score (`100`), the `x10` per-dimension multiplier, the `-100` policy-contradiction penalty, and the `80`/`50`/`0` HIGH/MEDIUM/LOW thresholds are all carried over from the Bible unchanged. Routed to **SENT-7-05**.

### Deviation 8 — `evaluate_opa_policy()` sanitizes `datetime` values before JSON-encoding the payload

**Bible says:** Section 3.4's `evaluate_opa_policy()` POSTs `{"input": payload}` directly via `json=`.

**Implemented:** `payload` is passed through a new `_json_safe()` helper first, which recursively converts `datetime.datetime`/`datetime.date` values to ISO-8601 strings before the `json=` encode.

**Why:** asyncpg returns native `datetime.datetime` objects for `TIMESTAMP` columns (e.g. `changes.qa_approval_date`). httpx's `json=` encoder raises `TypeError: Object of type datetime is not JSON serializable` on them — a `TypeError`, not `httpx.RequestError`/`httpx.HTTPStatusError`, so it was not caught by this function's existing `except` clause and would crash whichever agent called it. This was latent since Phase 2 (every table `evaluate_opa_policy()` might see a row from can have a `TIMESTAMP` column) and unexercised until Phase 3 plan 03-03: A2's only evidence table (`periodic_evaluations`) has no `TIMESTAMP` column, so A2/C1 never hit this path, but 03-03's A4 Change Agent cites the `changes` table, and C1's `fetch_evidence_record()`/`build_opa_payload()` (`app.agents.c1_verifier`) do a bare `SELECT *` and forward whatever asyncpg returns. 03-03-PLAN.md `<critical_findings>` places `c1_verifier.py` and `a2_compliance.py` out of scope for that plan to edit; the fix belongs in `opa_client.py` instead, the one place a Postgres row's native Python types cross into an HTTP JSON body, regardless of which caller supplied the row.

**Evidence:** `[VERIFIED: backend/tests/test_opa_client.py::test_payload_containing_datetime_value_does_not_raise_typeerror]` — a payload built exactly like C1 would build for `ANNEX11-S10-CHG-001` (a `changes` row with a real `datetime.datetime` `qa_approval_date`) round-trips through `evaluate_opa_policy()` without raising and returns the expected violation.

**Scope:** `backend/app/opa_client.py` only — a new `_json_safe()` function and one call-site change. Routed to **SENT-7-05**.

### Deviation 9 — `blast_radius()` uses `nx.descendants` in place of the Bible's literal `dfs_preorder_nodes`

**Bible says:** Section 10.1's `find_downstream_impacts` sketch uses `nx.dfs_preorder_nodes(G, source)`.

**Implemented:** `backend/app/graph/evidence_graph.py`'s `blast_radius()` uses `nx.descendants(G, source_node_id)` instead.

**Why:** `descendants` is the purpose-built "what is reachable from here" API — it returns the reachable set as a plain `set`, which is exactly the shape every one of Bible Section 14.3's nine Graph Questions buckets from, rather than a generator over a specific traversal order Blast Radius has no use for. It also excludes the source node by default, matching the "never include the source" contract every bucket in `blast_radius()`'s return value carries — though the implementation still defensively discards the source from the descendant set before bucketing, since that exclusion is not guaranteed on a graph containing a cycle back to the source.

**Scope:** `backend/app/graph/evidence_graph.py`'s `blast_radius()` only. Routed to **SENT-7-05**.

## AgentFinding conventions (Phase 3)

Phase 3's `AgentFinding` (the `TypedDict` in `backend/app/graph/state.py`) shape is unchanged from Phase 2, but plan 03-02 pins a value convention every later plan (03-03 through 03-06) follows. This table lives here, in the repository, rather than only in a planning artifact:

| Field | Convention this phase |
|-------|-----------------------|
| `finding_id` | `"{AGENT}-{RULE_ID}-{RECORD_ID}"`, e.g. `A2-ANNEX11-S11-PE-001-PE-2024-01` |
| `claim` | Narrative sentence. LLM-narrated when the router succeeds; a deterministic template when it degrades. |
| `regulatory_citations` | The OPA rule ids from `policies/gxp_rules.rego` that ground this finding, e.g. `["ANNEX11-S11-PE-001"]`. These ids carry the Bible's own `# Source:` regulatory mapping and are the only permitted citation source (CLAUDE.md Rule 13 — never model recall). |
| `confidence_score` | `"UNVERIFIED"` on emission by any A-agent. Only C1 assigns `HIGH` / `MEDIUM` / `LOW` / `INSUFFICIENT_EVIDENCE`. The one exception is a Bible-specified failure-behavior finding, which carries `"LOW"` verbatim per Section 2. |
| `evidence_ids` | Postgres primary keys of the rows the claim rests on, e.g. `["PE-2024-01"]`. |
| `alcoa_score` | `ALCOAScore().model_dump()` — all 9 boolean fields present. |
| `model_attribution` | `LLMResponse.model_id` when the router succeeded; the literal `deterministic-fallback` when it degraded. |

`verification_results` (C1's output into `AgentState`) is a dict keyed by `finding_id`, each value being `{"confidence": str, "db_record_found": bool, "opa_corroborated": bool, "opa_rule_ids": List[str], "evidence_ids": List[str]}`.

## C1 Critical-review coverage (SENT-2-12)

Plan 03-05 brought `backend/app/agents/c1_verifier.py` to the Critical-review bar CLAUDE.md and `BRANCHING.md` section 6 require for C1: unit + negative + edge-case + integration coverage, not a smoke test. All four classes live in `backend/tests/test_c1_verifier.py`, in four clearly commented sections (`# UNIT`, `# NEGATIVE`, `# EDGE`, `# INTEGRATION`):

| Coverage class | Test names |
|---|---|
| **Unit** | `test_unit_grade_ladder_full_sweep`, `test_unit_boundary_exclusive_above_80_seven_true_dims_grades_medium_not_high`, `test_unit_boundary_inclusive_at_50_four_true_dims_grades_medium_not_low`, `test_unit_boundary_exclusive_above_0_nine_true_dims_policy_false_grades_insufficient_not_low`, `test_unit_policy_contradiction_dominates_across_all_dimension_counts`, `test_unit_falsy_db_record_grades_insufficient_regardless_of_dimensions_or_policy`, `test_unit_absent_or_empty_alcoa_score_grades_low_and_does_not_raise`, `test_unit_run_c1_empty_findings_returns_empty_mapping` |
| **Negative** | `test_negative_evid02_contradiction_against_real_approved_urs_row`, `test_negative_evid02_fabricated_evidence_short_circuits_before_opa_call`, `test_negative_positive_control_truthful_claim_against_real_row_scores_medium` |
| **Edge-case** | `test_edge_unrecognised_rule_id_resolves_no_record_without_building_sql`, `test_edge_empty_evidence_ids_list_resolves_no_record_without_raising` |
| **Integration** | `test_integration_run_c1_mixed_list_returns_three_distinct_graded_entries`, `test_integration_ten_rules_resolve_real_record_and_payload_shape_matches_documented_input`, `test_integration_ten_rules_verify_finding_grades_and_at_least_eight_corroborate`, `test_integration_rule_5_payload_test_cases_object_shape_and_corroborates`, `test_integration_rule_10_payload_carries_both_changes_and_change_actions_keys`, `test_integration_fail_closed_opa_unreachable_all_ten_grade_insufficient_evidence`, `test_integration_fail_closed_postgres_unreachable_run_c1_all_insufficient_evidence` |

**EVID-02 — a contradicting claim, proven against live state, neither Postgres nor OPA mocked.** `test_negative_evid02_contradiction_against_real_approved_urs_row` asserts a claim stating the genuinely real, genuinely `APPROVED` `DOC-2026-URS-01` document (`infra/postgres/seed/002_urs_fixture.sql`) is *not* approved — the opposite of the real row's real `status` column. Rego rule 1 (`ANNEX11-S4-DOC-001`) only fires for `doc_type == "O&M"`, and this row's `doc_type` is `"URS"`, so the real OPA sidecar returns no violation for it: real row says approved, real policy engine says nothing, and C1 correctly returns `INSUFFICIENT_EVIDENCE`. `test_negative_evid02_fabricated_evidence_short_circuits_before_opa_call` asserts the companion claim: `evidence_ids` naming `PE-9999-FAKE`, a record id absent from `periodic_evaluations` entirely, returns `INSUFFICIENT_EVIDENCE` while a call-counting wrapper installed around the OPA client proves `evaluate_opa_policy()` is never invoked — the short-circuit is asserted, not assumed. `test_negative_positive_control_truthful_claim_against_real_row_scores_medium` runs a truthful claim against the real, genuinely overdue `PE-2024-01` row through the same code path and gets `MEDIUM`, proving the two negative results above are discrimination, not a mechanism that always refuses.

**C1 fails closed on both outage directions.** `test_integration_fail_closed_opa_unreachable_all_ten_grade_insufficient_evidence` repoints the OPA client at a closed local port (same monkeypatch pattern as `test_opa_client.py`'s own unreachable-host test) and asserts all ten seeded gap findings grade `INSUFFICIENT_EVIDENCE` rather than being silently treated as corroborated. This direction is deliberate: `opa_client.py`'s fallback degrades to an *empty* violation list on any OPA failure (Deviation 1/2 above), and C1 treats "not found in the (possibly empty) violation list" as "not corroborated" — never as agreement. Reading an empty violation list as agreement would let a policy-engine outage silently mark every finding trusted, which is the exact failure the deterministic-first architecture (Bible Section 1.3) exists to prevent. `test_integration_fail_closed_postgres_unreachable_run_c1_all_insufficient_evidence` repoints `DATABASE_URL` at a closed port and asserts `run_c1()` returns `INSUFFICIENT_EVIDENCE` for every finding without raising — Postgres unreachable degrades identically, never to trusted-by-default.

**`build_opa_payload()`'s multi-input-key fix (closes `.planning/WINDOWS.md` id 1).** Plan 03-04 discovered that `build_opa_payload()` queried every `RULE_OPA_INPUT` table using the finding's own `evidence_ids`, which silently broke OPA corroboration for the two rules needing a second, differently-keyed table (`ANNEX11-S4-TRC-001`'s `test_cases`, `ANNEX11-S10-CHG-001`'s `change_actions`) — out of 03-04's file-boundary scope to fix. Plan 03-05 fixed it (see `c1_verifier.py`'s module and `RULE_OPA_INPUT` docstrings for the `id_source` mechanism), still with no per-rule branching in `build_opa_payload()` itself, and `test_integration_rule_5_payload_test_cases_object_shape_and_corroborates` / `test_integration_rule_10_payload_carries_both_changes_and_change_actions_keys` assert the corrected shape and corroboration directly. `test_hero_tracer.py`'s two assertions that had recorded the pre-fix (buggy) behavior were updated to the corrected `MEDIUM`/`opa_corroborated=True` outcome.

**`calculate_confidence()`'s constants are fixed by transcription, not tunable.** The starting score (`100`), the `x10` per-missing-dimension penalty, the `-100` policy-contradiction penalty, the `80`/`50`/`0` HIGH/MEDIUM/LOW/INSUFFICIENT_EVIDENCE threshold ladder, and `ALCOA_DIMENSION_COUNT = 9` are all unchanged by this plan — see Deviation 7 above for the 9-dimension correction's own rationale (D-06), not restated here. This plan proves the transcription against real state in both directions; it does not improve the arithmetic (03-RESEARCH.md "Don't Hand-Roll" — the algorithm is the product's differentiator).

**What this phase does not claim.** The confidence mechanism above is proven against real Postgres rows and real OPA policy evaluation, in both the corroborating and the contradicting direction, plus both outage directions. It does **not** prove that a live LLM's claims would grade sensibly end to end, because no provider key was configured this phase (03-RESEARCH.md Pitfall 6) — every fixture in `test_c1_verifier.py` is a finding dict built directly, not narrated by a real model call. Setting a provider key (`GEMINI_API_KEY` et al.) and re-running the hero tracer against a live model remains the outstanding operator follow-up, tracked since plan 03-01's `user_setup`.

## Phase 3 backend hero loop

Plan 03-06 closes the Phase 3 gate: `backend/tests/test_hero_loop.py` is the phase's reviewable EVID-04 evidence (ROADMAP.md Phase 3 success criterion 5). Run it with Postgres and OPA up and both seed scripts applied:

```bash
bash infra/health-check.sh
bash infra/apply-seed.sh
cd backend && .venv/Scripts/python -m pytest tests/test_hero_loop.py -k hero -q
```

Nine tests, three named scenarios, all driving one `compiled_graph.ainvoke()` call over the literal query `"Is GXP-MFG-DEMO-01 audit ready?"`:

- **Fully-mocked run against `GXP-MFG-DEMO-01`** (six test functions) — A0 classifies to the full agent set (naming A2), fanning out to A2 plus the five other real specialists. A2's periodic-evaluation and traceability findings are graded from the real seeded `PE-2024-01` row (provenance-checked back against the live database, `due_date_ns == 1704067200000000000`) and a real OPA evaluation, scoring `MEDIUM`. Every finding's `model_attribution` names a real provider model id, never `deterministic-fallback`.
- **Discrimination control against the healthy `BUS-IT-DEMO-02`** — the same invocation grades every finding `INSUFFICIENT_EVIDENCE`, proving the loop refuses as well as verifies (T-03-29).
- **Keyless run** — every provider key removed; A0 falls back to the full six-agent set, every finding's `model_attribution` is the `deterministic-fallback` marker, and the periodic-evaluation entry still grades `MEDIUM`, because C1 makes no model call at all (D-01).

A ninth test calls `run_c1({"findings": []})` directly and asserts an empty `verification_results` mapping — C1 never fabricates a bare verified default.

**What is live, what is mocked.** The compiled LangGraph `StateGraph`, Postgres, and the OPA sidecar are all live in every scenario above — never mocked, never monkeypatched (`app.db.DATABASE_URL` / `app.opa_client.OPA_URL` do not appear as `monkeypatch.setattr` targets anywhere in this module). The one mocked layer is the LLM provider transport: the fully-mocked scenario installs respx routes for all four providers (Gemini, DeepSeek, Groq, OpenRouter), with Gemini's route resolved by inspecting the outgoing request body (A0's classification prompt vs. every other Gemini caller's narration prompt share the identical `generateContent` URL — see `test_hero_loop.py`'s module docstring).

**What this phase does not claim, restated for this test specifically.** No provider API key was configured during this phase. Every claim the loop graded above was either produced from a mocked provider response (the fully-mocked and discrimination-control scenarios) or from a deterministic template (the keyless scenario) — never from a live model call. The wire contract (request shape, response parsing, `model_id` attribution) and the confidence mechanism (`calculate_confidence()` against real DB/OPA state) are both proven. Live classification quality (does Gemini actually route a given query to a sensible agent subset) and live narration quality (does the synthesized `claim` text read as a coherent, accurate compliance finding) are **not** proven — a summary claiming this loop "works end to end" without that qualification would be wrong.

To close that gap, set `GEMINI_API_KEY` (and optionally `DEEPSEEK_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`) in the repo-root `.env` file (per `.env.example`; `app.db`/`app.llm_router` both call `load_dotenv()`), then:

```bash
cd backend && .venv/Scripts/python -m pytest tests/test_hero_loop.py -q
```

and invoke the loop once against a live provider to confirm A0's classification picks a sensible agent subset and A2's narration reads as a coherent compliance finding — the one claim the automated suite above cannot make.

`verification_results` is the shape Phase 4's Assurance Card UI reads its data from — see "AgentFinding conventions (Phase 3)" above for the full field-by-field contract; not restated here.

## Phase 4 evidence graph (plan 04-01, GRAPH-01/GRAPH-03)

`app/graph/evidence_graph.py` builds an in-memory `nx.DiGraph` from live
domain-table state for one system (`build_graph`), persists it into the
`graph_nodes`/`graph_edges` cache tables (`persist_graph`), and reads that
cache back without touching a domain table (`load_graph`). This is the
Bible Section 10.1 `build_evidence_graph` deliverable, transcribed under
the deterministic-first constraint (Bible Section 1.3): the module
contains no model call, and never will — graph relationship derivation
stays permanently in the Python/NetworkX tier.

**Type-prefixed node ids.** `graph_nodes.node_id` is one `VARCHAR(100)`
primary key shared by every entity type. Seed data happens to use disjoint
id prefixes per domain table today, but that is a habit, not a schema
guarantee — a future collision would silently overwrite an unrelated node.
Every node id is therefore `"{node_type}:{entity_id}"`, built only via
`make_node_id`/split only via `split_node_id` (split on the first `:`, so
an entity id containing a colon still round-trips).

**Frozen allowlists.** `NODE_SPECS` (node type -> table/columns/scope) and
`RELATION_TYPES` are the only source of a table name or a relation-type
string that reaches SQL — never a request value, never a database row
(threat T-04-02). This plan populates `SYSTEM`/`REQUIREMENT`/`TEST_CASE`
and `{"VERIFIED_BY"}`; plan 04-02 extends both dicts without changing
their shape.

**Explicit-rebuild-only (D-01/D-02).** `persist_graph` is the only writer
of the two cache tables anywhere in the codebase — the cache never holds a
fact not derivable from domain state. The read endpoint below never
recomputes; an empty cache is a real, expected state (not a bug) until an
operator calls rebuild.

**Endpoints** (`app/routes/evidence_graph.py`, registered on `app.main:app`):

```bash
# Rebuild the cache for one system from live domain-table state
curl -X POST http://127.0.0.1:8000/api/systems/GXP-MFG-DEMO-01/evidence-graph/rebuild

# Read the cache only -- no rebuild triggered by this call
curl http://127.0.0.1:8000/api/systems/GXP-MFG-DEMO-01/evidence-graph
```

Both return `404` when `system_id` is absent from `gxp_systems`, `503`
when the Postgres pool is unavailable (`acquire_pool_or_none()`'s
degrade-don't-raise contract). A system with an empty cache returns `200`
with empty `nodes`/`edges` arrays from the GET endpoint, not `404`.

## Phase 4 evidence graph (plan 04-01)

`backend/app/graph/evidence_graph.py` builds an in-memory `networkx.DiGraph` from live domain-table state and persists it into the previously-empty `graph_nodes`/`graph_edges` cache tables (`infra/postgres/initdb/001_schema.sql`). No LLM ever appears in this path (Bible Section 1.3) — every node and edge traces back to a real Postgres row and a real foreign-key-shaped column value.

**Type-prefixed node ids.** `graph_nodes.node_id` is a single `VARCHAR(100)` primary key shared by every entity type. Seed data happens to use disjoint id prefixes per domain table today (`URS-*`, `TC-*`, ...), but that is a seed-data habit, not a schema guarantee — a future collision between two tables' raw ids would otherwise silently overwrite an unrelated node. Every node id is therefore `"{node_type}:{entity_id}"`, produced only by `make_node_id`/`split_node_id`.

**Frozen allowlists.** `NODE_SPECS` (node type -> table, property columns, scope) and `RELATION_TYPES` (permitted `graph_edges.relation_type` values) are the only source of a table name or relation-type string that reaches SQL — never request data, never a database row. This plan populates `SYSTEM`, `REQUIREMENT`, `TEST_CASE` and `{"VERIFIED_BY"}`; plan 04-02 extends both.

**Explicit-rebuild-only (D-02).** `persist_graph()` is the only writer of the two cache tables anywhere in the codebase. The read endpoint below never recomputes — an empty cache is a real, expected state (run the rebuild endpoint first), not a bug silently papered over by an on-read rebuild.

Endpoints (registered on the shared `app` object in `app/main.py`):

```
POST /api/systems/{system_id}/evidence-graph/rebuild   # build_graph + persist_graph; 404 unknown system, 503 pool down
GET  /api/systems/{system_id}/evidence-graph            # reads graph_nodes/graph_edges only; never rebuilds
```

Run commands (from `backend/`, with Postgres up and seeded):

```bash
.venv/Scripts/python -m uvicorn app.main:app --port 8000
# in another shell:
node -e "fetch('http://127.0.0.1:8000/api/systems/GXP-MFG-DEMO-01/evidence-graph/rebuild',{method:'POST'}).then(r=>r.json()).then(j=>console.log(j))"
node -e "fetch('http://127.0.0.1:8000/api/systems/GXP-MFG-DEMO-01/evidence-graph').then(r=>r.json()).then(j=>console.log(j))"
```

Tests: `backend/tests/test_evidence_graph.py` (module-level build/persist/load, unit + negative/edge + integration) and `backend/tests/test_routes_evidence_graph.py` (the two HTTP endpoints via `TestClient`, including the D-02 mutate-the-cache-behind-the-endpoint's-back proof).

## Phase 4 evidence graph (plan 04-02, GRAPH-01)

Plan 04-02 expands the tracer graph from 3 nodes / 1 edge to the full 15
node types / 7 relation types the demo system (`GXP-MFG-DEMO-01`) actually
produces 14 nodes and 9 edges from. `NODE_SPECS` and `RELATION_TYPES` grew
as pure data (new dict entries / frozenset members); the one control-flow
addition is a single `EDGE_SPECS`-driven loop in `build_graph` that
replaced 04-01's hand-written `VERIFIED_BY` pass, plus
`_add_change_affects_edges` for the one non-FK edge source in the whole
graph (see below). No caller-facing symbol was renamed.

**Node types (15).** `SYSTEM`, `DOCUMENT`, `TEST_CASE`, `TEST_RESULT`,
`REQUIREMENT`, `RISK`, `DESIGN_ELEMENT`, `INCIDENT`, `ACCESS_REVIEW`,
`ACCESS_RECORD`, `SUPPLIER`, `SUPPLIER_ASSESSMENT`, `PERIODIC_EVALUATION`,
`CHANGE`, `CHANGE_ACTION` -- one `NodeSpec` (table, property columns,
scope) each in `evidence_graph.NODE_SPECS`. `TEST_RESULT`,
`SUPPLIER_ASSESSMENT`, and `CHANGE_ACTION` are scoped
`("via_parent", parent_type, fk_column)` rather than a plain `system_id`
column -- they have none of their own -- and are fetched by binding the
parent type's already-collected ids to `WHERE fk_column = ANY($1::varchar[])`.

**Relation types (7) and their source.**

| Relation type | Edge | Derived from |
|---|---|---|
| `VERIFIED_BY` | `REQUIREMENT -> TEST_CASE` | `requirements.test_case_id` FK (Bible 14.3) |
| `HAS_RESULT` | `TEST_CASE -> TEST_RESULT` | `test_results.test_case_id` FK |
| `HAS_ACTION` | `CHANGE -> CHANGE_ACTION` | `change_actions.change_id` FK |
| `ASSESSED_BY` | `SUPPLIER -> SUPPLIER_ASSESSMENT` | `supplier_assessments.supplier_id` FK |
| `GOVERNS` | `DOCUMENT -> SYSTEM` | `documents.system_id` FK (Bible 14.3) |
| `ASSOCIATED_WITH` | `RISK -> SYSTEM` | `risks.system_id` FK (Bible 14.3) |
| `AFFECTS` | `INCIDENT -> SYSTEM` (FK) **and** `CHANGE -> {REQUIREMENT\|TEST_CASE\|DOCUMENT\|DESIGN_ELEMENT\|RISK}` (junction row) | `incidents.system_id` FK (Bible 14.3) for the first; `change_affects` (below) for the second -- the one relation type with two distinct sources |

`HAS_RESULT`, `HAS_ACTION`, and `ASSESSED_BY` are foreign-key-derived
additions beyond Bible Section 14.3's own illustrative (non-exhaustive)
relationship list; they follow the same "declared FK only" rule as every
other edge in this module.

**`change_affects` (D-03) -- the one non-FK edge source.** Neither
`changes` nor `change_actions` carries a foreign key to `requirements`,
`design_elements`, or `test_cases`, so Bible Section 14.3's
`CHANGE --AFFECTS--> X` relationship has no column to derive from. The
additive `infra/postgres/initdb/002_change_affects.sql` table
(`change_id`, `entity_type`, `entity_id`, composite
`PRIMARY KEY(change_id, entity_type, entity_id)`) supplies it explicitly:
`_add_change_affects_edges` reads every row for the graph's already-
fetched `CHANGE` ids and draws an `AFFECTS` edge to
`make_node_id(entity_type, entity_id)`. `entity_type` is validated against
the frozen `CHANGE_AFFECTS_ENTITY_TYPES` allowlist
(`{REQUIREMENT, TEST_CASE, DOCUMENT, DESIGN_ELEMENT, RISK}`) before it is
ever used to build a node id -- an out-of-allowlist value is logged and
skipped, never reaching SQL or an invented node type (T-04-02); a valid
`entity_type` whose `entity_id` does not resolve to a node already in the
graph is dropped by the existing endpoint-presence check in `_add_edge`
(T-04-07). `entity_id` deliberately carries no database foreign key of its
own -- Postgres cannot express one spanning several target tables.

**Bible deviation -- `ACCESS_REVIEW --CONTROLS--> ACCESS_RECORD` not implemented.**
Bible Section 14.3 also lists this relationship, but `access_reviews` and
`access_records` share no foreign key -- both independently reference only
`gxp_systems(id)`. D-03 explicitly rejects same-`system_id` blanket
association as an edge source (this module derives edges from declared
foreign keys and `change_affects` only, never from two rows merely sharing
a column value), so this relationship type has no derivable source under
this module's rules and is omitted from both `RELATION_TYPES` and
`EDGE_SPECS`. Routed to **SENT-7-05** alongside every other Bible
deviation recorded in this document.

**Test coverage (SENT-3-01 Critical-review bar).**
`backend/tests/test_evidence_graph.py` carries unit (NODE_SPECS/EDGE_SPECS
shape, insertion-order, allowlist membership -- no DB), integration
(`build_graph` returns exactly 14 nodes / 9 edges for `GXP-MFG-DEMO-01`,
the full node-type and relation-type histograms match seeded reality, a
real-column provenance check on `INCIDENT:INC-849201`, persist/load
round-trip, the `BUS-IT-DEMO-02` discrimination control), negative (an
out-of-allowlist `change_affects.entity_type`, a `change_affects` row
naming a non-existent entity, and the D-03 same-`system_id`-is-not-an-edge
guarantee between `ACCESS_REVIEW`/`ACCESS_RECORD` and `SUPPLIER`/`SYSTEM`),
and edge-case (a single-node system, a system with no `changes` rows,
build-twice determinism) sections, live Postgres throughout, never mocked.

## Phase 4 Blast Radius (plan 04-04, GRAPH-02)

`evidence_graph.blast_radius(G, source_node_id)` answers every one of Bible
Section 14.3's nine Graph Questions from a single `nx.descendants`
traversal over an already-loaded graph (`load_graph` -- never
`build_graph`, per D-02: this is a read path and a read never rebuilds).
Exposed as `GET /api/systems/{system_id}/blast-radius?node_id=...`. No
model call appears anywhere in the traversal (Bible Section 1.3, 14.3);
`grep -rn "call_llm|llm_router" backend/app/graph/evidence_graph.py`
returns no matches.

**Response shape.** `BlastRadiusResponse` carries `source_node_id`,
`system_id`, one field per Graph Question (`direct_dependencies`,
`indirect_dependencies`, `affected_requirements`, `affected_tests`,
`affected_risks`, `affected_changes`, `affected_controls`,
`potential_gxp_impact`, `highest_impact_downstream`), plus
`affected_systems`. Every list is sorted ascending, so a response is
byte-stable across runs.

**404 vs 200 vs 503.** An unknown `system_id` or a `node_id` absent from
that system's graph (`nx.NetworkXError`, caught in the route handler)
returns `404` -- a change with no derived edges is a valid state, not a
server error. An empty blast radius for a node that *is* in the graph
(e.g. the `SYSTEM` sink node itself) returns `200` with all-empty buckets,
never `404`. An unreachable Postgres pool returns `503`.

**Test coverage (SENT-3-03 Critical-review bar).**
`backend/tests/test_blast_radius.py` carries:

| Coverage class | Test names |
|---|---|
| **Unit** | `test_unit_node_type_impact_rank_contains_every_node_specs_key_exactly_once`, `test_unit_control_node_types_is_access_review_and_access_record`, `test_unit_three_node_chain_yields_direct_b_indirect_c`, `test_unit_source_node_never_appears_in_any_returned_list`, `test_unit_every_returned_list_is_sorted_ascending_and_calls_are_equal`, `test_unit_assess_gxp_impact_high_for_downstream_system_with_gxp_impact_true`, `test_unit_assess_gxp_impact_high_for_downstream_incident_patient_safety_relevant_true`, `test_unit_assess_gxp_impact_medium_for_nonempty_set_without_high_signal`, `test_unit_assess_gxp_impact_none_for_empty_set`, `test_unit_rank_highest_impact_picks_node_with_most_descendants`, `test_unit_rank_highest_impact_tie_break_by_node_type_impact_rank`, `test_unit_rank_highest_impact_tie_break_within_one_type_by_lower_node_id`, `test_unit_rank_highest_impact_returns_none_for_empty_set` |
| **Integration** | Nine tests, one per Bible Section 14.3 Graph Question (`test_integration_q1_...` through `test_integration_q9_...`), plus `test_integration_second_traversal_from_requirement_tracks_real_subgraph` and `test_integration_traversal_from_system_sink_returns_empty_everywhere` |
| **Negative** | `test_negative_absent_node_raises_networkx_error`, `test_negative_node_from_a_different_systems_graph_raises_networkx_error`, `test_negative_malformed_node_id_with_no_type_prefix_raises_networkx_error`, `test_negative_positive_control_same_graph_returns_correct_nonempty_result` |
| **Edge-case** | `test_edge_empty_graph_raises_for_any_source`, `test_edge_single_isolated_node_returns_all_empty_buckets`, `test_edge_cycle_terminates_and_excludes_source_includes_others`, `test_edge_self_loop_terminates_and_excludes_source`, `test_edge_disconnected_component_not_reported`, `test_edge_diamond_reports_sink_exactly_once_in_indirect`, `test_edge_node_reachable_by_direct_and_longer_path_classified_as_direct_only`, `test_edge_nodes_with_no_properties_key_return_medium_not_keyerror` |

**What this coverage does and does not claim.** The graph-shape hazards
(cycle, self-loop, diamond, disconnected component, dual-path node) are
each proven by their own hand-built `nx.DiGraph` fixture, not by seeded
data -- the domain graph today is acyclic, so these shapes cannot occur in
the live seed and must be constructed directly (critical finding 7). The
nine Graph Question tests against `CHANGE:CR-2026-089` prove the
traversal's answers are correct for the one real, multi-hop shape the
seeded demo actually produces; they do not claim every possible graph
topology has been exercised against live Postgres, only that the pure
traversal function handles the topologies enumerated above regardless of
where the graph came from.

## Narration memo cache (quick task 260826-0b5)

`GET /api/systems/{system_id}/assurance-cards` re-narrated every failing
compliance check through the LLM router on every single request, and
`POST /api/actions/generate-capa` re-derived findings server-side by
narrating every failing check until one matched the requested
`finding_id` -- a single live testing session burned 811 Gemini requests
for what amounted to 2-3 distinct findings' worth of text. `app/narration_cache.py`
fixes this by memoizing `app.agents.a2_compliance.narrate_gap()`'s LLM
call itself, in-process, so all three of its call sites (`run_a2`,
`routes/findings.py::get_assurance_cards`, and
`routes/actions.py::_find_finding_server_side`) share one memo.

**What is cached.** Only the narration pair -- `(claim_text, model_id)`.
Nothing else `narrate_gap` touches is stored, and the module cannot
reach anything else: `app/narration_cache.py` imports nothing from
`app.*`, so it has no access to `verify_finding`, OPA, or any `passed`
boolean. Every deterministic field a caller reads elsewhere (`passed`,
`confidence`, `db_record_found`, `opa_corroborated`) is recomputed
against live Postgres and live OPA on every request, cache hit or not.

**The key.** A hex digest of `narrate_gap`'s finished prompt string, which
is built from the check name, its description, `record_id`, `rule_id`,
and the whole `record!r`. Every field that reaches the model is therefore
inside the key by construction -- an edited record produces a different
prompt, a different key, and a miss.

**No TTL, no rebuild endpoint.** Because the key *is* the input, staleness
is structurally impossible rather than merely unlikely, so there is
nothing to invalidate and no rebuild routine to keep in sync with the
prompt template. This is deliberately not the same pattern as
`app/graph/evidence_graph.py`'s rebuild/read split (D-02): that split
exists because `graph_nodes`/`graph_edges` are *snapshot* caches of
domain state that can genuinely drift, so a human-triggered rebuild
endpoint is the only way to refresh them. Narration has no such gap, so
copying that pattern here would be a control with no job. A Postgres
table was also considered and rejected -- it would require a schema
change, and the schema is closed (CLAUDE.md Rule 7).

**Degraded results are never stored.** When the LLM router degrades (no
provider key, or every provider fails), `narrate_gap` returns its
deterministic fallback sentence and does not call `narration_cache.put()`.
Caching that would latch a provider outage into memory for the lifetime
of the process -- the endpoint would keep serving fallback text long
after the provider recovered.

**No in-flight de-duplication.** Two concurrent requests for the same
cold key can both call the provider. A module-level `asyncio.Lock` would
fix that, but a module-level asyncio primitive is bound to the event loop
that created it -- the exact failure mode `backend/tests/conftest.py`
documents at length for asyncpg pools under this suite's
`asyncio.run()`-per-test convention. Sequential repeats (the same user
reloading the same page) are the dominant real-world cost here, so this
is accepted deliberately, not overlooked.

**Cross-system key sharing is intentional.** A check whose `record` is
`None` builds a prompt with no system identifier in it, so two systems
that both lack, say, a URS document hit the same cache entry. That is
correct dedup, not leakage: nothing system-specific is in the prompt, so
nothing system-specific can come out. `finding_id`, `evidence_ids` and
`confidence` are all computed per-system outside the cache, from the
live check result and C1's verification, never from the cached text.

**Per-process, not shared.** This is an in-process `OrderedDict`, bounded
at 256 entries with least-recently-used eviction (the demo corpus
produces findings in the low tens, so the bound exists to make unbounded
growth structurally impossible rather than to actively manage memory).
Under multiple uvicorn workers each worker keeps its own copy -- still
correct, just less effective, since a request that lands on a different
worker than the one that warmed the cache is a cold miss there. Not a
problem for this single-process demo deployment; recorded here for
whoever adds a second worker later.
