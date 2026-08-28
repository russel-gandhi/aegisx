"""
Document parsing, chunking, and indexing pipeline (Phase 06.1, plan
06.1-01, RAG-01/RAG-02, D-01/D-04).

Ticket: n/a (roadmap phase 06.1) | Requirements: RAG-01, RAG-02
Source: AegisX-AI-Project-Bible-v6.md Section 9.1 (`chunk_text` sample);
Bible Section 15's hybrid-retrieval spec.

Mirrors `app.graph.evidence_graph`'s `build_graph`/`persist_graph`
two-phase shape: compute in pure Python first (`parse_text`,
`chunk_blocks` -- no I/O, no DB, no network), then one write phase
(`index_document`) that embeds and persists. Every SQL statement here uses
asyncpg `$N`-style placeholders exclusively -- `content`/`section` and
every other upload-derived value cross a trust boundary at
`routes/documents.py` (Security Domain V5, SQL injection).

Deviation 16: Bible Section 9.1's `chunk_text()` sample slices Python
string characters despite its own "Token-based chunking logic here"
comment (06.1-RESEARCH.md Pitfall 5) -- the sample's actual body is
`text[i:i + chunk_size]` over `range(0, len(text), chunk_size - overlap)`,
which is character-index chunking, not token-based chunking. This module
chunks on word boundaries deliberately, with no tokenizer dependency.

Plumbing note: `chunk_blocks()`'s frozen signature (`blocks -> List[Chunk]`)
does not receive the original upload filename, so each `Chunk.metadata`
carries only `{"chunker": "word-bounded", "chunk_words": CHUNK_WORDS}` at
this layer. `routes/documents.py` (plan 06.1-01 Task 2), which does have
the client filename, sets `metadata["source_filename"]` on each chunk
before calling `index_document()`.
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.retrieval.embeddings import call_embeddings_batch
from app.retrieval.qdrant_store import upsert_chunks

logger = logging.getLogger(__name__)

INGESTION_STAGES: Tuple[str, ...] = (
    "uploading",
    "parsing",
    "structure",
    "chunking",
    "indexing",
    "ready",
)

CHUNK_WORDS: int = 350
CHUNK_OVERLAP_WORDS: int = 50
MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024
MAX_CHUNKS_PER_DOCUMENT: int = 500
SUPPORTED_TEXT_EXTENSIONS = frozenset({".txt", ".md", ".markdown"})

_HEADING_RE_PREFIX = "#"


@dataclass
class ParsedBlock:
    text: str
    section: Optional[str]
    page: Optional[int]


@dataclass
class Chunk:
    chunk_id: str
    content: str
    section: Optional[str]
    page: Optional[int]
    chunk_index: int
    parent_chunk_id: Optional[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IngestResult:
    chunk_count: int
    indexed_vector_count: int
    status: str
    failed_stage: Optional[str] = None


def _match_heading(line: str) -> Optional[str]:
    """Return the heading text for a Markdown ATX heading line
    (`^#{1,6}\\s+(.*)$`), or `None` if `line` is not a heading."""
    stripped = line.lstrip()
    hashes = len(stripped) - len(stripped.lstrip(_HEADING_RE_PREFIX))
    if hashes < 1 or hashes > 6:
        return None
    rest = stripped[hashes:]
    if not rest[:1].isspace():
        return None
    return rest.strip()


def parse_text(raw: bytes, filename: str) -> List[ParsedBlock]:
    """Decode `raw` as UTF-8 (`errors="replace"` -- an upload must never
    crash the parser on an invalid byte sequence) and split on Markdown
    ATX headings (`#`..`######`) to assign each block's `section`. Plain
    `.txt` content with no headings falls through to a single block with
    `section=None`. `page` is always `None` for text/Markdown input --
    only the binary formats plan 06.1-04 adds carry real page numbers.
    """
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()

    blocks: List[ParsedBlock] = []
    current_section: Optional[str] = None
    current_lines: List[str] = []

    def _flush() -> None:
        content = "\n".join(current_lines).strip()
        if content:
            blocks.append(ParsedBlock(text=content, section=current_section, page=None))

    for line in lines:
        heading = _match_heading(line)
        if heading is not None:
            _flush()
            current_lines = []
            current_section = heading
        else:
            current_lines.append(line)
    _flush()

    return blocks


def chunk_blocks(blocks: List[ParsedBlock]) -> List[Chunk]:
    """Word-bounded chunking (Deviation 16): `CHUNK_WORDS`-sized windows
    with `CHUNK_OVERLAP_WORDS` of overlap between consecutive chunks
    within the same block. `chunk_index` is a single document-global
    monotonic counter (not reset per block/section). `parent_chunk_id` is
    `None` for the first chunk produced from a given block (its section's
    leader) and that leader's `chunk_id` for every later chunk from the
    same block. Stops entirely at `MAX_CHUNKS_PER_DOCUMENT` -- a
    pathologically large upload is truncated, not rejected outright
    (rejection-by-size is `MAX_UPLOAD_BYTES`'s job, enforced by the route
    before parsing ever runs). Never returns an empty-content chunk.
    """
    chunks: List[Chunk] = []
    chunk_index = 0

    for block in blocks:
        words = block.text.split()
        if not words:
            continue

        section_leader_id: Optional[str] = None
        start = 0
        while start < len(words):
            if len(chunks) >= MAX_CHUNKS_PER_DOCUMENT:
                return chunks

            end = min(start + CHUNK_WORDS, len(words))
            content = " ".join(words[start:end])
            new_chunk_id = str(uuid.uuid4())
            parent_id = section_leader_id  # None for the section's first chunk

            chunks.append(
                Chunk(
                    chunk_id=new_chunk_id,
                    content=content,
                    section=block.section,
                    page=block.page,
                    chunk_index=chunk_index,
                    parent_chunk_id=parent_id,
                    metadata={"chunker": "word-bounded", "chunk_words": CHUNK_WORDS},
                )
            )
            if section_leader_id is None:
                section_leader_id = new_chunk_id
            chunk_index += 1

            if end == len(words):
                break
            start = end - CHUNK_OVERLAP_WORDS

    return chunks


async def index_document(
    pool: Any,
    qdrant_client: Any,
    document_id: str,
    system_id: str,
    chunks: List[Chunk],
) -> IngestResult:
    """Embed every chunk's content (one `call_embeddings_batch()` call,
    `task_type="RETRIEVAL_DOCUMENT"`), then write Postgres and Qdrant
    together inside a single Postgres transaction: if the Qdrant upsert
    raises, the `document_chunks` INSERTs already issued in this same
    transaction roll back with it, so a Qdrant failure never leaves an
    orphaned Postgres row with no matching vector.

    If ANY embedding response is degraded, writes nothing to either store
    and returns `IngestResult(status="FAILED", failed_stage="indexing")` --
    an honest failure envelope (D-09 discipline), never a zero-vector
    index and never a fabricated success.
    """
    if not chunks:
        return IngestResult(chunk_count=0, indexed_vector_count=0, status="READY", failed_stage=None)

    embeddings = await call_embeddings_batch(
        [chunk.content for chunk in chunks], task_type="RETRIEVAL_DOCUMENT"
    )

    if any(embedding.degraded for embedding in embeddings):
        logger.warning(
            "index_document: embedding provider degraded for document_id=%s "
            "(%d chunk(s)); writing nothing to Postgres or Qdrant.",
            document_id,
            len(chunks),
        )
        return IngestResult(chunk_count=0, indexed_vector_count=0, status="FAILED", failed_stage="indexing")

    async with pool.acquire() as conn:
        async with conn.transaction():
            for chunk, embedding in zip(chunks, embeddings):
                await conn.execute(
                    "INSERT INTO document_chunks "
                    "(chunk_id, document_id, content, embedding_id, section, page, "
                    "parent_chunk_id, chunk_index, metadata) "
                    "VALUES ($1::uuid, $2, $3, $4, $5, $6, $7::uuid, $8, $9::jsonb)",
                    chunk.chunk_id,
                    document_id,
                    chunk.content,
                    chunk.chunk_id,
                    chunk.section,
                    chunk.page,
                    chunk.parent_chunk_id,
                    chunk.chunk_index,
                    json.dumps(chunk.metadata),
                )

            points = [
                {
                    "chunk_id": chunk.chunk_id,
                    "document_id": document_id,
                    "system_id": system_id,
                    "vector": embedding.vector,
                    "section": chunk.section,
                    "page": chunk.page,
                    "chunk_index": chunk.chunk_index,
                }
                for chunk, embedding in zip(chunks, embeddings)
            ]
            indexed_count = await upsert_chunks(qdrant_client, points)

    return IngestResult(
        chunk_count=len(chunks),
        indexed_vector_count=indexed_count,
        status="READY",
        failed_stage=None,
    )
