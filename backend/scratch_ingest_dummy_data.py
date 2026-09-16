"""One-off script: ingest the full Dummy_data corpus into GXP-MFG-DEMO-01
through the real POST /api/documents/upload route (real Ollama embeddings,
real Postgres, real Qdrant -- no mocking). Not part of the app or test
suite; run and discard."""

import os
import sys
import time

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(__file__))

from app.main import app  # noqa: E402

DUMMY_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Dummy_data")
SYSTEM_ID = "GXP-MFG-DEMO-01"
IDENTITY_HEADERS = {"X-User-Id": "dummy-corpus-ingest", "X-User-Role": "IT System Manager"}
DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def main() -> None:
    client = TestClient(app)
    files = sorted(f for f in os.listdir(DUMMY_DATA_DIR) if f.lower().endswith(".docx"))
    print(f"Found {len(files)} files in {DUMMY_DATA_DIR}")

    results = []
    for name in files:
        path = os.path.join(DUMMY_DATA_DIR, name)
        with open(path, "rb") as handle:
            content = handle.read()
        start = time.monotonic()
        try:
            resp = client.post(
                "/api/documents/upload",
                files={"file": (name, content, DOCX_CONTENT_TYPE)},
                data={"system_id": SYSTEM_ID, "doc_type": "UPLOADED"},
                headers=IDENTITY_HEADERS,
                timeout=300,
            )
            elapsed = time.monotonic() - start
            if resp.status_code == 200:
                body = resp.json()
                print(f"OK   {elapsed:6.1f}s  {name}  status={body.get('status')} chunks={body.get('chunk_count')}")
                results.append((name, "OK", body.get("status"), body.get("chunk_count")))
            else:
                print(f"FAIL {elapsed:6.1f}s  {name}  http={resp.status_code}  {resp.text[:300]}")
                results.append((name, f"HTTP_{resp.status_code}", None, None))
        except Exception as exc:  # noqa: BLE001
            elapsed = time.monotonic() - start
            print(f"ERR  {elapsed:6.1f}s  {name}  {type(exc).__name__}: {exc}")
            results.append((name, f"EXC_{type(exc).__name__}", None, None))

    ok = sum(1 for r in results if r[1] == "OK")
    print(f"\n{ok}/{len(results)} ingested successfully")
    failures = [r for r in results if r[1] != "OK"]
    if failures:
        print("Failures:")
        for r in failures:
            print(" -", r)


if __name__ == "__main__":
    main()
