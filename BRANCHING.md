# BRANCHING.md

The operational answer to Bible Rule 10 (never let multiple agents freely edit the same critical files). This document turns "no two agents edit the same critical file" from an aspiration into a written allocation of file ownership, so two agents working simultaneously never collide.

## 1. Model

Trunk-based development (D-03). `main` is always green: it builds, its tests pass, and `bash infra/health-check.sh` exits 0 against it. Work happens on short-lived branches cut from `main` and merged back by PR. There are no long-lived integration branches.

## 2. Branch naming

Branches are named `SENT-<stage>-<number>`, matching the Build-Map ticket ID exactly, with an optional trailing slug for readability — e.g. `SENT-1-03` or `SENT-1-03-rego-rules`.

One ticket, one branch, one PR. Ticket scope equals branch scope — this equality is what makes Rule 10 hold, because file ownership below is allocated per ticket, not per agent or per session.

## 3. Worktrees for parallel agents

Each parallel agent gets its own `git worktree`, cut from `main`, on its own ticket branch:

```bash
git worktree add ../sentinel-SENT-1-03 -b SENT-1-03 main
```

After the branch merges:

```bash
git worktree remove ../sentinel-SENT-1-03
```

This matters because separate worktrees give each parallel agent its own checkout on disk. Two agents cannot write the same file in the same working tree even by accident, because they are never in the same working tree — each agent's edits land in a filesystem location no other agent touches until the PR merge point.

## 4. Stage 1 file ownership (Rule 10)

| Ticket | Owner model | Review | Owns these paths |
|---|---|---|---|
| SENT-1-01 | Sonnet | Standard | `infra/postgres/initdb/` — DDL scripts |
| SENT-1-02 | Sonnet | Standard | `infra/postgres/seed/` — seed scripts |
| SENT-1-03 | Sonnet (rules) / Opus (policy review) | **Critical** | `policies/` — Rego sources and their `opa test` fixtures |
| SENT-1-04 | Sonnet | Standard | The backend OPA client module and its `python_fallback_rules()` stub |
| SENT-1-05 | Sonnet | Standard | The FastAPI application entrypoint and the Pydantic schema modules |
| SENT-1-06 | Opus (design) / Sonnet (impl) | Standard | The LangGraph `StateGraph` module |
| SENT-1-07 | Sonnet | Standard | `frontend/` — app shell, routing, Tailwind config, React Flow canvas |
| SENT-1-08 | Sonnet | Standard | The backend WebSocket route module and the frontend WebSocket client module |
| SENT-1-09 | Sonnet | Standard (P1) | `.github/workflows/` |

Exact filenames inside each owned path are settled when that ticket is planned; this table allocates directories and modules, and it is amended by PR — never by two agents silently agreeing in a chat.

## 5. Shared-file protocol

`docker-compose.yml`, `.env.example`, `README.md`, and `BRANCHING.md` are cross-cutting and owned by no single Stage 1 ticket. Any change to them is its own small PR, merged before the tickets that depend on it start. This is exactly how Phase 1 itself sequenced plan 01-01 and plan 01-03 against the same Compose file: each touched `docker-compose.yml` in its own PR, one after the other, rather than both editing it in parallel.

## 6. Merge rules

A branch merges when:

- Its ticket contract is met.
- Its tests pass, including the failure path, not just the happy path (Rules 4/5).
- For a `Critical`-review ticket, it carries unit, negative, edge-case, and integration coverage plus the stronger review pass (Rule 6). The Critical tickets are: `SENT-1-03`, `SENT-2-12`, `SENT-3-01`, `SENT-3-03`, `SENT-3-08`, `SENT-4-01`, `SENT-4-02`, `SENT-4-03`, `SENT-4-06`, `SENT-4-07`, `SENT-6-01`, `SENT-6-02`, `SENT-6-03`, `SENT-7-05`.

Never force-push `main`; rebase the feature branch onto `main` instead. Do not start a ticket whose Build-Map dependencies are still open — for Stage 1, all tickets depend on Stage 0 being closed, `SENT-1-04` depends on `SENT-1-03`, and `SENT-1-06` depends on `SENT-1-05`.

## 7. Conflict resolution

Resolve conflicts by hand on the feature branch. When two tickets genuinely need the same file, stop and raise a reviewed integration task rather than letting either agent guess at how to merge the two changes. Do not resolve a conflict in a `Critical` path (see the list above) by taking one side wholesale — a Critical-path conflict is itself a signal that the file-ownership allocation in Section 4 needs to be amended by PR, not patched around.
