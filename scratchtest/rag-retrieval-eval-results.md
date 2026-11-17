# RAG Retrieval Evaluation — 350 Audit Questions x 10 Epochs

Retrieval-only (dense + BM25 + RRF fusion), no LLM reranker. Corpus: 34/35 Dummy_data docs ingested into `COMPLIANCE-RAG-EVAL-01` (2639 chunks/vectors; `NOVOLIFE-MES-IQTC-IQ Test Cases-v0.1-DUMMY.docx` failed ingestion twice with a real embedding-provider 400 error — excluded from the corpus, not silently retried away).

## Epoch stability

**All 350 questions produced byte-identical top-1 fused scores across all 10 epochs.** Confirms this retrieval path (embedding -> dense search -> BM25 -> RRF fusion) is fully deterministic and reproducible, as expected — no LLM or sampling in this code path.

## Overall summary (350 questions)

- Mean top-1 fused (RRF) score: **0.0295**
- Median top-1 fused score: **0.0310**
- Questions with zero candidates (fully insufficient): **0/350**

## Per-phase summary

| Phase | N | Mean | Median | Min | Max | Zero-candidate |
|---|---|---|---|---|---|---|
| 01 Concept Business Case | 25 | 0.0292 | 0.0306 | 0.0164 | 0.0328 | 0 |
| 02 URS | 25 | 0.0296 | 0.0318 | 0.0164 | 0.0328 | 0 |
| 03 Risk GAMP | 25 | 0.0299 | 0.0315 | 0.0164 | 0.0328 | 0 |
| 04 Supplier Qualification | 25 | 0.0294 | 0.0303 | 0.0164 | 0.0328 | 0 |
| 05 Functional Design | 25 | 0.0305 | 0.0310 | 0.0164 | 0.0325 | 0 |
| 06 Config Development | 25 | 0.0304 | 0.0315 | 0.0164 | 0.0328 | 0 |
| 07 IQ | 25 | 0.0283 | 0.0306 | 0.0164 | 0.0325 | 0 |
| 08 OQ | 25 | 0.0298 | 0.0318 | 0.0164 | 0.0328 | 0 |
| 09 PQ UAT | 25 | 0.0289 | 0.0302 | 0.0164 | 0.0328 | 0 |
| 10 GoLive Handover | 25 | 0.0301 | 0.0304 | 0.0164 | 0.0328 | 0 |
| 11 Ops Periodic Review | 25 | 0.0306 | 0.0315 | 0.0164 | 0.0328 | 0 |
| 12 Change Config Mgmt | 25 | 0.0292 | 0.0308 | 0.0164 | 0.0328 | 0 |
| 13 Incident Problem Dev | 25 | 0.0275 | 0.0309 | 0.0164 | 0.0325 | 0 |
| 14 Decommission Retention | 25 | 0.0302 | 0.0312 | 0.0164 | 0.0328 | 0 |

## Worst 15 questions (lowest score / zero candidates)

| Q_ID | Phase | Top-1 fused score |
|---|---|---|
| DA-01-005 | 01 Concept Business Case | 0.0164 |
| DA-01-013 | 01 Concept Business Case | 0.0164 |
| DA-01-014 | 01 Concept Business Case | 0.0164 |
| DA-02-003 | 02 URS | 0.0164 |
| DA-02-005 | 02 URS | 0.0164 |
| DA-02-020 | 02 URS | 0.0164 |
| DA-03-001 | 03 Risk GAMP | 0.0164 |
| DA-03-006 | 03 Risk GAMP | 0.0164 |
| DA-04-003 | 04 Supplier Qualification | 0.0164 |
| DA-04-009 | 04 Supplier Qualification | 0.0164 |
| DA-05-003 | 05 Functional Design | 0.0164 |
| DA-06-016 | 06 Config Development | 0.0164 |
| DA-07-006 | 07 IQ | 0.0164 |
| DA-07-012 | 07 IQ | 0.0164 |
| DA-07-014 | 07 IQ | 0.0164 |

## Best 15 questions (highest score)

| Q_ID | Phase | Top-1 fused score |
|---|---|---|
| DA-14-015 | 14 Decommission Retention | 0.0328 |
| DA-14-004 | 14 Decommission Retention | 0.0328 |
| DA-14-003 | 14 Decommission Retention | 0.0328 |
| DA-12-024 | 12 Change Config Mgmt | 0.0328 |
| DA-12-016 | 12 Change Config Mgmt | 0.0328 |
| DA-12-014 | 12 Change Config Mgmt | 0.0328 |
| DA-12-013 | 12 Change Config Mgmt | 0.0328 |
| DA-11-009 | 11 Ops Periodic Review | 0.0328 |
| DA-11-001 | 11 Ops Periodic Review | 0.0328 |
| DA-10-021 | 10 GoLive Handover | 0.0328 |
| DA-10-014 | 10 GoLive Handover | 0.0328 |
| DA-10-009 | 10 GoLive Handover | 0.0328 |
| DA-10-001 | 10 GoLive Handover | 0.0328 |
| DA-09-024 | 09 PQ UAT | 0.0328 |
| DA-09-012 | 09 PQ UAT | 0.0328 |

Raw per-epoch data (3500 rows): `scratchtest/rag-retrieval-eval-raw.csv`
