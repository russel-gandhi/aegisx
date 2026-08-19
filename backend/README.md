# backend/

FastAPI + LangGraph application tier (D-01).

## What lands here

- The FastAPI app entrypoint and route modules (`/api/*`)
- The LangGraph `StateGraph` implementing the fixed request topology: `C2 → A0 → [A1…A6 in parallel via Send] → C1 → A7 → C3`
- Pydantic schemas (`AgentFinding`, `ActionProposal`, `AgentState`, and the rest of Section 4.3)
- The OPA client module (`evaluate_opa_policy()` and its `python_fallback_rules()` stub)
- The six domain agents (A1 System Knowledge, A2 Compliance, A3 Risk, A4 Change, A5 Incident, A6 Access) plus A0 Orchestrator and A7 Remediation
- The C1 Evidence & Grounding Verifier, C2 Policy & Safety Gateway, and C3 Action Gateway modules

## Owning tickets (Stage 1)

| Ticket | Contract |
|---|---|
| SENT-1-05 | FastAPI skeleton + Pydantic schemas — all Section 4.3 types importable, `/api/health` live |
| SENT-1-06 | LangGraph `StateGraph` skeleton — compiles with stub node returns, edges match the C2→A0→[A1-A6]→C1→A7→C3 topology exactly |
| SENT-1-04 | OPA Docker sidecar wired to the app — `evaluate_opa_policy()` calls the real REST endpoint |

## Deterministic-first constraint (Bible Section 1.3)

No LLM call in this tier may ever evaluate a compliance threshold, an RBAC decision, or a prompt-injection judgment. Those checks run in Python, Rego (via the OPA client), or NetworkX only — never inside a generative model call. See `CLAUDE.md` and Bible Section 1.3's decision table before choosing an implementation method for any check that lands in this tier.

This tier is intentionally empty until Stage 1 (ROADMAP Phase 2) begins.
