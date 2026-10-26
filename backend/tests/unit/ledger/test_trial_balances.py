"""SPEC-309 (TASK-320): the trial balance of record's code-computed lines, totals, leadsheets,
Δ%, candidate differences and the fail-closed layer slot."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.ledger import trial_balances as tb_module
from abacus.modules.ledger.trial_balances import (
    UNASSIGNED,
    AdjustmentEntry,
    AreaRule,
    EntryLine,
    EntrySet,
    LayerUnavailable,
    apply_entries,
    area_of_rules,
    build_lines,
    compare_lines,
    final_totals,
    layer_available,
    layer_totals,
    leadsheets,
    pct,
    totals,
    trial_balance_view,
)

CY_SNAP, PY_SNAP = uuid4(), uuid4()
D = Decimal


def _row(snap: object, code: str, name: str, debit: str, credit: str) -> SimpleNamespace:
    return SimpleNamespace(
        snapshot_id=snap,
        account_code=code,
        account_name=name,
        debit=Decimal(debit),
        credit=Decimal(credit),
    )


CY = [
    _row(CY_SNAP, "1000", "Cash", "120000.00", "0.00"),
    _row(CY_SNAP, "1200", "Receivables", "48600.00", "0.00"),
    _row(CY_SNAP, "2000", "Payables", "0.00", "68600.00"),
    _row(CY_SNAP, "4000", "Revenue", "0.00", "100000.00"),
]
PY = [
    _row(PY_SNAP, "1000", "Cash", "100000.00", "0.00"),
    _row(PY_SNAP, "2000", "Payables", "0.00", "60000.00"),
    _row(PY_SNAP, "3000", "Retained earnings", "0.00", "40000.00"),
]


def test_ac2_lines_pair_the_prior_year_and_keep_every_account() -> None:
    lines = build_lines(CY, PY, {"1000": ("Cash", "C-100")})  # type: ignore[arg-type]  # SimpleNamespace rows
    by = {line.account_code: line for line in lines}
    assert list(by) == ["1000", "1200", "2000", "3000", "4000"]
    assert by["1000"].boy == Decimal("100000.00") and by["1000"].eoy == Decimal("120000.00")
    assert by["1000"].change == Decimal("20000.00") and by["1000"].wp_ref == "C-100"
    assert by["1200"].boy == Decimal("0.00")  # new this year
    assert by["3000"].eoy == Decimal("0.00") and by["3000"].boy == Decimal("-40000.00")
    assert by["2000"].eoy == Decimal("-68600.00")
    no_prior = build_lines(CY, None, {})  # type: ignore[arg-type]  # SimpleNamespace rows
    assert all(line.boy is None and line.change is None for line in no_prior)


def test_ac4_balance_is_debits_equal_credits() -> None:
    assert totals(Decimal("168600.00"), Decimal("168600.00")).balanced
    off = totals(Decimal("168600.00"), Decimal("167040.00"))
    assert not off.balanced and off.difference == Decimal("1560.00")


def test_ac5_delta_percent_rounds_half_even_to_a_tenth() -> None:
    assert pct(Decimal("1018150"), Decimal("5102300")) == Decimal("20.0")
    assert pct(Decimal("2560000"), Decimal("13940000")) == Decimal("18.4")
    assert pct(Decimal("25"), Decimal("1000")) == Decimal("2.5")
    assert pct(Decimal("-8600"), Decimal("-60000")) == Decimal("-14.3")
    assert pct(Decimal("5"), Decimal("0")) is None


def test_ac5_leadsheets_group_by_area_and_never_drop_a_line() -> None:
    notes = {"1000": ("Cash", None), "1200": ("Receivables", None)}
    sheets = leadsheets(build_lines(CY, PY, notes))  # type: ignore[arg-type]  # SimpleNamespace rows
    assert [s.area for s in sheets] == ["Cash", "Receivables", UNASSIGNED]
    cash = sheets[0]
    assert (cash.py, cash.cy, cash.change, cash.change_pct) == (
        Decimal("100000.00"),
        Decimal("120000.00"),
        Decimal("20000.00"),
        Decimal("20.0"),
    )
    assert sheets[1].change_pct is None  # no prior balance
    assert len(sheets[2].rows) == 3  # payables, retained earnings, revenue


def test_ac7_candidates_count_changed_accounts() -> None:
    newer = [*CY[:3], _row(CY_SNAP, "4000", "Revenue", "0.00", "101560.00")]
    assert compare_lines(CY, newer) == (1, Decimal("1560.00"))  # type: ignore[arg-type]  # SimpleNamespace rows
    assert compare_lines(CY, CY[:3]) == (1, Decimal("100000.00"))  # type: ignore[arg-type]  # SimpleNamespace rows
    assert compare_lines(CY, CY) == (0, Decimal("0.00"))  # type: ignore[arg-type]  # SimpleNamespace rows


def test_ac4_adjusted_layers_fail_closed_until_a_source_registers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tb_module, "_ADJUSTMENT_SOURCES", [])
    assert layer_available("unadjusted")
    assert not layer_available("final") and not layer_available("aje")

    async def source(_tenant: object, _engagement: object) -> EntrySet:
        return EntrySet((), 0)

    tb_module.register_adjustment_source(source)
    assert layer_available("final")


def test_spec311_recorded_entries_make_aje_rje_and_final() -> None:
    lines = build_lines(CY, PY, {"1200": ("Receivables", None)})  # type: ignore[arg-type]  # SimpleNamespace rows
    aje1 = AdjustmentEntry(
        "AJE-1",
        "aje",
        (EntryLine("1200", D("15060.00"), D("0.00")), EntryLine("4000", D("0.00"), D("15060.00"))),
    )
    rje1 = AdjustmentEntry(
        "RJE-1",
        "rje",
        (EntryLine("2000", D("500.00"), D("0.00")), EntryLine("2100", D("0.00"), D("500.00"))),
    )
    out = {line.account_code: line for line in apply_entries(lines, [aje1, rje1])}
    assert out["1200"].final == D("63660.00") and out["1200"].refs == ("AJE-1",)
    assert out["4000"].aje == D("-15060.00") and out["4000"].final == D("-115060.00")
    assert out["2100"].eoy == D("0.00") and out["2100"].rje == D("-500.00")  # a new account
    assert out["1000"].final == out["1000"].eoy and out["1000"].refs == ()
    balanced = final_totals(list(out.values()))
    assert balanced.balanced and balanced.debit == D("183660.00")
    sheets = leadsheets(list(out.values()), "final")
    assert sheets[0].area == "Receivables" and sheets[0].cy == D("63660.00")
    assert leadsheets(list(out.values()))[0].cy == D("48600.00")


def test_ac1_only_people_adopt_or_annotate() -> None:
    def allowed(action: str) -> set[str]:
        return {r for r, d in RULES[action].decisions.items() if d == "allow"}

    assert "agent" not in allowed("trial_balance.adopt")
    assert "agent" not in allowed("trial_balance.annotate")
    assert "agent" not in allowed("trial_balance.read")
    assert all(RULES[a].independence for a in ("trial_balance.read", "trial_balance.adopt"))


async def test_ac14_aje_rje_and_final_answer_layer_unavailable_without_a_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A-02-T07: refused before anything is read, so never a Final equal to Unadjusted."""
    monkeypatch.setattr(tb_module, "_ADJUSTMENT_SOURCES", [])
    tenant = TenantContext(uuid4(), "human", str(uuid4()))
    for layer in ("aje", "rje", "final"):
        with pytest.raises(LayerUnavailable) as refused:
            await trial_balance_view(tenant, uuid4(), uuid4(), None, layer)
        assert refused.value.code == "layer_unavailable"


