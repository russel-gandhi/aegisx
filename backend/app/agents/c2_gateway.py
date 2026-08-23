"""
C2 - Policy & Safety Gateway (Phase 5, plans 05-01 and 05-02).

Ticket: SENT-4-01 | Requirements: SAFE-01, SAFE-02 | Source: Bible Section 2, C2

This module never contains a model call -- that constraint is permanent,
not a stub-stage convenience (Bible Section 1.3, mirroring
`c1_verifier.py`'s own docstring language). RBAC is a fixed-topology
decision: an LLM may never decide whether a role is permitted to invoke
an agent, so this file is the single place `PERMISSION_MATRIX` exists in
the codebase -- no route, no other module, keeps a second copy.

Prompt-injection detection (entropy + regex, the other half of C2's
Bible-specified responsibility) is implemented below as `detect_injection`,
built from two independent, deterministic legs: a regex leg matching the
Bible's literal jailbreak phrases, and a Shannon-entropy leg over
whitespace-split tokens that catches obfuscated (e.g. base64) payloads
the regex leg cannot see. Neither leg calls a model -- this is what Bible
Section 2 means by "Bypasses LLM interpretation entirely" and what
Section 1.3 makes a permanent constraint on this module.
"""

import math
import re
from collections import Counter
from typing import Dict, FrozenSet, Optional, Tuple

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


# Bible Section 2, C2 "Prompt Injection Logic", transcribed verbatim
# (including its `(?i)` flag and its three alternatives). This tuple is
# the only copy of the jailbreak phrase list in the repository -- a
# second copy drifting from it is the same failure mode
# `opa_client.py`'s own docstring already warns against for duplicated
# Rego logic. Compiled once at import.
JAILBREAK_PATTERNS: Tuple[re.Pattern, ...] = (
    re.compile(r"(?i)(ignore previous instructions|override system prompt|disregard rules)"),
)

# Bible Section 2 specifies "Shannon entropy calculations" but supplies no
# threshold, window, or minimum token length. 4.5 bits/char was chosen
# because ordinary English prose sits well below it, while base64
# approaches log2(64) = 6 bits/char and hex approaches log2(16) = 4
# bits/char. 12 characters is the minimum length at which a token can
# carry a meaningful encoded instruction, and it keeps ordinary hyphenated
# GxP record ids and UUIDs below the evaluation floor. This is recorded as
# assumption A1 in 05-RESEARCH.md's Assumptions Log, tuned against the
# fixtures in test_c2_gateway.py rather than asserted from any external
# standard. The two fixtures that pin this constant in both directions
# are `test_benign_domain_identifiers_are_not_flagged` (must stay under
# threshold) and `test_base64_obfuscated_jailbreak_is_caught_by_entropy_leg`
# (must clear threshold) -- a future change to either constant must move
# those two tests together.
ENTROPY_THRESHOLD_BITS_PER_CHAR: float = 4.5
MIN_TOKEN_LENGTH_FOR_ENTROPY: int = 12


def shannon_entropy(text: str) -> float:
    """Pure function, no I/O. Returns 0.0 for an empty string."""
    if not text:
        return 0.0
    counts = Counter(text)
    length = len(text)
    return -sum((n / length) * math.log2(n / length) for n in counts.values())


def detect_injection(text: str) -> Optional[str]:
    """Returns a reason string when injection is suspected, else None.

    Regex leg first: catches the Bible's literal jailbreak phrasing.
    Entropy leg second: catches high-entropy tokens (base64/hex blobs)
    used to smuggle instructions past the regex. Both legs are
    deterministic Python -- no model call occurs anywhere in this
    function, which is what Bible Section 2 means by "Bypasses LLM
    interpretation entirely" (Bible Section 1.3).

    The entropy leg's reason string truncates the offending token to 16
    characters so the reason -- which lands in an audit row -- cannot
    itself become a replay of the payload.
    """
    for pattern in JAILBREAK_PATTERNS:
        if pattern.search(text):
            return f"regex_match:{pattern.pattern}"

    for token in text.split():
        if (
            len(token) >= MIN_TOKEN_LENGTH_FOR_ENTROPY
            and shannon_entropy(token) >= ENTROPY_THRESHOLD_BITS_PER_CHAR
        ):
            return f"high_entropy_token:{token[:16]}..."

    return None
