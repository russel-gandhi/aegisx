"""
Tests for `app.retrieval.ingest` (Phase 06.1, plan 06.1-01).

Covers every `<behavior>` bullet in 06.1-01-PLAN.md Task 1 for
`parse_text`/`chunk_blocks` (pure unit tests, no I/O) and
`index_document`'s write/rollback behaviour against live Postgres and live
Qdrant, following `test_evidence_graph.py`'s established
asyncpg-fixture/live-state conventions (never mocked for the integration
section) and `test_llm_router.py`'s respx convention for the embedding
call itself.

Structured in the same UNIT / INTEGRATION comment-section convention
`test_evidence_graph.py` and `test_c1_verifier.py` establish.
"""

import asyncio
from typing import List
from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from app.db import get_pool
from app.retrieval.embeddings import EMBEDDING_DIMENSIONS
from app.retrieval.ingest import (
    CHUNK_OVERLAP_WORDS,
    CHUNK_WORDS,
    MAX_CHUNKS_PER_DOCUMENT,
    Chunk,
    IngestResult,
    ParsedBlock,
    chunk_blocks,
    index_document,
    parse_text,
)
from app.retrieval.qdrant_store import QDRANT_COLLECTION, QDRANT_URL, get_qdrant_client

DEMO_SYSTEM = "GXP-MFG-DEMO-01"
QDRANT_URL_FOR_TESTS = QDRANT_URL  # pass-through target for the respx routes below
DEMO_DOCUMENT_ID = "DOC-2026-OM-99"  # seeded row, infra/postgres/seed/001_seed.sql

MARKDOWN_TWO_SECTIONS = (
    "Lead-in text before any heading.\n\n"
    "## Section A\n"
    "Content for section A, several words long to be non-trivial.\n\n"
    "## Section B\n"
    "Content for section B, also several words long here.\n"
)

MARKDOWN_NO_HEADINGS = "Just a plain paragraph with no ATX heading anywhere in it at all.\n"


def _embedding_success_body(dimensions: int) -> dict:
    values = [((i + 1) % 23) / 7.0 - 1.5 for i in range(dimensions)]
    return {"embedding": {"values": values}}


def _batch_success_body(count: int, dimensions: int) -> dict:
    return {
        "embeddings": [
            {"values": [((i + j + 1) % 23) / 7.0 - 1.5 for i in range(dimensions)]}
            for j in range(count)
        ]
    }


async def _cleanup_chunks(chunk_ids: List[str]) -> None:
    if not chunk_ids:
        return
    pool = await get_pool()
    await pool.execute(
        "DELETE FROM document_chunks WHERE chunk_id = ANY($1::uuid[])", chunk_ids
    )
    client = await get_qdrant_client()
    if client is not None:
        try:
            await client.delete(collection_name=QDRANT_COLLECTION, points_selector=chunk_ids)
        except Exception:  # noqa: BLE001 -- best-effort cleanup only
            pass


# ---------------------------------------------------------------------------
# UNIT -- parse_text / chunk_blocks (no I/O)
# ---------------------------------------------------------------------------


def test_unit_parse_text_splits_on_markdown_headings():
    blocks = parse_text(MARKDOWN_TWO_SECTIONS.encode("utf-8"), "fixture.md")
    sections = [b.section for b in blocks]
    assert sections[0] is None  # lead-in text before any heading
    assert "Section A" in sections
    assert "Section B" in sections
    section_a_block = next(b for b in blocks if b.section == "Section A")
    section_b_block = next(b for b in blocks if b.section == "Section B")
    assert "section A" in section_a_block.text
    assert "section B" in section_b_block.text
    assert all(b.page is None for b in blocks)


def test_unit_parse_text_no_headings_returns_one_block():
    blocks = parse_text(MARKDOWN_NO_HEADINGS.encode("utf-8"), "plain.txt")
    assert len(blocks) == 1
    assert blocks[0].section is None
    assert blocks[0].page is None


