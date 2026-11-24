"""C-02-T39 (TASK-8920; C-02 F8; CLS-12 a to d; C12; DEC-5922; amber): the close-to-tax hand-off,
closes side.

Row acceptance: "Priya's hand-off on Jan 12, 2027 lands TB v1 with three tax issues for Olivia
Brandt and Samuel Ito, and a hand-off after the Jan 20 reopen supersedes it." Here, by code: an
August close (or an unlocked December one) is not available with CLS-12 b's words; the five
schedules compute CLS-12 a's figures from the close's arrangements and TB (cost 278,400.00,
accumulated depreciation 74,900.00, 2026 book depreciation 25,680.00; prepaid 8,400.00 amortized
to 0.00; distributions 144,000.00); the first version is TB v1 and the next TB v2; C12 accepts a
`close_issue` item and the tax landing words it; the publish names the return's preparer and
reviewer and supersedes the previous row. The DB path is the integration test.
"""

from __future__ import annotations

import inspect
from decimal import Decimal
from pathlib import Path

from abacus.modules.closes import tax_handoff as th
from abacus.modules.ledger.api import tb_handoff

D = Decimal
ROOT = Path(th.__file__).resolve().parents[4]


def test_only_a_locked_december_close_can_hand_off() -> None:
    assert th.gate("2026-08", "locked") == "Available after the December 2026 close locks"
    assert th.gate("2026-12", "approved") == "Available after the December 2026 close locks"
    assert th.gate("2026-12", "locked") is None
    assert th.month_words("2026-12") == "December 2026"


def _results() -> list[th.ScheduleResult]:
    # Three assets costing 278,400 depreciated 2,140 a month in 2026 (25,680) down to an ending
    # net book value of 203,500 (accumulated 74,900); the BOP prepaid 700 a month to 0.
    months = [f"2026-{m:02d}" for m in range(1, 13)]
    assets = th.ScheduleResult(
        "fixed_asset", D("278400"),
        [(p, D("-2140"), D("203500") + D("2140") * (12 - i - 1)) for i, p in enumerate(months)],
    )  # fmt: skip
    prepaid = th.ScheduleResult(
        "prepaid", D("8400"),
        [(p, D("-700"), D("8400") - D("700") * (i + 1)) for i, p in enumerate(months)],
    )  # fmt: skip
    deferred = th.ScheduleResult(
        "deferred_revenue", D("36000"), [("2026-12", D("-3000"), D("9000"))]
    )
    payroll = th.ScheduleResult("accrual", D("0"), [("2026-12", D("0"), D("18650"))])
    return [assets, prepaid, deferred, payroll]


def test_the_five_schedules_compute_cls12s_figures() -> None:
    found = {s.key: s for s in th.schedules(2026, _results(), D("-144000"))}
    assert list(found) == [k for k, _ in th.SCHEDULES]
    fa = found["fixed_assets"].figures
    assert (fa["cost"], fa["accumulated_depreciation"], fa["book_depreciation"]) == (
        D("278400"), D("74900"), D("25680"),
    )  # fmt: skip
    pre = found["prepaid_expenses"].figures
    assert (pre["amortized"], pre["ending_balance"]) == (D("8400"), D("0"))
    assert found["shareholder_distributions"].figures["total"] == D("144000")
    assert found["accrued_liabilities"].figures["ending_balance"] == D("18650")
    assert all(s.included for s in found.values())
    # A close with no arrangements of a kind carries no row for it.
    assert [s.key for s in th.schedules(2026, [], None)] == []


def test_distributions_come_from_the_tb() -> None:
    accounts = [("3100", "Shareholder distributions", D("144000")), ("1000", "Cash", D("5"))]
    assert th.distributions_of(accounts) == D("144000")
    assert th.distributions_of([("1000", "Cash", D("5"))]) is None


def test_versions_and_c12_kinds() -> None:
    assert (th.tb_version(0), th.tb_version(1)) == ("TB v1", "TB v2")
    item = tb_handoff.TaxItem("close_issue", {"issue_id": "x", "ref": "December 2026 close"},
                              D(0), True)  # fmt: skip
    assert item.item_kind == "close_issue"
    from abacus.modules.tax.tb_handoff_landing import item_title

    assert item_title("close_issue", {"ref": "December 2026 close"}, D(0)) == (
        "Tax-relevant item from the December 2026 close handed off: review it for the return"
    )
    migration = (ROOT / "migrations/versions/1017_close_handoff_kinds.py").read_text("utf-8")
    assert "'close_issue'" in migration and "'shareholder_distributions'" in migration


def test_publish_lands_through_c12_and_supersedes() -> None:
    source = inspect.getsource(th.publish)
    assert "tb_handoff.create(" in source and '"close_lock"' in source
    assert "TaxHandoffPublished(" in source and "TaxHandoffSuperseded(" in source
    assert "target.preparer_user_id, target.reviewer_user_id" in source
    assert '"sup": None if previous is None else previous.id' in source
    contract = (ROOT / "src/abacus/modules/closes/delivery_contract.py").read_text("utf-8")
    start = contract.index('f"{_C}/tax-handoff"')
    end = contract.index("/client-entities/{client_entity_id}/information-returns")
    assert "NotImplementedYet" not in contract[start:end]
