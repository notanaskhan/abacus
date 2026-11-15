"""T-07-T10 (TASK-8037; ADR-078; SPEC-656 AC-5.1, AC-6.1, AC-7.1, AC-9.2, AC-11.1): the fiduciary
engine against the Calloway goldens (`calloway_ty2025.yaml`, transcribed from the epic and the
handoff, each case citing its screen and state), and its properties: the K-1 boxes foot to IDD for
any distribution set, DNI is conserved (carried out + retained = DNI), and the engine is
idempotent (the same inputs, the same result and hash).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import yaml
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from abacus.modules.tax.compute import fiduciary as f

GOLDEN: dict[str, Any] = yaml.safe_load(  # Any: the YAML document
    (Path(__file__).parent / "calloway_ty2025.yaml").read_text(encoding="utf-8")
)
D = Decimal
CASES = GOLDEN["cases"]


def _inputs(**changes: Any) -> f.FiduciaryInputs:  # noqa: ANN401
    raw = GOLDEN["inputs"]
    base = f.FiduciaryInputs(
        tax_year=raw["tax_year"],
        determinations=f.Determinations(raw["entity_type"], gains_clause_ref="Art. II"),
        fai_lines=tuple(
            f.FaiLine(x["key"], x["character"], D(x["amount"]), D(x.get("qualified", "0")))
            for x in raw["fai_lines"]
        ),
        expenses=tuple(
            f.TrustExpense(x["key"], D(x["amount"]), x["charged_to"], clause_ref=x["clause_ref"])
            for x in raw["expenses"]
        ),
        distributions=tuple(
            f.Distribution(x["beneficiary"], x["name"], date.fromisoformat(x["paid_on"]),
                           D(x["amount"]))
            for x in raw["distributions"]
        ),
    )  # fmt: skip
    return replace(base, **changes)


def _pct(share: Decimal) -> str:
    return str((share * 100).quantize(D("0.1"), ROUND_HALF_UP))


def _by(result: f.FiduciaryResult) -> dict[str, f.BeneficiaryAllocation]:
    return {a.beneficiary: a for a in result.allocations}


def test_golden_base_txt02_a() -> None:
    case = CASES["base"]
    r = f.compute(_inputs())
    assert r.fai == D(case["fai"])
    assert r.expense_by_character == {k: D(v) for k, v in case["expense_by_character"].items()}
    assert (r.dni, r.dni_qualified) == (D(case["dni"]), D(case["dni_qualified"]))
    assert r.dni_by_character == {k: D(v) for k, v in case["dni_by_character"].items()}
    assert (r.distributions, r.idd) == (D(case["distributions"]), D(case["idd"]))
    for key, boxes in case["boxes"].items():
        a = _by(r)[key]
        assert (a.box_1, a.box_2a, a.box_2b, a.dni_allocated) == tuple(
            D(boxes[k]) for k in ("box_1", "box_2a", "box_2b", "dni")
        )
        assert _pct(a.share) == case["shares_pct"][key]
    for box, total in case["totals"].items():
        assert sum((getattr(a, box) for a in r.allocations), D(0)) == D(total)
    assert (r.retained_dni, r.exemption, r.taxable_income) == (
        D(case["retained_dni"]), D(case["exemption"]), D(case["taxable_income"]),
    )  # fmt: skip
    assert r.fai_not_distributed == D(case["fai_not_distributed"])
    assert r.tie


def test_golden_theo_changed_txt02_d() -> None:
    case = CASES["theo_changed"]
    base = _inputs()
    edited = tuple(
        replace(d, amount=D(case["theo_dec_15"])) if d.beneficiary == "theo" else d
        for d in base.distributions
    )
    r = f.compute(replace(base, distributions=edited))
    assert (r.distributions, r.idd) == (D(case["distributions"]), D(case["idd"]))
    assert {k: _pct(a.share) for k, a in _by(r).items()} == case["shares_pct"]
    theo = _by(r)["theo"]
    assert (theo.box_1, theo.box_2a, theo.box_2b, theo.dni_allocated) == tuple(
        D(case["boxes"]["theo"][k]) for k in ("box_1", "box_2a", "box_2b", "dni")
    )
    assert (r.retained_dni, r.taxable_income) == (
        D(case["retained_dni"]), D(case["taxable_income"]),
    )  # fmt: skip


def test_golden_principal_invaded_txt01_c() -> None:
    case = CASES["principal_invaded"]
    extra = case["theo_principal"]
    base = _inputs()
    r = f.compute(
        replace(
            base,
            distributions=(
                *base.distributions,
                f.Distribution("theo", "Theo Calloway", date.fromisoformat(extra["paid_on"]),
                               D(extra["amount"]), "principal", extra["clause_ref"]),
            ),
        )
    )  # fmt: skip
    assert (r.distributions, r.idd, r.retained_dni) == (
        D(case["distributions"]), D(case["idd"]), D(case["retained_dni"]),
    )  # fmt: skip
    assert {k: a.distributions for k, a in _by(r).items()} == {
        k: D(v) for k, v in case["carried"].items()
    }


def test_golden_by_character_txt02_c() -> None:
    case = CASES["by_character"]
    r = f.compute(_inputs())
    assert r.dni_by_character["interest"] == D(case["interest"])
    assert r.dni_by_character["ordinary_dividends"] == D(case["ordinary_dividends"])
    assert r.dni_qualified == D(case["qualified"])
    # The trust's share of each character is what it keeps: DNI less what Nora and Theo carry.
    kept = {
        "box_1": r.dni_by_character["interest"] - sum((a.box_1 for a in r.allocations), D(0)),
        "box_2a": r.dni_by_character["ordinary_dividends"]
        - sum((a.box_2a for a in r.allocations), D(0)),
        "box_2b": r.dni_qualified - sum((a.box_2b for a in r.allocations), D(0)),
    }
    assert kept == {k: D(v) for k, v in case["trust_share"].items()}


def test_golden_simple_trust_variant() -> None:
    case = CASES["simple_trust"]
    r = f.compute(_inputs(determinations=f.Determinations("simple_trust")))
    assert (r.exemption, r.idd, r.retained_dni) == (
        D(case["exemption"]), D(case["idd"]), D(case["retained_dni"]),
    )  # fmt: skip


def test_golden_gains_in_dni_variant() -> None:
    case = CASES["gains_in_dni"]
    base = _inputs()
    lines = (
        *base.fai_lines,
        f.FaiLine("gains", "capital_gains", D(case["gains"]), to_principal=True),
    )
    inside = f.compute(
        replace(base, fai_lines=lines, determinations=f.Determinations("complex_trust", True))
    )
    outside = f.compute(replace(base, fai_lines=lines))
    assert inside.dni == D(case["dni"]) and outside.dni == D(case["gains_out_dni"])
    assert outside.taxable_income == D(case["gains_out_taxable_income"])


def test_golden_65_day_windows() -> None:
    for year, end in GOLDEN["windows"].items():
        if year == "cites":
            continue
        assert f.sixty_five_day_window(int(year)) == (
            date(int(year) + 1, 1, 1),
            date.fromisoformat(end),
        )


# --- properties ---------------------------------------------------------------------------------

_amount = st.integers(min_value=0, max_value=500_000).map(lambda n: D(n))
_distribution = st.tuples(
    st.sampled_from(["nora", "theo", "ivy"]), _amount, st.sampled_from(["income", "principal"])
)


def _with(rows: list[tuple[str, Decimal, str]]) -> f.FiduciaryResult:
    distributions = tuple(
        f.Distribution(who, who.title(), date(2025, 12, 15), amount, source)  # type: ignore[arg-type]
        for who, amount, source in rows
    )
    return f.compute(_inputs(distributions=distributions))


@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(st.lists(_distribution, max_size=8))
def test_property_k1_boxes_foot_to_idd_for_any_distribution_set(
    rows: list[tuple[str, Decimal, str]],
) -> None:
    r = _with(rows)
    assert sum((a.dni_allocated for a in r.allocations), D(0)) == r.idd
    assert sum((a.box_1 + a.box_2a for a in r.allocations), D(0)) == r.idd
    assert all(a.box_2b <= a.box_2a for a in r.allocations)
    assert r.tie


@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(st.lists(_distribution, max_size=8))
def test_property_dni_is_conserved(rows: list[tuple[str, Decimal, str]]) -> None:
    r = _with(rows)
    assert r.idd + r.exempt_carried_out + r.retained_dni == r.dni
    assert r.idd <= min(r.distributions, r.dni)


@settings(max_examples=50, deadline=None)
@given(st.lists(_distribution, max_size=6))
def test_property_the_engine_is_idempotent(rows: list[tuple[str, Decimal, str]]) -> None:
    first, second = _with(rows), _with(rows)
    assert first == second and first.inputs_hash == second.inputs_hash
