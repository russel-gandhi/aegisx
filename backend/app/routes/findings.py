"""
Assurance Card HTTP routes (Phase 4, plan 04-03; concurrency + SSE sibling
route added quick task 260826-p1q).

Ticket: SENT-3-05 | Requirement: EVID-03 | Decision: D-04
Source: 04-03-PLAN.md <interface_contract> route table and Bible Section
11.2's Assurance Card field list.

This module computes no confidence, decides no `passed` boolean, and
makes no model call of its own beyond A2's own already-existing
narration step (Bible Section 1.3). Every field this route returns is
read from `app.agents.a2_compliance`'s and `app.agents.c1_verifier`'s
existing return values -- both Critical-review Phase 3 modules are
read-only inputs here and are not modified by this plan (critical
finding 2, CLAUDE.md Rule 10).

That narration step may now serve text generated for a byte-identical
earlier prompt rather than issuing a fresh model call every time
(quick task 260826-0b5, `app/narration_cache.py`) -- every field this
route reads from C1 (`confidence`, `db_record_found`, `opa_corroborated`)
is still recomputed against live Postgres and live OPA on every request,
regardless of whether the narration itself was a cache hit or a miss.

Calls A2's three deterministic check functions and C1's verifier
directly rather than invoking the compiled LangGraph: the graph would
fan out to five specialists this card has no use for, and would lose
the per-check name (`check_result["check"]`) the DETERMINISTIC CHECK
field requires -- `build_finding` drops that name (critical finding 3).

**Concurrency (quick task 260826-p1q).** `_card_for_check` runs one
`A2_CHECKS` entry to completion -- check -> narrate -> build -> verify --
and both routes below fan its four instances out concurrently rather
than looping sequentially. `verify_finding` is always awaited to
completion *inside* `_card_for_check`, before a card object exists at
all: no caller can ever emit a card whose confidence has not yet been
computed, which is the plan's explicit "no unverified content on
screen" invariant (CLAUDE.md, PLAN.md "What this plan explicitly does
NOT touch"). Concurrency is bounded by a per-request
`asyncio.Semaphore(_MAX_CONCURRENT_CHECKS)` -- sized to `A2_CHECKS`'
own length (4) -- because the asyncpg pool (`app/db.py`) caps at 5
connections; the pre-warm background task (`app/prewarm.py`) stays
strictly sequential for the same reason, so it cannot race a live
request's 4-way fan-out past the pool cap. The semaphore is
constructed *inside* each route function, never at module scope: this
suite runs a fresh asyncio event loop per test (`asyncio.run()`-per-
test convention, `tests/conftest.py`), and an asyncio primitive bound
at import time would bind to whichever loop happened to exist first
and silently break every later test.

The blocking route below fans `_card_for_check` out via `asyncio.gather`,
which returns results in *input* order -- so its `cards` list is
byte-identical in ordering to the old sequential loop's, which is the
property the eleven existing call sites (routes/actions.py,
tests/test_routes_findings.py, tests/test_routes_actions.py,
tests/test_narration_cache.py) depend on. The `/stream` sibling route
uses `asyncio.as_completed` instead, because there the whole point of
streaming is to paint each card the moment ITS OWN narration+verification
finishes, in completion order, not input order.
"""

import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict, Optional

from fastapi import APIRouter, HTTPException
from starlette.responses import StreamingResponse

from app.agents.a2_compliance import A2_CHECKS, build_finding, narrate_gap
from app.agents.c1_verifier import verify_finding
from app.db import acquire_pool_or_none
from app.routes.evidence_graph import _system_exists
from app.schemas import AssuranceCard, AssuranceCardsResponse, DeterministicCheck

logger = logging.getLogger(__name__)

router = APIRouter()

# A2_CHECKS has exactly 4 entries today; bounding concurrency at that count
# is a belt-and-suspenders cap (gather/as_completed already only ever
# start 4 tasks), documented here so a later reader who adds a 5th check
# to A2_CHECKS knows this constant does not need to move in lockstep --
# it exists to protect the asyncpg pool (max_size=5, app/db.py), not to
# mirror A2_CHECKS' length for its own sake.
_MAX_CONCURRENT_CHECKS = 4


def _assemble_card(
    check_result: Dict[str, Any],
    finding: Dict[str, Any],
    verification_result: Dict[str, Any],
) -> AssuranceCard:
    """Build one `AssuranceCard` from three already-computed Phase 3
    objects: A2's check result, A2's finding, and C1's verification
    result.

    `confidence` is read from `verification_result["confidence"]` --
    C1's real grade against real Postgres and real OPA -- and NEVER from
    `finding["confidence_score"]`, which A2 sets to the fixed literal
    `"UNVERIFIED"` for every finding it emits (critical finding 6,
    backend/README.md's AgentFinding conventions table). The two fields
    are adjacent and similarly named on the finding dict; reading the
    wrong one is this plan's single most likely defect.
    """
    deterministic_check = DeterministicCheck(
        check_name=check_result["check"],
        passed=check_result["passed"],
        db_record_found=verification_result["db_record_found"],
        opa_corroborated=verification_result["opa_corroborated"],
        opa_rule_ids=verification_result["opa_rule_ids"],
        opa_bundle_hash=verification_result.get("opa_bundle_hash", "unavailable"),
    )
    return AssuranceCard(
        finding_id=finding["finding_id"],
        claim=finding["claim"],
        evidence_ids=finding["evidence_ids"],
        regulatory_citations=finding["regulatory_citations"],
        deterministic_check=deterministic_check,
        confidence=verification_result["confidence"],
        alcoa_score=finding["alcoa_score"],
        model_attribution=finding["model_attribution"],
    )


