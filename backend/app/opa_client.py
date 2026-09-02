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

Deviation 8 (backend tier, plan 03-03): `evaluate_opa_policy()` now passes
`payload` through `_json_safe()` before encoding it. asyncpg returns
native `datetime.datetime`/`datetime.date` objects for `TIMESTAMP`
columns (e.g. `changes.qa_approval_date`), and httpx's `json=` encoder
raises `TypeError: Object of type datetime is not JSON serializable` on
them — uncaught by this function's existing `except (httpx.RequestError,
httpx.HTTPStatusError)` clause, since a `TypeError` from request-encoding
is neither. This was latent from Phase 2 (Section 3.4's original `json=`
call already carried the same gap) and unexercised until Phase 3 plan
03-03's A4 Change Agent became the first caller whose evidence table
(`changes`) has a `TIMESTAMP` column — C1's `fetch_evidence_record()`/
`build_opa_payload()` (`app.agents.c1_verifier`, out of scope for this
plan to edit per 03-03-PLAN.md `<critical_findings>`) do a bare `SELECT *`
and forward whatever asyncpg returns. The fix belongs here, at the one
place a Postgres row's native Python types cross into an HTTP JSON body,
not in the caller. Routed to **SENT-7-05**.
"""

import datetime
import hashlib
import logging
import os
from typing import Any, Dict, List

import httpx
from dotenv import load_dotenv

from app.http_client import get_shared_client

load_dotenv()

logger = logging.getLogger(__name__)


def _json_safe(value: Any) -> Any:
    """Recursively convert `datetime.datetime`/`datetime.date` values
    (asyncpg's native representation of a `TIMESTAMP` column) to ISO-8601
    strings; every other value is returned unchanged. See Deviation 8
    above. A no-op for the already-JSON-safe payloads
    `tests/test_opa_client.py` already exercises."""
    if isinstance(value, dict):
        return {key: _json_safe(v) for key, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    return value

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

# 2026-09-02 production-incident remediation: docker-compose.yml runs OPA in
# directory-mode with no `--watch` flag (policies/README.md, opa-gate.sh
# both already document "restart after every edit"), so a `.rego` edit made
# after the container started is invisible to a running OPA server until a
# manual `docker compose restart opa` -- and evaluate_opa_policy() below has
# no way to tell "OPA answered with a stale bundle" apart from "OPA answered
# correctly with zero violations". A live OPA-reachability incident (13
# tests briefly failing with `len(violations) == 0` against known-violating
# seed data) turned out on investigation to be transient unreachability, not
# staleness -- but the underlying ambiguity (both failure modes silently
# degrade to the same `[]`) is real regardless of which one fired that day.
#
# This hash does not close that ambiguity by itself (it cannot prove what
# the OPA *server* actually loaded -- only OPA's own bundle-status API
# could, and directory-mode loading does not expose one). What it gives:
# (1) the Trust Centre (Bible Section 11.8) an honest, non-hardcoded
# "policy bundle version" value an operator can eyeball, and (2) every C1
# verification result / A7 audit event a recorded fingerprint of what the
# BACKEND CHECKOUT believed the bundle to be at evaluation time, so a later
# investigation can at least rule in/out "the policy files changed between
# these two audit events" without guessing from git history.
_POLICIES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "policies",
)


def get_policy_bundle_hash(policies_dir: str = _POLICIES_DIR) -> str:
    """SHA-256 hex digest over every non-test `.rego` file under
    `policies_dir`, sorted by filename, hashed as `"{filename}\\n{content}\\n"`
    pairs (so a rename changes the hash even if content is byte-identical).

    Returns the literal string `"unavailable"` if the directory can't be
    listed or a file can't be read -- this is a diagnostic value, not a
    correctness dependency, so a filesystem hiccup here must never raise
    into a caller (`verify_finding`, `get_trust_centre`) that has real
    compliance work to finish.
    """
    try:
        rego_files = sorted(
            f
            for f in os.listdir(policies_dir)
            if f.endswith(".rego") and not f.endswith("_test.rego")
        )
    except OSError:
        return "unavailable"

    hasher = hashlib.sha256()
    for filename in rego_files:
        try:
            with open(os.path.join(policies_dir, filename), "r", encoding="utf-8") as fh:
                content = fh.read()
        except OSError:
            return "unavailable"
        hasher.update(filename.encode("utf-8"))
        hasher.update(b"\n")
        hasher.update(content.encode("utf-8"))
        hasher.update(b"\n")
    return hasher.hexdigest()


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
        client = get_shared_client()
        response = await client.post(
            OPA_URL,
            json={"input": _json_safe(payload)},
            timeout=2.0,
        )
        response.raise_for_status()
        return response.json().get("result", [])
    except httpx.RequestError as e:
        # 2026-09-02 incident remediation: this branch means OPA never
        # answered at all (connection refused, DNS failure, timeout).
        # Logged at ERROR (not WARNING) and with its own distinct message,
        # separate from the HTTPStatusError branch below -- a caller
        # reading `[]` back from this function cannot tell this apart from
        # "OPA correctly found zero violations" (that ambiguity is the
        # actual defect; this log line is the only place today that can
        # still tell the two apart after the fact). See
        # get_policy_bundle_hash()'s docstring above for the related
        # bundle-staleness ambiguity this does NOT close.
        logger.error(
            "OPA UNREACHABLE (url=%s): %s. Falling back to python_fallback_rules() "
            "-- the caller is receiving an EMPTY violation list that means "
            "'OPA did not answer', not 'no violations found'.",
            OPA_URL, e,
        )
        return python_fallback_rules(payload)
    except httpx.HTTPStatusError as e:
        # Deviation 2 (backend tier): a non-2xx response (500, 400, etc.) is
        # exactly as unusable as no response, so it degrades the same way --
        # but it is logged as its own branch, distinctly from RequestError
        # above, because a non-2xx status usually means a real server-side
        # problem (a malformed request this codebase built, or an OPA
        # process that started but failed to load its policy bundle) rather
        # than a network-level failure, and the two point an investigator
        # at different next steps.
        logger.error(
            "OPA returned a non-2xx status (url=%s): %s. Falling back to "
            "python_fallback_rules() -- same caller-visible 'empty means "
            "unanswered, not compliant' ambiguity as an unreachable OPA.",
            OPA_URL, e,
        )
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
