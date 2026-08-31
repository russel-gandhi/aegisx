-- infra/postgres/initdb/005_documents_content_hash.sql
--
-- Remediation follow-up to SYSTEM-DESIGN-DIAGNOSIS.md #6 (upload
-- idempotency). This is **additive Phase-06.1 schema**, not
-- AegisX-AI-Project-Bible-v6.md Section 4.1 DDL -- like
-- 002_change_affects.sql and 004_document_chunks_structure.sql, no
-- statement here is transcribed from the Bible.
--
-- Why it exists: `POST /api/documents/upload` had no way to detect that a
-- given system's document set already contains the exact bytes being
-- uploaded again (double-click, client retry after a slow response, a
-- flaky-network resubmit). Each such duplicate re-ran the full
-- parse->chunk->embed->index pipeline and paid the embedding-provider cost
-- a second time for identical content -- the same failure *class* as the
-- LLM-router amplification incident, just triggered by a human retry
-- instead of a timeout/cascade bug.
--
-- `content_sha256` is a SHA-256 hex digest of the raw uploaded bytes,
-- computed in `routes/documents.py` before parsing. The partial unique
-- index is scoped to `(system_id, content_sha256)` rather than
-- `content_sha256` alone, since the same document content legitimately
-- uploaded for two different systems is not a duplicate. `WHERE
-- content_sha256 IS NOT NULL` keeps this from blocking on the previous
-- migration's existing rows, which have no hash recorded.
--
-- `IF NOT EXISTS` framing makes this file safe to apply both
-- automatically (fresh volume, docker-compose initdb mount) and manually
-- via infra/apply-migrations.sh against an already-running stack.
--
-- Routed to SENT-7-05 for Bible reconciliation.

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS content_sha256 VARCHAR(64);

CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_system_content_hash
    ON documents (system_id, content_sha256)
    WHERE content_sha256 IS NOT NULL;
