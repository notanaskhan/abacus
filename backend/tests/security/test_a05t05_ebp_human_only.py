"""A-05-T05 (TASK-2811; DEC-1860): the EBP acts that are a person's are refused to the agent and
the system at the matrix, and the three EBP flags are off by default (the generated allow and
deny suites in `test_permission_matrix_generated.py` cover every role; this names the five acts).

Row acceptance: "Generated allow and deny tests prove agents are refused verify, adopt, record
correction, evaluate certification and conclude, and make check-fast passes with the three flags
off."
"""

from __future__ import annotations

import pytest

from abacus.kernel import _flags
from abacus.kernel._statuses import (
    Aud27ItemStatus,
    EbpLateRemittanceStatus,
    EbpTestResultStatus,
)
from abacus.modules.identity.authz import _matrix

HUMAN_ONLY = {
    "verify": "field.sign_off",
    "adopt the trust report": "ledger_snapshot.create_from_document",
    "adopt a test result": "test.mark",
    "record correction": "ebp_correction.record",
    "evaluate certification": "ebp_certification.evaluate",
    "conclude": "decision.decide",
    "raise the conclusion": "estimate.request_conclusion",
}


@pytest.mark.parametrize(("act", "action"), sorted(HUMAN_ONLY.items()))
def test_t05_the_agent_and_the_system_are_refused(act: str, action: str) -> None:
    cells = _matrix.ACTIONS[action]
    assert cells.get("agent") in (None, "deny"), act
    assert cells.get("system") in (None, "deny"), act
    assert any(v == "allow" for r, v in cells.items() if r not in ("agent", "system")), act


def test_t05_the_three_flags_default_off() -> None:
    for name in ("ebp.modules", "ebp.form5500_tieout", "assurance.estimates_rp"):
        assert str(_flags.FLAGS[name].default).lower() == "false", name


def test_t05_the_status_words_are_registered() -> None:
    assert {s.value for s in EbpLateRemittanceStatus} == {"found", "pending_vfcp_scc", "corrected"}
    assert len(list(EbpTestResultStatus)) == 6
    assert {s.value for s in Aud27ItemStatus} == {
        "unevaluated",
        "evaluated",
        "exception",
        "screened_out",
    }
