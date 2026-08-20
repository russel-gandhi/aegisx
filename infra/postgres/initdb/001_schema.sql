-- infra/postgres/initdb/001_schema.sql
--
-- SENT-1-01 / ENV-02: full Postgres DDL for GxP Sentinel.
-- Source of truth: GxP-Sentinel-Project-Bible-v6.md Section 4.1 (lines 587-828).
-- Transcribed verbatim; do not "improve" primary key types or column types
-- (see 02-RESEARCH.md "Notable design choices" and this file's own comments).
--
-- 27 CREATE TABLE statements, 21 FOREIGN KEY constraints, 8 nanosecond-epoch
-- BIGINT columns, 4 JSONB columns. Declaration order matches the Bible's own
-- order, which already satisfies "every foreign key target declared above it".
--
-- Auto-executed by the postgres:16.15 image on a fresh (empty) data
-- directory, via the read-only bind mount declared in docker-compose.yml
-- (./infra/postgres/initdb -> /docker-entrypoint-initdb.d). Editing this
-- file requires `docker compose down -v --remove-orphans` followed by
-- `docker compose up -d --wait` to take effect — see infra/README.md.
--
-- Add nothing the Bible does not declare: no indexes, no unique constraints
-- beyond primary keys, no ON DELETE clauses, no check constraints, no
-- default values beyond the DEFAULT TRUE / DEFAULT 0 / DEFAULT FALSE
-- already written in Section 4.1 (CLAUDE.md Rule 7 — no scope expansion).

-- Core System Registry (EU GMP Annex 11 Section 4)
CREATE TABLE gxp_systems (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    system_owner VARCHAR(100) NOT NULL,
    lifecycle_state VARCHAR(50) NOT NULL,
    gxp_impact BOOLEAN DEFAULT TRUE,
    readiness_score INT DEFAULT 0,
    last_backup_test_ns BIGINT
);

CREATE TABLE documents (
    id VARCHAR(50) PRIMARY KEY,
    system_id VARCHAR(50) REFERENCES gxp_systems(id),
    doc_type VARCHAR(50),
    title VARCHAR(255),
    version VARCHAR(10),
    author VARCHAR(100),
    created_date TIMESTAMP,
    effective_date TIMESTAMP,
    status VARCHAR(50)
);

CREATE TABLE document_chunks (
    chunk_id UUID PRIMARY KEY,
    document_id VARCHAR(50) REFERENCES documents(id),
    content TEXT,
    embedding_id VARCHAR(100)
);

CREATE TABLE requirements (
    id VARCHAR(50) PRIMARY KEY,
    system_id VARCHAR(50) REFERENCES gxp_systems(id),
    req_text TEXT,
    test_case_id VARCHAR(50)
);

CREATE TABLE risks (
    id VARCHAR(50) PRIMARY KEY,
    system_id VARCHAR(50) REFERENCES gxp_systems(id),
    risk_summary TEXT,
    severity VARCHAR(20),
    probability VARCHAR(20),
    last_review_date_ns BIGINT,
    owner VARCHAR(100)
);

CREATE TABLE design_elements (
    id VARCHAR(50) PRIMARY KEY,
    system_id VARCHAR(50) REFERENCES gxp_systems(id),
    description TEXT
);

CREATE TABLE test_cases (
    id VARCHAR(50) PRIMARY KEY,
    system_id VARCHAR(50) REFERENCES gxp_systems(id),
    status VARCHAR(50)
);

CREATE TABLE test_results (
    id VARCHAR(50) PRIMARY KEY,
    test_case_id VARCHAR(50) REFERENCES test_cases(id),
    execution_date_ns BIGINT,
    pass_fail BOOLEAN,
    tester VARCHAR(100)
);

CREATE TABLE incidents (
    id VARCHAR(50) PRIMARY KEY,
    system_id VARCHAR(50) REFERENCES gxp_systems(id),
    title VARCHAR(255),
    description TEXT,
    severity VARCHAR(20),
    status VARCHAR(50),
    opened_date_ns BIGINT,
    rca_started BOOLEAN DEFAULT FALSE,
    patient_safety_relevant BOOLEAN DEFAULT FALSE
);

CREATE TABLE access_reviews (
    id VARCHAR(50) PRIMARY KEY,
    system_id VARCHAR(50) REFERENCES gxp_systems(id),
    review_type VARCHAR(50),
    scheduled_date_ns BIGINT,
    status VARCHAR(50),
    reviewer VARCHAR(100),
    accounts_in_scope INT
);

CREATE TABLE access_records (
    id VARCHAR(50) PRIMARY KEY,
    system_id VARCHAR(50) REFERENCES gxp_systems(id),
    user_id VARCHAR(50),
    is_privileged BOOLEAN,
    user_status VARCHAR(50)
);

CREATE TABLE suppliers (
    id VARCHAR(50) PRIMARY KEY,
    system_id VARCHAR(50) REFERENCES gxp_systems(id),
    name VARCHAR(255),
    reassessment_due_date_ns BIGINT,
    status VARCHAR(50)
);

CREATE TABLE supplier_assessments (
    id VARCHAR(50) PRIMARY KEY,
    supplier_id VARCHAR(50) REFERENCES suppliers(id),
    assessment_date_ns BIGINT,
    result VARCHAR(50)
);

CREATE TABLE periodic_evaluations (
    id VARCHAR(50) PRIMARY KEY,
    system_id VARCHAR(50) REFERENCES gxp_systems(id),
    due_date_ns BIGINT,
    status VARCHAR(50)
);

CREATE TABLE changes (
    id VARCHAR(50) PRIMARY KEY,
    system_id VARCHAR(50) REFERENCES gxp_systems(id),
    description TEXT,
    status VARCHAR(50),
    qa_approval_date TIMESTAMP
);

CREATE TABLE change_actions (
    id VARCHAR(50) PRIMARY KEY,
    change_id VARCHAR(50) REFERENCES changes(id),
    description TEXT,
    status VARCHAR(50)
);

CREATE TABLE findings (
    id VARCHAR(50) PRIMARY KEY,
    system_id VARCHAR(50) REFERENCES gxp_systems(id),
    agent_id VARCHAR(50),
    severity VARCHAR(20),
    status VARCHAR(50),
    description TEXT
);

CREATE TABLE evidence_refs (
    id VARCHAR(50) PRIMARY KEY,
    finding_id VARCHAR(50) REFERENCES findings(id),
    reference_type VARCHAR(50),
    reference_id VARCHAR(50)
);

CREATE TABLE action_proposals (
    id VARCHAR(50) PRIMARY KEY,
    action_type VARCHAR(50),
    target_system VARCHAR(50),
    payload JSONB,
    status VARCHAR(50)
);

-- Hash-Chained Audit Log (21 CFR Part 11.10(e))
CREATE TABLE audit_events (
    event_id VARCHAR(64) PRIMARY KEY,
    timestamp_utc TIMESTAMP,
    session_id VARCHAR(100),
    user_id VARCHAR(100),
    user_role VARCHAR(50),
    agent_id VARCHAR(50),
    action_type VARCHAR(50),
    target_system_id VARCHAR(50),
    target_record_id VARCHAR(50),
    input_hash VARCHAR(64),
    output_summary TEXT,
    evidence_ids JSONB,
    opa_rule_ids JSONB,
    model_id VARCHAR(50),
    prompt_version VARCHAR(50),
    approval_id VARCHAR(50),
    previous_event_hash VARCHAR(64),
    event_hash VARCHAR(64) NOT NULL
);

CREATE TABLE agent_messages (
    id VARCHAR(50) PRIMARY KEY,
    session_id VARCHAR(100),
    agent_id VARCHAR(50),
    message_content TEXT,
    timestamp_utc TIMESTAMP
);

CREATE TABLE graph_nodes (
    node_id VARCHAR(100) PRIMARY KEY,
    system_id VARCHAR(50) REFERENCES gxp_systems(id),
    node_type VARCHAR(50),
    properties JSONB
);

CREATE TABLE graph_edges (
    source_id VARCHAR(100) REFERENCES graph_nodes(node_id),
    target_id VARCHAR(100) REFERENCES graph_nodes(node_id),
    relation_type VARCHAR(50)
);

CREATE TABLE candidate_memory (
    id VARCHAR(50) PRIMARY KEY,
    fact_text TEXT,
    status VARCHAR(50)
);

CREATE TABLE trusted_memory (
    id VARCHAR(50) PRIMARY KEY,
    fact_text TEXT,
    approved_by VARCHAR(100)
);

CREATE TABLE users (
    id VARCHAR(50) PRIMARY KEY,
    username VARCHAR(100),
    role VARCHAR(50)
);

CREATE TABLE sessions (
    id VARCHAR(50) PRIMARY KEY,
    user_id VARCHAR(50) REFERENCES users(id),
    start_time TIMESTAMP,
    end_time TIMESTAMP
);
