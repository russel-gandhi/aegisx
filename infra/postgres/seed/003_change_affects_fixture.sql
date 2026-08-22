-- infra/postgres/seed/003_change_affects_fixture.sql
--
-- Phase 4, plan 04-02 (GRAPH-01, D-03). This is **additive Phase-4 test
-- fixture data**, not AegisX-AI-Project-Bible-v6.md Section 5 seed data —
-- like infra/postgres/seed/002_urs_fixture.sql, no literal here is
-- transcribed from the Bible.
--
-- Why it exists: neither `changes` nor `change_actions` carries a foreign
-- key to `requirements`, `design_elements`, or `test_cases`
-- (infra/postgres/initdb/001_schema.sql, confirmed by full read), so
-- Bible Section 14.3's `CHANGE --AFFECTS--> X` relationship type has no
-- source to derive from until a `change_affects` row supplies one
-- (infra/postgres/initdb/002_change_affects.sql). This file supplies
-- three real rows for the already-seeded `CR-2026-089`
-- (infra/postgres/seed/001_seed.sql, Gap 10), resolving 04-RESEARCH.md
-- Open Question 2 with concrete targets.
--
-- No gap is added and none is removed, and no existing row is changed:
-- every INSERT here is either a brand-new row in a table
-- 001_seed.sql leaves entirely empty (`design_elements`) or a brand-new
-- row in the brand-new `change_affects` table. Every column supplied is
-- declared by 001_schema.sql or by 002_change_affects.sql — no column
-- outside that DDL is referenced (CLAUDE.md Rule 7, schema closed for this
-- phase).
--
-- Follows 002_urs_fixture.sql's own idempotency style: every INSERT ends
-- with a conflict-safe upsert-noop guard, so re-running this file is
-- always safe and adds nothing on a second application. `change_affects`
-- has a composite PRIMARY KEY(change_id, entity_type, entity_id)
-- (confirmed at this plan's checkpoint:decision), so its three inserts use
-- `ON CONFLICT (change_id, entity_type, entity_id) DO NOTHING` directly,
-- the same pattern `design_elements`' single-column-PK insert already
-- uses.
--
-- Routed to SENT-7-05 for AegisX-AI-Project-Bible-v6.md reconciliation,
-- same as every other deviation/addition recorded this phase.

-- Closes 04-RESEARCH.md Pitfall 3: `design_elements` is otherwise
-- completely unseeded (001_seed.sql has no `INSERT INTO design_elements`
-- statement anywhere), so Bible Section 14.3's illustrative
-- `CHANGE --AFFECTS--> DESIGN_ELEMENT` relationship would have no real
-- target to point at. `DE-2026-DB-01` is the batch-release database schema
-- design element the `CR-2026-089` migration alters.
INSERT INTO design_elements (id, system_id, description)
VALUES ('DE-2026-DB-01', 'GXP-MFG-DEMO-01', 'Batch release database schema, altered by the CR-2026-089 migration')
ON CONFLICT (id) DO NOTHING;

-- CR-2026-089 -> URS-042 (REQUIREMENT). Supplies a genuine second hop
-- through the existing VERIFIED_BY edge (requirements.test_case_id) to
-- TC-2026-042, so Blast Radius traversal from this change reaches two
-- hops deep through a real, declared foreign key on the far side.
INSERT INTO change_affects (change_id, entity_type, entity_id)
VALUES ('CR-2026-089', 'REQUIREMENT', 'URS-042')
ON CONFLICT (change_id, entity_type, entity_id) DO NOTHING;

-- CR-2026-089 -> DOC-2026-OM-99 (DOCUMENT). Supplies a second hop through
-- the existing GOVERNS edge (documents.system_id) into the system node.
INSERT INTO change_affects (change_id, entity_type, entity_id)
VALUES ('CR-2026-089', 'DOCUMENT', 'DOC-2026-OM-99')
ON CONFLICT (change_id, entity_type, entity_id) DO NOTHING;

-- CR-2026-089 -> DE-2026-DB-01 (DESIGN_ELEMENT). Supplies the third
-- downstream entity type reachable from this change.
INSERT INTO change_affects (change_id, entity_type, entity_id)
VALUES ('CR-2026-089', 'DESIGN_ELEMENT', 'DE-2026-DB-01')
ON CONFLICT (change_id, entity_type, entity_id) DO NOTHING;

-- CA-2026-089-1 deliberately gets no junction row here: it is already
-- reachable from CR-2026-089 through the real, declared
-- change_actions.change_id foreign key (001_schema.sql), which is D-03's
-- priority-1 edge source and outranks a hand-seeded change_affects mapping
-- for a target the schema can already express.