def test_unit_chunk_blocks_900_words_single_section_yields_three_chunks_with_overlap():
    words = [f"word{i}" for i in range(900)]
    block = ParsedBlock(text=" ".join(words), section="Section A", page=None)

    chunks = chunk_blocks([block])

    assert [c.chunk_index for c in chunks] == [0, 1, 2]
    for chunk in chunks:
        assert len(chunk.content.split()) <= CHUNK_WORDS
        assert chunk.section == "Section A"

    chunk0_words = chunks[0].content.split()
    chunk1_words = chunks[1].content.split()
    chunk2_words = chunks[2].content.split()
    assert chunk0_words[-CHUNK_OVERLAP_WORDS:] == chunk1_words[:CHUNK_OVERLAP_WORDS]
    assert chunk1_words[-CHUNK_OVERLAP_WORDS:] == chunk2_words[:CHUNK_OVERLAP_WORDS]


def test_unit_chunk_blocks_sets_parent_chunk_id_to_section_leader():
    words = [f"word{i}" for i in range(900)]
    block = ParsedBlock(text=" ".join(words), section="Section A", page=None)

    chunks = chunk_blocks([block])

    leader = chunks[0]
    assert leader.parent_chunk_id is None
    for later_chunk in chunks[1:]:
        assert later_chunk.parent_chunk_id == leader.chunk_id


def test_unit_chunk_blocks_caps_at_max_chunks_per_document():
    words = [f"word{i}" for i in range(CHUNK_WORDS * (MAX_CHUNKS_PER_DOCUMENT + 10))]
    block = ParsedBlock(text=" ".join(words), section=None, page=None)

    chunks = chunk_blocks([block])

    assert len(chunks) == MAX_CHUNKS_PER_DOCUMENT
    assert all(chunk.content.strip() != "" for chunk in chunks)


def test_unit_chunk_blocks_never_returns_empty_content_chunk():
    blocks = [
        ParsedBlock(text="   ", section=None, page=None),  # whitespace-only -> zero words
        ParsedBlock(text="real content here", section="Section A", page=None),
    ]
    chunks = chunk_blocks(blocks)
    assert len(chunks) == 1
    assert chunks[0].content == "real content here"


def test_unit_chunk_blocks_multiple_sections_each_get_own_leader():
    blocks = [
        ParsedBlock(text="alpha beta gamma", section="Section A", page=None),
        ParsedBlock(text="delta epsilon zeta", section="Section B", page=None),
    ]
    chunks = chunk_blocks(blocks)
    assert len(chunks) == 2
    assert chunks[0].parent_chunk_id is None
    assert chunks[1].parent_chunk_id is None  # each is its own section's leader
    assert chunks[0].chunk_index == 0
    assert chunks[1].chunk_index == 1


# ---------------------------------------------------------------------------
# INTEGRATION -- index_document against live Postgres + live Qdrant
# ---------------------------------------------------------------------------


