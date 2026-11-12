"""T-05-T25 (TASK-7517; T-05 §4.2 M4, F3; C8): the adjusted TB's tax layers. ATB = UTB + AJE + RJE
(the ledger's final), TJE = each account's approved TJE net, TTB = ATB + TJE; a tax-only account
(4510-T) appears only in the tax layer; a tax-only line belongs to a TJE; a TJE is always a named
human's approval; the contract carries the layers and the line's account scope.

Row acceptance: "TJE-1 reclasses 6,200 to Schedule K line 18a with net zero, and every layer
balances."
"""

from __future__ import annotations

import inspect
from decimal import Decimal
from typing import get_args

import pytest

from abacus.modules.adjustments import contract, entries

D = Decimal

# A TB that foots (debits positive, credits negative): cash, a property tax expense, capital.
BOOK: list[entries.BookRow] = [
    ("1000", "Cash", D(50_000), None, None, D(50_000)),
    ("7300", "Property tax", D(18_500), D(6_200), None, D(24_700)),
    ("3000", "Partners' capital", D(-68_500), D(-6_200), None, D(-74_700)),
]
# TJE-1: the 6,200 nondeductible property tax reclassed to the tax-only 4510-T (Schedule K 18a).
TJE_1 = [
    entries.Line(
        1, "4510-T", "Nondeductible expenses (Sch K 18a)", None, D(6_200), D(0), "tax_only"
    ),
    entries.Line(2, "7300", "Property tax", None, D(0), D(6_200), "book"),
]


def _column(lines: tuple[entries.TaxLayerLine, ...], name: str) -> Decimal:
    return sum((getattr(ln, name) or D(0) for ln in lines), D(0))


def test_tje1_reclasses_6200_with_net_zero_and_every_layer_balances() -> None:
    lines = entries.tax_layers(BOOK, TJE_1)
    by_code = {ln.account_code: ln for ln in lines}
    assert by_code["7300"].tje == D(-6_200)
    assert by_code["7300"].ttb == D(18_500)
    assert by_code["4510-T"].tje == D(6_200)
    assert by_code["4510-T"].ttb == D(6_200)
    assert by_code["4510-T"].atb == D(0)
    for column in ("eoy", "final", "atb", "tje", "ttb"):
        assert _column(lines, column) == D(0), column


def test_the_tax_only_account_lives_only_in_the_tax_layer() -> None:
    lines = entries.tax_layers(BOOK, TJE_1)
    tax_only = [ln for ln in lines if ln.account_scope == "tax_only"]
    assert [ln.account_code for ln in tax_only] == ["4510-T"]
    assert (tax_only[0].eoy, tax_only[0].final) == (None, None)


def test_without_tjes_the_ttb_is_the_atb() -> None:
    lines = entries.tax_layers(BOOK, [])
    assert all(ln.ttb == ln.atb and ln.tje is None for ln in lines)


def test_a_tax_only_line_belongs_to_a_tje() -> None:
    line = entries.NewLine("4510-T", D(1), D(0), "tax_only")
    for kind in ("aje", "rje", "paje", "elimination"):
        with pytest.raises(entries.TaxOnlyOutsideTje) as refused:
            entries.check_scope(kind, [line])
        assert refused.value.code == "tax_only_outside_tje"
    entries.check_scope("tje", [line])


def test_a_tje_is_always_a_named_humans_approval() -> None:
    """A TJE is never within threshold: it waits for review under the firm's tax JE standard."""
    source = inspect.getsource(entries.propose)
    assert 'if new.kind == "tje"' in source
    assert entries._PREFIX["tje"] == "TJE"


def test_the_contract_carries_the_layers_and_the_scope() -> None:
    assert {"atb", "tje", "ttb"} <= set(get_args(contract.Layer))
    assert {"atb", "tje", "ttb", "account_scope"} <= set(contract.AdjustedLineOut.model_fields)
    assert "account_scope" in contract.LineOut.model_fields
    assert contract.LineIn.model_validate({"account_code": "4510-T"}).account_scope == "book"
    assert set(get_args(contract.AccountScope)) == {"book", "tax_only"}
