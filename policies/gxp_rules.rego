package sentinel.gxp

# 1. ANNEX11-S4-DOC-001: O&M Manual must be approved
# Source: EU GMP Annex 11, Section 4 (Documentation)
# Input shape: {"documents": [{"id": "...", "system_id": "...", "doc_type": "O&M", "status": "DRAFT"}]}
# Expected Output: violation array containing record_id of DRAFT O&M document.
violation contains {
    "rule_id": "ANNEX11-S4-DOC-001", "severity": "HIGH",
    "system_id": doc.system_id, "record_id": doc.id,
    "description": "O&M Document is not in APPROVED state"
} if {
    doc := input.documents[_]
    doc.doc_type == "O&M"
    doc.status != "APPROVED"
}
