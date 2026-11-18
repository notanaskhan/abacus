"""C-02-T12 (SPEC-700; DEC-5621): who may approve what under BH AJE thresholds v2. The DB paths
(batch, held approval, Undo, withdraw) run in the S50 end pass integration suite."""

from __future__ import annotations

import pytest

from abacus.modules.adjustments import close_approvals as ca


@pytest.mark.parametrize(
    ("role", "level", "ok"),
    [
        ("senior", "senior_or_above", True),
        ("senior", "manager_or_partner", False),
        ("manager", "manager_or_partner", True),
        ("engagement_partner", "partner", True),
        ("manager", "partner", False),
        ("staff", "senior_or_above", False),
        (None, "senior_or_above", False),
        ("senior", "unknown_level", False),
    ],
)
def test_meets(role: str | None, level: str, ok: bool) -> None:
    assert ca.meets(role, level) is ok


def test_role_labels_for_the_footer() -> None:
    assert ca.role_label("senior") == "Senior"
    assert ca.role_label("engagement_partner") == "Partner"
    assert ca.role_label(None) == ""


def test_undo_window_is_ten_seconds() -> None:
    assert ca.UNDO_WINDOW.total_seconds() == 10
