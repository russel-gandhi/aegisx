"""
Tests for `app.routes.reports` (SENT-9-04, `POST /api/reports/evidence-pack`).

Follows this codebase's established convention: real Postgres, never
mocked, via the shared `client` fixture. `pypdf` (already a project
dependency) extracts real text from the generated PDF bytes to prove the
export actually contains the live assurance-card data it claims to, not
just that the response has the right content-type.
"""

import io

from pypdf import PdfReader


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def test_evidence_pack_returns_a_real_pdf_for_a_known_system(client):
    resp = client.post(
        "/api/reports/evidence-pack", json={"system_id": "GXP-MFG-DEMO-01"}
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:5] == b"%PDF-"


def test_evidence_pack_content_disposition_names_the_system(client):
    resp = client.post(
        "/api/reports/evidence-pack", json={"system_id": "GXP-MFG-DEMO-01"}
    )
    assert "evidence-pack-GXP-MFG-DEMO-01.pdf" in resp.headers["content-disposition"]


def test_evidence_pack_pdf_text_contains_real_assurance_card_data(client):
    # Cross-check against the live assurance-cards endpoint this route
    # reuses internally -- proves the PDF isn't a static template but
    # actually renders the same real, currently-open findings.
    cards_resp = client.get("/api/systems/GXP-MFG-DEMO-01/assurance-cards")
    cards = cards_resp.json()["cards"]
    assert cards, "expected GXP-MFG-DEMO-01 to have at least one open finding to assert against"
    first_finding_id = cards[0]["finding_id"]

    pdf_resp = client.post(
        "/api/reports/evidence-pack", json={"system_id": "GXP-MFG-DEMO-01"}
    )
    text = _extract_pdf_text(pdf_resp.content)
    assert first_finding_id in text
    assert "GXP-MFG-DEMO-01" in text
    assert "PROTOTYPE" in text  # the synthetic-data disclaimer


def test_evidence_pack_unknown_system_returns_404(client):
    resp = client.post(
        "/api/reports/evidence-pack", json={"system_id": "NO-SUCH-SYSTEM"}
    )
    assert resp.status_code == 404


def test_evidence_pack_missing_system_id_returns_422(client):
    resp = client.post("/api/reports/evidence-pack", json={})
    assert resp.status_code == 422


def test_evidence_pack_second_seeded_system_also_returns_a_real_pdf(client):
    resp = client.post(
        "/api/reports/evidence-pack", json={"system_id": "BUS-IT-DEMO-02"}
    )
    assert resp.status_code == 200
    assert resp.content[:5] == b"%PDF-"
    text = _extract_pdf_text(resp.content)
    assert "BUS-IT-DEMO-02" in text


def test_build_pdf_with_no_cards_renders_the_honest_empty_state():
    # Unit-level check of the empty-list path directly (rather than
    # relying on finding a real seeded system with zero open findings,
    # which neither seeded system happens to have) -- proves the "no open
    # findings" branch in `_build_pdf` is real code, not dead code.
    from app.routes.reports import _build_pdf

    pdf_bytes = _build_pdf("EMPTY-SYSTEM", [])
    assert pdf_bytes[:5] == b"%PDF-"
    text = _extract_pdf_text(pdf_bytes)
    assert "no open findings" in text.lower()
