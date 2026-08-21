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

This section records every point where `backend/app/opa_client.py` departs from the literal text of `GxP-Sentinel-Project-Bible-v6.md` Section 3.4 (lines 548-579). **Per CLAUDE.md ("when bible content and a ticket contract disagree, the bible wins" / "drift is reconciled explicitly"), this section is input to the final bible-reconciliation review, ticket `SENT-7-05`.** No rule logic, threshold, or regulatory citation is affected — `opa_client.py` calls into the deterministic Rego policy engine, it does not itself evaluate any compliance decision (Bible Section 1.3).

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
