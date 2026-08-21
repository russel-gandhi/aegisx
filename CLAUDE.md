# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository currently is

This is a **specification vault, not a codebase**. It is an Obsidian vault (`.obsidian/`) containing the complete design for **AegisX AI** — an agentic AI co-pilot for audit-ready GxP IT system management, built as a 20-day hackathon project. No application source, build tooling, or tests exist yet; everything below describes the system to be built and the process rules that govern building it.

There are therefore no build/lint/test commands yet. When the first code lands, the intended commands per the bible are:

```bash
docker-compose up -d postgres qdrant opa   # entire environment setup (Stage 0 gate)
opa test <policy-dir>                      # Rego rules, tested independently of the app
```

Services bind to fixed localhost ports: Postgres `5432`, Qdrant `6333`, OPA `8181`, FastAPI `8000`, Vite frontend `3000`.

## The four documents

| File | Role |
|---|---|
| `AegisX-AI-Project-Bible-v6.md` | **Source of truth** (Rule 14). ~3,300 lines, Sections 1–17 plus Section 16 process rules. Contains the full DDL, all 10 Rego rules, Pydantic models, agent system prompts, API table, demo script. |
| `AegisX-Build-Map.md` | Stage 0–7 ticket breakdown (`SENT-<stage>-<number>`), each with a contract, owner model, priority, and review level. Ticket contracts cite bible sections. |
| `GSD_Core_Reference.md` | Reference for the GSD (Git. Ship. Done.) `/gsd-*` slash-command workflow — not installed here, reference only. |
| `Refined_MetaPrompt.md` | A planning meta-prompt with an evidence-tagging discipline (`(user)` / `(verified: <source>)` / `[assumed: … — if wrong: …]`). |

When bible content and a ticket contract disagree, the bible wins; drift is reconciled explicitly (ticket SENT-7-05).

## Architecture the code must implement

**Deterministic-first is the central architectural constraint.** Generative models are structurally isolated from compliance decisions. An LLM may never evaluate a compliance threshold, an RBAC decision, or a prompt-injection judgment — those run in Python, Rego, or NetworkX traversal. Section 1.3 is the binding decision table; consult it before choosing an implementation method for any check.

Request flow (LangGraph `StateGraph`, topology fixed): `C2 → A0 → [A1…A6 in parallel via Send] → C1 → A7 → C3`.

- **A0 Orchestrator** — intent classification, fans out to a subset of A1–A6. On 2000ms timeout it must fall back to the full `["A1".."A6"]` set.
- **A1–A6** — System Knowledge (Qdrant RAG), Compliance, Risk, Change, Incident, Access. Each emits `AgentFinding` objects and each has a specified degraded-mode fallback (abstain, downgrade model, rule-only) that is part of its contract, not an afterthought.
- **C1 Evidence & Grounding Verifier** — fan-in. `calculate_confidence()` consumes the real DB record and the real OPA evaluation. When an LLM claim contradicts DB/OPA truth, C1 must return `INSUFFICIENT_EVIDENCE`. ALCOA+ 9-dimension scoring (16.12) extends C1 — it is explicitly *not* a new agent, page, or table.
- **C2 Policy & Safety Gateway** — RBAC (IT System Manager / QA-Compliance / Auditor) plus entropy+regex injection detection with zero LLM in the decision path.
- **A7 Remediation** — LLM synthesis of `ActionProposal` / CAPA narratives from *already verified* findings.
- **C3 Action Gateway** — routes READ / DRAFT / MOCK_WRITE_LOW_RISK / GXP_RELEVANT_WRITE / PROHIBITED. GxP-relevant writes sit `PENDING` in `action_proposals` until human approval. The approval dialog is rendered from server-trusted proposal metadata, never from LLM-generated UI.

Supporting layers: **OPA/Rego sidecar** (10 named policies mapped to EU GMP Annex 11 / 21 CFR 11 / ICH Q9 clauses, called over REST via `evaluate_opa_policy()` with a `python_fallback_rules()` stub); **hash-chained append-only audit trail** with `verify_chain()` written alongside the chain, plus a deliberate `/api/audit/demonstrate-tamper` endpoint; **NetworkX evidence graph** built from live Postgres state, driving Blast Radius impact traversal; **Qdrant hybrid retrieval** (dense + BM25 sparse → fusion → cross-encoder rerank → parent-context expansion).

**Multi-provider LLM router** (Section 8): Gemini 2.5 Flash for orchestration/synthesis/remediation and thinking-off compliance/knowledge/change work, DeepSeek R1 for risk, Groq Llama 3.3 70B for incident/access/high-volume, OpenRouter as universal fallback. Every response carries the actual `model_id` used, for auditability.

Frontend is React + TypeScript + Vite + Tailwind + React Flow, 7+ pages (Section 11), driven over REST plus a `/api/copilot/stream/{session_id}` WebSocket that streams live agent state.

## Working rules that apply to Claude Code here

Section 16.11 of the bible defines 15 mandatory agentic-coding rules. The ones that most change day-to-day behavior:

- **Rule 3 — explicit contract before implementation.** Never accept or act on an unbounded instruction ("build the compliance system"). Every task states inputs, outputs, and acceptance criteria first. Tickets in the build map are already written this way; keep new work at that granularity.
- **Rule 4/5 — tests ship with the implementation, and "done" requires verification.** For anything touching compliance, security, authorization, evidence, graph, or audit, verify the failure path as well as the happy path. "It compiles and returns something" is explicitly called out as the known failure mode to avoid.
- **Rule 6 — `Critical`-review tickets** (C1, C2, C3, hash-chain, Rego rules, Blast Radius, ALCOA+, evidence graph) need unit + negative + edge-case + integration coverage plus a stronger review pass. Do not close them on a smoke test.
- **Rule 7 — no silent scope expansion.** ALCOA+ in particular has an explicit no-new-subsystem constraint.
- **Rule 10 — no two agents editing the same critical file.** Parallelize across ticket boundaries, not inside them.
- **Rule 13 — never trust a generated regulatory claim.** Regulatory citations (Annex 11 sections, CFR clauses, ICH Q9) come from the bible's citation map (Section 14), not from model recall.

Ticket owners are labeled `Opus` (architecture, algorithms, policy review, critical paths) vs `Sonnet` (bounded implementation). Treat that label as a signal about how much design latitude a ticket carries.

## Dependency order

Tickets are staged and gated; do not start a ticket whose dependencies are still open. Stage gates: environment healthy (0) → schema + one Rego rule + API skeleton (1) → real non-stub agents feeding a real C1 confidence score (2) → graph builds from live Postgres and Blast Radius is correct (3) → injection blocked deterministically, writes held pending, tamper detected (4) → full Monitor→Investigate→Trust→Remediate→Audit loop walkable unaided (5) → adversarial hardening + one-command demo reset (6) → freeze (7).
