"""
FastAPI application entrypoint for AegisX AI.

Ticket: SENT-1-05 | Requirement: ENV-04
Source: AegisX-AI-Project-Bible-v6.md Section 12 (API table, lines
1404-1420) — only `GET /api/health` is in scope for this plan.

Only one route is registered here. Bible Section 12 lists ten further
endpoints (`/api/systems`, `/api/copilot/query`,
`/api/actions/{id}/approve`, `/api/audit/*`, `/api/reports/evidence-pack`,
`/api/opa/evaluate`, and others), but those belong to tickets in Stages 2
through 5. Pre-registering stub routes for them here would put this plan's
branch inside other tickets' contracts (CLAUDE.md Rule 7; BRANCHING.md §4
file-ownership allocation), so they are deliberately absent. The one
planned exception is plan 02-07, which attaches the
`/api/copilot/stream/{session_id}` WebSocket route to this same `app`
object in wave 2, sequentially after this plan merges.

This module imports nothing from `app.graph` or `app.opa_client` — those
do not exist until wave 2 — so it has no import-time database, OPA, or
network dependency and can be imported with every Compose service stopped.

Plan 02-07 registers exactly one further route here: the
`/api/copilot/stream/{session_id}` WebSocket router from `app.ws.copilot`.
See that module's docstring for the wire contract.

Plan 04-01 (GRAPH-01/GRAPH-03) registers a second router: the evidence
graph rebuild/read endpoints from `app.routes.evidence_graph`.

Plan 04-03 (EVID-03) registers a third router: the Assurance Card
endpoint from `app.routes.findings`.

Plan 05-01 registers a fourth router: the action/approval endpoints from
`app.routes.actions`.

Plan 05-03 registers a fifth router: the audit chain endpoints from
`app.routes.audit`.

Plan 06-01 registers a sixth router: the Copilot non-hero-query endpoint
from `app.routes.copilot_query` (D-04) -- gives `detect_injection()` its
first real HTTP caller.

Plan 06-02 registers a seventh router: the access/supplier overdue-signals
endpoint from `app.routes.system_signals` (D-07 mini-cards #5/#6).

Plan 06.1-01 registers an eighth router: the document ingestion endpoint
from `app.routes.documents` (RAG-01) -- `POST /api/documents/upload`.

REMEDIATION-PLAN.md #6 registers a ninth and tenth router: `GET
/api/systems` and `GET /api/systems/{id}/readiness` from
`app.routes.systems`, and `POST /api/opa/evaluate` (Bible lists this as
GET; see `app.routes.opa`'s own docstring for why that's a deliberate
deviation) from `app.routes.opa` -- closing two of the four remaining
gaps against the Bible's original ten-endpoint list this docstring's
opening paragraph names. `POST /api/reports/evidence-pack` remains
unbuilt: it requires WeasyPrint, which needs native GTK/Pango/Cairo
libraries this project has no provisioning path for yet (no backend
Dockerfile exists anywhere in this repo to install them into, and they
don't install via pip alone on Windows) -- implementing it without a way
to verify it actually runs would be shipping untested code, not a fix.

Quick task 260826-p1q (Task 3) adds a `lifespan` context manager: on
startup it schedules `app.prewarm.prewarm_narration_cache()` as a
background `asyncio.create_task` WITHOUT awaiting it, so the ASGI
`lifespan.startup.complete` message -- and therefore `/api/health` -- is
never delayed by a narration call. On shutdown it cancels that task and
awaits it with `CancelledError` suppressed, so neither a live `uvicorn
--reload` nor this test suite ever leaks it. This is also what keeps the
pre-warm inert under `pytest`: Starlette's `TestClient` only runs the ASGI
lifespan protocol when entered as `with client:`
(`starlette/testclient.py`), and `tests/conftest.py`'s session-scoped
`client` fixture is a bare `TestClient(app)`, never entered that way --
`load_dotenv()` (`app/llm_router.py`) can pick up a live provider key in
this environment, and an auto-firing pre-warm would make every `pytest`
invocation issue real, billed provider calls. Do not "fix" this by adding
`with client:` anywhere in the suite; see `app/prewarm.py`'s own docstring
and `tests/test_prewarm.py`.
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.http_client import aclose_shared_client
from app.prewarm import prewarm_narration_cache
from app.retrieval.qdrant_store import aclose_qdrant_client
from app.routes.actions import router as actions_router
from app.routes.audit import router as audit_router
from app.routes.copilot_query import router as copilot_query_router
from app.routes.documents import router as documents_router
from app.routes.evidence_graph import router as evidence_graph_router
from app.routes.findings import router as findings_router
from app.routes.opa import router as opa_router
from app.routes.system_signals import router as system_signals_router
from app.routes.systems import router as systems_router
from app.ws.copilot import router as copilot_ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Scheduled, not awaited: `yield` is reached (and the ASGI
    # startup-complete message sent) before any narration call resolves --
    # this is what structurally guarantees the pre-warm never delays
    # readiness. The reference is held on `app.state` so nothing garbage-
    # collects the task mid-flight.
    app.state.prewarm_task = asyncio.create_task(prewarm_narration_cache())
    yield
    app.state.prewarm_task.cancel()
    try:
        await app.state.prewarm_task
    except asyncio.CancelledError:
        pass
    # Closes the shared httpx.AsyncClient (SYSTEM-DESIGN-DIAGNOSIS.md #1)
    # and the cached Qdrant client (#2) so a live process doesn't leak
    # pooled connections on shutdown. Never entered under pytest, matching
    # the prewarm task above -- see this module's own docstring on why
    # TestClient(app) never runs the ASGI lifespan.
    await aclose_shared_client()
    await aclose_qdrant_client()


app = FastAPI(
    title="AegisX AI",
    description=(
        "Agentic AI co-pilot for audit-ready GxP IT system management. "
        "Deterministic evidence verification (C1) is the product's core "
        "thesis — see AegisX-AI-Project-Bible-v6.md Section 1."
    ),
    lifespan=lifespan,
)

# Local dev only: the Vite frontend (127.0.0.1:3000 / localhost:3000) is a
# different origin than this API (127.0.0.1:8000), so the browser blocks
# fetch() without an explicit CORS allow — curl/httpx never hit this, which
# is why this was missed until a real browser session surfaced it.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(copilot_ws_router)
app.include_router(evidence_graph_router)
app.include_router(findings_router)
app.include_router(actions_router)
app.include_router(audit_router)
app.include_router(copilot_query_router)
app.include_router(documents_router)
app.include_router(system_signals_router)
app.include_router(systems_router)
app.include_router(opa_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
