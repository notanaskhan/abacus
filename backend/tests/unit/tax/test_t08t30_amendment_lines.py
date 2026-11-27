"""T-08-T30 (TASK-9005; TAX-16 a; AC6.1): the 1040-X and IL-1040-X lines. Row acceptance:
"Okafor's 1040-X foots to (2,708), refund 2,708 and IL (495)"."""

from __future__ import annotations

from decimal import Decimal as D

from abacus.modules.tax.compute import amendment as am

# Okafor 2025 as filed and as amended: the missed Lakeview Credit Union 1098 and the Ridge
# Avenue roof depreciation lower taxable income; payments do not move.
FILED = {
    "1040.11": D("212400"),
    "1040.12": D("29200"),
    "1040.15": D("183200"),
    "1040.16": D("37400"),
    "1040.24": D("40386"),
    "1040.33": D("41000"),
    "il1040.agi": D("212400"),
    "il1040.tax": D("10514"),
}
AMENDED = {
    **FILED,
    "1040.12": D("38660"),
    "1040.15": D("173740"),
    "1040.16": D("35206"),
    "1040.24": D("37678"),
    "il1040.agi": D("202400"),
    "il1040.tax": D("10019"),
}


def test_t08t30_acceptance_okafor_federal_change_and_refund() -> None:
    found = am.amend("federal", FILED, AMENDED)
    assert (found.total_change, found.refund_due, found.balance_due) == (
        D("-2708.00"),
        D("2708.00"),
        None,
    )
    assert [ln.line_key for ln in found.lines] == [k for k, _ in am.LINES["federal"]]
    tax = next(ln for ln in found.lines if ln.line_key == "1040.24")
    assert (tax.as_filed, tax.as_amended, tax.change) == (
        D("40386.00"),
        D("37678.00"),
        D("-2708.00"),
    )


def test_t08t30_acceptance_okafor_illinois_change() -> None:
    found = am.amend("il", FILED, AMENDED)
    assert found.total_change == D("-495.00")
    assert (found.refund_due, found.balance_due) == (D("495.00"), None)


def test_t08t30_no_amended_summary_yet_means_no_change() -> None:
    found = am.amend("federal", FILED, None)
    assert found.total_change == 0 and found.refund_due is None and found.balance_due is None
    assert all(ln.change == 0 for ln in found.lines)


def test_t08t30_an_increase_is_a_balance_due_and_missing_keys_read_zero() -> None:
    more = {**FILED, "1040.24": D("41000"), "1040.33": D("41000")}
    found = am.amend("federal", FILED, more)
    assert (found.total_change, found.refund_due, found.balance_due) == (
        D("614.00"),
        None,
        D("614.00"),
    )
    empty = am.amend("federal", {}, {"1040.24": D("10")})
    assert empty.total_change == D("10.00") and empty.balance_due == D("10.00")
