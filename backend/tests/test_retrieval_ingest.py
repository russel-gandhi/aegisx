"""
Tests for `app.retrieval.ingest` (Phase 06.1, plans 06.1-01/06.1-04).

Covers every `<behavior>` bullet in 06.1-01-PLAN.md Task 1 for
`parse_text`/`chunk_blocks` (pure unit tests, no I/O) and
`index_document`'s write/rollback behaviour against live Postgres and live
Qdrant, following `test_evidence_graph.py`'s established
asyncpg-fixture/live-state conventions (never mocked for the integration
section) and `test_llm_router.py`'s respx convention for the embedding
call itself. Also covers every `<behavior>` bullet in 06.1-04-PLAN.md
Task 1 (`parse_pdf`/`parse_docx`) and Task 2 (`parse_csv`/`detect_format`/
`parse_document`).

Structured in the same UNIT / INTEGRATION comment-section convention
`test_evidence_graph.py` and `test_c1_verifier.py` establish.
"""

import asyncio
import os
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
    CSV_ROWS_PER_BLOCK,
    MAX_CHUNKS_PER_DOCUMENT,
    MAX_CSV_ROWS,
    MAX_PDF_PAGES,
    SUPPORTED_FORMATS,
    Chunk,
    IngestResult,
    ParsedBlock,
    chunk_blocks,
    detect_format,
    index_document,
    parse_csv,
    parse_docx,
    parse_pdf,
    parse_text,
)
from app.retrieval.qdrant_store import QDRANT_COLLECTION, QDRANT_URL, get_qdrant_client
from tests.fixtures.documents.make_fixtures import build_minimal_pdf

