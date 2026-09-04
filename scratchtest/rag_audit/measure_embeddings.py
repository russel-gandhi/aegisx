"""
Real-document embedding instrumentation script (dispatch Part 2/6).

Loads the repo root .env (real GEMINI_API_KEY), parses a real DOCX from
Dummy_data/, chunks it with the production chunker, and calls the
production `call_embeddings_batch` / `call_embedding` functions directly
-- no mocking -- while patching httpx.AsyncClient.post to log every real
HTTP request/response (timestamp, batch size, attempt, status, latency,
retry-after) without altering behavior.

Run from backend/ with: ..\.venv\Scripts\python ..\scratchtest\rag_audit\measure_embeddings.py <docx_path> [repeat_count]
"""
import asyncio
import os
import sys
import time
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

# Load real .env from repo root (not backend/) before importing app modules.
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import httpx
from app.retrieval.ingest import parse_document, detect_format, chunk_blocks
from app.retrieval import embeddings as emb_mod

LOG = []

_orig_post = httpx.AsyncClient.post

async def _instrumented_post(self, url, *args, **kwargs):
    t0 = time.monotonic()
    is_batch = "batchEmbedContents" in url
    body = kwargs.get("json", {})
    n = len(body.get("requests", [])) if is_batch else 1
    resp = await _orig_post(self, url, *args, **kwargs)
    latency = time.monotonic() - t0
    LOG.append({
        "ts": time.time(),
        "type": "batch" if is_batch else "individual",
        "n_texts": n,
        "status": resp.status_code,
        "latency_s": round(latency, 3),
        "retry_after": resp.headers.get("retry-after"),
    })
    return resp

httpx.AsyncClient.post = _instrumented_post


async def main():
    docx_path = sys.argv[1] if len(sys.argv) > 1 else None
    repeat = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    if not docx_path:
        print("usage: measure_embeddings.py <docx_path> [repeat_count]")
        return

    raw = Path(docx_path).read_bytes()
    filename = Path(docx_path).name
    fmt = detect_format(raw, filename)
    print(f"detected format: {fmt}")
    blocks = parse_document(raw, filename, fmt)
    print(f"parsed blocks: {len(blocks)}")
    chunks = chunk_blocks(blocks)
    print(f"chunks: {len(chunks)}")

    texts = [c.content for c in chunks] * repeat
    print(f"total texts to embed (repeat={repeat}): {len(texts)}")

    key_present = bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))
    print(f"GEMINI_API_KEY/GOOGLE_API_KEY present: {key_present}")
    if not key_present:
        print("NO LIVE KEY -- aborting live measurement.")
        return

    t0 = time.monotonic()
    results = await emb_mod.call_embeddings_batch(texts, task_type="RETRIEVAL_DOCUMENT")
    total_time = time.monotonic() - t0

    n_success = sum(1 for r in results if not r.degraded)
    n_failed = sum(1 for r in results if r.degraded)
    failure_reasons = {}
    for r in results:
        if r.degraded:
            failure_reasons[r.failure_reason] = failure_reasons.get(r.failure_reason, 0) + 1

    n_batch_requests = sum(1 for e in LOG if e["type"] == "batch")
    n_individual_requests = sum(1 for e in LOG if e["type"] == "individual")
    n_429 = sum(1 for e in LOG if e["status"] == 429)
    n_other_fail = sum(1 for e in LOG if e["status"] not in (200, 429))

    summary = {
        "chunk_count": len(chunks),
        "texts_embedded": len(texts),
        "total_http_requests": len(LOG),
        "batch_requests": n_batch_requests,
        "individual_requests": n_individual_requests,
        "requests_429": n_429,
        "requests_other_failure": n_other_fail,
        "successful_embeddings": n_success,
        "failed_embeddings": n_failed,
        "failure_reasons": failure_reasons,
        "total_wall_time_s": round(total_time, 2),
    }
    print(json.dumps(summary, indent=2))

    out_path = Path(__file__).parent / f"log_{Path(docx_path).stem}_{repeat}x.json"
    out_path.write_text(json.dumps({"summary": summary, "requests": LOG}, indent=2))
    print(f"full request log written to {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
