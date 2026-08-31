"""
Direct OPA policy-evaluation route (Bible Section 12: `.../api/opa/evaluate`).

Remediation follow-up to REMEDIATION-PLAN.md #6. This endpoint was never
claimed by any ticket in any phase of `.planning/ROADMAP.md` (Phases 1
through 06.1.1) -- unlike the other four routes the Bible's own API table
lists, it wasn't deferred to a later phase, it simply had no owner at
all. `app.opa_client.evaluate_opa_policy()` has existed since Phase 3 and
is exercised internally by C1's verification path, but was never exposed
as its own public route.

Method deviation from the Bible's literal table: the Bible lists this as
`GET /api/opa/evaluate` with a `Dict` request body. A body-carrying GET is
non-standard HTTP (most HTTP clients/proxies don't reliably forward a GET
body, and FastAPI's own OpenAPI generation doesn't model it cleanly) --
this route is `POST` instead, the same class of pragmatic correction this
codebase already records for other Bible literalisms (llm_router.py's
Deviations 4/5/6/10/11/12). Routed to SENT-7-05 like those.

RBAC: no restriction beyond a recognised role (`require_identity` already
fails closed on that), mirroring `routes/actions.py`'s `list_actions` and
its own stated reasoning -- this is a read-only policy query with no
side effects, the same class of read Bible Section 2 grants the
read-only Auditor role ("Read-only System and Compliance metrics"). This
is deliberately NOT modeled on `routes/audit.py`'s `post_demonstrate_tamper`
(CR-01): that route excludes Auditor via `check_rbac(role, "A7")` because
it performs a real write. Gating this route on any single `PERMISSION_MATRIX`
agent id would be dead code in practice -- "A1" (System Knowledge) is the
only agent id all three roles share, so a check against it can never
actually reject a recognised role; reaching for it anyway would only
create the appearance of a meaningful restriction that isn't one.
"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from app.identity import RequestIdentity, require_identity
from app.opa_client import evaluate_opa_policy
from app.schemas import OPAViolation

router = APIRouter()

logger = logging.getLogger(__name__)


@router.post("/api/opa/evaluate", response_model=List[OPAViolation])
async def post_opa_evaluate(
    payload: Dict[str, Any],
    identity: RequestIdentity = Depends(require_identity),
) -> List[OPAViolation]:
    """Evaluates `payload` against the live OPA policy bundle and returns
    whatever violation list OPA actually produced -- never a mock, never a
    fixture, the same guarantee `evaluate_opa_policy()` already gives its
    internal callers. Degrades to `python_fallback_rules(payload)`
    (inside `evaluate_opa_policy` itself) rather than raising when OPA is
    unreachable, so this route's only error responses are 422 (FastAPI's
    own request-validation, e.g. a malformed body) and 403 (an
    unrecognised role, via `require_identity`) -- never a 502/504 for an
    OPA outage. `identity` itself is otherwise unused here; it exists so
    every write-and-read-capable route in this codebase resolves identity
    the same way, not because this route branches on it."""
    violations = await evaluate_opa_policy(payload)
    return [OPAViolation(**violation) for violation in violations]
