-- infra/postgres/initdb/003_action_proposals_workflow.sql
--
-- Phase 5, plan 05-01 (SAFE-01, AUDIT-01, AUDIT-02, REM-01..REM-04). This is
-- **additive Phase-5 schema**, not AegisX-AI-Project-Bible-v6.md Section 4.1
-- DDL -- unlike infra/postgres/initdb/001_schema.sql, no statement here is
-- transcribed from the Bible.
--
-- Why it exists: the live `action_proposals` table
-- (infra/postgres/initdb/001_schema.sql:174-180) has only
-- `id, action_type, target_system, payload, status`. REM-03 requires the
-- approval dialog to render a `justification`, and REM-04 requires approval
-- provenance (who approved, when, execution result) and a queue ordering.
-- The Bible's own Section 4.1 DDL never declared these columns either --
-- `justification` exists only on the Pydantic `ActionProposal` model
-- (app/schemas.py) -- so this is a pre-existing Bible-internal gap, not
-- something Phases 1-4 introduced.
--
-- 05-01-PLAN.md's Task 1 checkpoint:decision (gate=blocking-human) presented
-- three options for closing this gap; the developer selected Option A
-- (additive migration, `category` derived at read time rather than
-- persisted) -- recorded verbatim in 05-01-SUMMARY.md under "Schema
-- decision". `category` is deliberately NOT a column here: it is fully
-- derivable from `action_type` via the frozen `ACTION_CATEGORIES` allowlist
-- in `backend/app/agents/c3_gateway.py`, and persisting it would create a
-- second source of truth that can silently drift from that allowlist --
-- the same "cache never holds a fact not derivable from domain state"
-- principle `graph_nodes`/`graph_edges` (Phase 4) already follows.
--
-- `IF NOT EXISTS` makes this file safe to apply both automatically, via the
-- read-only initdb bind mount on a fresh volume (docker-compose.yml ->
-- ./infra/postgres/initdb:/docker-entrypoint-initdb.d, applied after
-- 001_schema.sql and 002_change_affects.sql in sorted filename order), and
-- manually against an already-running stack via infra/apply-migrations.sh,
-- without destroying existing data.
--
-- Routed to SENT-7-05 for AegisX-AI-Project-Bible-v6.md reconciliation,
-- same as every other deviation/addition recorded this phase.

ALTER TABLE action_proposals ADD COLUMN IF NOT EXISTS justification TEXT;
ALTER TABLE action_proposals ADD COLUMN IF NOT EXISTS finding_id VARCHAR(100);
ALTER TABLE action_proposals ADD COLUMN IF NOT EXISTS session_id VARCHAR(100);
ALTER TABLE action_proposals ADD COLUMN IF NOT EXISTS model_id VARCHAR(50);
ALTER TABLE action_proposals ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT now();
ALTER TABLE action_proposals ADD COLUMN IF NOT EXISTS approved_by VARCHAR(100);
ALTER TABLE action_proposals ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP;
ALTER TABLE action_proposals ADD COLUMN IF NOT EXISTS execution_result TEXT;
