"""T-07-T09 (TASK-8036; SPEC-656 AC-5.1, AC-6.1, AC-6.2, AC-7.1, AC-11.1): the fiduciary engine.

Acceptance (the task row): "Calloway base, Changed and principal-invaded inputs reproduce the
screens' figures exactly, the tie holds, and line and branch coverage is 100%." The figures are
TXT-02 a, d and TXT-01 c; the ADR-078 goldens and properties are T-07-T10's
(`tests/golden/fiduciary/`). These tests also reach every branch of `tax/compute/fiduciary.py`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from abacus.modules.tax.compute import fiduciary as f

D = Decimal
DET = f.Determinations(
    "complex_trust",
    gains_clause_ref="Art. II",
    distribution_clause_ref="Art. III(a)",
    retained_clause_ref="Art. IV(a)",
)
LINES = (
    f.FaiLine("interest", "interest", D("107500")),
    f.FaiLine("dividends", "ordinary_dividends", D("322500"), qualified=D("258000")),
)
FEES = (f.TrustExpense("trustee_fees", D("30000"), "principal", clause_ref="Art. V(c)"),)


def _distributions(theo: str = "80000") -> tuple[f.Distribution, ...]:
    return (
        f.Distribution("nora", "Nora Calloway", date(2025, 6, 30), D("80000")),
        f.Distribution("nora", "Nora Calloway", date(2025, 12, 15), D("80000")),
        f.Distribution("theo", "Theo Calloway", date(2025, 12, 15), D(theo)),
    )


def _run(
    distributions: tuple[f.Distribution, ...] | None = None,
    *,
    det: f.Determinations = DET,
    lines: tuple[f.FaiLine, ...] = LINES,
    expenses: tuple[f.TrustExpense, ...] = FEES,
) -> f.FiduciaryResult:
    return f.compute(
        f.FiduciaryInputs(
            2025,
            det,
            lines,
            expenses,
            _distributions() if distributions is None else distributions,
        )
    )


def _boxes(result: f.FiduciaryResult) -> list[tuple[str, str, str, str]]:
    return [(a.name, str(a.box_1), str(a.box_2a), str(a.box_2b)) for a in result.allocations]


def test_ac61_calloway_base_reproduces_txt02_a() -> None:
    r = _run()
    assert r.fai == D("430000.00")
    assert r.expense_by_character == {
        "interest": D("7500.00"),
        "ordinary_dividends": D("22500.00"),
    }
    assert (r.dni, r.dni_qualified) == (D("400000.00"), D("240000.00"))
    assert r.dni_by_character == {"interest": D("100000.00"), "ordinary_dividends": D("300000.00")}
    assert (r.distributions, r.idd, r.retained_dni) == (
        D("240000.00"), D("240000.00"), D("160000.00"),
    )  # fmt: skip
    assert _boxes(r) == [
        ("Nora Calloway", "40000.00", "120000.00", "96000.00"),
        ("Theo Calloway", "20000.00", "60000.00", "48000.00"),
    ]
    assert [a.share for a in r.allocations] == [D("0.666667"), D("0.333333")]
    assert (r.exemption, r.taxable_income) == (D("100"), D("159900.00"))
    assert r.tie and r.fai_not_distributed == D("190000.00")
    assert "fai_not_distributed:190000.00" in r.notes


def test_ac71_theo_100000_reproduces_txt02_d() -> None:
    r = _run(_distributions("100000"))
    assert (r.distributions, r.idd, r.retained_dni, r.taxable_income) == (
        D("260000.00"), D("260000.00"), D("140000.00"), D("139900.00"),
    )  # fmt: skip
    assert [a.share for a in r.allocations] == [D("0.615385"), D("0.384615")]
    assert _boxes(r)[1] == ("Theo Calloway", "25000.00", "75000.00", "60000.00")
    assert r.tie


def test_ac51_principal_invaded_reproduces_txt01_c() -> None:
    invaded = (
        *_distributions(),
        f.Distribution(
            "theo", "Theo Calloway", date(2025, 9, 1), D("25000"), "principal", "Art. IV(b)"
        ),
    )
    r = _run(invaded)
    assert (r.distributions, r.principal_distributions) == (D("265000.00"), D("25000.00"))
    assert (r.idd, r.retained_dni) == (D("265000.00"), D("135000.00"))
    assert [(a.name, a.distributions) for a in r.allocations] == [
        ("Nora Calloway", D("160000.00")),
        ("Theo Calloway", D("105000.00")),
    ]
    assert "principal_invaded:25000.00" in r.notes and r.tie


def test_ac62_gains_stay_out_of_dni_without_a_clause_and_in_with_one() -> None:
    gains = (*LINES, f.FaiLine("gains", "capital_gains", D("50000"), to_principal=True))
    out = _run(lines=gains)
    assert out.dni == D("400000.00")
    assert out.taxable_income == D("209900.00")  # the trust pays on the gains it keeps
    chips = {row.key: row.clause_ref for row in out.tree[2].children}
    assert chips["dni.capital_gains_excluded"] == "Art. II"
    inside = _run(
        lines=gains,
        det=f.Determinations("complex_trust", gains_in_dni=True, gains_clause_ref="II"),
    )
    assert inside.dni == D("450000.00") and "4a" in inside.allocations[0].box_other
    assert inside.tie


def test_ac62_clause_chips_only_where_the_instrument_governs() -> None:
    tree = {row.key: row for row in _run().tree}
    assert tree["expenses"].children[0].clause_ref == "Art. V(c)"
    assert tree["distributions"].clause_ref == "Art. III(a)"
    assert tree["retained_dni"].clause_ref == "Art. IV(a)"
    assert tree["fai"].clause_ref is None and tree["taxable_income"].clause_ref is None


def test_tax_exempt_interest_carries_out_but_is_never_deducted() -> None:
    lines = (*LINES, f.FaiLine("munis", "tax_exempt_interest", D("40000")))
    r = _run(lines=lines)
    assert r.exempt_carried_out > 0
    assert r.idd == (r.distributions - r.exempt_carried_out)
    assert all("14A" in a.box_other for a in r.allocations)
    assert r.deductible_expenses < D("30000.00")  # the exempt share of fees is not deductible
    assert r.tie


def test_other_income_lands_in_box_5() -> None:
    lines = (*LINES, f.FaiLine("royalty", "other", D("10000")))
    r = _run(lines=lines)
    assert all("5" in a.box_other for a in r.allocations) and r.tie


def test_a_simple_trust_is_deemed_to_distribute_all_fai_and_takes_300() -> None:
    simple = f.Determinations("simple_trust")
    r = _run(det=simple)
    assert r.exemption == D("300")
    assert r.idd == D("400000.00")  # min(FAI 430,000, DNI 400,000)


def test_an_estate_takes_600_and_income_charged_fees_reduce_fai() -> None:
    estate = f.Determinations("estate")
    fees = (f.TrustExpense("fees", D("30000"), "income"),)
    r = _run(det=estate, expenses=fees)
    assert (r.exemption, r.fai) == (D("600"), D("400000.00"))


def test_nothing_distributed_retains_all_dni() -> None:
    r = _run(())
    assert (r.idd, r.retained_dni, r.allocations, r.tie) == (D("0.00"), D("400000.00"), (), True)
    assert r.exempt_carried_out == D("0.00")


def test_a_non_deductible_expense_and_no_qualified_dividends() -> None:
    lines = (f.FaiLine("dividends", "ordinary_dividends", D("100000")),)
    fees = (f.TrustExpense("penalty", D("1000"), "principal", deductible=False),)
    r = _run(lines=lines, expenses=fees)
    assert (r.dni, r.dni_qualified) == (D("100000.00"), D("0.00"))
    assert all(a.box_2b == 0 for a in r.allocations)


def test_no_income_means_no_dni_and_nothing_carried_out() -> None:
    r = _run(lines=())
    assert (r.fai, r.dni, r.idd) == (D("0.00"), D("0.00"), D("0.00"))


def test_ac111_the_65_day_window() -> None:
    assert f.sixty_five_day_window(2025) == (date(2026, 1, 1), date(2026, 3, 6))
    assert f.sixty_five_day_window(2026) == (date(2027, 1, 1), date(2027, 3, 6))
    assert f.sixty_five_day_window(2027) == (date(2028, 1, 1), date(2028, 3, 5))


def test_the_same_inputs_give_the_same_hash_and_a_change_another() -> None:
    assert _run().inputs_hash == _run().inputs_hash
    assert _run().inputs_hash != _run(_distributions("100000")).inputs_hash
    assert (_run().engine_name, _run().engine_version) == ("tax.fiduciary", "1")


def test_parameters() -> None:
    assert f.parameters(2025).top_bracket_threshold == D("15650")
    assert f.parameters(2027).top_bracket_threshold is None
    with pytest.raises(LookupError):
        f.parameters(1999)
    with pytest.raises(ValueError, match=r"exemption\.estate"):
        f.parse_parameters(
            {"tax_year": 2025, "version": 1, "exemption": {"estate": None},
             "sixty_five_day_election_days": 65, "top_bracket_threshold": None,
             "niit_rate_pct": "3.8"}
        )  # fmt: skip
    with pytest.raises(ValueError, match="not a decimal"):
        f.parse_parameters(
            {"tax_year": 2025, "version": 1,
             "exemption": {"estate": True, "simple_trust": "300", "complex_trust": "100"},
             "sixty_five_day_election_days": 65, "top_bracket_threshold": None,
             "niit_rate_pct": "3.8"}
        )  # fmt: skip
