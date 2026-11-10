"""R-02-T19 (TASK-6620; SPEC-646 AC-12; POR-08): the acknowledgement's two frozen figures.

POR-08's uncorrected-misstatements card reads "$35,300.00 - $13,050.00 = $22,250.00". The two parts
are computed by the SUM engine and frozen in the snapshot's totals beside the net, so the portal
shows them without arithmetic; a snapshot frozen before they were keeps the short sentence.
"""

from __future__ import annotations

from decimal import Decimal

from abacus.modules.assurance import uncorrected_ack as ua
from abacus.modules.assurance.compute import sum as sum_engine
from abacus.modules.engagements.api import ApprovalLine

NORTHWIND = sum_engine.Thresholds(Decimal("252200"), Decimal("189150"), Decimal("12610"))
ITEMS = (
    sum_engine.Item("PAJE-1", Decimal("35300"), Decimal("35300")),
    sum_engine.Item("PY-1", Decimal("-1150"), Decimal("-13050"), prior_year=True),
    sum_engine.Item("BCT-1", Decimal("4210"), Decimal("4210"), below_ct=True),
)


def test_the_engine_splits_the_iron_curtain_into_its_two_parts() -> None:
    found = sum_engine.evaluate(ITEMS, NORTHWIND, column_set="ebp_net_assets")
    assert (found.iron_curtain_increase, found.iron_curtain_decrease) == (
        Decimal("35300.00"),
        Decimal("13050.00"),
    )
    assert found.iron_curtain_increase - found.iron_curtain_decrease == found.iron_curtain


def test_below_ct_items_stay_out_of_the_parts() -> None:
    found = sum_engine.evaluate(ITEMS[2:], NORTHWIND, column_set="ebp_net_assets")
    assert (found.iron_curtain_increase, found.iron_curtain_decrease) == (Decimal(0), Decimal(0))


def test_the_acknowledgement_lines_come_from_the_frozen_totals() -> None:
    totals = {
        "iron_curtain": "22250.00",
        "iron_curtain_increase": "35300.00",
        "iron_curtain_decrease": "13050.00",
    }
    assert ua.parts(totals) == (
        ApprovalLine("Would increase net assets", debit=Decimal("35300.00")),
        ApprovalLine("Would decrease net assets", credit=Decimal("13050.00")),
    )


def test_an_older_snapshot_has_no_lines() -> None:
    assert ua.parts({"iron_curtain": "22250.00"}) == ()
