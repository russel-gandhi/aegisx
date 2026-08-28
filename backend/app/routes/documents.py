"""
Document upload route (Phase 06.1, plans 06.1-01/06.1-04, RAG-01).

Ticket: n/a (roadmap phase 06.1) | Requirements: RAG-01, RAG-02
Source: 06.1-01-PLAN.md Task 2; 06.1-04-PLAN.md Task 2; 06.1-PATTERNS.md
`routes/documents.py` section (guard-order copied from
`routes/evidence_graph.py`).

`POST /api/documents/upload` is this phase's only ingestion entry point.
Guard order mirrors `routes/evidence_graph.py`'s pool-acquire-or-503 /
system-exists-or-404 convention, with two upload-specific guards ahead
of it: size (413) and `detect_format`'s extension-AND-magic-bytes sniff
(415) -- both run before any parse, before the pool is even acquired, so
an oversized or content-mismatched upload never reaches Postgres
(T-06.1-21).

Never-fabricate discipline (matching `routes/copilot_query.py`'s own
module docstring): every field in the returned `DocumentUploadResponse`
is read from either the caller's own input (`system_id`, `doc_type`) or
`IngestResult`, computed by `app.retrieval.ingest.index_document()` against
real Postgres/Qdrant state. This route authors no compliance judgment of
its own.

The client-supplied filename is used only as display text for
`documents.title` -- via `os.path.basename` plus a 255-char truncation --
never as a filesystem path component and never as the document id
(T-06.1-02). Parsing runs on the in-memory bytes; no temp file is ever
written.
"""

import os
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.db import acquire_pool_or_none
from app.identity import RequestIdentity, require_identity
from app.retrieval.ingest import (
    MAX_UPLOAD_BYTES,
    SUPPORTED_FORMATS,
    chunk_blocks,
    detect_format,
    index_document,
    parse_document,
)
from app.retrieval.qdrant_store import ensure_collection, get_qdrant_client
from app.routes.evidence_graph import _system_exists
from app.schemas import DocumentUploadResponse

router = APIRouter()


@router.post("/api/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    system_id: str = Form(...),
    doc_type: Optional[str] = Form(None),
    identity: RequestIdentity = Depends(require_identity),
) -> DocumentUploadResponse:
    # (a) size guard -- read at most MAX_UPLOAD_BYTES + 1 bytes, before any
    # parse and before the pool is even acquired.
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Upload exceeds the {MAX_UPLOAD_BYTES}-byte limit",
        )

    original_filename = file.filename or ""

    # (b) extension AND content-magic-bytes agreement (T-06.1-21) -- the
    # extension alone is never sufficient. `detect_format` returns None
    # for an unsupported extension, a binary payload behind a text
    # extension, a text payload behind a binary extension, or a payload
    # whose magic bytes disagree with its claimed binary format.
    fmt = detect_format(raw, original_filename)
    if fmt is None:
        raise HTTPException(
            status_code=415,
            detail=(
                "Unsupported or content-mismatched file; supported formats "
                f"(by extension AND content): {sorted(SUPPORTED_FORMATS)}"
            ),
        )

    # (d) pool-acquire-or-503 / (e) system-exists-or-404 -- the same guard
    # order every other route in this codebase uses
    # (routes/evidence_graph.py, routes/findings.py).
    pool = await acquire_pool_or_none()
    if pool is None:
        raise HTTPException(status_code=503, detail="Postgres pool unavailable")
    if not await _system_exists(pool, system_id):
        raise HTTPException(status_code=404, detail=f"Unknown system_id: {system_id}")

    # Qdrant unavailability degrades the same way an unreachable Postgres
    # pool does above (503, not an unhandled exception from deep inside
    # index_document's upsert call) -- `get_qdrant_client()` already
    # mirrors `acquire_pool_or_none()`'s degrade-don't-raise contract; this
    # route completes that contract by turning `None` into a clean guard.
    # Checked here, before any write, so a Qdrant outage never leaves a
    # `documents` row with no matching chunks (the same "no partial state"
    # property the Postgres guard above gives).
    qdrant_client = await get_qdrant_client()
    if qdrant_client is None:
        raise HTTPException(status_code=503, detail="Qdrant unavailable")
    await ensure_collection(qdrant_client)

    # (f) server-generated document_id -- never derived from the client
    # filename (T-06.1-02).
    document_id = f"DOC-{uuid4().hex[:12].upper()}"
    title = os.path.basename(original_filename)[:255] or document_id
    # doc_type defaults to the sniffed format's uppercased key when the
    # form field is absent (06.1-04-PLAN.md Task 2 <action> item 4) --
    # never a bare "UPLOADED" literal that discards the one thing this
    # route already determined for certain about the file.
    resolved_doc_type = doc_type or fmt.upper()

    await pool.execute(
        "INSERT INTO documents (id, system_id, doc_type, title, version, author, "
        "created_date, status) VALUES ($1, $2, $3, $4, $5, $6, now(), $7)",
        document_id,
        system_id,
        resolved_doc_type,
        title,
        None,
        identity.user_id,
        "READY",
    )

    # (g) parse -> chunk -> index. Parsing runs on the in-memory bytes
    # already read above; no temp file is ever written.
    blocks = parse_document(raw, original_filename, fmt)

    # A parse that yields no blocks for a non-empty, non-CSV payload is a
    # parsing failure (T-06.1-22), not an honest zero: an empty CSV (no
    # data rows) is the one legitimate "zero blocks" case, per
    # parse_csv's own docstring. The `documents` row above is left in
    # place so the Knowledge list can show the failure honestly instead
    # of silently discarding the upload attempt.
    if not blocks and fmt != "csv" and len(raw) > 0:
        return DocumentUploadResponse(
            document_id=document_id,
            system_id=system_id,
            title=title,
            doc_type=resolved_doc_type,
            chunk_count=0,
            indexed_vector_count=0,
            status="FAILED",
            failed_stage="parsing",
        )

    chunks = chunk_blocks(blocks)
    for chunk in chunks:
        # chunk_blocks() has no access to the client filename (its own
        # frozen signature is `blocks -> List[Chunk]`) -- this route is
        # the one caller that has it, so it attaches source_filename here,
        # before the write phase.
        chunk.metadata["source_filename"] = title

    result = await index_document(pool, qdrant_client, document_id, system_id, chunks)

    return DocumentUploadResponse(
        document_id=document_id,
        system_id=system_id,
        title=title,
        doc_type=resolved_doc_type,
        chunk_count=result.chunk_count,
        indexed_vector_count=result.indexed_vector_count,
        status=result.status,
        failed_stage=result.failed_stage,
    )
