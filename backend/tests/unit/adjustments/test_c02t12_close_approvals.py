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


def test_the_classification_carries_the_listed_class_limit() -> None:
    from uuid import uuid4

    from abacus.modules.methodology.api import PolicyRef
    from abacus.modules.methodology.standards_contract import (
        AjeThresholdsPayload,
        classify_entry,
    )

    def row(cls: str, rule: str, level: str, limit: int | None, batch: bool) -> dict[str, object]:
        return {"account_class": cls, "rule": rule, "approver_level": level,
                "limit_usd": limit, "batch": batch}  # fmt: skip

    payload = AjeThresholdsPayload.model_validate(
        {
            "kind": "aje_thresholds",
            "rows": [
                row("other_accruals", "limit", "senior_or_above", 10000, True),
                row("All other classes", "review_required", "manager_or_partner", None, False),
                row("Attest clients", "always_held", "manager_or_partner", None, False),
            ],
        }
    )
    policy = PolicyRef("aje_thresholds", uuid4(), 2, "BH AJE thresholds v2")
    over = classify_entry(payload, policy, account_class="other_accruals", amount_usd=14900,
                          attest_client=False)  # fmt: skip
    assert (over.outcome, over.limit_usd) == ("review_required", 10000)
    unlisted = classify_entry(payload, policy, account_class="bank_adjustments", amount_usd=380,
                              attest_client=False)  # fmt: skip
    assert unlisted.limit_usd is None
