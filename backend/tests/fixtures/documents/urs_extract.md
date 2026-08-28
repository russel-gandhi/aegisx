# Synthetic User Requirements Specification Extract

This fixture is synthetic content authored for the AegisX AI test suite
(Phase 06.1, plan 06.1-01). It is not a real regulated document, not
derived from any real customer system, and carries no real GxP data. It
exists to give `parse_text`/`chunk_blocks`/`index_document` a realistic
Markdown shape to exercise: an unheaded lead-in paragraph, two `##`
section headings, and enough total word count across the two sections to
force multi-chunk word-bounded chunking under `CHUNK_WORDS=350`.

## Section A: System Purpose and Scope

The NovaSynth Manufacturing Execution Support System exists to coordinate
batch production records, equipment qualification status, and operator
training verification for a single regulated manufacturing line. The
system must maintain a complete, attributable, and contemporaneous record
of every batch disposition decision, and every decision must be traceable
back to the underlying test result, calibration record, or training
completion that justified it. This traceability requirement is the
central design constraint driving every downstream requirement in this
specification, because an auditor reviewing a released batch must be able
to reconstruct, from stored records alone, exactly which checks passed,
which operator performed which step, and which equipment was in a
qualified state at the time of use. The system shall never allow a batch
release decision to proceed while any linked requirement remains in an
unverified or failed state, and any attempt to override that constraint
shall itself be recorded as a distinct, non-repudiable event with the
identity of the person who performed the override and the stated
justification for doing so. Every requirement captured in this document
is intended to be independently testable, independently verifiable
against real system state, and independently traceable to at least one
test case that proves the requirement is satisfied in the deployed
system, not merely in a design document. The scope of this specification
covers batch record management, equipment status tracking, operator
training status, and the audit trail that ties all three together into a
single coherent evidentiary record suitable for regulatory inspection.
Deployment environments are assumed to be validated GxP infrastructure
with restricted network access, role-based access control, and a
documented change control process governing any modification to the
production configuration. This document intentionally does not specify
the underlying database technology, network topology, or hosting
arrangement, since those are implementation decisions delegated to the
system's design specification rather than its user requirements. What
matters at this layer is observable behavior: given a specific sequence
of operator actions and equipment states, the system must produce a
specific, predictable, and auditable outcome every single time, with no
silent divergence between two runs given identical inputs.

## Section B: Traceability and Evidence Requirements

Every requirement in Section A shall have at least one linked test case
recorded in the test management system, and that test case's most recent
execution result shall be visible from within the requirement's own
detail view without requiring a separate lookup or manual cross-reference
by the reviewing auditor. A requirement with no linked test case, or
whose linked test case has never been executed, shall be flagged as an
open traceability gap and shall count against the system's overall
audit-readiness score until it is resolved. The system shall additionally
support a downstream impact query: given any single requirement, design
element, or risk record, an authorized user shall be able to retrieve the
complete set of directly and indirectly dependent records, so that a
proposed change to one requirement can be evaluated for its full blast
radius before that change is approved and implemented. This impact query
must be derived from real, currently stored relationship data rather than
a cached snapshot that can silently drift out of sync with the underlying
records, and any query result must be reproducible: running the same
query twice against unchanged data must return byte-identical results.
Evidence supporting a compliance claim must always be traceable to a
specific database record, a specific test execution, or a specific
policy evaluation result, and no compliance claim shall be presented to a
user as verified unless that underlying evidence has actually been
retrieved and checked against the claim at request time, not derived
from a previously cached judgment that may no longer reflect current
system state. This is the foundational trust requirement the rest of the
platform depends on: a claim without independently checked evidence
behind it is not a verified finding, it is merely an assertion, and the
system must never blur that distinction for the benefit of a shorter or
more confident-sounding answer.
