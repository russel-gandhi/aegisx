"""
Evidence Pack PDF export (Bible Section 12, `POST /api/reports/evidence-pack`).

Ticket: SENT-9-04 | Requirement: bible Section 12's own table entry
Source: AegisX-AI-Project-Bible-v6.md Section 12 -- request `Dict`,
response "PDF Stream", generation method "WeasyPrint".

This endpoint was the one genuinely unbuilt item from the Bible's original
ten-endpoint list (`app/main.py`'s own long-standing docstring note):
WeasyPrint needs native GTK/Pango/Cairo libraries with no provisioning path
on this project (no backend Dockerfile exists to install them into, and
they don't install via pip alone on Windows). Rather than block this
indefinitely on containerizing the backend -- itself complicated by Ollama
running on the host, not in a container, which a naive container build
would have no path to reach -- this uses `reportlab` instead: a pure-Python
PDF library with zero native dependencies, so the endpoint is buildable and
verifiable today rather than shipped untested.

Reuses `app.routes.findings.get_assurance_cards` directly for its data --
never a second query path, never a second copy of the Claim/Evidence/
ALCOA+/Confidence/Model-Attribution assembly logic C1's own verification
flow already produces (Bible Section 11.2's Assurance Card contract).
Every field on the page traces to that same real, already-verified
response; nothing here is authored by a model or invented for the export.
"""

import io
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.db import acquire_pool_or_none
from app.routes.evidence_graph import _system_exists
from app.routes.findings import get_assurance_cards
from app.schemas import AssuranceCard

logger = logging.getLogger(__name__)

router = APIRouter()


class EvidencePackRequest(BaseModel):
    system_id: str


_ALCOA_DIMENSION_LABELS = (
    "Attributable", "Legible", "Contemporaneous", "Original", "Accurate",
    "Complete", "Consistent", "Enduring", "Available",
)


def _build_pdf(system_id: str, cards: list[AssuranceCard]) -> bytes:
    """Pure function: no I/O, no model call -- every value it renders was
    already computed by `get_assurance_cards`'s own real Postgres/OPA
    verification before this function ever runs (mirrors
    `app.graph.evidence_graph.build_graph`'s compute-then-write split
    elsewhere in this codebase)."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=LETTER,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
    )
    styles = getSampleStyleSheet()
    disclaimer_style = ParagraphStyle(
        "Disclaimer", parent=styles["Normal"], textColor=colors.HexColor("#b91c1c"),
        fontName="Helvetica-Bold", fontSize=9, spaceAfter=12,
    )
    claim_style = ParagraphStyle("Claim", parent=styles["BodyText"], spaceAfter=4)

    story = []
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    story.append(Paragraph("AegisX AI — Evidence Pack", styles["Title"]))
    story.append(Paragraph(f"System: {system_id}", styles["Heading2"]))
    story.append(Paragraph(f"Generated: {generated_at}", styles["Normal"]))
    story.append(Spacer(1, 0.15 * inch))
    # Same disclaimer the frontend's persistent red banner shows on every
    # page (App.tsx) -- an exported artifact must carry it too, not just
    # the live UI (this is a synthetic-data prototype, never a real
    # regulatory submission).
    story.append(Paragraph(
        "PROTOTYPE — SYNTHETIC DATA — NOT VALIDATED FOR PRODUCTION GxP USE",
        disclaimer_style,
    ))

    if not cards:
        story.append(Paragraph(
            "No open findings for this system at generation time — every "
            "deterministic check A2 runs against it currently passes.",
            styles["Normal"],
        ))
    else:
        for card in cards:
            story.append(KeepTogether(_render_card(card, styles, claim_style)))
            story.append(Spacer(1, 0.2 * inch))

    doc.build(story)
    return buffer.getvalue()


def _render_card(card: AssuranceCard, styles, claim_style) -> list:
    check = card.deterministic_check
    elements = [
        Paragraph(f"Finding {card.finding_id}", styles["Heading3"]),
        Paragraph(card.claim, claim_style),
    ]

    detail_rows = [
        ["Evidence IDs", ", ".join(card.evidence_ids) or "—"],
        ["Regulatory citations", ", ".join(card.regulatory_citations) or "—"],
        ["Deterministic check", check.check_name],
        ["Check passed", "No" if not check.passed else "Yes"],
        ["Database record found", "Yes" if check.db_record_found else "No"],
        ["OPA corroborated", "Yes" if check.opa_corroborated else "No"],
        ["Confidence", card.confidence],
        ["Model attribution", card.model_attribution],
    ]
    detail_table = Table(detail_rows, colWidths=[1.8 * inch, 4.2 * inch])
    detail_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 0), (-1, -2), 0.25, colors.HexColor("#e2e8f0")),
    ]))
    elements.append(detail_table)

    alcoa_row_labels = ["ALCOA+"] + list(_ALCOA_DIMENSION_LABELS)
    alcoa_row_values = [""] + [
        "✓" if card.alcoa_score.get(field.lower(), False) else "✗"
        for field in _ALCOA_DIMENSION_LABELS
    ]
    alcoa_table = Table([alcoa_row_labels, alcoa_row_values], colWidths=None)
    alcoa_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
    ]))
    elements.append(Spacer(1, 0.1 * inch))
    elements.append(alcoa_table)
    return elements


@router.post("/api/reports/evidence-pack")
async def generate_evidence_pack(body: EvidencePackRequest):
    pool = await acquire_pool_or_none()
    if pool is None:
        raise HTTPException(status_code=503, detail="Postgres pool unavailable")
    if not await _system_exists(pool, body.system_id):
        raise HTTPException(status_code=404, detail=f"Unknown system_id: {body.system_id}")

    cards_response = await get_assurance_cards(body.system_id)
    pdf_bytes = _build_pdf(body.system_id, cards_response.cards)

    filename = f"evidence-pack-{body.system_id}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
