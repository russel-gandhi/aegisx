"""
FastAPI application entrypoint for GxP Sentinel.

Ticket: SENT-1-05 | Requirement: ENV-04
Source: GxP-Sentinel-Project-Bible-v6.md Section 12 (API table, lines
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
"""

from fastapi import FastAPI

app = FastAPI(
    title="GxP Sentinel",
    description=(
        "Agentic AI co-pilot for audit-ready GxP IT system management. "
        "Deterministic evidence verification (C1) is the product's core "
        "thesis — see GxP-Sentinel-Project-Bible-v6.md Section 1."
    ),
)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
