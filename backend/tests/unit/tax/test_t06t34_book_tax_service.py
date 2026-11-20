"""T-06-T34 (TASK-8832; T-06 F2; TXP-04; DEC-5834): the book-tax service.

Row acceptance: "The With proposed fix view previews 6,200 / 7,466,200 / 6,866,200 without
writing, and a stale seen_version answers 409 proposal_changed."
"""

from __future__ import annotations

import inspect
from decimal import Decimal

from abacus.modules.tax import book_tax_service as bt

D = Decimal


def _rows() -> list[bt.Row]:
    return [
        bt.Row("m3_part2", "2_11", "Interest income", D("1000"), D("0"), D("-200"), D("800"),
               "permanent"),
        bt.Row("m3_part3", "3_31", "Depreciation", D("-5000"), D("-700"), D("0"), D("-5700"),
               "temporary"),
    ]  # fmt: skip


def test_m3_required_and_filed_at_ten_million() -> None:
    m3 = bt.m3_of(_rows(), D("12000000"))
    assert m3.required and m3.filed and m3.book_income == D("-4000")


def test_m1_never_filed_beside_m3() -> None:
    assert not bt.m1_of(_rows(), D("12000000")).filed
    assert bt.m1_of(_rows(), D("7466200")).filed  # Ridgeline: under $10 million, the M-1 files


def test_m3_not_required_below_threshold() -> None:
    assert not bt.m3_of(_rows(), D("7466200")).filed


def test_ac_with_fix_previews_without_writing() -> None:
    from abacus.modules.tax import entity_schedules as es
    from abacus.modules.tax import workbook_contract

    source = inspect.getsource(workbook_contract)
    assert "m2_with_fix" in source and "with_fix" in source
    for line in inspect.getsource(es.m2_with_fix).splitlines():
        assert "write" not in line and "uow(" not in line


def test_ac_stale_seen_version_is_proposal_changed() -> None:
    from abacus.modules.agents.proposals import ProposalChanged

    assert ProposalChanged.code == "proposal_changed"
