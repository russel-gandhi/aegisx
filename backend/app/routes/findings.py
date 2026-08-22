"""
Assurance Card HTTP route (Phase 4, plan 04-03).

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

Calls A2's three deterministic check functions and C1's verifier
directly rather than invoking the compiled LangGraph: the graph would
fan out to five specialists this card has no use for, and would lose
the per-check name (`check_result["check"]`) the DETERMINISTIC CHECK
field requires -- `build_finding` drops that name (critical finding 3).
"""

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.agents.a2_compliance import A2_CHECKS, build_finding, narrate_gap
from app.agents.c1_verifier import verify_finding
from app.db import acquire_pool_or_none
from app.routes.evidence_graph import _system_exists
from app.schemas import AssuranceCard, AssuranceCardsResponse, DeterministicCheck

router = APIRouter()


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


@router.get(
    "/api/systems/{system_id}/assurance-cards",
    response_model=AssuranceCardsResponse,
)
async def get_assurance_cards(system_id: str):
    """Run A2's three deterministic checks against live Postgres, narrate
    each failing one, verify each resulting finding through C1 against
    real Postgres and real OPA, and return one card per failing check.

    A check that passes produces no finding and no card at all (A2's own
    contract, critical finding 5) -- a system whose checks all pass
    returns an empty `cards` array with HTTP 200, not an error.
    """
    pool = await acquire_pool_or_none()
    if pool is None:
        raise HTTPException(status_code=503, detail="Postgres pool unavailable")
    if not await _system_exists(pool, system_id):
        raise HTTPException(status_code=404, detail=f"Unknown system_id: {system_id}")

    cards = []
    for check_fn in A2_CHECKS:
        check_result = await check_fn(pool, system_id)
        if check_result["passed"]:
            continue
        claim, model_id = await narrate_gap(check_result)
        finding = build_finding(check_result, claim, model_id)
        verification_result = await verify_finding(pool, finding)
        cards.append(_assemble_card(check_result, finding, verification_result))

    return AssuranceCardsResponse(system_id=system_id, cards=cards)
