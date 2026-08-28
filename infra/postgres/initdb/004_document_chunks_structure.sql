-- infra/postgres/initdb/004_document_chunks_structure.sql
--
-- Phase 06.1, plan 06.1-01 (RAG-01, D-02). This is **additive Phase-06.1
-- schema**, not AegisX-AI-Project-Bible-v6.md Section 4.1 DDL -- like
-- infra/postgres/initdb/002_change_affects.sql, no statement here is
-- transcribed from the Bible.
--
-- Why it exists: `001_schema.sql`'s literal `document_chunks` DDL (`chunk_id`,
-- `document_id`, `content`, `embedding_id`) has no column for the chunk's
-- source section heading, source page, chunking order, parent-chunk lineage,
-- or free-form ingestion metadata -- all of which Bible Section 15's
-- hybrid-retrieval spec (parent-context expansion, section-aware citation)
-- requires and none of which the Section 4.1 table predates that spec well
-- enough to already provide.
--
-- Deviation 13: document_chunks extended with structure-aware columns for
-- real ingestion -- Bible Section 4.1's literal DDL predates Section 15's
-- hybrid-retrieval spec and never defined a chunk hierarchy.
--
-- `IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS` framing makes this file safe
-- to apply both automatically, via the read-only initdb bind mount on a
-- fresh volume (docker-compose.yml -> ./infra/postgres/initdb:/docker-
-- entrypoint-initdb.d, applied after 001_schema.sql in sorted filename
-- order), and manually against an already-running stack via
-- infra/apply-migrations.sh, without destroying existing data.
--
-- Routed to SENT-7-05 for Bible reconciliation.

ALTER TABLE document_chunks
    ADD COLUMN IF NOT EXISTS section VARCHAR,
    ADD COLUMN IF NOT EXISTS page INT,
    ADD COLUMN IF NOT EXISTS parent_chunk_id UUID REFERENCES document_chunks(chunk_id),
    ADD COLUMN IF NOT EXISTS chunk_index INT,
    ADD COLUMN IF NOT EXISTS metadata JSONB;

CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id ON document_chunks(document_id);
