"""
Document upload + list routes (Phase 06.1, plans 06.1-01/06.1-04, RAG-01).

Ticket: n/a (roadmap phase 06.1) | Requirements: RAG-01, RAG-02
Source: 06.1-01-PLAN.md Task 2; 06.1-04-PLAN.md Task 2/Task 3;
06.1-PATTERNS.md `routes/documents.py` section (guard-order copied from
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

`GET /api/documents` (plan 06.1-04 Task 3) lists every uploaded document
with a `COUNT(*)`-derived `chunk_count` -- never a stored counter that
could drift out of sync with the real `document_chunks` rows -- and a
read-time-derived `ingestion_status`. `identity` is required, matching
the upload route: a document inventory is closer to a write-route's
sensitivity than to the deliberately-ungated Phase 4 read-route
precedent (T-06.1-24).

A successful upload also triggers an evidence-graph rebuild for the
affected `system_id` only (`_rebuild_evidence_graph_for`, closes
06.1-RESEARCH.md Pitfall 2), so a just-uploaded document is immediately
visible to Blast Radius / graph-expanded Copilot evidence without a
separate manual `POST /api/systems/{system_id}/evidence-graph/rebuild`
call. A rebuild failure is logged with `exc_info=True` and swallowed --
it never turns a successful ingest into a reported failure -- and its
consequence (graph expansion is stale for this document until the next
rebuild) is documented here, not surfaced to the caller. The pre-existing
explicit rebuild route remains the recovery path (T-06.1-25). No polling
or push refresh is added by this plan; the standing `/blast-radius` and
`/findings` live-refresh item (`.planning/STATE.md` Pending Todos) stays
out of scope.
"""

import asyncio
import hashlib
import logging
import os
from typing import Optional
from uuid import uuid4

import asyncpg
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from app.agents.c2_gateway import detect_injection
from app.audit_trail import log_event
from app.db import acquire_pool_or_none
from app.graph.evidence_graph import build_graph, persist_graph
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
from app.schemas import (
    DocumentApproveResponse,
    DocumentListResponse,
    DocumentSummary,
    DocumentUploadResponse,
)

router = APIRouter()

