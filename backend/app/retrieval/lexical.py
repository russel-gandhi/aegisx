"""
BM25 lexical retrieval (Phase 06.1, plan 06.1-03, RAG-03).

Ticket: n/a (roadmap phase 06.1) | Requirements: RAG-03
Source: 06.1-03-PLAN.md Task 1 <action>; AegisX-AI-Project-Bible-v6.md
Section 15.2/15.3 ("BM25 -> 20 candidates" alongside "Vector Search -> 20
candidates").

Dense-only retrieval (plan 06.1-02) misses exact identifier matches -- a
GxP corpus is full of `URS-042`, `ANNEX11-S4-DOC-001`, `TC-2026-042`
tokens that lexical search finds reliably and embeddings blur. This
module is the second candidate leg `app.retrieval.hybrid_search` fuses
with Reciprocal Rank Fusion.

Uses `rank_bm25.BM25Okapi` (Don't Hand-Roll: 06.1-RESEARCH.md's own
table -- BM25's IDF/length-normalization math is easy to get subtly
wrong), not a hand-rolled scorer.

The corpus is rebuilt fresh on every call to `bm25_search` (via
`build_corpus`) rather than cached -- correct and fast enough at demo
corpus size, and explicitly preferable to a cached index that could
silently serve stale results for a document that was just re-ingested
(this project's post-upload graph rebuild, 06.1-04, makes the same
freshness tradeoff for the evidence graph).

Deterministic-first boundary (D-08, CLAUDE.md): this module makes zero
model/`call_llm`/`call_embedding` calls. `tokenize`/`build_corpus`/
`bm25_search` are pure computation and Postgres reads.
"""

import logging
import re
from typing import Dict, List, Optional, Tuple

from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)

# Bible Section 15.2/15.3 sizing ("BM25 -> 20 candidates"), matching
# `hybrid_search.DENSE_CANDIDATE_LIMIT`'s own depth before fusion.
BM25_CANDIDATE_LIMIT: int = 20

# Caps how many chunks are pulled into the in-memory BM25 index per query
# (T-06.1-17, Denial of Service via an unbounded corpus build) -- bound at
# the database via a `LIMIT` clause, not merely truncated after fetch.
BM25_CORPUS_MAX_CHUNKS: int = 5000

# `URS-042` must survive as one token rather than splitting into `urs` and
# `042` -- a GxP identifier is a single searchable term. Matches one or
# more lowercase-alphanumeric runs, optionally hyphen-joined to further
# such runs.
_TOKEN_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def tokenize(text: str) -> List[str]:
    """Lowercase, then split on non-alphanumeric boundaries while keeping
    hyphenated identifiers intact as one token."""
    return _TOKEN_RE.findall(text.lower())


async def build_corpus(pool, system_id: str) -> Tuple[List[str], Optional[BM25Okapi]]:
    """Fetch every chunk belonging to `system_id`'s documents (capped at
    `BM25_CORPUS_MAX_CHUNKS`, in stable `document_id`/`chunk_index` order)
    and build a `BM25Okapi` index over their tokenized `content`.

    Returns `(ids, None)` when the corpus is empty -- `BM25Okapi` raises
    on an empty corpus, so this guards construction rather than letting
    that exception escape to `bm25_search`'s caller.
    """
    rows = await pool.fetch(
        "SELECT c.chunk_id, c.content FROM document_chunks c JOIN documents d ON d.id = "
        "c.document_id WHERE d.system_id = $1 ORDER BY c.document_id, c.chunk_index LIMIT $2",
        system_id,
        BM25_CORPUS_MAX_CHUNKS,
    )
    if len(rows) >= BM25_CORPUS_MAX_CHUNKS:
        logger.warning(
            "BM25 corpus truncated at %d chunks (system_id=%s)", BM25_CORPUS_MAX_CHUNKS, system_id
        )

    ids = [str(row["chunk_id"]) for row in rows]
    if not ids:
        return ids, None

    tokenized_corpus = [tokenize(row["content"] or "") for row in rows]
    return ids, BM25Okapi(tokenized_corpus)


async def bm25_search(
    pool, query: str, system_id: str, limit: int = BM25_CANDIDATE_LIMIT
) -> List[Tuple[str, float]]:
    """Build `system_id`'s corpus and score `query` against it.

    Returns at most `limit` `(chunk_id, score)` pairs sorted by descending
    score, dropping non-positive scores (BM25 assigns a term-overlap
    score of 0 to a document sharing no token with the query -- not a
    genuine, if weak, match). Never raises: an empty/missing corpus
    (`build_corpus` returning `(ids, None)`) returns `[]`.
    """
    ids, bm25 = await build_corpus(pool, system_id)
    if bm25 is None:
        return []

    raw_scores = bm25.get_scores(tokenize(query))
    pairs: List[Tuple[str, float]] = [
        (chunk_id, float(score)) for chunk_id, score in zip(ids, raw_scores) if score > 0
    ]
    pairs.sort(key=lambda pair: pair[1], reverse=True)
    return pairs[:limit]
