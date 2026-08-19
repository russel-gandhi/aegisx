<!-- GSD:project-start source:PROJECT.md -->

## Project

**GxP Sentinel**

GxP Sentinel is an agentic AI co-pilot for always-on, audit-ready GxP IT system management, built as a 20-day hackathon project. It lets a QA/Compliance or IT System Manager user ask natural-language questions about a GxP system's audit readiness, and answers with AI-generated findings that are independently, deterministically verified against real database records and OPA/Rego policy evaluation before being trusted — never presented as unverified LLM output.

**Core Value:** **Deterministic evidence verification (C1) is the thesis of the product.** The winning idea is not "AI agents for GxP" — it's "we use AI to investigate, but we never blindly trust AI: every important conclusion is independently verified with deterministic evidence." The minimum viable proof of this is the demo loop: user asks "Is GXP-MFG-DEMO-01 audit ready?" → A0 routes → A2 Compliance Agent produces a claim (e.g. "URS traceability incomplete") → C1 Evidence Verification retrieves real evidence (URS record, test case, execution status), runs the deterministic rule check (e.g. ANNEX11-S4-DOC-001) against real DB/OPA state, and returns a VERIFIED (or INSUFFICIENT_EVIDENCE) finding with confidence. Remove C1 and the product becomes "a chatbot that reads compliance documents" — that destroys the differentiation. Everything else is supporting infrastructure around this hero loop.

### Constraints

- **Timeline**: 20-day hackathon, full runway available as of project start — but scope must stay demo-hierarchy-ordered (Tier 1 before Tier 2 before Tier 3) so a credible demo exists at any cut point
- **Architecture**: Deterministic-first is non-negotiable — no LLM may ever evaluate a compliance threshold, RBAC decision, or prompt-injection judgment; those run in Python, Rego, or NetworkX only (Bible Section 1.3)
- **Source of truth**: When any planning artifact disagrees with `GxP-Sentinel-Project-Bible-v6.md`, the Bible wins; drift must be reconciled explicitly
- **Regulatory citations**: Annex 11 / 21 CFR 11 / ICH Q9 citations must come from the Bible's Section 14 citation map, never from model recall
- **Critical-path review**: C1, C2, C3, hash-chain, Rego rules, Blast Radius, ALCOA+, and the evidence graph require unit + negative + edge-case + integration test coverage, not a smoke test

<!-- GSD:project-end -->

<!-- GSD:stack-start source:STACK.md -->

## Technology Stack

Technology stack not yet documented. Will populate after codebase mapping or first phase.
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:

- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
