---
phase: 03-intelligence-retrieval
plan: 01
requirements-completed: [ORC-02, ORC-03, EVID-01]
---

# Plan 03-01 Summary: LLM Router + Postgres Connectivity

## Result

Built the two pieces of shared infrastructure Phase 3 has no substitute for: `backend/app/llm_router.py` (Bible Section 8 multi-provider router) and `backend/app/db.py` (real asyncpg connectivity — did not exist anywhere in the backend before this plan). Extended `backend/app/schemas.py` with the three Bible Section 2 models (`OrchestratorInput`, `OrchestratorOutput`, `ComplianceInput`). Full backend suite: **47/47 passing.**

## Execution note — resumed after two session-limit interruptions

This plan's execution spanned multiple sessions (the executing agent hit the Claude usage limit twice). Task 1 (package-legitimacy checkpoint) and most of Task 2 (`db.py`, `.env.example`, `requirements.txt`, `conftest.py` fixture scaffolding) were already done and uncommitted when this session resumed; Task 2's tests and all of Task 3 were completed in this session.

## Task 1 — Package legitimacy checkpoint (resolved)

Per the operator's standing instruction to continue autonomously while away, this blocking checkpoint was resolved by direct verification rather than waiting: `asyncpg==0.31.0` (MagicStack, the Bible's own Section 7.1 stated driver) and `respx==0.23.1` (lundberg, httpx's standard mocking companion, `httpx>=0.25.0` requirement satisfied by the pinned `httpx==0.28.1`) were confirmed against `pip index versions` and PyPI project pages — both are genuine, actively-maintained, non-typosquat packages. Recorded here for human spot-check.

## Task 2 — Postgres connectivity

`backend/app/db.py`: `DATABASE_URL` (env-backed, re-read at call time), `get_pool()` (asyncpg pool singleton, raises on failure), `acquire_pool_or_none()` (degrade-don't-raise entry point every agent uses), `close_pool()` (idempotent). Live test reads the seeded `GXP-MFG-DEMO-01` row (`name`, `readiness_score=61`) through a real connection to the Compose Postgres container. `backend/tests/test_db.py`: 5 tests, all passing.

**Two real Windows-specific bugs found and fixed by running tests live, not assumed** (both documented in code comments, not silently patched):

1. **`WindowsProactorEventLoopPolicy` breaks under pytest.** pytest's stdout/stderr capture replaces `sys.stdout`/`sys.stderr` with a non-file-like object, which breaks the default Proactor event loop's overlapped-I/O self-pipe mid-write, manifesting as `AttributeError: 'NoneType' object has no attribute 'send'` deep inside a live asyncpg socket write. Reproduced outside pytest (works) vs. inside pytest (fails) with the default policy; confirmed fixed by switching to `WindowsSelectorEventLoopPolicy` in `conftest.py` before any event loop is created.
2. **asyncpg `Pool` objects are event-loop-bound.** This codebase's established convention (`asyncio.run()` inside a plain `def test_*`, no pytest-asyncio) gives every test its own fresh, short-lived event loop. A pool created in one `asyncio.run()` call and handed to a *different* `asyncio.run()` call (e.g. via a naive session-scoped fixture) breaks with `asyncpg.exceptions.InterfaceError: cannot perform operation: another operation is in progress` or `RuntimeError: Event loop is closed`. Fixed at the source: `get_pool()`/`close_pool()` now track which loop owns the cached pool and transparently discard-and-recreate (or skip awaiting a dead pool) rather than reusing a connection bound to a closed loop. The `db_pool` conftest fixture no longer hands back a cross-loop `Pool` object — its docstring documents why, and tests needing the pool call `db.get_pool()` themselves inside their own `asyncio.run()`.

Both fixes are narrowly scoped (event-loop bookkeeping only) and change no SQL, no query shape, no public function signature beyond what the plan specified.

## Task 3 — Multi-provider LLM router

`backend/app/llm_router.py`: `PROVIDER_CONFIG` (Bible Section 8.1, transcribed with 3 corrections — see Deviations 4-6 below), `LLMResponse` Pydantic model, `select_provider(task)` (raises `KeyError` on unknown task, no silent default), `call_llm(task, prompt, ...)` (never raises to its caller; cascades once to `openrouter_fallback` on missing key / timeout / 429 / 5xx per Section 8.2; returns a degraded response if the cascade target is also unusable).

10 tests in `backend/tests/test_llm_router.py`, all passing, covering: task routing, unknown-task `KeyError`, Gemini wire-contract parsing (`x-goog-api-key` header, `thinkingConfig.thinkingBudget` per-task value), OpenAI-compatible wire-contract parsing (Groq), 429/500/timeout cascade to OpenRouter, no-key-present degraded response with **zero outbound HTTP requests** (respx has no routes registered — any accidental request would fail loudly), and two key-leakage tests confirming no log record ever contains a set API key value.

### Bible deviations 4-6 (recorded in `backend/README.md`, routed to SENT-7-05)

4. `deepseek_r1["model"]`: Bible's `"deepseek-reasoner"` → `"deepseek-v4-pro"` (retired model; out of MVP scope, A3 not exercised this phase).
5. `openrouter_fallback["model"]`: Bible's `"auto"` → `"openrouter/auto"` (OpenRouter's actual model string).
6. Google `api_key_env`: Bible's single `"GOOGLE_API_KEY"` → tuple `("GEMINI_API_KEY", "GOOGLE_API_KEY")`, first-set-wins (matches `.env.example`'s D-01 naming convention; Google AI Studio itself issues keys under the `GEMINI_API_KEY` name).

## Credential gap (D-01) — honestly incomplete, by design

No LLM provider API key is configured anywhere in this repo. Every code path in `llm_router.py` is production-shaped (real HTTP calls, real response parsing, no `if DEMO_MODE` shortcuts) and proven correct via respx-mocked responses shaped exactly like each provider's real API. What is **not** proven this session: that a live Gemini/DeepSeek/Groq/OpenRouter call returns useful, well-formed content. That remains the operator's follow-up — set `GEMINI_API_KEY` / `DEEPSEEK_API_KEY` / `GROQ_API_KEY` / `OPENROUTER_API_KEY` in `.env` and re-run.

## Artifacts

| Artifact | Status |
|---|---|
| `backend/app/db.py` | Created — `DATABASE_URL`, `get_pool()`, `acquire_pool_or_none()`, `close_pool()` |
| `backend/app/llm_router.py` | Created — `PROVIDER_CONFIG`, `LLMResponse`, `select_provider()`, `call_llm()` |
| `backend/app/schemas.py` | Extended — `OrchestratorInput`, `OrchestratorOutput`, `ComplianceInput` |
| `backend/tests/conftest.py` | Extended — `db_pool`, `reset_db_pool` fixtures + Windows event-loop-policy fix |
| `backend/tests/test_db.py` | Created — 5 tests |
| `backend/tests/test_llm_router.py` | Created — 10 tests |
| `backend/requirements.txt` | Extended — `asyncpg==0.31.0`, `respx==0.23.1` |
| `.env.example` | Extended — 4 provider-key placeholders + `DATABASE_URL` |
| `backend/README.md` | Extended — Deviations 4, 5, 6 |

Full backend suite: 47/47 passing (`pytest -q` from `backend/`, live Postgres + OPA required for `test_db.py`/`test_opa_client.py`).

STATE.md and ROADMAP.md were not modified — left for the orchestrator.