async def _card_for_check(pool, system_id: str, check_fn, semaphore: asyncio.Semaphore) -> Optional[AssuranceCard]:
    """Run one `A2_CHECKS` entry to completion: check -> (narrate -> build
    -> verify) if and only if it failed. Returns `None` immediately for a
    passing check -- a passing check produces no finding and no card
    (A2's own contract, critical finding 5) -- and otherwise returns the
    fully-assembled `AssuranceCard`.

    `verify_finding` is awaited to completion INSIDE this coroutine, before
    the card object is constructed at all, so no caller of this function
    can ever emit a card whose confidence has not yet been computed.
    """
    async with semaphore:
        check_result = await check_fn(pool, system_id)
        if check_result["passed"]:
            return None
        claim, model_id = await narrate_gap(check_result)
        finding = build_finding(check_result, claim, model_id)
        verification_result = await verify_finding(pool, finding)
        return _assemble_card(check_result, finding, verification_result)


@router.get(
    "/api/systems/{system_id}/assurance-cards",
    response_model=AssuranceCardsResponse,
)
async def get_assurance_cards(system_id: str):
    """Run A2's four deterministic checks against live Postgres
    CONCURRENTLY, narrate and verify each failing one, and return one card
    per failing check.

    A check that passes produces no finding and no card at all (A2's own
    contract, critical finding 5) -- a system whose checks all pass
    returns an empty `cards` array with HTTP 200, not an error.

    The four checks now run concurrently (quick task 260826-p1q) via
    `asyncio.gather` over `_card_for_check`, bounded by a per-request
    semaphore (see module docstring). `gather` preserves INPUT order, so
    this route's `cards` list is byte-identical in ordering to the old
    sequential loop's -- the property this route's eleven existing call
    sites depend on. `return_exceptions` is left at its default (`False`),
    so a check raising still surfaces as a 500, exactly as it did before.
    """
    pool = await acquire_pool_or_none()
    if pool is None:
        raise HTTPException(status_code=503, detail="Postgres pool unavailable")
    if not await _system_exists(pool, system_id):
        raise HTTPException(status_code=404, detail=f"Unknown system_id: {system_id}")

    semaphore = asyncio.Semaphore(_MAX_CONCURRENT_CHECKS)
    results = await asyncio.gather(
        *(_card_for_check(pool, system_id, check_fn, semaphore) for check_fn in A2_CHECKS)
    )
    cards = [card for card in results if card is not None]

    return AssuranceCardsResponse(system_id=system_id, cards=cards)


async def _stream_cards(pool, system_id: str) -> AsyncGenerator[bytes, None]:
    """Inner SSE generator: fan `_card_for_check` out over
    `asyncio.as_completed` (COMPLETION order, not input order -- the whole
    point of streaming is to paint each card the moment its own
    narration+verification finishes) and yield one `data: ` frame per
    non-`None` result, followed by exactly one terminal frame.

    A per-check exception is caught here (never allowed to propagate out
    of an already-started `StreamingResponse` -- the 200 status line is
    already committed by the time this generator runs, so a raise here
    would produce a torn response, not a 500). It is logged and reported
    as one error frame, and the stream stops -- there is no way to
    retroactively turn a mid-stream failure into an honest HTTP status.
    """
    semaphore = asyncio.Semaphore(_MAX_CONCURRENT_CHECKS)
    tasks = [
        asyncio.ensure_future(_card_for_check(pool, system_id, check_fn, semaphore))
        for check_fn in A2_CHECKS
    ]
    count = 0
    try:
        for coro in asyncio.as_completed(tasks):
            card = await coro
            if card is None:
                continue
            count += 1
            frame = {"event": "card", "card": card.model_dump(mode="json")}
            yield f"data: {json.dumps(frame)}\n\n".encode("utf-8")
    except Exception as exc:
        logger.warning(
            "assurance-cards stream failed for system_id=%s: %s", system_id, exc, exc_info=True
        )
        error_frame = {"event": "error", "detail": "assurance card stream failed"}
        yield f"data: {json.dumps(error_frame)}\n\n".encode("utf-8")
        return

    done_frame = {"event": "done", "system_id": system_id, "count": count}
    yield f"data: {json.dumps(done_frame)}\n\n".encode("utf-8")


@router.get("/api/systems/{system_id}/assurance-cards/stream")
async def get_assurance_cards_stream(system_id: str):
    """SSE sibling of `get_assurance_cards` (quick task 260826-p1q):
    streams one card frame per currently-failing check, in completion
    order, followed by exactly one terminal frame.

    The `acquire_pool_or_none()` / `_system_exists()` guards run HERE, in
    the route function body, above the generator -- exactly where the
    blocking route runs them. Once `StreamingResponse` begins, the 200
    status line is already committed, so a guard failure discovered inside
    the generator could never become a real 404/503; it must be checked
    before the generator is even constructed.
    """
    pool = await acquire_pool_or_none()
    if pool is None:
        raise HTTPException(status_code=503, detail="Postgres pool unavailable")
    if not await _system_exists(pool, system_id):
        raise HTTPException(status_code=404, detail=f"Unknown system_id: {system_id}")

    return StreamingResponse(
        _stream_cards(pool, system_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            # Harmless with no reverse proxy in front locally; removes the
            # one environmental assumption (Research Assumption A3) that
            # could silently collapse the stream back into a blocking
            # payload if a buffering proxy were ever introduced.
            "X-Accel-Buffering": "no",
        },
    )
