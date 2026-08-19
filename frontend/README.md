# frontend/

Vite + React + TypeScript + Tailwind + React Flow application tier (D-01).

## What lands here

- The Vite app shell, routing, and Tailwind configuration
- The 7+ pages described in Bible Section 11 (including the React Flow canvas used for graph/agent visualization)
- REST API client code against the backend's `/api/*` routes
- The WebSocket client for `/api/copilot/stream/{session_id}`, streaming live agent state
- Evidence cards and the human approval dialog for `action_proposals`

## Owning tickets (Stage 1)

| Ticket | Contract |
|---|---|
| SENT-1-07 | React/Vite/Tailwind shell — app boots, routing scaffolded for the 7 pages, React Flow canvas mounted with placeholder nodes |
| SENT-1-08 | WebSocket connection pattern — frontend client connects to `/api/copilot/stream/{session_id}` and echoes a test event end-to-end |

Dev server runs on port `3000`.

## Server-trusted rendering only

Approval dialogs and evidence cards render exclusively from server-trusted data returned by the backend API — never from LLM-generated markup or LLM-authored UI content. This mirrors the C3 Action Gateway's own rule that the approval dialog is rendered from server-trusted proposal metadata, not from anything a model produced.

This tier is intentionally empty until Stage 1 (ROADMAP Phase 2) begins.
