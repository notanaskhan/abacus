"""A-05-T34 (TASK-3272; DEC-2252): EBP scenario slice 2.

Row acceptance: "Net assets foot to 16,812,400 + 48,600 = 16,861,000 across the EBP-06, EBP-07
and EBP-08 goldens, and every document is synthetic with fictional providers."
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import yaml

from abacus_tools.synthetic.scenarios.brightwater_hale import ebp2
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import slice_events

GOLDEN = yaml.safe_load(
    (
        Path(__file__).resolve().parents[2] / "golden" / "ebp" / "northwind_py2025_slice2.yaml"
    ).read_text()
)


def test_net_assets_foot_16812400_plus_48600_to_16861000() -> None:
    t = ebp2.totals()
    assert t["trust"] == t["funds"] + t["brokerwindow"] + t["loans"] == Decimal("16812400.00")
    assert t["net_assets"] == t["trust"] + t["receivable"] == Decimal("16861000.00")
    assert t["balances"] == t["trust"]


def test_the_figure_book_matches_the_golden() -> None:
    t = ebp2.totals()
    for key in ("funds", "brokerwindow", "loans", "trust", "balances", "receivable", "net_assets"):
        assert str(t[key]) == GOLDEN[key], key
    assert len(ebp2.brokerwindow_accounts()) == GOLDEN["brokerwindow_accounts"]
    assert len(ebp2.account_balances()) == GOLDEN["participants"]
    assert list(ebp2.sample_rows()) == GOLDEN["sample"]


def test_the_sample_is_ten_distinct_rows_of_sixty_four() -> None:
    rows = ebp2.sample_rows()
    assert len(rows) == len(set(rows)) == 10
    assert all(1 <= r <= 64 for r in rows)


def test_the_form_5500_draft_reports_the_same_net_assets() -> None:
    assert b"16,861,000.00" in ebp2.form5500_pdf()


def test_every_file_builds_and_names_only_fictional_providers() -> None:
    real = ("Fidelity", "Vanguard", "Schwab", "Empower", "Principal", "John Hancock")
    for file in ebp2.FILES:
        body = file.content()
        assert body
        assert not any(name.encode() in body or name in file.file_name for name in real)


def test_the_slice_is_registered_and_opt_in_after_part_one() -> None:
    assert ebp2.NEEDS == ("ebp",)
    assert slice_events(ebp2.SLICE)
