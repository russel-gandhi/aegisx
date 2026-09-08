"""
Tests for `app.retrieval.embeddings`' concurrency-gate isolation.

Source: observed live 2026-09-08 -- back-to-back
`POST /api/copilot/investigate` calls returned INSUFFICIENT_EVIDENCE with
zero retrieved items while Postgres, Qdrant and Ollama were all healthy
and the corpus was fully indexed. The cause was queueing, not retrieval:
embeddings shared the LLM router's 6-slot `acquire_slot("ollama")` gate,
so one request's parallel A1..A6 generation calls held every slot past
`OLLAMA_MAX_WAIT_SECONDS` and the next request's embedding call raised
`GateBusyError`.

Both workloads still hit the same local server; they are separated
because `nomic-embed-text` answers in ~0.02s warm while
`qwen2.5:7b-instruct` holds a slot for tens of seconds.
"""

# ---------------------------------------------------------------------------
# Embedding concurrency gate isolation (2026-09-08)
# ---------------------------------------------------------------------------


def test_embeddings_use_their_own_gate_key_not_the_llm_routers():
    """Regression guard. Embeddings and generation both hit the same local
    Ollama server, but sharing one 6-slot gate let a single investigate
    request's parallel A1..A6 generation calls hold every slot long enough
    that the next request's embedding call raised `GateBusyError` -- which
    surfaced to the user as INSUFFICIENT_EVIDENCE with zero retrieved
    items, i.e. a total retrieval failure caused purely by queueing."""
    from app.retrieval.embeddings import OLLAMA_EMBED_GATE_KEY

    assert OLLAMA_EMBED_GATE_KEY != "ollama"


def test_embedding_call_sites_do_not_reference_the_shared_ollama_gate():
    """Asserted against the source rather than behaviour: the failure mode
    is a starved queue under real concurrency, which a unit test cannot
    reproduce cheaply, but a call site reverting to `acquire_slot("ollama")`
    is exactly what would reintroduce it."""
    import inspect

    from app.retrieval import embeddings

    source = inspect.getsource(embeddings)
    assert 'acquire_slot("ollama")' not in source
    assert "acquire_slot(OLLAMA_EMBED_GATE_KEY)" in source
