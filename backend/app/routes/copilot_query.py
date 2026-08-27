"""
Copilot non-hero-query HTTP route (Phase 6, plan 06-01, Task 2).

Ticket: SENT-5-02 (context) | Requirement: UI-04 | Decision: D-04
Source: 06-01-PLAN.md Task 2 <action>; 06-UI-SPEC.md Interaction Notes'
"Non-hero-query chat path" section.

This route exists for exactly one reason: to give `detect_injection()`
(`app.agents.c2_gateway`, Phase 5, already Critical-reviewed, zero-LLM) its
first real HTTP caller. The Copilot chat's hero-query shape (a
system-readiness question against a known/seeded system id) never reaches
this route at all -- Copilot.tsx routes that shape straight to
`streamAssuranceCards()` / `GET .../assurance-cards/stream` (D-01),
unmodified by this plan. Every other chat input lands here.

`supported` is always `False` in v1: this route makes no claim about
system readiness, runs no compliance check, and calls no other agent. It
only answers the one question C2's injection detector can answer
deterministically -- was this input a suspected prompt-injection attempt?
-- and otherwise degrades to an honest "not supported yet" response
(D-04's never-fabricate discipline, extended from the UI to this route's
own contract).

No pool acquisition, no RBAC gate: this route performs no write and reads
no per-role data, matching `routes/actions.py`'s own documented precedent
for the Phase 4 read routes (`routes/evidence_graph.py`,
`routes/findings.py`) being deliberately left ungated. This route is even
lighter than a read -- it touches no DB and no OPA sidecar at all, only a
pure in-process regex/entropy computation.
"""

from fastapi import APIRouter

from app.agents.c2_gateway import detect_injection
from app.schemas import CopilotQueryRequest, CopilotQueryResponse

router = APIRouter()


@router.post("/api/copilot/query", response_model=CopilotQueryResponse)
async def query_copilot(request: CopilotQueryRequest) -> CopilotQueryResponse:
    """Runs the caller's free text through `detect_injection()` and returns
    an honest, never-fabricated response.

    `blocked=True` iff `detect_injection()` returns a reason (regex leg or
    entropy leg); `reason` is that exact string, unmodified, so the chat UI
    can interpolate the same real reason a Guided Tour step (06-UI-SPEC.md
    Step 5, "AI Safety") demonstrates live. `supported` is always `False`
    here -- see module docstring."""
    reason = detect_injection(request.query)
    if reason is not None:
        return CopilotQueryResponse(supported=False, blocked=True, reason=reason)
    return CopilotQueryResponse(supported=False, blocked=False, reason=None)
