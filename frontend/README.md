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

## Shell (Stage 1)

Scaffolded by SENT-1-07: Vite + React 19 + TypeScript + Tailwind v4 + `@xyflow/react` v12.

### Route table

| Path | Page | Bible |
|---|---|---|
| `/` | Command Centre | 11.1 |
| `/copilot` | Ask GxP Copilot (chat + React Flow agent topology) | 11.2 |
| `/audit-readiness` | Audit Readiness | 11.3 |
| `/suppliers` | Supplier Intelligence | 11.5 |
| `/actions` | Action / Approval Centre | 11.6 |
| `/assurance-lab` | Assurance Lab | 11.7 |
| `/trust-centre` | Trust Centre | 11.8 |
| `/inspection-simulator` | Inspection Readiness Simulator | 11.9 |

Bible Section 11 has no `11.4` subsection — the numbering jumps from 11.3 to 11.5. That gap is
almost certainly the Blast Radius page (Phase 4, SENT-3-04); the route table in
`src/routes.tsx` is a plain array with a comment marking exactly where a ninth
`/blast-radius` entry lands. Adding it requires appending one array entry, not restructuring
the router. `NavBar.tsx` derives its links from this same array, so a route can never exist
without a corresponding nav link falling out of sync.

The mandatory prototype banner (`PrototypeBanner.tsx`) renders above the router outlet in
`App.tsx`'s `AppShell`, so it persists across every route rather than being repeated per page.

### Tailwind v4

No `tailwind.config.js`, no `postcss.config.js`, no `@tailwind base/components/utilities`
directives — that is the v3 pattern and does not apply here. Tailwind v4 is wired via the
`@tailwindcss/vite` plugin (registered in `vite.config.ts`) plus a single
`@import "tailwindcss";` line in `src/index.css`. A v3-style setup would fail *silently*:
utility classes appear in JSX, the build succeeds, and nothing is styled — if that happens,
this is the first thing to check.

### React Flow (`@xyflow/react` v12)

`react-flow-renderer` and `reactflow` are both superseded names; this app installs and
imports `@xyflow/react` exclusively, using the v12 **named** import (`import { ReactFlow }`),
not v11's default import. Its stylesheet (`@xyflow/react/dist/style.css`) is imported once,
in `src/main.tsx` — without it, v12 renders a collapsed, unusable canvas with no error.
`AgentTopologyCanvas.tsx` mounts on `/copilot` with placeholder nodes laid out in the real
Bible Section 1.2 topology (`C2 → A0 → [A1…A6] → C1 → A7 → C3`), so Phase 6's live
agent-state streaming replaces node *colours*, not the whole component.

### Commands

| Command | Effect |
|---|---|
| `npm run dev` | Serves the app on port 3000 (`strictPort: true` — fails loudly on a port collision instead of silently relocating) |
| `npm run build` | Type-checks (`tsc -b`) then builds to `dist/` |
| `npm test` | Runs the Vitest suite once (`vitest run`), not in watch mode, for CI (plan 02-08) |