def test_integration_index_document_writes_postgres_and_qdrant_on_success(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    chunks = [
        Chunk(
            chunk_id="11111111-1111-1111-1111-111111111111",
            content="First chunk content for the integration test.",
            section="Section A",
            page=None,
            chunk_index=0,
            parent_chunk_id=None,
            metadata={"chunker": "word-bounded", "chunk_words": CHUNK_WORDS},
        ),
        Chunk(
            chunk_id="22222222-2222-2222-2222-222222222222",
            content="Second chunk content for the integration test.",
            section="Section A",
            page=None,
            chunk_index=1,
            parent_chunk_id="11111111-1111-1111-1111-111111111111",
            metadata={"chunker": "word-bounded", "chunk_words": CHUNK_WORDS},
        ),
    ]
    chunk_ids = [c.chunk_id for c in chunks]

    async def _run():
        pool = await get_pool()
        client = await get_qdrant_client()
        assert client is not None, "Qdrant must be reachable for this integration test"
        # Only the embedding endpoint is intercepted here -- the live Qdrant
        # upsert/retrieve calls below pass through to the real local service
        # via an explicit `pass_through()` route, matching this suite's
        # "never mock Postgres/Qdrant" integration convention
        # (test_evidence_graph.py). `assert_all_mocked=False` was tried and
        # rejected: in this sandbox it silently short-circuits ALL requests
        # (including the one meant to be mocked) to an empty 200 response
        # instead of actually passing anything through -- confirmed by
        # reproducing directly, not assumed.
        with respx.mock:
            respx.route(url__startswith=QDRANT_URL_FOR_TESTS).pass_through()
            respx.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents"
            ).mock(
                return_value=httpx.Response(200, json=_batch_success_body(len(chunks), EMBEDDING_DIMENSIONS))
            )
            result = await index_document(pool, client, DEMO_DOCUMENT_ID, DEMO_SYSTEM, chunks)

        rows = await pool.fetch(
            "SELECT chunk_id, document_id, content, section, page, parent_chunk_id, chunk_index, metadata "
            "FROM document_chunks WHERE chunk_id = ANY($1::uuid[]) ORDER BY chunk_index",
            chunk_ids,
        )
        points = (
            await client.retrieve(collection_name=QDRANT_COLLECTION, ids=chunk_ids, with_vectors=True)
        )
        return result, rows, points

    try:
        result, rows, points = asyncio.run(_run())

        assert isinstance(result, IngestResult)
        assert result.status == "READY"
        assert result.failed_stage is None
        assert result.chunk_count == 2
        assert result.chunk_count == result.indexed_vector_count

        assert len(rows) == 2
        for row in rows:
            assert row["document_id"] == DEMO_DOCUMENT_ID
            assert row["section"] == "Section A"
            assert row["chunk_index"] in (0, 1)
            # metadata is a D-02 column and must be populated (JSON, not NULL)
            assert row["metadata"] is not None

        assert len(points) == 2
        for point in points:
            assert len(point.vector) == EMBEDDING_DIMENSIONS
    finally:
        asyncio.run(_cleanup_chunks(chunk_ids))


def test_integration_index_document_degraded_embedding_writes_nothing(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    chunk = Chunk(
        chunk_id="33333333-3333-3333-3333-333333333333",
        content="This embedding call has no key configured.",
        section=None,
        page=None,
        chunk_index=0,
        parent_chunk_id=None,
        metadata={"chunker": "word-bounded", "chunk_words": CHUNK_WORDS},
    )

    async def _run():
        pool = await get_pool()
        client = await get_qdrant_client()
        result = await index_document(pool, client, DEMO_DOCUMENT_ID, DEMO_SYSTEM, [chunk])
        row = await pool.fetchrow(
            "SELECT chunk_id FROM document_chunks WHERE chunk_id = $1::uuid", chunk.chunk_id
        )
        return result, row

    try:
        result, row = asyncio.run(_run())
        assert result == IngestResult(
            chunk_count=0, indexed_vector_count=0, status="FAILED", failed_stage="indexing"
        )
        assert row is None  # nothing written to Postgres
    finally:
        asyncio.run(_cleanup_chunks([chunk.chunk_id]))


def test_integration_index_document_empty_chunks_returns_ready_noop():
    async def _run():
        pool = await get_pool()
        client = await get_qdrant_client()
        return await index_document(pool, client, DEMO_DOCUMENT_ID, DEMO_SYSTEM, [])

    result = asyncio.run(_run())
    assert result == IngestResult(chunk_count=0, indexed_vector_count=0, status="READY", failed_stage=None)


def test_integration_ensure_collection_is_idempotent():
    async def _run():
        client = await get_qdrant_client()
        assert client is not None
        from app.retrieval.qdrant_store import ensure_collection

        first = await ensure_collection(client)
        second = await ensure_collection(client)
        info = await client.get_collection(QDRANT_COLLECTION)
        return first, second, info

    first, second, info = asyncio.run(_run())
    assert first is True
    assert second is True
    assert info.config.params.vectors.size == 768
    assert str(info.config.params.vectors.distance).lower().endswith("cosine")
