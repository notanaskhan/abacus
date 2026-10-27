"""A-02-T17 (TASK-1417; SPEC-333 AC-10 to AC-12; A-02 AC-3.1 to AC-3.3): the tie engine's goldens,
by exact Decimal.

`ties.yaml` defines AUD-06's three checks (net assets to the trust report, BOY to the PY2024
audited statements, the loan rollforward) and a balanced check over Northwind PY2025 (read from
`../ledger/tb_layers.yaml`), and what each must give on AUD-06 a and on c's BrokerWindow variant.
Each check passes `clean` first, as the service does, so a golden is also a valid definition; an
expected value without a citation is refused `citation_required`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest
import yaml

from abacus.modules.workpapers.tie_out import CheckInput, CitationRequired, clean
from abacus.modules.workpapers.ties import (
    MINUS,
    Balances,
    Component,
    Definition,
    evaluate,
    money,
)

HERE = Path(__file__).parent
GOLDEN = cast(dict[str, object], yaml.safe_load((HERE / "ties.yaml").read_text()))
LAYERS = cast(
    dict[str, object], yaml.safe_load((HERE.parent / "ledger" / "tb_layers.yaml").read_text())
)
Case = Mapping[str, object]


def _d(text: object) -> Decimal:
    assert isinstance(text, str), f"amounts are quoted text, never a float: {text!r}"
    return Decimal(text)


def _tb_case() -> Case:
    cases = cast(list[Case], LAYERS["cases"])
    return next(c for c in cases if c["id"] == GOLDEN["trial_balance"])


def _balances(changes: Mapping[str, Sequence[str]]) -> Balances:
    tb = _tb_case()
    current = {
        str(row[0]): (_d(row[2]), _d(row[3])) for row in cast(list[list[object]], tb["current"])
    }
    for code, (debit, credit) in changes.items():
        current[code] = (_d(debit), _d(credit))
    prior = {str(row[0]): _d(row[2]) - _d(row[3]) for row in cast(list[list[object]], tb["prior"])}
    debit = sum((d for d, _ in current.values()), Decimal("0.00"))
    credit = sum((c for _, c in current.values()), Decimal("0.00"))
    boy = {code: prior.get(code, Decimal("0.00")) for code in current}
    return Balances(
        eoy={code: d - c for code, (d, c) in current.items()},
        boy=boy,
        totals={"eoy": (debit, credit), "boy": None},
    )


def _input(check: Case, *, cited: bool) -> CheckInput:
    accounts = check.get("accounts", [])
    if accounts == "assets":
        accounts = GOLDEN["assets"]
    components = tuple(
        Component(str(c[0]), int(cast(int, c[1])), _d(c[2]))
        for c in cast(list[list[object]], check.get("components", []))
    )
    expected = check.get("expected")
    return CheckInput(
        label=str(check["label"]),
        kind=cast(str, check["kind"]),  # type: ignore[arg-type]  # the golden's kinds
        accounts=tuple(str(a) for a in cast(list[object], accounts)),
        column=cast(str, check["column"]),  # type: ignore[arg-type]  # eoy or boy
        negate=bool(check.get("negate", False)),
        expected=_d(expected) if expected is not None else None,
        components=components,
        citation_ids=(uuid4(),) if cited else (),
        tolerance=Decimal("0.00"),
    )


def _definition(check: Case) -> Definition:
    body = clean(_input(check, cited=bool(check["cited"])))
    return Definition(
        body.kind,
        body.accounts,
        body.column,
        body.negate,
        body.expected,
        body.components,
        body.tolerance,
    )


CHECKS = {str(c["check"]): c for c in cast(list[Case], GOLDEN["checks"])}
CASES = cast(list[Case], GOLDEN["cases"])


@pytest.mark.parametrize("case", CASES, ids=[str(c["id"]) for c in CASES])
def test_ac10_ac11_each_check_gives_its_golden_result(case: Case) -> None:
    balances = _balances(cast(Mapping[str, Sequence[str]], case["changes"]))
    for key, want in cast(Mapping[str, Mapping[str, str]], case["expected"]).items():
        got = evaluate(_definition(CHECKS[key]), balances)
        assert got.status == want["status"], key
        for field in ("actual", "expected", "difference"):
            if field in want:
                assert getattr(got, field) == _d(want[field]), (key, field)
        if "formula" in want:
            assert got.formula == want["formula"]
        if "display" in want:
            assert got.difference is not None
            assert f"{got.status} {money(got.difference)}" == want["display"]


def test_ac10_the_rollforward_golden_reads_312_400() -> None:
    got = evaluate(_definition(CHECKS["loan-rollforward"]), _balances({}))
    assert (got.status, got.expected) == ("tie", Decimal("312400.00"))
    assert (
        got.formula == f"288,500.00 + 96,200.00 {MINUS} 57,450.00 {MINUS} 14,850.00 = 312,400.00"
    )


@pytest.mark.parametrize("key", ["net-assets-trust-report", "loan-rollforward"])
def test_ac12_an_uncited_expected_value_is_refused_citation_required(key: str) -> None:
    with pytest.raises(CitationRequired) as refused:
        clean(_input(CHECKS[key], cited=False))
    assert refused.value.code == "citation_required"


def test_the_goldens_trial_balance_balances_in_both_states() -> None:
    for case in CASES:
        totals = _balances(cast(Mapping[str, Sequence[str]], case["changes"])).totals["eoy"]
        assert totals is not None and totals[0] == totals[1]
