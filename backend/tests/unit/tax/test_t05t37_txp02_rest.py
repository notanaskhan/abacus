"""T-05-T37 rest (TASK-7634; DEC-4629): TXP-02's three statement ties, the derivation terms and
each amount's sheet 01 address, all the server's (ADR-050).

On Ridgeline's goldens (T-05-T11, `ridgeline_ty2025.yaml`, Run 2 ATB): total assets 17,914,500 =
liabilities 11,048,300 + partners' capital 6,866,200, and the capital roll-forward 5,960,000 +
250,000 + 1,256,200 - 600,000 = 6,866,200 (SPEC-651 AC-3.1). The M-2 checks read `pending` until
sheet 07 is written, and `off` with the difference when it disagrees.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import yaml

from abacus.modules.tax.entity_tb import (
    TbRow,
    account_cells,
    capital_roll,
    figures,
    group_of,
    statement_tallies,
    with_cells,
)

D = Decimal
GOLDEN = Path(__file__).resolve().parents[2] / "golden" / "tax_entity" / "ridgeline_ty2025.yaml"


def _ridgeline() -> list[TbRow]:
    data = yaml.safe_load(GOLDEN.read_text(encoding="utf-8"))["tb_pipeline"]
    rows: list[TbRow] = []
    for code, _section, line, _py, utb, aje, tje, _role in data["accounts"]:
        u, a, t = D(utb), D(aje), D(tje)
        rows.append(
            TbRow(
                account_code=code,
                account_name=f"Account {code}",
                form_line_key=line,
                unadjusted=u,
                aje=a,
                rje=D(0),
                tje=t,
                tax_basis=u + a + t,
                adjusted=u + a,
                group=group_of(line),
            )
        )
    return rows


ROWS = _ridgeline()


def test_ac3_1_the_capital_roll_forward_is_the_goldens() -> None:
    roll = capital_roll(ROWS)
    assert roll.assets == D("17914500")
    assert roll.liabilities == D("11048300")
    assert (roll.beginning, roll.contributions, roll.distributions) == (
        D("5960000"),
        D("250000"),
        D("600000"),
    )
    assert roll.net_income == D("1256200")
    assert roll.ending == D("6866200")


def test_ac3_1_the_balance_sheet_ties_and_the_m2_checks_wait_for_sheet_07() -> None:
    by_key = {t.key: t for t in statement_tallies(ROWS, None, None)}
    assert by_key["balance_sheet"].state == "tie"
    assert by_key["balance_sheet"].difference == D(0)
    assert [(t.label, t.amount) for t in by_key["balance_sheet"].terms] == [
        ("Total liabilities", D("11048300")),
        ("Partners' capital", D("6866200")),
    ]
    assert by_key["capital_tie"].state == "pending"
    assert by_key["retained_earnings"].state == "pending"
    assert [(t.label, t.op) for t in by_key["capital_tie"].terms] == [
        ("Beginning capital", "+"),
        ("Contributions", "+"),
        ("Book net income", "+"),
        ("Distributions", "-"),
    ]


def test_ac3_1_the_m2_checks_tie_or_name_the_difference() -> None:
    tied = {t.key: t for t in statement_tallies(ROWS, D("1256200"), D("6866200"))}
    assert tied["capital_tie"].state == "tie"
    assert tied["retained_earnings"].state == "tie"
    off = {t.key: t for t in statement_tallies(ROWS, D("1262400"), D("6872400"))}
    assert (off["capital_tie"].state, off["capital_tie"].difference) == ("off", D("-6200"))
    assert (off["retained_earnings"].state, off["retained_earnings"].difference) == (
        "off",
        D("-6200"),
    )


def test_ac3_1_an_unmapped_account_puts_the_balance_sheet_off() -> None:
    rows = [r if r.account_code != "1300" else TbRow(
        "1300", "Prepaid", None, D("158000"), D(0), D(0), D(0), D("158000"), D("158000")
    ) for r in ROWS]  # fmt: skip
    sheet = {t.key: t for t in statement_tallies(rows, None, None)}["balance_sheet"]
    assert (sheet.state, sheet.difference) == ("off", D("-158000"))


def test_the_rents_derivation_names_each_account_and_nets_the_deductions() -> None:
    cards = {f.key: f for f in figures(ROWS)}
    rents = cards["gross_rents"]
    assert rents.amount == D("3872900")
    assert [(t.label, t.amount, t.op) for t in rents.terms] == [
        ("Account 4000", D("3776500"), "+"),
        ("Account 4100", D("96400"), "+"),
    ]
    net = cards["net_rental_income"]
    assert net.amount == D("1231600")
    assert net.terms[-1].label == "Total deductions"
    assert (net.terms[-1].amount, net.terms[-1].op) == (D("2641300"), "-")
    assert sum((t.amount if t.op == "+" else -t.amount for t in net.terms), D(0)) == net.amount


def test_ac3_3_each_amount_names_its_sheet_01_cell() -> None:
    values = {
        "01!A2": {"t": "text", "v": "1000"},
        "01!A18": {"t": "text", "v": "2050"},
        "01!C18": {"t": "decimal", "v": "-75500"},
        "05!A2": {"t": "text", "v": "1000"},  # another sheet's column A is not the TB
    }
    cells = account_cells(values)
    assert dict(cells["2050"]) == {
        "utb": "01!C18",
        "aje": "01!D18",
        "rje": "01!E18",
        "atb": "01!F18",
    }
    assert dict(cells["1000"])["atb"] == "01!F2"
    shown = {r.account_code: dict(r.cells) for r in with_cells(ROWS, cells)}
    assert shown["2050"]["atb"] == "01!F18"
    assert shown["5000"] == {}  # not on sheet 01 yet: no address, nothing to open
    assert account_cells(None) == {}