logger = logging.getLogger(__name__)


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

    # (c2) idempotency guard (SYSTEM-DESIGN-DIAGNOSIS.md #6): a double-click,
    # a client retry after a slow response, or a flaky-network resubmit must
    # not re-run the full parse->chunk->embed->index pipeline and pay the
    # embedding-provider cost a second time for bytes already ingested for
    # this system. Scoped to (system_id, content hash), never the hash
    # alone -- identical content legitimately uploaded for two different
    # systems is not a duplicate. Checked before the Qdrant guard below so a
    # duplicate resubmit never even needs Qdrant to be reachable.
    content_sha256 = hashlib.sha256(raw).hexdigest()
    existing = await pool.fetchrow(
        "SELECT d.id, d.title, d.doc_type, d.status, "
        "COUNT(c.chunk_id) AS chunk_count "
        "FROM documents d LEFT JOIN document_chunks c ON c.document_id = d.id "
        "WHERE d.system_id = $1 AND d.content_sha256 = $2 "
        "GROUP BY d.id",
        system_id,
        content_sha256,
    )
    # 2026-11-16: a FAILED document is not a duplicate -- it is an upload that
    # never got indexed (embedding provider down, Qdrant error, unparseable at
    # the time). Returning it here as `duplicate=True` made that failure
    # permanent for these exact bytes: the hash is on the row forever, so
    # every retry of the same file was answered with the stale failure and
    # the pipeline never ran again. A FAILED row is instead re-ingested in
    # place, under its existing id (the unique index on
    # (system_id, content_sha256) already guarantees there is only one).
    # QUARANTINED stays a terminal duplicate below: that verdict is a
    # deterministic function of the bytes and cannot change on retry.
    retry_document_id: Optional[str] = None
    if existing is not None and existing["status"] == "FAILED":
        retry_document_id = existing["id"]
        existing = None

    if existing is not None:
        return DocumentUploadResponse(
            document_id=existing["id"],
            system_id=system_id,
            title=existing["title"],
            doc_type=existing["doc_type"],
            chunk_count=existing["chunk_count"],
            indexed_vector_count=existing["chunk_count"],
            status=existing["status"],
            failed_stage=None,
            # A duplicate resubmit of content that was quarantined on its
            # first upload must keep reporting that honestly -- re-running
            # the scan is unnecessary (the decision cannot have changed for
            # byte-identical content) but silently dropping back to
            # `quarantined=False` here would misreport a caught attack as
            # a clean, ordinary duplicate.
            quarantined=existing["status"] == "QUARANTINED",
            quarantine_reason=(
                "Previously quarantined by C2's deterministic injection detector "
                "(see the original upload's audit_events row for the exact match)."
                if existing["status"] == "QUARANTINED"
                else None
            ),
            duplicate=True,
        )

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
    document_id = retry_document_id or f"DOC-{uuid4().hex[:12].upper()}"
    title = os.path.basename(original_filename)[:255] or document_id
    # doc_type defaults to the sniffed format's uppercased key when the
    # form field is absent (06.1-04-PLAN.md Task 2 <action> item 4) --
    # never a bare "UPLOADED" literal that discards the one thing this
    # route already determined for certain about the file.
    resolved_doc_type = doc_type or fmt.upper()

    if retry_document_id is not None:
        # Re-ingest in place. `index_document` is all-or-nothing, so a FAILED
        # row should own no chunks -- deleted anyway so a retry can never
        # stack a second set on top of a partial first one.
        await pool.execute("DELETE FROM document_chunks WHERE document_id = $1", document_id)
        await pool.execute(
            "UPDATE documents SET doc_type = $2, title = $3, author = $4, "
            "created_date = now(), status = 'READY' WHERE id = $1",
            document_id,
            resolved_doc_type,
            title,
            identity.user_id,
        )
    else:
        try:
            await pool.execute(
                "INSERT INTO documents (id, system_id, doc_type, title, version, author, "
                "created_date, status, content_sha256) VALUES ($1, $2, $3, $4, $5, $6, now(), $7, $8)",
                document_id,
                system_id,
                resolved_doc_type,
                title,
                None,
                identity.user_id,
                "READY",
                content_sha256,
            )
        except asyncpg.UniqueViolationError:
            # Two uploads of the same bytes raced past the duplicate check
            # above; the unique index let exactly one INSERT through. This
            # is the other one -- previously an unhandled 500.
            raise HTTPException(
                status_code=409,
                detail="An upload of this exact file for this system is already in progress",
            )

    # (g) parse -> chunk -> index. Parsing runs on the in-memory bytes
    # already read above; no temp file is ever written.
    #
    # `parse_document` (PDF/DOCX parsing especially) is real CPU-bound work,
    # not I/O -- calling it directly inside this `async def` would block the
    # single-worker event loop for its entire duration, stalling every other
    # concurrent request (other users' API calls, the copilot WebSocket,
    # even /api/health) for as long as this one upload takes to parse.
    # `asyncio.to_thread` moves it to the default executor so the event loop
    # stays free (SYSTEM-DESIGN-DIAGNOSIS.md #4).
    blocks = await asyncio.to_thread(parse_document, raw, original_filename, fmt)

    # A parse that yields no blocks for a non-empty, non-CSV payload is a
    # parsing failure (T-06.1-22), not an honest zero: an empty CSV (no
    # data rows) is the one legitimate "zero blocks" case, per
    # parse_csv's own docstring. The `documents` row above is left in
    # place so the Knowledge list can show the failure honestly instead
    # of silently discarding the upload attempt.
    if not blocks and fmt != "csv" and len(raw) > 0:
        # The `documents` row was inserted as "READY" above before parsing
        # ran; a parsing failure must not leave that raw column claiming
        # success indefinitely (Phase 13 DB-integrity invariant) even
        # though `list_documents` already recomputes an honest status at
        # read time from `chunk_count`. Any future direct reader of this
        # column (e.g. a new agent query) must see the true outcome.
        await pool.execute(
            "UPDATE documents SET status = 'FAILED' WHERE id = $1", document_id
        )
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

    chunks = await asyncio.to_thread(chunk_blocks, blocks)
    for chunk in chunks:
        # chunk_blocks() has no access to the client filename (its own
        # frozen signature is `blocks -> List[Chunk]`) -- this route is
        # the one caller that has it, so it attaches source_filename here,
        # before the write phase.
        chunk.metadata["source_filename"] = title

    # (h) deterministic, zero-LLM injection scan (Bible Section 11.7,
    # Assurance Lab) -- reuses C2's own `detect_injection` (regex +
    # Shannon-entropy legs, the identical check every copilot query
    # already passes through) against each parsed chunk's text. A
    # document whose content itself carries jailbreak phrasing or a
    # high-entropy smuggled payload is quarantined here, before any
    # embedding call: it is never written to `document_chunks`, never
    # upserted into Qdrant, and therefore can never surface as retrieved
    # "knowledge" a later query could be grounded against. A real
    # audit_events row is written for the quarantine decision itself.
    quarantine_reason: Optional[str] = None
    for chunk in chunks:
        reason = detect_injection(chunk.content)
        if reason is not None:
            quarantine_reason = reason
            break

    if quarantine_reason is not None:
        await pool.execute(
            "UPDATE documents SET status = 'QUARANTINED' WHERE id = $1", document_id
        )
        await log_event(
            pool,
            {
                "user_id": identity.user_id,
                "user_role": identity.role,
                "agent_id": "C2",
                "action_type": "DOCUMENT_QUARANTINED",
                "target_system_id": system_id,
                "target_record_id": document_id,
                "input_hash": content_sha256,
                "output_summary": (
                    f"Upload {title!r} quarantined by C2's deterministic injection "
                    f"detector before indexing: {quarantine_reason}"
                ),
            },
        )
        return DocumentUploadResponse(
            document_id=document_id,
            system_id=system_id,
            title=title,
            doc_type=resolved_doc_type,
            chunk_count=0,
            indexed_vector_count=0,
            status="QUARANTINED",
            failed_stage=None,
            quarantined=True,
            quarantine_reason=quarantine_reason,
        )

    result = await index_document(pool, qdrant_client, document_id, system_id, chunks)

    # Mirror the true ingest outcome onto the persisted row (see the
    # parsing-failure branch above for why this matters even though
    # `list_documents` already recomputes status from `chunk_count`).
    if result.status == "FAILED":
        await pool.execute(
            "UPDATE documents SET status = 'FAILED' WHERE id = $1", document_id
        )

    # Post-ingest evidence-graph rebuild (06.1-04-PLAN.md Task 3, closes
    # 06.1-RESEARCH.md Pitfall 2) -- only after a successful index, never
    # after a failed one, so a rebuild is never attempted over a document
    # this route itself has already reported as FAILED.
    if result.status == "READY":
        await _rebuild_evidence_graph_for(pool, system_id)

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