DEMO_SYSTEM = "GXP-MFG-DEMO-01"
QDRANT_URL_FOR_TESTS = QDRANT_URL  # pass-through target for the respx routes below
DEMO_DOCUMENT_ID = "DOC-2026-OM-99"  # seeded row, infra/postgres/seed/001_seed.sql

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "documents")
SOP_PDF_PATH = os.path.join(FIXTURES_DIR, "sop_extract.pdf")
VALIDATION_DOCX_PATH = os.path.join(FIXTURES_DIR, "validation_protocol.docx")
TRACEABILITY_CSV_PATH = os.path.join(FIXTURES_DIR, "traceability_matrix.csv")

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
    # 2026-09-01: Ollama's /api/embed shape (raw vectors, not Gemini's
    # {"values": [...]} objects) -- see embeddings.py's own
    # EMBEDDING_PROVIDER_CONFIG comment for why Gemini was replaced.
    return {
        "model": "nomic-embed-text",
        "embeddings": [
            [((i + j + 1) % 23) / 7.0 - 1.5 for i in range(dimensions)]
            for j in range(count)
        ],
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
# UNIT -- parse_pdf / parse_docx (06.1-04-PLAN.md Task 1, no DB/network I/O)
# ---------------------------------------------------------------------------


def test_unit_parse_pdf_returns_real_1indexed_page_numbers():
    raw = open(SOP_PDF_PATH, "rb").read()
    blocks = parse_pdf(raw, "sop_extract.pdf")
    assert sorted({b.page for b in blocks}) == [1, 2, 3]


def test_unit_parse_pdf_sets_section_from_heading_heuristic():
    raw = open(SOP_PDF_PATH, "rb").read()
    blocks = parse_pdf(raw, "sop_extract.pdf")
    sections = {b.section for b in blocks}
    assert "Standard Operating Procedure" in sections
    assert "Equipment Calibration Requirements" in sections
    assert "Record Retention Policy" in sections


def test_unit_parse_pdf_no_heading_line_yields_section_none():
    # Every line ends with "." (body-shaped, per _is_pdf_heading_line's
    # own heuristic) -- no line on this page is heading-shaped, so the
    # resulting block's section must be None rather than a guessed value.
    raw = build_minimal_pdf(
        [["A body sentence with no heading anywhere on this page at all."]]
    )
    blocks = parse_pdf(raw, "no_heading.pdf")
    assert len(blocks) == 1
    assert blocks[0].section is None
    assert blocks[0].page == 1


def test_unit_parse_pdf_unparseable_bytes_returns_empty_list_no_exception():
    assert parse_pdf(b"not a pdf at all", "garbage.pdf") == []


def test_unit_parse_pdf_stops_at_max_pdf_pages(monkeypatch, caplog):
    import app.retrieval.ingest as ingest_module

    monkeypatch.setattr(ingest_module, "MAX_PDF_PAGES", 2)
    raw = open(SOP_PDF_PATH, "rb").read()  # 3-page fixture, cap forced to 2
    with caplog.at_level("WARNING"):
        blocks = parse_pdf(raw, "sop_extract.pdf")
    assert sorted({b.page for b in blocks}) == [1, 2]
    assert any("truncating" in record.message for record in caplog.records)


def test_unit_chunk_blocks_preserves_page_for_pdf_chunks():
    raw = open(SOP_PDF_PATH, "rb").read()
    blocks = parse_pdf(raw, "sop_extract.pdf")
    chunks = chunk_blocks(blocks)
    assert sorted({c.page for c in chunks}) == [1, 2, 3]


def test_unit_parse_docx_sets_section_from_heading_paragraphs_page_none():
    raw = open(VALIDATION_DOCX_PATH, "rb").read()
    blocks = parse_docx(raw, "validation_protocol.docx")
    sections = {b.section for b in blocks if b.section}
    assert "Installation Qualification" in sections
    assert "Operational Qualification" in sections
    assert all(b.page is None for b in blocks)


def test_unit_parse_docx_includes_table_cells_under_preceding_section():
    raw = open(VALIDATION_DOCX_PATH, "rb").read()
    blocks = parse_docx(raw, "validation_protocol.docx")
    table_block = next(b for b in blocks if "Power-on self-test" in b.text)
    assert table_block.section == "Operational Qualification"
    assert "Test Step | Expected Result | Actual Result" in table_block.text


def test_unit_parse_docx_tables_use_their_own_preceding_heading_not_the_last_one():
    # Regression: `document.paragraphs` and `document.tables` are two
    # separate, non-interleaved python-docx collections. Iterating them
    # one after the other -- rather than walking `document.element.body`
    # in true source order -- silently attaches EVERY table in the
    # document to whichever heading is LAST in the file, regardless of
    # which heading actually precedes that specific table. This fixture
    # has two headings each immediately followed by their own table, so a
    # regression to the old two-pass approach would report both tables
    # under "Operational Qualification" (the last heading) instead of the
    # first table correctly landing on "Installation Qualification".
    raw = open(os.path.join(FIXTURES_DIR, "interleaved_headings_tables.docx"), "rb").read()
    blocks = parse_docx(raw, "interleaved_headings_tables.docx")

    iq_table = next(b for b in blocks if "Power-on self-test" in b.text)
    oq_table = next(b for b in blocks if "Load calibration weight" in b.text)
    assert iq_table.section == "Installation Qualification"
    assert oq_table.section == "Operational Qualification"


def test_unit_parse_docx_corrupt_payload_returns_empty_list_no_exception():
    assert parse_docx(b"not a docx at all", "garbage.docx") == []


def test_unit_parsers_never_write_a_temp_file():
    import inspect

    import app.retrieval.ingest as ingest_module

    source = inspect.getsource(ingest_module)
    assert "tempfile" not in source
    assert "NamedTemporaryFile" not in source


# ---------------------------------------------------------------------------
# UNIT -- parse_csv / detect_format (06.1-04-PLAN.md Task 2, no DB/network I/O)
# ---------------------------------------------------------------------------


def test_unit_parse_csv_60_rows_yields_25_row_blocks_with_header_repeated():
    raw = open(TRACEABILITY_CSV_PATH, "rb").read()
    blocks = parse_csv(raw, "traceability_matrix.csv")

    assert len(blocks) == 3  # 60 rows / 25-per-block -> 25, 25, 10
    header_line = "urs_id | requirement | test_case_id | execution_status"
    for block in blocks:
        assert block.text.startswith(header_line)


def test_unit_parse_csv_section_is_filename_stem_page_is_block_number():
    raw = open(TRACEABILITY_CSV_PATH, "rb").read()
    blocks = parse_csv(raw, "traceability_matrix.csv")

    assert all(b.section == "traceability_matrix" for b in blocks)
    assert [b.page for b in blocks] == [1, 2, 3]


def test_unit_parse_csv_rows_rendered_as_col_value_pairs_not_raw_csv():
    raw = b"urs_id,requirement\nURS-001,First requirement text\n"
    blocks = parse_csv(raw, "small.csv")

    assert len(blocks) == 1
    # "col: value" pairs joined by "; " -- never a raw comma-separated line.
    assert "urs_id: URS-001; requirement: First requirement text" in blocks[0].text
    assert "URS-001,First requirement text" not in blocks[0].text


def test_unit_parse_csv_stops_at_max_csv_rows_and_logs(monkeypatch, caplog):
    import app.retrieval.ingest as ingest_module

    monkeypatch.setattr(ingest_module, "MAX_CSV_ROWS", 10)
    header = "urs_id,requirement\n"
    body = "".join(f"URS-{i:03d},req {i}\n" for i in range(20))
    raw = (header + body).encode("utf-8")

    with caplog.at_level("WARNING"):
        blocks = parse_csv(raw, "big.csv")

    total_rows = sum(len(b.text.split("\n")) - 1 for b in blocks)  # minus header line
    assert total_rows == 10
    assert any("truncating" in record.message for record in caplog.records)


def test_unit_parse_csv_no_rows_returns_empty_list():
    raw = b"urs_id,requirement\n"  # header only, zero data rows
    assert parse_csv(raw, "empty.csv") == []


def test_unit_detect_format_pdf_docx_csv_text_and_magic_byte_mismatches():
    assert detect_format(b"%PDF-1.7 rest-of-file", "a.pdf") == "pdf"
    assert detect_format(b"hello, not a pdf", "a.pdf") is None
    assert detect_format(b"PK\x03\x04rest", "a.docx") == "docx"
    assert detect_format(b"%PDF-1.7 rest-of-file", "a.docx") is None  # PDF bytes, .docx claim
    assert detect_format(b"a,b\n1,2\n", "a.csv") == "csv"
    assert detect_format(b"# Heading\n\nbody text", "a.md") == "text"
    assert detect_format(b"x", "a.exe") is None


def test_unit_detect_format_unknown_extension_returns_none_even_for_valid_text():
    assert detect_format(b"perfectly valid utf-8 text", "a.docx.bak") is None


def test_unit_supported_formats_frozen_allowlist():
    assert sorted(SUPPORTED_FORMATS) == ["csv", "docx", "pdf", "text"]
    assert MAX_CSV_ROWS == 5000
    assert CSV_ROWS_PER_BLOCK == 25


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
            respx.post("http://127.0.0.1:11434/api/embed").mock(
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
    """Ollama needs no key -- mocked unreachable instead of relying on a
    missing credential, the realistic degrade scenario for a local
    provider."""
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
        with respx.mock:
            respx.route(url__startswith=QDRANT_URL_FOR_TESTS).pass_through()
            respx.post("http://127.0.0.1:11434/api/embed").mock(
                side_effect=httpx.ConnectError("connection refused")
            )
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