def test_a02_t07_an_annotated_area_wins_over_the_methodology_rule() -> None:
    rules = [AreaRule("Cash", "1000", "1099"), AreaRule("Liabilities", "2000", "2999")]
    lines = build_lines(CY, PY, {"1000": ("Treasury", None), "2000": (None, "L-1")}, rules)  # type: ignore[arg-type]  # SimpleNamespace rows
    by = {line.account_code: line for line in lines}
    assert by["1000"].area == "Treasury"  # the annotation
    assert (by["2000"].area, by["2000"].wp_ref) == (
        "Liabilities",
        "L-1",
    )  # the rule, the note's ref
    assert by["4000"].area is None  # no rule holds it
    assert area_of_rules("1050", rules) == "Cash" and area_of_rules("3000", rules) is None


def test_ac17_layer_totals_put_each_adjustment_on_its_own_side() -> None:
    lines = apply_entries(
        build_lines(CY, PY, {}),  # type: ignore[arg-type]  # SimpleNamespace rows
        [
            AdjustmentEntry(
                "RJE-1",
                "rje",
                (
                    EntryLine("2000", D("500.00"), D("0.00")),
                    EntryLine("2100", D("0.00"), D("500.00")),
                ),
            )
        ],
    )
    assert layer_totals(lines, "rje") == totals(D("500.00"), D("500.00"))
    assert layer_totals(lines, "aje") == totals(D("0.00"), D("0.00"))
    assert layer_totals(lines, "unadjusted") == totals(D("168600.00"), D("168600.00"))
    with pytest.raises(LayerUnavailable):
        layer_totals(lines, "budget")
