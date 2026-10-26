"""A-02-T07 (TASK-1285; ADR-078; A-02 §9): golden footing for the trial balance of record's layer
engine, Northwind PY2025 and Granite Peak FY2026, by exact Decimal.

`tb_layers.yaml` carries each case's snapshot lines, prior lines, methodology area rules and
recorded adjustment entries, and the figures the engine must produce: every layer's debits and
credits, named footings, Final lines and leadsheets with Δ and Δ% (half-even to 0.1). Amounts are
quoted YAML text read as `Decimal`; a float is refused. Northwind's inputs are probed against the
scenario documents' regions, so the golden fails if the seed drifts from it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest
import yaml

from abacus.modules.ledger.models import TrialBalanceLineRow
from abacus.modules.ledger.trial_balances import (
    AdjustmentEntry,
    AreaRule,
    EntryLine,
    LayerUnbalanced,
    TbLine,
    apply_entries,
    build_lines,
    layer_totals,
    leadsheets,
    require_balanced,
    totals,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.documents import documents

HERE = Path(__file__).parent
Case = Mapping[str, object]


def _load() -> list[Case]:
    raw = yaml.safe_load((HERE / "tb_layers.yaml").read_text())
    return cast(list[Case], cast(dict[str, object], raw)["cases"])


CASES = _load()


def _dec(value: object) -> Decimal:
    if not isinstance(value, str):
        raise TypeError(f"golden amounts are quoted text, not {type(value).__name__}: {value!r}")
    return Decimal(value)


def _rows(case: Case, key: str) -> list[TrialBalanceLineRow]:
    snapshot = uuid4()
    return [
        TrialBalanceLineRow(
            id=uuid4(),
            tenant_id=uuid4(),
            snapshot_id=snapshot,
            account_code=str(r[0]),
            account_name=str(r[1]),
            debit=_dec(r[2]),
            credit=_dec(r[3]),
            source_ref="golden",
        )
        for r in cast(list[list[object]], case[key])
    ]


def _rules(case: Case) -> list[AreaRule]:
    return [AreaRule(*map(str, r)) for r in cast(list[list[object]], case["area_rules"])]


def _entries(case: Case) -> list[AdjustmentEntry]:
    out: list[AdjustmentEntry] = []
    for e in cast(list[dict[str, object]], case["entries"]):
        kind = str(e["kind"])
        assert kind in ("aje", "rje")
        lines = tuple(
            EntryLine(str(x[0]), _dec(x[1]), _dec(x[2]))
            for x in cast(list[list[object]], e["lines"])
        )
        out.append(AdjustmentEntry(str(e["ref"]), "aje" if kind == "aje" else "rje", lines))
    return out


def _lines(case: Case) -> list[TbLine]:
    lines = build_lines(_rows(case, "current"), _rows(case, "prior"), {}, _rules(case))
    entries = _entries(case)
    return apply_entries(lines, entries, _rules(case)) if entries else lines


def _expected(case: Case) -> dict[str, object]:
    return cast(dict[str, object], case["expected"])


def _ids(cases: Sequence[Case]) -> list[str]:
    return [str(c["id"]) for c in cases]


@pytest.mark.parametrize("case", CASES, ids=_ids(CASES))
def test_ac17_each_layer_foots_and_balances(case: Case) -> None:
    lines = _lines(case)
    balances = cast(dict[str, dict[str, object]], _expected(case)["balances"])
    for layer, want in balances.items():
        if layer == "boy":
            prior = _rows(case, "prior")
            got = totals(
                sum((r.debit for r in prior), Decimal(0)),
                sum((r.credit for r in prior), Decimal(0)),
            )
        else:
            got = require_balanced(lines, layer)
        assert (got.debit, got.credit, got.difference) == (
            _dec(want["debit"]),
            _dec(want["credit"]),
            _dec(want["difference"]),
        ), layer
        assert got.balanced


@pytest.mark.parametrize("case", CASES, ids=_ids(CASES))
def test_ac5_named_footings_by_exact_decimal(case: Case) -> None:
    by = {line.account_code: line for line in _lines(case)}
    for footing in cast(list[dict[str, object]], _expected(case)["footings"]):
        accounts = [str(a) for a in cast(list[object], footing["accounts"])]
        assert all(a in by for a in accounts), footing["label"]
        picked = [by[a] for a in accounts]
        if "boy" in footing:
            assert sum((x.boy or Decimal(0) for x in picked), Decimal(0)) == _dec(footing["boy"])
        if "eoy" in footing:
            assert sum((x.eoy for x in picked), Decimal(0)) == _dec(footing["eoy"])
        if "final" in footing:
            assert all(x.final is not None for x in picked)
            assert sum((x.final or Decimal(0) for x in picked), Decimal(0)) == _dec(
                footing["final"]
            )


@pytest.mark.parametrize("case", CASES, ids=_ids(CASES))
def test_ac18_leadsheets_from_methodology_rules(case: Case) -> None:
    sheets = {s.area: s for s in leadsheets(_lines(case))}
    for area, want in cast(dict[str, dict[str, object]], _expected(case)["leadsheets"]).items():
        sheet = sheets[area]
        assert (sheet.py, sheet.cy, sheet.change) == (
            _dec(want["py"]),
            _dec(want["cy"]),
            _dec(want["change"]),
        ), area
        if "change_pct" in want:
            assert sheet.change_pct == _dec(want["change_pct"]), area
        rows = {r.account_code: r for r in sheet.rows}
        for row in cast(list[list[object]], want.get("rows", [])):
            got = rows[str(row[0])]
            assert (got.py, got.cy, got.change) == (_dec(row[1]), _dec(row[2]), _dec(row[3]))
            if len(row) > 4:
                assert got.change_pct == _dec(row[4]), row[0]


@pytest.mark.parametrize("case", CASES, ids=_ids(CASES))
def test_ac19_no_account_is_dropped_by_the_rollup(case: Case) -> None:
    lines = _lines(case)
    codes = {
        str(r[0]) for key in ("current", "prior") for r in cast(list[list[object]], case[key])
    }
    assert codes <= {line.account_code for line in lines}
    rolled = [row.account_code for sheet in leadsheets(lines) for row in sheet.rows]
    assert sorted(rolled) == sorted(line.account_code for line in lines)


def test_ac15_northwind_final_layer_carries_aje1() -> None:
    case = next(c for c in CASES if c["id"] == "northwind-py2025")
    by = {line.account_code: line for line in _lines(case)}
    for code, want in cast(dict[str, dict[str, object]], _expected(case)["final_lines"]).items():
        line = by[code]
        assert (line.boy, line.eoy, line.aje, line.final) == (
            _dec(want["boy"]),
            _dec(want["eoy"]),
            _dec(want["aje"]),
            _dec(want["final"]),
        ), code
        assert list(line.refs) == [str(r) for r in cast(list[object], want["refs"])]


def test_ac17_an_unbalanced_layer_is_refused_with_its_difference() -> None:
    case = next(c for c in CASES if c["id"] == "northwind-py2025")
    lines = build_lines(_rows(case, "current"), None, {})
    one_sided = AdjustmentEntry(
        "AJE-X", "aje", (EntryLine("1400", Decimal("48600.00"), Decimal(0)),)
    )
    adjusted = apply_entries(lines, [one_sided])
    assert require_balanced(adjusted, "unadjusted").balanced
    for layer in ("aje", "final"):
        assert not layer_totals(adjusted, layer).balanced
        with pytest.raises(LayerUnbalanced) as refused:
            require_balanced(adjusted, layer)
        assert refused.value.facts == {"layer": layer, "difference": "48600.00"}


def _money(value: Decimal) -> str:
    return f"{value:,.2f}"


def test_northwind_inputs_are_the_seeds() -> None:
    """The golden's Northwind lines are the seed's: the TB document's name and amount regions and
    Harborline's 1/1/2025 column, read from the scenario documents themselves."""
    case = next(c for c in CASES if c["id"] == "northwind-py2025")
    found = {d.key: d for d in documents()}
    tb = found["northwind_trial_balance"]
    for code, name, debit, credit in cast(list[list[object]], case["current"]):
        assert tb.region(f"{code}.name").text == name
        assert tb.region(f"{code}.amount").text == _money(_dec(debit) or _dec(credit))
    trust = found["northwind_net_trust_assets"]
    for _code, _name, debit, credit, probe in cast(list[list[object]], case["prior"]):
        assert trust.region(str(probe)).text == _money(_dec(debit) or _dec(credit))
