"""T-07-T24 (red): the 1041 K-1 release gate's truth table: release only after final approval
AND a completed, current Form 8879-F."""

from __future__ import annotations

import pytest

from abacus.modules.tax.k1_release import gate_1041

DONE = ("form_8879_f", "completed", False)


@pytest.mark.parametrize(
    ("approved", "envelopes", "unmet"),
    [
        (True, [DONE], []),
        (False, [DONE], ["final_approval"]),
        (True, [("form_8879_f", "sent", False)], ["form_8879_f"]),
        (True, [("form_8879_f", "completed", True)], ["form_8879_f"]),  # superseded by drift
        (True, [("form_8879_pe", "completed", False)], ["form_8879_f"]),
        (False, [], ["final_approval", "form_8879_f"]),
    ],
)
def test_ac_release_before_the_trustee_signs_lists_form_8879_f_unmet(
    approved: bool, envelopes: list[tuple[str, str, bool]], unmet: list[str]
) -> None:
    assert gate_1041(approved, envelopes) == unmet
