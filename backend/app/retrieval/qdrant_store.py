"""
Qdrant vector store client (Phase 06.1, plan 06.1-01, RAG-01/RAG-02).

Ticket: n/a (roadmap phase 06.1) | Requirements: RAG-01, RAG-02
Source: AegisX-AI-Project-Bible-v6.md Section 9.2 (Qdrant collection/search
sample); Bible's Qdrant schema comment (line 1260, "768 dimensions... cosine
distance").

Qdrant has been running healthy in `docker-compose.yml` with zero
collections and zero client code since Phase 1 (06.1-CONTEXT.md). This
module is the first code in the repository to talk to it.

No existing external-vector-DB client pattern exists in this codebase to
extend (06.1-PATTERNS.md), so this module follows `app.db`'s closest
structural precedent instead: a module-level, re-read-at-call-time
`QDRANT_URL` constant (mirrors `app.db.DATABASE_URL` -- a test can
`monkeypatch.setattr(qdrant_store, "QDRANT_URL", ...)` and have it take
effect on the next `get_qdrant_client()` call), and a
degrade-don't-raise `get_qdrant_client()` entry point mirroring
`app.db.acquire_pool_or_none()`: returns `None` on any construction/ping
failure instead of propagating the exception.

Deviation 15: Bible Section 9.2's sample code calls the deprecated
`client.search(...)` method. This module uses `AsyncQdrantClient.
query_points(...)` instead -- `search`/`search_batch` are deprecated in
current `qdrant-client` releases in favour of `query_points`/
`query_batch_points` (06.1-RESEARCH.md Pitfall 6). Verified against the
installed `qdrant-client==1.19.0`'s own `query_points` signature
(`collection_name`, `query`, `limit`, `query_filter`, `with_payload`, ...)
at implementation time.
"""

import logging
import os
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

logger = logging.getLogger(__name__)

QDRANT_COLLECTION: str = "gxp_document_chunks"

# Read once at import, re-read as a module attribute (not a captured
# default-arg value) on every call below -- mirrors app.db.DATABASE_URL's
# own rationale exactly, including the reason 127.0.0.1 is not used here:
# unlike DATABASE_URL, no prior deviation in this codebase established a
# 127.0.0.1-over-localhost convention for Qdrant, and docker-compose.yml
# already publishes Qdrant on `localhost:6333` for host-side callers.
QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")

# Bible's Qdrant schema comment (line 1260): 768-dim, cosine distance.
_DENSE_VECTOR_SIZE: int = 768


class DenseHit(BaseModel):
    chunk_id: str
    document_id: str
    score: float


async def get_qdrant_client() -> Optional[AsyncQdrantClient]:
    """Construct an `AsyncQdrantClient` against the current `QDRANT_URL`
    and confirm it actually answers before returning it.

    Never raises: any construction or connectivity failure is logged at
    `warning` level (target URL + exception type only, matching this
    module's degrade-don't-raise contract) and `None` is returned, exactly
    as `app.db.acquire_pool_or_none()` degrades on an unreachable
    Postgres. Every caller of this function must handle `None` as a real,
    expected state -- not treat it as impossible.
    """
    try:
        client = AsyncQdrantClient(url=QDRANT_URL)
        await client.get_collections()
        return client
    except Exception as exc:  # noqa: BLE001 -- qdrant-client/httpx raise a
        # variety of exception types for "unreachable"; the caller-facing
        # contract here is "never raises", so every exception degrades.
        logger.warning(
            "Qdrant client unavailable (target=%s): %s", QDRANT_URL, type(exc).__name__
        )
        return None


async def ensure_collection(client: AsyncQdrantClient) -> bool:
    """Create `QDRANT_COLLECTION` (768-dim, cosine distance) if it does not
    already exist. Idempotent: a second call against an already-created
    collection is a no-op that still returns `True`. Returns `True` once
    the collection is confirmed to exist (whether just created or already
    present), `False` only if creation itself reports failure.
    """
    exists = await client.collection_exists(QDRANT_COLLECTION)
    if exists:
        return True
    created = await client.create_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config=VectorParams(size=_DENSE_VECTOR_SIZE, distance=Distance.COSINE),
    )
    return bool(created)


async def upsert_chunks(client: AsyncQdrantClient, points: List[Dict[str, Any]]) -> int:
    """Upsert `points` (one dict per chunk: `chunk_id`, `document_id`,
    `system_id`, `vector`, and optionally `section`/`page`/`chunk_index`)
    into `QDRANT_COLLECTION`. `chunk_id` becomes the Qdrant point id
    (stringified, since Qdrant accepts either an unsigned int or a UUID
    string); the same fields (minus the vector itself) become the
    payload, so `dense_search()` can answer a query filtered by
    `system_id` without a second Postgres round-trip. Returns the number
    of points written; `0` for an empty `points` list (no-op, not an
    error).
    """
    if not points:
        return 0

    structs = [
        PointStruct(
            id=str(point["chunk_id"]),
            vector=point["vector"],
            payload={
                "chunk_id": str(point["chunk_id"]),
                "document_id": point["document_id"],
                "system_id": point["system_id"],
                "section": point.get("section"),
                "page": point.get("page"),
                "chunk_index": point.get("chunk_index"),
            },
        )
        for point in points
    ]
    await client.upsert(collection_name=QDRANT_COLLECTION, points=structs)
    return len(structs)


async def dense_search(
    client: AsyncQdrantClient, query_vector: List[float], system_id: str, limit: int = 20
) -> List[DenseHit]:
    """Dense (cosine) search over `QDRANT_COLLECTION`, filtered to
    `system_id` via the payload's `system_id` field. Uses `query_points`
    (Deviation 15) -- never the deprecated `search()`/`search_batch()`
    helpers.
    """
    response = await client.query_points(
        collection_name=QDRANT_COLLECTION,
        query=query_vector,
        limit=limit,
        query_filter=Filter(
            must=[FieldCondition(key="system_id", match=MatchValue(value=system_id))]
        ),
        with_payload=True,
    )
    hits: List[DenseHit] = []
    for scored_point in response.points:
        payload = scored_point.payload or {}
        hits.append(
            DenseHit(
                chunk_id=str(payload.get("chunk_id", scored_point.id)),
                document_id=str(payload.get("document_id", "")),
                score=float(scored_point.score),
            )
        )
    return hits
