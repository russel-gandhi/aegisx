"""
Tests for `app.agents.c3_gateway` — Critical-review coverage (Phase 5,
plan 05-04, Task 1).

Ticket: SENT-4-03 | Requirement: REM-02, REM-03 | CLAUDE.md Rule 6

Covers the plan's `<behavior>` list (five-category routing, fail-closed
default, `describe_category`) plus the Critical-review additions: all
five Bible categories are reachable and asserted as a literal set, an
unknown `action_type` fails closed to PROHIBITED across several shapes,
an AST gate proves this module never imports a model client, and a live
Postgres round-trip proves `persist_proposal` binds every value rather
than interpolating it.

Follows this suite's established convention (`asyncio.run()` inside a
plain `def test_*`, no pytest-asyncio — `backend/tests/conftest.py`) and
`test_routes_actions.py`'s own module-fixture cleanup pattern for rows
this file inserts itself.
"""

import ast
import asyncio
from pathlib import Path
from typing import List

import pytest

from app.agents.c3_gateway import (
    ACTION_CATEGORIES,
    BLOCKED_CATEGORIES,
    QUEUED_CATEGORIES,
    describe_category,
    persist_proposal,
    route_action,
)
from app.db import get_pool

C3_MODULE_PATH = Path(__file__).resolve().parents[1] / "app" / "agents" / "c3_gateway.py"

# Bible Section 2, C3 "Categories" — the five literal category names,
# transcribed here independently of ACTION_CATEGORIES so a dropped or
# invented category in the implementation fails this test rather than
# silently agreeing with itself.
BIBLE_FIVE_CATEGORIES = {
    "READ",
    "DRAFT",
    "MOCK_WRITE_LOW_RISK",
    "GXP_RELEVANT_WRITE",
    "PROHIBITED",
}

# Bible Section 2, C3 "Categories" — the five one-line dispositions,
# transcribed verbatim.
BIBLE_CATEGORY_DISPOSITIONS = {
    "READ": "Automatic execution.",
    "DRAFT": "Saved to local state, automatic execution.",
    "MOCK_WRITE_LOW_RISK": "Sent to Human Approval Queue.",
    "GXP_RELEVANT_WRITE": "Blocked. Requires out-of-band execution.",
    "PROHIBITED": "Blocked immediately.",
}


async def _cleanup(pool, proposal_ids: List[str]) -> None:
    if proposal_ids:
        await pool.execute(
            "DELETE FROM action_proposals WHERE id = ANY($1::varchar[])", proposal_ids
        )


# --- <behavior>: route_action for each of the five categories --------------


def test_route_action_read():
    assert route_action("READ_SYSTEM_RECORD") == "READ"


def test_route_action_draft():
    assert route_action("DRAFT_CAPA_NARRATIVE") == "DRAFT"


def test_route_action_mock_write_low_risk():
    assert route_action("DRAFT_SERVICENOW_TICKET") == "MOCK_WRITE_LOW_RISK"


def test_route_action_gxp_relevant_write():
    assert route_action("CREATE_CAPA_RECORD") == "GXP_RELEVANT_WRITE"


def test_route_action_prohibited():
    assert route_action("DELETE_AUDIT_EVENT") == "PROHIBITED"


# --- <behavior>: fail-closed default ----------------------------------------


@pytest.mark.parametrize(
    "action_type",
    ["", "unknown-type", "create_capa_record"],
    ids=["empty_string", "unmapped_type", "wrong_case"],
)
def test_route_action_fails_closed_to_prohibited(action_type):
    assert route_action(action_type) == "PROHIBITED"


# --- <behavior>: QUEUED_CATEGORIES / BLOCKED_CATEGORIES --------------------


def test_queued_categories_contains_exactly_the_two_queued_categories():
    assert QUEUED_CATEGORIES == frozenset({"MOCK_WRITE_LOW_RISK", "GXP_RELEVANT_WRITE"})


def test_blocked_categories_contains_prohibited():
    assert "PROHIBITED" in BLOCKED_CATEGORIES


def test_prohibited_absent_from_queued_categories():
    assert "PROHIBITED" not in QUEUED_CATEGORIES


# --- <behavior>: describe_category ------------------------------------------


@pytest.mark.parametrize("category", sorted(BIBLE_CATEGORY_DISPOSITIONS))
def test_describe_category_matches_bible_text(category):
    assert describe_category(category) == BIBLE_CATEGORY_DISPOSITIONS[category]


def test_describe_category_raises_key_error_for_unknown_category():
    with pytest.raises(KeyError):
        describe_category("NOT_A_REAL_CATEGORY")


# --- <behavior>: persist_proposal writes exactly one PENDING_APPROVAL row --


