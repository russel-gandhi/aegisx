"""
Regression guard for the `confidence_score` vs `verification_result
["confidence"]` trap (2026-09-02 production-incident triage).

`routes/findings.py::_assemble_card` and `agents/a7_remediation.py` already
carry their own docstrings warning about this exact trap, and
`test_routes_findings.py::test_unit_assemble_card_reads_confidence_from_verification_not_finding`
already proves the primary card-assembly path reads the right field. What
was NOT covered anywhere: `CopilotFinding.confidence_score` (`schemas.py`,
mirrored in `frontend/src/lib/api.ts`) is still exposed on the wire with
nothing structurally stopping a FUTURE `.tsx` component from reading it
directly and rendering A2's permanent `"UNVERIFIED"` sentinel as if it were
C1's real grade. This file is that missing guard.
"""

from pathlib import Path

# backend/tests/test_confidence_field_contract.py -> backend/tests -> backend -> aegisx (repo root)
_REPO_ROOT = Path(__file__).resolve().parents[2]
_FRONTEND_SRC = _REPO_ROOT / "frontend" / "src"


def test_no_frontend_component_reads_confidence_score_directly():
    """Scans every `.tsx`/`.ts` file under `frontend/src` (excluding
    `__tests__/`, which is allowed to reference the field name in a mock
    fixture object literal, and `lib/api.ts` itself, which must declare the
    field's TYPE to mirror the backend's wire shape) for a direct
    `.confidence_score` property read. A future component doing
    `finding.confidence_score` to decide what to render would pass every
    existing test (nothing else exercises that component) and silently
    show every finding as `"UNVERIFIED"` regardless of C1's real grade --
    this test is the tripwire for exactly that mistake.
    """
    assert _FRONTEND_SRC.is_dir(), f"expected frontend source tree at {_FRONTEND_SRC}"

    offenders = []
    for path in _FRONTEND_SRC.rglob("*.ts*"):
        if "__tests__" in path.parts:
            continue
        if path == _FRONTEND_SRC / "lib" / "api.ts":
            continue
        text = path.read_text(encoding="utf-8")
        if ".confidence_score" in text:
            offenders.append(str(path.relative_to(_REPO_ROOT)))

    assert offenders == [], (
        "The following file(s) read `.confidence_score` directly -- this "
        "is A2's permanent 'UNVERIFIED' emission-time placeholder, never a "
        "real grade. Read `verification_result.confidence` / the card's "
        "`confidence` field instead (see routes/findings.py::_assemble_card "
        f"and agents/a7_remediation.py's docstrings): {offenders}"
    )
