"""Tests for `app.routes.suppliers` (Bible Section 11.5, Supplier Intelligence)."""

from app.db import get_pool


def test_gxp_demo_suppliers_includes_datasync_overdue(client):
    resp = client.get("/api/systems/GXP-MFG-DEMO-01/suppliers")
    assert resp.status_code == 200
    body = resp.json()
    assert body["system_id"] == "GXP-MFG-DEMO-01"

    by_name = {s["name"]: s for s in body["suppliers"]}
    assert "DataSync Solutions" in by_name
    datasync = by_name["DataSync Solutions"]
    assert datasync["is_overdue"] is True
    assert datasync["reassessment_due_date_ns"] is not None


def test_supplier_with_no_assessment_row_reports_none_not_fabricated(client):
    resp = client.get("/api/systems/GXP-MFG-DEMO-01/suppliers")
    body = resp.json()
    datasync = next(s for s in body["suppliers"] if s["name"] == "DataSync Solutions")
    # The seed data gives DataSync Solutions no supplier_assessments row --
    # this must come back None, never a guessed/defaulted result string.
    assert datasync["latest_assessment_result"] is None
    assert datasync["latest_assessment_date_ns"] is None


def test_unknown_system_returns_404(client):
    resp = client.get("/api/systems/NO-SUCH-SYSTEM/suppliers")
    assert resp.status_code == 404


def test_bus_it_demo_empty_supplier_list_returns_200(client):
    resp = client.get("/api/systems/BUS-IT-DEMO-02/suppliers")
    assert resp.status_code == 200
    assert resp.json()["suppliers"] == []


def test_postgres_unreachable_returns_503(client, monkeypatch, reset_db_pool):
    from app import db

    monkeypatch.setattr(
        db, "DATABASE_URL", "postgresql://sentinel:sentinel@127.0.0.1:1/sentinel"
    )
    resp = client.get("/api/systems/GXP-MFG-DEMO-01/suppliers")
    assert resp.status_code == 503
