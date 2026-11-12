"""T-04-T53 (ADR-079; DEC-4513): the individual return's compute engines and the tax tools are a
red mutation scope with a floor, the p95 budgets, and survivor triage for the pure engines the
weekly run mutates first: every boundary of the residency call, the other-state credit, half-up
rounding, the QBI limit's two arms, largest-remainder sourcing, the PTET shares and IT-201's
balance due and overpayment. The figures are the Feld 2025 goldens (T-04 §4.4)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from abacus.modules.tax.compute.individual import engine, forms, k1, residency
from abacus_tools.loadtest import t04_budgets
from abacus_tools.quality import mutation
from abacus_tools.quality.mutation_floors import FILE, parse

D = Decimal
TY = 2025

# --- scopes, floors and budgets ------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "src/abacus/modules/tax/compute/individual/engine.py",
        "src/abacus/modules/tax/compute/individual/k1.py",
        "src/abacus/modules/tax/compute/individual/residency.py",
        "src/abacus/modules/tax/compute/individual/forms.py",
        "src/abacus/modules/tax/tools.py",
        "src/abacus/modules/tax/agent_tools.py",
    ],
)
def test_the_individual_engines_and_tools_are_their_own_red_scope(path: str) -> None:
    assert mutation.scope_of(path) == "tax/individual"


def test_the_entity_engines_stay_in_the_broad_compute_scope() -> None:
    assert mutation.scope_of("src/abacus/modules/tax/compute/entity/capital.py") == "compute"


def test_the_scope_has_a_floor_and_files() -> None:
    assert "tax/individual" in parse(FILE.read_text())
    red = mutation.red_files()
    assert sum(1 for p in red if mutation.scope_of(p) == "tax/individual") >= 6


def test_the_budgets_and_their_breaches() -> None:
    ok = {b.name: b.p95_ms for b in t04_budgets.BUDGETS}
    assert ok == {"review_tree": D(300), "worksheet_fields": D(250), "approve": D(500)}
    assert t04_budgets.breaches(ok) == []
    assert t04_budgets.breaches({**ok, "approve": D(501)}) == ["approve: p95 501 ms > 500 ms"]
    assert t04_budgets.breaches({"review_tree": D(1), "approve": D(1)}) == [
        "worksheet_fields: not measured"
    ]


# --- engine: rounding, parameters and stamps -----------------------------------------------------


@pytest.mark.parametrize(
    ("value", "rounded"),
    [(D("0.5"), D(1)), (D("0.49"), D(0)), (D("-0.5"), D(-1)), (D("4267.5"), D(4268))],
)
def test_whole_rounds_half_up_away_from_zero(value: Decimal, rounded: Decimal) -> None:
    assert engine.whole(value) == rounded


def test_pct_is_a_fraction() -> None:
    assert engine.pct("2.5") == D("0.025")


def test_a_year_without_parameters_raises() -> None:
    with pytest.raises(LookupError):
        engine.parameters(1999)


def test_stamps_change_with_inputs_and_not_with_key_order() -> None:
    a = engine.stamp("x", {"a": D(1), "b": [D(2)]})
    b = engine.stamp("x", {"b": [D(2)], "a": D(1)})
    c = engine.stamp("x", {"a": D(1), "b": [D(3)]})
    assert a == b
    assert a.inputs_hash != c.inputs_hash
    assert engine.stamp("y", {"a": D(1), "b": [D(2)]}).inputs_hash != a.inputs_hash


# --- residency -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("days", "abode", "elsewhere", "recommended", "conflict"),
    [
        (281, True, False, "full_year_nys_nyc", False),  # the golden
        (184, True, True, "full_year_nys_nyc", False),  # more than 183 with an abode
        (183, True, False, "full_year_nys_part_year_nyc", False),  # exactly 183 is not more
        (184, False, False, "full_year_nys_part_year_nyc", False),  # no abode
        (150, True, True, "full_year_nys_part_year_nyc", True),  # Rhinebeck: a conflict
        (150, False, False, "full_year_nys_part_year_nyc", False),
    ],
)
def test_residency_rules_at_every_boundary(
    days: int, abode: bool, elsewhere: bool, recommended: str, conflict: bool
) -> None:
    call = residency.residency_rules(residency.ResidencyFacts(days, abode, elsewhere), TY)
    assert (call.recommended, call.conflict) == (recommended, conflict)


def test_allocation_and_it225_foot() -> None:
    assert residency.allocation([D(268_400), D(6_910), D(14_820), D(307_900)]).total == D(598_030)
    assert residency.allocation([]).total == D(0)
    assert residency.it225([D(4_746), D(11_279)]).total == D(16_025)


def test_it112r_takes_the_lesser_and_refuses_a_zero_agi() -> None:
    golden = residency.it112r(D(11_279), D(41_070), D(238_623), D(615_605))
    assert (golden.limit, golden.credit) == (D(15_920), D(11_279))
    capped = residency.it112r(D(20_000), D(41_070), D(238_623), D(615_605))
    assert capped.credit == D(15_920)
    with pytest.raises(ValueError, match="positive"):
        residency.it112r(D(1), D(1), D(1), D(0))


# --- K-1 -----------------------------------------------------------------------------------------


def test_qbi_takes_the_tentative_when_below_the_ubia_arm() -> None:
    q = k1.qbi_199a(D(307_900), D(0), D(3_938_000), TY)
    assert (q.tentative, q.limit, q.deduction, q.below_limit) == (
        D(61_580),
        D(98_450),
        D(61_580),
        True,
    )


def test_qbi_takes_the_wage_arm_when_it_is_larger_and_caps_the_deduction() -> None:
    q = k1.qbi_199a(D(1_000_000), D(100_000), D(0), TY)
    # 50% x 100,000 = 50,000 > 25% x 100,000 + 0 = 25,000; 20% x 1,000,000 = 200,000 is capped.
    assert (q.limit, q.deduction, q.below_limit) == (D(50_000), D(50_000), False)


def test_qbi_at_the_limit_is_not_below_it() -> None:
    q = k1.qbi_199a(D(250_000), D(100_000), D(0), TY)
    assert (q.tentative, q.limit, q.below_limit) == (D(50_000), D(50_000), False)


def test_outside_basis_adds_the_liability_share() -> None:
    assert k1.outside_basis(D(1_912_500), D(2_762_075)).total == D(4_674_575)


def test_state_sourcing_foots_by_largest_remainder() -> None:
    s = k1.state_sourcing(D(307_900), [("IL", D("46.0")), ("CO", D("31.5")), ("NY", D("22.5"))])
    assert s.shares == (("IL", D(141_634)), ("CO", D(96_989)), ("NY", D(69_277)))
    assert sum(v for _, v in s.shares) == D(307_900)


def test_ptet_shares_round_each_half_up() -> None:
    p = k1.ptet_share([("IL", D(28_044)), ("CO", D(17_070)), ("NY", D(18_982))], TY)
    assert p.shares == (("IL", D(7_011)), ("CO", D(4_268)), ("NY", D(4_746)))
    assert p.total == D(16_025)


def test_the_sch_e_matrix_carries_the_prior_year_or_none() -> None:
    m = k1.sch_e_matrix([("box2", "Box 2", D(307_900)), ("box1", "Box 1", None)], [("box2", D(1))])
    assert [(line.field_key, line.prior_year) for line in m.lines] == [
        ("box2", D(1)),
        ("box1", None),
    ]


# --- forms ---------------------------------------------------------------------------------------


def test_a_leadsheet_line_sums_its_parts() -> None:
    line = forms.leadsheet_line("8", [D(268_400), D(6_910)])
    assert (line.total, line.parts) == (D(275_310), (D(268_400), D(6_910)))


def _it201(payments: tuple[Decimal, ...]) -> forms.It201:
    return forms.it201(
        forms.It201Inputs(
            line19_federal_agi=D(598_030),
            line20_interest_other_states=D(1_000),
            line22_ptet_addback=D(16_025),
            line34_deduction=D(8_000),
            line39_ny_tax_import=D(41_070),
            line47a_nyc_tax_import=D(22_000),
            payments=payments,
        )
    )


def test_it201_derives_its_lines() -> None:
    r = _it201((D(60_000),))
    assert (r.line33_ny_agi, r.line37_taxable, r.total_tax) == (D(615_055), D(607_055), D(63_070))
    assert (r.balance_due, r.overpayment) == (D(3_070), D(0))


def test_it201_overpaid_and_exactly_paid() -> None:
    over = _it201((D(60_000), D(5_000)))
    assert (over.balance_due, over.overpayment) == (D(0), D(1_930))
    exact = _it201((D(63_070),))
    assert (exact.balance_due, exact.overpayment) == (D(0), D(0))
