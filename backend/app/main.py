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
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.evidence_graph import router as evidence_graph_router
from app.routes.findings import router as findings_router
from app.ws.copilot import router as copilot_ws_router

app = FastAPI(
    title="AegisX AI",
    description=(
        "Agentic AI co-pilot for audit-ready GxP IT system management. "
        "Deterministic evidence verification (C1) is the product's core "
        "thesis — see AegisX-AI-Project-Bible-v6.md Section 1."
    ),
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


@app.get("/api/health")
async def health():
    return {"status": "ok"}
