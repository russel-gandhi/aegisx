-- infra/postgres/initdb/002_change_affects.sql
--
-- Phase 4, plan 04-02 (GRAPH-01, D-03). This is **additive Phase-4 schema**,
-- not AegisX-AI-Project-Bible-v6.md Section 4.1 DDL — unlike
-- infra/postgres/initdb/001_schema.sql, no statement here is transcribed
-- from the Bible.
--
-- Why it exists: neither `changes` nor `change_actions`
-- (001_schema.sql) carries a foreign key to `requirements`,
-- `design_elements`, or `test_cases`, so `CHANGE --AFFECTS--> X` — a
-- relationship Bible Section 14.3 names explicitly — cannot be derived
-- from the existing schema. This table is the one explicit junction that
-- makes that edge derivable without falling back to a shared-`system_id`
-- guess or a text match (D-03 rejects both as edge sources).
--
-- `entity_id` deliberately carries no foreign key of its own: Postgres
-- cannot express a single foreign key that targets several different
-- tables depending on a sibling column's value. `entity_type` names which
-- table `entity_id` resolves against, and is validated against the frozen
-- `CHANGE_AFFECTS_ENTITY_TYPES` allowlist in
-- `backend/app/graph/evidence_graph.py` instead of by a database
-- constraint — the same allowlist-not-database-constraint pattern
-- `backend/app/agents/c1_verifier.py` already uses for rule ids. A row
-- naming an out-of-allowlist `entity_type`, or a valid `entity_type` whose
-- `entity_id` does not resolve to a real row, is silently skipped by the
-- graph builder rather than rejected here.
--
-- Composite PRIMARY KEY(change_id, entity_type, entity_id): confirmed at
-- this plan's `checkpoint:decision` (04-02-PLAN.md) as the "add-composite-pk"
-- option. Makes a duplicate junction row impossible at the database level
-- and gives infra/postgres/seed/003_change_affects_fixture.sql a real
-- `ON CONFLICT` target, in place of the `WHERE NOT EXISTS` guard the
-- checkpoint's alternative "as-proposed" option would have required.
--
-- `IF NOT EXISTS` makes this file safe to apply both automatically, via the
-- read-only initdb bind mount on a fresh volume (docker-compose.yml ->
-- ./infra/postgres/initdb:/docker-entrypoint-initdb.d, applied after
-- 001_schema.sql in sorted filename order), and manually against an
-- already-running stack via infra/apply-migrations.sh, without destroying
-- existing data.
--
-- Routed to SENT-7-05 for AegisX-AI-Project-Bible-v6.md reconciliation,
-- same as every other deviation/addition recorded this phase.

CREATE TABLE IF NOT EXISTS change_affects (
    change_id   VARCHAR(50) REFERENCES changes(id),
    entity_type VARCHAR(50) NOT NULL,
    entity_id   VARCHAR(50) NOT NULL,
    PRIMARY KEY (change_id, entity_type, entity_id)
);
