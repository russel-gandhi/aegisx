"""
Tests for `POST /api/changes/{change_id}/affects` (`app.routes.changes`).

Closes the gap where `change_affects` (backing the evidence graph's
`CHANGE --AFFECTS--> X` edge, `app.graph.evidence_graph._add_change_affects_edges`)
had no write path -- only a static 3-row seed fixture for the one demo
change `CR-2026-089`. Exercises real seeded rows: `CR-2026-089` (changes)
and `TC-2026-042` (test_cases), both from `infra/postgres/seed/001_seed.sql`
-- deliberately not the REQUIREMENT/DOCUMENT/DESIGN_ELEMENT rows
`003_change_affects_fixture.sql` already seeded for this same change_id,
since this file's own cleanup deletes rows by exact
(change_id, entity_type, entity_id) match and must never touch fixture
data another test file (`test_evidence_graph.py`) asserts against.
"""

import asyncio

from app import db

ITSM_HEADERS = {"X-User-Id": "u-itsm-test", "X-User-Role": "IT System Manager"}
QA_HEADERS = {"X-User-Id": "u-qa-test", "X-User-Role": "QA/Compliance"}

REAL_CHANGE_ID = "CR-2026-089"
# Deliberately NOT (CR-2026-089, REQUIREMENT, URS-042) or the DOCUMENT/
# DESIGN_ELEMENT pairs -- those three rows are real seeded fixture data
# (infra/postgres/seed/003_change_affects_fixture.sql) that
# test_evidence_graph.py's integration tests assert against; deleting one
# in this file's cleanup would silently corrupt that fixture for every
# other test in the suite. TC-2026-042 (test_cases, seeded by
# 001_seed.sql) is real but was never given a change_affects row, so it's
# a safe, real target this file owns exclusively.
REAL_TEST_CASE_ID = "TC-2026-042"


def _delete_row(entity_type: str, entity_id: str) -> None:
    async def _run():
        pool = await db.get_pool()
        await pool.execute(
            "DELETE FROM change_affects WHERE change_id = $1 AND entity_type = $2 "
            "AND entity_id = $3",
            REAL_CHANGE_ID,
            entity_type,
            entity_id,
        )

    asyncio.run(_run())


def test_create_change_affects_as_itsm_returns_201_and_persists(client):
    _delete_row("TEST_CASE", REAL_TEST_CASE_ID)
    try:
        resp = client.post(
            f"/api/changes/{REAL_CHANGE_ID}/affects",
            json={"entity_type": "TEST_CASE", "entity_id": REAL_TEST_CASE_ID},
            headers=ITSM_HEADERS,
        )
        assert resp.status_code == 201
        assert resp.json() == {
            "change_id": REAL_CHANGE_ID,
            "entity_type": "TEST_CASE",
            "entity_id": REAL_TEST_CASE_ID,
        }

        async def _fetch():
            pool = await db.get_pool()
            return await pool.fetchrow(
                "SELECT * FROM change_affects WHERE change_id = $1 AND entity_type = $2 "
                "AND entity_id = $3",
                REAL_CHANGE_ID,
                "TEST_CASE",
                REAL_TEST_CASE_ID,
            )

        row = asyncio.run(_fetch())
        assert row is not None
    finally:
        _delete_row("TEST_CASE", REAL_TEST_CASE_ID)


def test_create_change_affects_is_idempotent_on_duplicate_insert(client):
    _delete_row("TEST_CASE", REAL_TEST_CASE_ID)
    try:
        body = {"entity_type": "TEST_CASE", "entity_id": REAL_TEST_CASE_ID}
        first = client.post(
            f"/api/changes/{REAL_CHANGE_ID}/affects", json=body, headers=ITSM_HEADERS
        )
        assert first.status_code == 201
        second = client.post(
            f"/api/changes/{REAL_CHANGE_ID}/affects", json=body, headers=ITSM_HEADERS
        )
        assert second.status_code == 201
    finally:
        _delete_row("TEST_CASE", REAL_TEST_CASE_ID)


def test_create_change_affects_invalid_entity_type_returns_422(client):
    resp = client.post(
        f"/api/changes/{REAL_CHANGE_ID}/affects",
        json={"entity_type": "SUPPLIER", "entity_id": "SUP-001"},
        headers=ITSM_HEADERS,
    )
    assert resp.status_code == 422


def test_create_change_affects_unknown_change_id_returns_404(client):
    resp = client.post(
        "/api/changes/NOT-A-REAL-CHANGE/affects",
        json={"entity_type": "TEST_CASE", "entity_id": REAL_TEST_CASE_ID},
        headers=ITSM_HEADERS,
    )
    assert resp.status_code == 404


def test_create_change_affects_unknown_entity_id_returns_404(client):
    resp = client.post(
        f"/api/changes/{REAL_CHANGE_ID}/affects",
        json={"entity_type": "TEST_CASE", "entity_id": "NOT-A-REAL-TEST-CASE"},
        headers=ITSM_HEADERS,
    )
    assert resp.status_code == 404


def test_create_change_affects_non_itsm_role_returns_403(client):
    resp = client.post(
        f"/api/changes/{REAL_CHANGE_ID}/affects",
        json={"entity_type": "TEST_CASE", "entity_id": REAL_TEST_CASE_ID},
        headers=QA_HEADERS,
    )
    assert resp.status_code == 403


def test_create_change_affects_missing_identity_headers_returns_422(client):
    resp = client.post(
        f"/api/changes/{REAL_CHANGE_ID}/affects",
        json={"entity_type": "TEST_CASE", "entity_id": REAL_TEST_CASE_ID},
    )
    assert resp.status_code == 422


def test_create_change_affects_postgres_unreachable_returns_503(
    client, monkeypatch, reset_db_pool
):
    monkeypatch.setattr(
        db, "DATABASE_URL", "postgresql://sentinel:sentinel@127.0.0.1:1/sentinel"
    )
    resp = client.post(
        f"/api/changes/{REAL_CHANGE_ID}/affects",
        json={"entity_type": "TEST_CASE", "entity_id": REAL_TEST_CASE_ID},
        headers=ITSM_HEADERS,
    )
    assert resp.status_code == 503
