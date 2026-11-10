"""T-04-T16 (TASK-6615; SPEC-649; ADR-050): the derived lines recompute in code. Row acceptance:
"Editing line 20 with a reason recomputes lines 33, 37 and the balance due in code, creates one
checkpoint and stales the Payments and credits sign-off, while an edit without a reason answers
422 reason_required." The route, checkpoint and sign-off half is the end pass's integration
suite; this is the formula half."""

from __future__ import annotations

from decimal import Decimal

import pytest

from abacus.modules.tax.worksheet_formulas import FORMULAS, UnknownFormula, recompute

D = Decimal
F1040 = {
    "line_21": "f1040.line_21",
    "line_22": "f1040.line_22",
    "line_24": "f1040.line_24",
    "line_33": "f1040.line_33",
    "line_34": "f1040.line_34",
    "line_37": "f1040.line_37",
}
BASE = {
    "line_18": D("12000.00"), "line_19": D("0.00"), "line_20": D("500.00"),
    "line_23": D("1200.00"), "line_25d": D("9000.00"), "line_26": D("1500.00"),
    "line_32": D("0.00"),
}  # fmt: skip


def test_a_line_20_edit_recomputes_the_payments_and_the_balance_due() -> None:
    first = recompute(BASE, F1040)
    assert first["line_24"] == D("12700.00")  # 12000 - 500 + 1200
    assert first["line_33"] == D("10500.00")
    assert first["line_37"] == D("2200.00")
    assert "line_34" not in first or first["line_34"] == D("0.00")
    edited = {**BASE, **first, "line_20": D("1550.00")}
    second = recompute(edited, F1040)
    assert second["line_21"] == D("1550.00")
    assert second["line_37"] == D("1150.00")
    assert "line_33" not in second  # payments did not move


def test_recompute_is_deterministic_and_idempotent() -> None:
    once = {**BASE, **recompute(BASE, F1040)}
    assert recompute(once, F1040) == {}


def test_an_overpayment_is_line_34_never_negative_37() -> None:
    found = recompute({**BASE, "line_25d": D("20000.00")}, F1040)
    assert found["line_34"] == D("8800.00")
    assert found.get("line_37", D("0.00")) == D("0.00")


def test_an_unknown_formula_fails_closed() -> None:
    with pytest.raises(UnknownFormula):
        recompute(BASE, {"line_99": "f1040.line_99"})
    assert set(F1040.values()) <= set(FORMULAS)
