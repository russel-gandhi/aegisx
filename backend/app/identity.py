"""
Request identity (Phase 5, plan 05-01).

Ticket: SENT-4-01 | Requirement: SAFE-01 | Decision: D-01
Source: AegisX-AI-Project-Bible-v6.md Section 2, C2 "Permission Matrix"
(role strings); 05-CONTEXT.md D-01 (fixed demo identity, role selector,
every request carries user_id + role).

This module implements a fixed demo identity: no credential is ever
verified. D-01 marked this a one-way choice for this hackathon's scope --
there is no login flow, no session table wiring, and no password anywhere
in this path. A real auth swap (JWT bearer, session cookie, etc.) replaces
this module's `require_identity` dependency and nothing else -- every
write-capable route already depends on `RequestIdentity` via FastAPI's
`Depends()`, not on any header-parsing logic of its own, so the swap point
is exactly this one function.

The server re-derives identity from the current request's headers on every
call -- it never trusts a value cached client-side or embedded in a
request body field (05-RESEARCH.md Security Domain: "Server independently
re-derives user_id/role from the request on every write-capable route").
"""

from dataclasses import dataclass
from typing import FrozenSet

from fastapi import Header, HTTPException

# Bible Section 2, C2 "Permission Matrix" role strings, transcribed
# verbatim -- including the slash in "QA/Compliance". 05-CONTEXT.md D-01
# writes the role "QA-Compliance" (hyphen) in its own prose, but the
# Bible is the source of truth on any drift (CLAUDE.md Rule 14), so no
# mapping table exists anywhere in this codebase between the two
# spellings -- "QA/Compliance" (slash) is the one and only accepted
# string for this role.
DEMO_ROLES: FrozenSet[str] = frozenset({"IT System Manager", "QA/Compliance", "Auditor"})


@dataclass(frozen=True)
class RequestIdentity:
    user_id: str
    role: str


async def require_identity(
    x_user_id: str = Header(...),
    x_user_role: str = Header(...),
) -> RequestIdentity:
    """FastAPI dependency resolving identity from the `X-User-Id` /
    `X-User-Role` request headers.

    Headers were chosen over a request-body field (05-RESEARCH.md Open
    Question 1) so identity stays orthogonal to every route's own request
    schema -- no route's Pydantic model needs a `user_id`/`role` field of
    its own, and this is also the idiomatic place a future real-auth swap
    (JWT bearer) would live.

    Raises HTTP 403 for an unrecognised role -- fail closed, mirroring
    `c2_gateway.check_rbac`'s own default for an unrecognised role. This
    keeps "identity could not be established" and "identity was
    established but is not permitted to do X" as two independently
    fail-closed checks (this function vs. `check_rbac`), rather than
    collapsing them into one.
    """
    if x_user_role not in DEMO_ROLES:
        raise HTTPException(status_code=403, detail=f"Unrecognized role: {x_user_role}")
    return RequestIdentity(user_id=x_user_id, role=x_user_role)