async def _rebuild_evidence_graph_for(pool, system_id: str) -> None:
    """Rebuilds and persists the evidence graph for `system_id` after a
    successful document ingest, calling the exact same two functions
    `routes/evidence_graph.py::rebuild_evidence_graph` calls (imported,
    never reimplemented). Runs inside a broad-exception guard: a rebuild
    failure here is logged with `exc_info=True` and swallowed -- it never
    fails the upload response, which has already committed to
    `status="READY"` by the time this runs. The documented consequence is
    that graph expansion (Blast Radius, graph-based Copilot evidence)
    stays stale for the newly uploaded document until the next rebuild;
    the pre-existing `POST /api/systems/{system_id}/evidence-graph/rebuild`
    route remains available as the explicit recovery path (T-06.1-25)."""
    try:
        graph = await build_graph(pool, system_id)
        await persist_graph(pool, system_id, graph)
    except Exception:
        logger.error(
            "Evidence graph rebuild failed after document upload for system_id=%s; "
            "graph expansion is stale until the next explicit rebuild.",
            system_id,
            exc_info=True,
        )


@router.get("/api/documents", response_model=DocumentListResponse)
async def list_documents(
    system_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    identity: RequestIdentity = Depends(require_identity),
) -> DocumentListResponse:
    """Lists every uploaded document, optionally filtered to one
    `system_id`. `chunk_count` is a real `COUNT(*)` over `document_chunks`
    computed in this one query -- never a stored counter that could
    drift. `ingestion_status` is derived at read time from `chunk_count`
    (mirroring the `category`-derived-not-persisted precedent set by the
    `003_action_proposals_workflow.sql` migration): `"READY"` when
    `chunk_count > 0`, `"FAILED"` when the `documents` row exists with
    zero chunks. `failed_stage` is deliberately left `None` at read time
    -- a stored chunk count alone cannot distinguish a parsing failure
    from an indexing failure, and this route never guesses. An empty
    result set (a `system_id` filter that matches zero documents) is a
    200 with `documents: []`, never a 404 -- only an unknown `system_id`
    itself is a 404.

    `limit`/`offset` (SYSTEM-DESIGN-DIAGNOSIS.md #5) bound the response to
    at most `limit` rows (default 50, capped at 200) starting at `offset`,
    ordered newest-first -- this endpoint had no ceiling on result-set size
    before, which is fine at demo data volumes and a self-inflicted
    unbounded-query risk once it isn't. `total_count` is computed in the
    same query via `COUNT(*) OVER()` (one round trip, not two) so a caller
    can tell whether more pages exist without a second request."""
    pool = await acquire_pool_or_none()
    if pool is None:
        raise HTTPException(status_code=503, detail="Postgres pool unavailable")
    if system_id is not None and not await _system_exists(pool, system_id):
        raise HTTPException(status_code=404, detail=f"Unknown system_id: {system_id}")

    rows = await pool.fetch(
        "SELECT d.id, d.system_id, d.title, d.doc_type, d.version, d.created_date, "
        "d.status, "
        "COUNT(c.chunk_id) AS chunk_count, "
        "COUNT(*) OVER() AS total_count "
        "FROM documents d LEFT JOIN document_chunks c ON c.document_id = d.id "
        "WHERE ($1::varchar IS NULL OR d.system_id = $1) "
        "GROUP BY d.id ORDER BY d.created_date DESC NULLS LAST "
        "LIMIT $2 OFFSET $3",
        system_id,
        limit,
        offset,
    )

    documents = [
        DocumentSummary(
            document_id=row["id"],
            title=row["title"],
            doc_type=row["doc_type"],
            version=row["version"],
            system_id=row["system_id"],
            created_date=row["created_date"].isoformat() if row["created_date"] else None,
            chunk_count=row["chunk_count"],
            # QUARANTINED is a deliberate, permanent write-time decision
            # (C2's injection scan) -- unlike FAILED, it must never be
            # inferred purely from `chunk_count == 0` (a legitimate
            # zero-chunk state a quarantined row also happens to have), or
            # it would misreport a caught attack as an ordinary parse
            # failure.
            ingestion_status=(
                "QUARANTINED"
                if row["status"] == "QUARANTINED"
                else "READY" if row["chunk_count"] > 0 else "FAILED"
            ),
            failed_stage=None,
            # See DocumentSummary's own docstring-comment: the stored
            # column verbatim, orthogonal to ingestion_status above.
            approval_status=row["status"],
        )
        for row in rows
    ]
    total_count = rows[0]["total_count"] if rows else 0

    return DocumentListResponse(
        system_id=system_id,
        documents=documents,
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/api/documents/{document_id}/approve",
    response_model=DocumentApproveResponse,
)
async def approve_document(
    document_id: str,
    identity: RequestIdentity = Depends(require_identity),
) -> DocumentApproveResponse:
    """Closes the gap `a2_compliance.verify_urs_approved` (and the URS
    branch of every check reading `documents.status`) otherwise leaves
    unreachable: `upload_document` above always inserts a row with
    `status='READY'`, an ingestion-pipeline status, and prior to this
    route there was no way for any uploaded document to ever reach
    `status='APPROVED'` -- only a row written directly into Postgres by a
    seed script could satisfy that check.

    Gated to "QA/Compliance" -- document approval is that role's real-world
    responsibility per the Bible's own agent Permission Matrix (which
    grants QA/Compliance A1-A6 but withholds A7 remediation-triggering,
    the inverse split of IT System Manager's administrative actions like
    `POST /api/systems`). RBAC is checked before the pool guard, matching
    every other write route in this codebase.

    A QUARANTINED document can never be approved through this route --
    C2's injection-detection quarantine is a permanent, deliberate
    decision (see `upload_document`'s own comment on this), not a
    reversible ingestion-pipeline state; approving quarantined content
    would defeat the point of quarantining it. Approving an
    already-APPROVED document is treated as idempotent success (no-op,
    still 200) rather than an error -- a QA reviewer re-submitting an
    approval action they already took should never see a failure.
    """
    if identity.role != "QA/Compliance":
        raise HTTPException(
            status_code=403,
            detail=f"Role {identity.role} may not approve documents",
        )

    pool = await acquire_pool_or_none()
    if pool is None:
        raise HTTPException(status_code=503, detail="Postgres pool unavailable")

    row = await pool.fetchrow("SELECT status FROM documents WHERE id = $1", document_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown document_id: {document_id}")

    if row["status"] == "QUARANTINED":
        raise HTTPException(
            status_code=409,
            detail=f"Document {document_id} is quarantined and cannot be approved",
        )

    if row["status"] != "APPROVED":
        await pool.execute(
            "UPDATE documents SET status = 'APPROVED' WHERE id = $1", document_id
        )

    return DocumentApproveResponse(document_id=document_id, status="APPROVED")
