"""
Async client for the live OPA sidecar's compliance rule evaluation endpoint.

Ticket: SENT-1-04 | Requirement: POL-02
Source: AegisX-AI-Project-Bible-v6.md Section 3.4 (lines 548-579) — the
async POST, 2.0-second timeout, non-2xx-status-check, and result-extraction
shape is transcribed from there. Three deliberate deviations from the
Bible's literal text are recorded in `backend/README.md` under "Bible
deviations (backend tier)" and routed to SENT-7-05: a configurable
`OPA_URL`, catching `httpx.HTTPStatusError` alongside `httpx.RequestError`,
and logging instead of `print`.

This module wraps calls to an external deterministic policy engine (OPA); it
does not itself evaluate any compliance, RBAC, or prompt-injection decision
(Bible Section 1.3, CLAUDE.md deterministic-first constraint). The rule
logic lives entirely in `policies/gxp_rules.rego` (plan 02-02). Every dict
this module returns has the same key set as `app.schemas.OPAViolation`
(`rule_id`, `severity`, `system_id`, `record_id`, `description`), so a
caller wanting validation can construct `OPAViolation(**violation)`
directly — this module intentionally returns raw dicts rather than
`OPAViolation` instances, since Phase 3's C1 Evidence & Grounding Verifier
is the component responsible for typing and scoring them.

Import nothing from `app.main` — this module must be importable standalone,
and doing so would risk a circular import.
"""

import logging
import os
from typing import Any, Dict, List

import httpx

logger = logging.getLogger(__name__)

# Deviation 1 (backend tier): the Bible hardcodes
# "http://localhost:8181/v1/data/sentinel/gxp/violation". Read it from the
# OPA_URL environment variable instead, defaulting to that same path (with
# 127.0.0.1 in place of localhost — see below). In normal operation the
# behaviour is identical; the fallback branch below cannot be exercised at
# all without pointing the client somewhere that does not answer, and this
# is what makes that possible without stopping the shared OPA container.
#
# 127.0.0.1 rather than localhost: sidesteps IPv6-first resolution that
# makes "localhost" intermittently slow to connect on Windows.
OPA_URL = os.getenv(
    "OPA_URL", "http://127.0.0.1:8181/v1/data/sentinel/gxp/violation"
)


async def evaluate_opa_policy(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Send `payload` to the live OPA REST endpoint and return the violation
    list OPA actually produced.

    POSTs `{"input": payload}` to `OPA_URL` with a 2.0-second timeout (a
    stated Bible constant — Phase 3's A0 orchestrator fan-out budget is
    built around policy calls returning fast). On success, returns
    `response.json().get("result", [])` verbatim — never a mock, never a
    fixture (POL-02).

    Degrades to `python_fallback_rules(payload)`, logging a warning rather
    than raising, on either failure branch:

    - `httpx.RequestError` (connection refused, DNS failure, timeout —
      `httpx.TimeoutException` is a `RequestError` subclass and needs no
      separate branch): OPA did not answer at all.
    - `httpx.HTTPStatusError` (deviation 2, backend tier): the Bible's own
      non-2xx status check raises this exception class, but it is not a
      `RequestError` subclass and would otherwise escape uncaught, crashing
      whichever agent called this function. An OPA that answers with a 500
      or a 400 is exactly as unusable to the caller as one that does not
      answer at all, so both branches route to the same fallback.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                OPA_URL,
                json={"input": payload},
                timeout=2.0,
            )
            response.raise_for_status()
            return response.json().get("result", [])
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        # Deviation 3 (backend tier): log, don't print. A server process
        # writing diagnostics to stdout loses them the moment it runs
        # anywhere other than a developer's terminal.
        logger.warning("OPA call failed (url=%s): %s. Using fallback rules.", OPA_URL, e)
        return python_fallback_rules(payload)


def python_fallback_rules(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Fallback evaluated when the live OPA sidecar cannot be reached or
    answers with an error status.

    Returns an empty list. The Bible states outright that this function's
    body is "omitted for brevity", and SENT-1-04's contract requires only
    that the stub exist and be reachable on the failure path.

    Deliberately NOT a second, hand-built copy of the 10 Rego rules in
    Python. A second, independently drifting copy of the compliance logic
    is worse than no copy at all: it would produce two possible answers to
    the same regulatory question with no mechanism keeping them equal,
    which is precisely the failure mode the deterministic-first
    architecture (Bible Section 1.3) exists to eliminate. Mirroring the
    Rego logic here is deferred to a future phase that has a genuine
    requirement for fully offline policy evaluation — none exists yet.
    """
    return []