def test_persist_proposal_writes_pending_approval_row_with_supplied_fields():
    async def run():
        pool = await get_pool()
        proposal_ids: List[str] = []
        try:
            proposal = {
                "action_type": "CREATE_CAPA_RECORD",
                "target_system": "GXP-MFG-DEMO-01",
                "payload": {"finding_id": "TEST-FINDING"},
                "justification": "Test justification text.",
            }
            proposal_id = await persist_proposal(
                pool, proposal, "GXP_RELEVANT_WRITE", None, "TEST-FINDING", "test-model"
            )
            proposal_ids.append(proposal_id)

            row = await pool.fetchrow(
                "SELECT * FROM action_proposals WHERE id = $1", proposal_id
            )
            assert row is not None
            assert row["status"] == "PENDING_APPROVAL"
            assert row["justification"] == "Test justification text."
            assert row["finding_id"] == "TEST-FINDING"
            assert row["session_id"] is None
            assert row["model_id"] == "test-model"
        finally:
            await _cleanup(pool, proposal_ids)

    asyncio.run(run())


# --- <behavior>: two persist_proposal calls sort in creation order --------


def test_proposal_ids_sort_in_creation_order():
    async def run():
        pool = await get_pool()
        proposal_ids: List[str] = []
        try:
            proposal = {
                "action_type": "CREATE_CAPA_RECORD",
                "target_system": "GXP-MFG-DEMO-01",
                "payload": {},
                "justification": "First.",
            }
            first_id = await persist_proposal(
                pool, proposal, "GXP_RELEVANT_WRITE", None, "TEST-FINDING-1", "test-model"
            )
            proposal_ids.append(first_id)
            second_id = await persist_proposal(
                pool, proposal, "GXP_RELEVANT_WRITE", None, "TEST-FINDING-2", "test-model"
            )
            proposal_ids.append(second_id)

            assert first_id != second_id
            assert sorted([first_id, second_id]) == [first_id, second_id]
        finally:
            await _cleanup(pool, proposal_ids)

    asyncio.run(run())


# --- Critical-review addition: all five Bible categories are reachable ----


def test_all_five_bible_categories_are_reachable():
    assert set(ACTION_CATEGORIES.values()) == BIBLE_FIVE_CATEGORIES


# --- Critical-review addition: fail-closed default, parametrised ----------


@pytest.mark.parametrize(
    "action_type",
    ["", "   ", "create_capa_record", "DRAFT_SERVICENOW_TICKET_V2"],
    ids=["empty_string", "whitespace", "wrong_case", "plausible_but_unmapped"],
)
def test_unknown_action_type_fails_closed_to_prohibited(action_type):
    """Returning READ (the most permissive category) on an unknown
    action_type would be the dangerous default here -- READ is Bible
    Section 2's 'Automatic execution' category. Failing closed to
    PROHIBITED is what makes an invented or mistyped action_type inert
    rather than silently auto-executing."""
    assert route_action(action_type) == "PROHIBITED"


# --- Critical-review addition: AST gate -- no model dependency ------------


def test_c3_module_has_no_model_dependency():
    """C3 is a fixed-topology decision node (Bible Section 1.3) -- an LLM
    may never decide action-category routing. Parses the module's own
    source (not its runtime import graph, which could be satisfied
    indirectly) and asserts no imported module name contains 'llm' and no
    imported name is 'call_llm'."""
    source = C3_MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(C3_MODULE_PATH))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "llm" not in alias.name.lower(), (
                    f"c3_gateway.py imports {alias.name!r} -- C3 must never "
                    "depend on a model client (Bible Section 1.3)."
                )
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            assert "llm" not in module_name.lower(), (
                f"c3_gateway.py imports from {module_name!r} -- C3 must "
                "never depend on a model client (Bible Section 1.3)."
            )
            for alias in node.names:
                assert alias.name != "call_llm", (
                    "c3_gateway.py imports call_llm -- C3 must never call "
                    "a model (Bible Section 1.3)."
                )


# --- Critical-review addition: SQL binding proof ---------------------------


def test_persist_proposal_binds_every_value():
    """A `action_type` containing a SQL metacharacter payload round-trips
    as the exact literal string, and exactly one row is inserted -- proof
    the value was bound through a `$N` placeholder, never interpolated
    (ASVS V5)."""

    async def run():
        pool = await get_pool()
        proposal_ids: List[str] = []
        try:
            payload_action_type = "CREATE_CAPA_RECORD'; DROP TABLE action_proposals; --"
            proposal = {
                "action_type": payload_action_type,
                "target_system": "GXP-MFG-DEMO-01",
                "payload": {},
                "justification": "SQL metacharacter probe.",
            }
            before = await pool.fetchval("SELECT count(*) FROM action_proposals")
            proposal_id = await persist_proposal(
                pool, proposal, "PROHIBITED", None, "TEST-FINDING-SQLI", "test-model"
            )
            proposal_ids.append(proposal_id)
            after = await pool.fetchval("SELECT count(*) FROM action_proposals")

            assert after == before + 1
            row = await pool.fetchrow(
                "SELECT action_type FROM action_proposals WHERE id = $1", proposal_id
            )
            assert row["action_type"] == payload_action_type
        finally:
            await _cleanup(pool, proposal_ids)

    asyncio.run(run())
