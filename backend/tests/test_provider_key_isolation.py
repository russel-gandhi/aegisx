"""
Regression guard for the test-suite real-LLM-call leak (quick task
260826-0b5; closed by `conftest.py`'s autouse `_isolate_llm_provider_keys`
fixture, 2026-08-29, Deviation 18).

2026-09-02 production-incident triage confirmed this fixture is already
present and correctly closes the original leak (an 811-request real-provider
session, caused by `app.llm_router`'s module-level `load_dotenv()` making a
real `.env`'s keys ambient in every test's `os.environ`) — but nothing in
the suite would have caught it if that fixture were ever deleted, narrowed
to a subset of keys, or accidentally scoped away from a test. This file is
that missing guard: if it starts failing, the exact regression that caused
the 811-request incident has reopened.

This is intentionally NOT a duplicate of `test_a2_compliance.py`'s
`_no_provider_keys` helper (which explicitly re-strips keys inside one
specific test as a belt-and-suspenders local guard) — this file instead
asserts the *autouse* fixture itself is doing its job, with no test-specific
setup of its own, so a regression shows up here regardless of which other
test file might also happen to catch it.
"""

import os

# Every provider-key env var this codebase has ever referenced, current
# (GROQ_API_KEY, OPENROUTER_API_KEY) and historical (GEMINI_API_KEY,
# GOOGLE_API_KEY, DEEPSEEK_API_KEY -- removed from PROVIDER_CONFIG in the
# 2026-09-01 Ollama migration, but still worth stripping: a future revert or
# a stray .env value should never leak into a test either way). Mirrors
# `conftest.py::_LLM_PROVIDER_KEY_ENV_VARS` exactly -- if that tuple and
# this one ever diverge, this test's whole point is undermined, so keep
# them identical.
_ALL_KNOWN_PROVIDER_KEY_ENV_VARS = (
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "DEEPSEEK_API_KEY",
    "GROQ_API_KEY",
    "OPENROUTER_API_KEY",
)


def test_provider_keys_are_stripped_by_default():
    """If a real `.env` is present in this environment (as it legitimately
    is for live manual testing, per `llm_router.py`'s own docstring), this
    test proves the autouse `_isolate_llm_provider_keys` fixture has
    already removed every provider key from `os.environ` by the time an
    ordinary test body runs -- BEFORE any test gets a chance to make a real,
    unmocked, billable network call to a paid LLM provider."""
    for env_name in _ALL_KNOWN_PROVIDER_KEY_ENV_VARS:
        assert os.getenv(env_name) is None, (
            f"{env_name} is set inside a test body. The autouse "
            "_isolate_llm_provider_keys fixture in conftest.py is not "
            "running, was narrowed, or was scoped away for this test. "
            "This is the exact regression that caused an 811-request real-"
            "provider session (quick task 260826-0b5) before that fixture "
            "existed."
        )


def test_conftest_fixture_covers_every_provider_key_this_test_file_knows_about():
    """Cross-checks this file's own env-var list against conftest.py's
    fixture list, so the two can never silently diverge -- a new provider
    added to PROVIDER_CONFIG without updating conftest.py's isolation
    fixture would otherwise go unnoticed until it leaked a real call."""
    from tests.conftest import _LLM_PROVIDER_KEY_ENV_VARS

    assert set(_LLM_PROVIDER_KEY_ENV_VARS) == set(_ALL_KNOWN_PROVIDER_KEY_ENV_VARS)
