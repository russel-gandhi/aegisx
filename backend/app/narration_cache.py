"""
Content-addressed in-process memo cache for `app.agents.a2_compliance`'s
`narrate_gap()` LLM call (quick task 260826-0b5).

## Why this exists

`GET /api/systems/{system_id}/assurance-cards` re-narrates every failing
compliance check through the LLM on every single request, and
`generate-capa` re-derives findings server-side by narrating every failing
check until one matches the requested `finding_id`. A live testing session
burned 811 Gemini requests for what amounted to 2-3 distinct findings'
worth of text. This module memoizes the narration step itself so a
byte-identical prompt costs one outbound request, not one per read.

## Why the key is a digest of the finished prompt

`narrate_gap()` builds its prompt from the check name, its description,
`record_id`, `rule_id`, and the whole `record!r`. Hashing the finished
prompt string puts every one of those fields inside the key by
construction — an edited record produces a different prompt, a different
key, and a miss. There is no TTL and no invalidation routine to keep in
sync with the prompt template, because staleness is structurally
impossible rather than merely unlikely. If a later plan adds a field to
the prompt, the key tracks it automatically. This is why this module has
no `invalidate()` function: there is nothing to invalidate.

## Why not the graph tables' rebuild/read split

`app/routes/evidence_graph.py`'s rebuild/read split exists (D-02) because
`graph_nodes`/`graph_edges` are *snapshot* caches: they hold a copy of
domain state that genuinely can drift, so a human-triggered rebuild
endpoint is the invalidation mechanism. Narration is content-addressed —
the key *is* the input — so there is nothing to invalidate and a rebuild
endpoint would be a control with no job. A Postgres table would also
require a schema change, and the schema is closed (CLAUDE.md Rule 7).

## What is never stored

A degraded router response (no provider key, or a router failure) is
never stored here — the caller must not call `put()` for a degraded
result. Caching a degraded response would latch a provider outage into
this cache for the lifetime of the process: the endpoint would keep
serving fallback text long after the provider recovered. This module has
no way to enforce that from the inside (it only ever sees `(text,
model_id)` pairs, never a `degraded` flag) — the discipline lives in the
caller, `narrate_gap()`.

This module also structurally cannot hold a compliance verdict: it
imports nothing from `app.*` (enforced by a grep gate in this plan's
Task 1 verification), so it has no access to `verify_finding`, OPA, or
any `passed` boolean. It stores exactly one thing: a narration sentence
paired with the model id that authored it.

## Why no in-flight de-duplication

Two concurrent requests for the same cold key can both call the provider.
Fixing that needs a module-level `asyncio.Lock`, and a module-level
asyncio primitive is bound to the event loop that created it — the exact
failure mode `tests/conftest.py` documents at length for asyncpg pools
under this suite's `asyncio.run()`-per-test convention. Sequential
repeats are the dominant cost here (the same user reloading the same
page), so this is accepted deliberately, not overlooked.

## Bounding

Bounded at `_MAX_ENTRIES` with least-recently-used eviction. The demo
corpus produces findings in the low tens, so the bound exists to make
unbounded growth structurally impossible rather than to actively manage
memory in practice.
"""

import hashlib
import logging
from collections import OrderedDict
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

_MAX_ENTRIES = 256

# key -> (text, model_id). Insertion order doubles as recency order: `get()`
# moves a hit to the end, `put()` appends and evicts from the front.
_cache: "OrderedDict[str, Tuple[str, str]]" = OrderedDict()


def cache_key(prompt: str) -> str:
    """Return a hex digest of `prompt`, encoded utf-8.

    The prompt is the entire input this module keys on — see the module
    docstring for why that makes a separate invalidation routine
    unnecessary.
    """
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def get(key: str) -> Optional[Tuple[str, str]]:
    """Return the stored `(text, model_id)` pair for `key`, or `None` on a
    miss. A hit marks the entry as most-recently-used."""
    if key not in _cache:
        return None
    _cache.move_to_end(key)
    return _cache[key]


def put(key: str, value: Tuple[str, str]) -> None:
    """Store `(text, model_id)` under `key`, then evict the
    least-recently-used entry while the map exceeds `_MAX_ENTRIES`.

    Callers must never pass a degraded router result here — see the
    module docstring's "What is never stored" section.
    """
    _cache[key] = value
    _cache.move_to_end(key)
    while len(_cache) > _MAX_ENTRIES:
        evicted_key, _ = _cache.popitem(last=False)
        logger.debug("narration_cache: evicted LRU entry %s", evicted_key)


def clear() -> None:
    """Empty the cache. Used by test isolation and by nothing else."""
    _cache.clear()


def size() -> int:
    """Return the number of entries currently cached."""
    return len(_cache)
