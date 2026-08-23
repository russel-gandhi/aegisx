"""
C2 - Policy & Safety Gateway (Phase 5, plan 05-01).

Ticket: SENT-4-01 | Requirement: SAFE-01 | Source: Bible Section 2, C2

This module never contains a model call -- that constraint is permanent,
not a stub-stage convenience (Bible Section 1.3, mirroring
`c1_verifier.py`'s own docstring language). RBAC is a fixed-topology
decision: an LLM may never decide whether a role is permitted to invoke
an agent, so this file is the single place `PERMISSION_MATRIX` exists in
the codebase -- no route, no other module, keeps a second copy.

Prompt-injection detection (entropy + regex, the other half of C2's
Bible-specified responsibility) is added to this same module by plan
05-02 -- this task deliberately leaves no placeholder function for it,
since an unused stub here would only invite drift between this module's
docstring and its actual contents before 05-02 lands.
"""

from typing import Dict, FrozenSet

# Bible Section 2, C2 "Permission Matrix", transcribed verbatim. The
# note "(Cannot trigger Remediation A7)" on QA/Compliance is enforced
# structurally here, not commented as an aside: QA/Compliance's set simply
# does not contain "A7".
PERMISSION_MATRIX: Dict[str, FrozenSet[str]] = {
    "IT System Manager": frozenset({"A1", "A2", "A3", "A4", "A5", "A6", "A7"}),
    "QA/Compliance": frozenset({"A1", "A2", "A3", "A4", "A5", "A6"}),
    "Auditor": frozenset({"A1", "A2"}),
}


def check_rbac(role: str, agent_id: str) -> bool:
    """Returns False for an unrecognised role too -- fail closed, never
    fail open on a typo'd or missing role string. Never consults a model
    for this decision (Bible Section 1.3)."""
    return agent_id in PERMISSION_MATRIX.get(role, frozenset())
