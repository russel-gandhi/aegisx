package sentinel.gxp_test

import data.sentinel.gxp

# --- Rule 1: ANNEX11-S4-DOC-001 (O&M document must be APPROVED) ---

test_rule1_draft_om_document_violates if {
    input_doc := {"documents": [{
        "id": "DOC-2026-OM-99", "system_id": "GXP-MFG-DEMO-01",
        "doc_type": "O&M", "status": "DRAFT",
    }]}
    violations := gxp.violation with input as input_doc
    count(violations) == 1
    some v in violations
    v.rule_id == "ANNEX11-S4-DOC-001"
    v.record_id == "DOC-2026-OM-99"
}

test_rule1_approved_om_document_does_not_violate if {
    input_doc := {"documents": [{
        "id": "DOC-2026-OM-99", "system_id": "GXP-MFG-DEMO-01",
        "doc_type": "O&M", "status": "APPROVED",
    }]}
    count(gxp.violation) == 0 with input as input_doc
}

test_rule1_non_om_doc_type_does_not_violate if {
    input_doc := {"documents": [{
        "id": "DOC-2026-SOP-01", "system_id": "GXP-MFG-DEMO-01",
        "doc_type": "SOP", "status": "DRAFT",
    }]}
    count(gxp.violation) == 0 with input as input_doc
}

test_rule1_empty_documents_array_does_not_violate_or_error if {
    count(gxp.violation) == 0 with input as {"documents": []}
}
