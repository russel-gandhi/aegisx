# AegisX AI

AegisX AI is an agentic AI co-pilot for always-on, audit-ready GxP IT system management. It lets a QA/Compliance or IT System Manager user ask natural-language questions about a GxP system's audit readiness, and answers with AI-generated findings that are independently, deterministically verified against real database records and OPA/Rego policy evaluation before being trusted — never presented as unverified LLM output. `AegisX-AI-Project-Bible-v6.md` is the source of truth for this project (Rule 14): when any other document in this repo disagrees with the Bible, the Bible wins, and the drift is reconciled explicitly.

## Status

| Phase | Name | Status |
|---|---|---|
| 0 | Environment | ✓ Complete |
| 1 | Foundation | ✓ Complete |
| 2 | Intelligence & Retrieval | ✓ Complete |
| 3 | (folded into 2/4 scope) | — |
| 4 | Evidence & Impact | ✓ Complete |
| 5 | Safety & Remediation (C2/C3/A7, audit chain) | ◆ In progress |

Backend (FastAPI + LangGraph) and frontend (Vite + React + React Flow) both have working code as of Phase 4: real agents feeding C1 evidence verification, a NetworkX evidence graph built from live Postgres state with Blast Radius traversal, and Assurance Cards rendered end-to-end in the browser. See `.planning/ROADMAP.md` and `.planning/STATE.md` for current phase detail.

## Mentor compliance mapping

AegisX AI was cross-checked against the industry mentor's `HACK-IT-SOP-001_v0.1_IT_System_Lifecycle.md` and `Top_25_Checklists_GxP_IT_Audit_Questions_2026.xlsx` (350 audit questions across 14 lifecycle-phase tabs). AegisX is the **audit agent** those documents describe — not the regulated system under audit — so it is evaluated against the SOP's own "Audit-Agent Answer Contract" (Section 11.4) rather than the full IT-system lifecycle gates a target system must pass.

That contract expects one of five conclusions per control question — Demonstrated / Partially Demonstrated / Not Demonstrated / N/A (with evidence) / Unable to Determine — and a 0–4 corroboration rubric (Absent → Claim → Document → Demonstrated → Corroborated). AegisX's `calculate_confidence()` (C1) uses a different but equivalent vocabulary:

| AegisX confidence | SOP §11.4 conclusion | SOP §11.5 rubric level |
|---|---|---|
| `INSUFFICIENT_EVIDENCE` | Unable to Determine | 0 (Absent) / 1 (Claim only) |
| `LOW` | Partially Demonstrated | 2 (Document, unverified) |
| `MEDIUM` | Demonstrated (single-source corroboration — DB record **or** OPA rule, not both) | 3 (Demonstrated) |
| `HIGH` | Demonstrated | 4 (Corroborated — real DB record **and** real OPA policy evaluation agree) |

An `N/A` conclusion has no AegisX equivalent by design — the deterministic-first architecture (Bible Section 1.3) never lets a check silently mark itself not-applicable; an inapplicable check simply passes (no finding is emitted).

## Prerequisites-

- **Docker Desktop** with Compose v2 (on Windows: WSL2 backend enabled)
- **Node 20+** — needed by the Vite frontend from Stage 1 onward, and by `infra/health-check.sh` for its host-side port probes
- **Git 2.20+** — needed for `git worktree`, used by the branching convention in `BRANCHING.md`

## Quickstart

1. Copy `.env.example` to `.env`.
2. Run `docker-compose up -d postgres qdrant opa`.
3. Run `bash infra/health-check.sh`.

That is the entire setup — there is no other manual step. The bring-up command above is written exactly as Bible Section 13 and requirement ENV-01 state it; the Compose v2 subcommand form `docker compose up -d postgres qdrant opa` (no hyphen) is equivalent.

## Services and ports

All three services publish on loopback (`127.0.0.1`) only, deliberately — the dev stack is not reachable from the LAN.

| Service | Image | Host address | Health endpoint |
|---|---|---|---|
| postgres | `postgres:16.15` | `127.0.0.1:5432` | `pg_isready` |
| qdrant | locally built from `qdrant/qdrant:v1.19.0` | `127.0.0.1:6333` | `/readyz` |
| opa | `openpolicyagent/opa:1.19.1-debug` | `127.0.0.1:8181` | `/health` |

## Repository layout

```
.
├── docker-compose.yml          # D-02: root, zero-arg `docker-compose up`
├── .env.example                 # committed credential template (placeholder values only)
├── BRANCHING.md                 # D-03 branching convention + Rule 10 file-ownership table
├── backend/                     # FastAPI + LangGraph app — agents, C1/graph, routes, tests (Phase 2+)
├── frontend/                    # Vite + React + TypeScript + Tailwind + React Flow app (Phase 2+)
├── policies/                    # Rego policy bundle root — OPA's read-only mount source
├── infra/
│   ├── postgres/initdb/         # Postgres init scripts (DDL lands here, Phase 2)
│   ├── qdrant/                  # Derived curl-capable Qdrant image for its healthcheck
│   └── health-check.sh          # ENV-01 gate: Compose health status + host port reachability
├── .planning/                   # GSD planning artifacts (roadmap, phase plans, state)
├── AegisX-AI-Project-Bible-v6.md   # Source of truth (Rule 14) — full DDL, Rego rules, agent prompts, demo script
├── AegisX-Build-Map.md              # Stage 0-7 ticket breakdown, reference for ticket contracts
├── GSD_Core_Reference.md              # GSD (Git. Ship. Done.) workflow reference
└── Refined_MetaPrompt.md              # Planning meta-prompt with evidence-tagging discipline
```

## Working conventions

Day-to-day work follows `BRANCHING.md` for branch/worktree allocation and file ownership. The three rules from the Bible's Section 16.11 agentic-coding rules that change day-to-day behavior most:

- **Rule 3 — explicit contract before implementation.** No task starts without stated inputs, outputs, and acceptance criteria.
- **Rules 4/5 — tests ship with the implementation, and "done" requires verification.** The failure path is verified, not just the happy path.
- **Rule 10 — one ticket per branch, no two agents editing the same critical file.** See `BRANCHING.md` for the Stage 1 file-ownership allocation that makes this concrete.
