"""T-04-T20 (TASK-6617; ADR-078 as amended; T-04 §4.3; ADR-050): the Feld goldens and the compute
package's properties. Row acceptance: "Goldens assert exact Decimal equality for every Feld figure
in the screen contracts, property tests pass 10,000 examples, and an off-by-one rounding mutation
is caught." Written from the blueprint's figures, not the compute code."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st

from abacus.kernel.numeric import allocate
from abacus.modules.tax.compute.individual.forms import It201Inputs, it201
from abacus.modules.tax.compute.individual.k1 import ptet_share, state_sourcing
from abacus.modules.tax.compute.individual.residency import allocation, it112r, it225

GOLDEN: dict[str, Any] = yaml.safe_load(  # Any: the YAML document
    (Path(__file__).parent / "feld_ty2025.yaml").read_text(encoding="utf-8")
)
D = Decimal


def test_the_goldens_name_their_source_and_reviewer() -> None:
    assert "§9.8" in GOLDEN["source"]
    assert "reviewed_by" in GOLDEN


def test_it201_foots_to_the_balance_due_exactly() -> None:
    raw = GOLDEN["it201"]["inputs"]
    found = it201(
        It201Inputs(
            D(raw["line19_federal_agi"]), D(raw["line20_interest_other_states"]),
            D(raw["line22_ptet_addback"]), D(raw["line34_deduction"]),
            D(raw["line39_ny_tax_import"]), D(raw["line47a_nyc_tax_import"]),
            tuple(D(p) for p in raw["payments"]),
        )
    )  # fmt: skip
    for key, value in GOLDEN["it201"]["expect"].items():
        assert getattr(found, key) == D(value), key


@pytest.mark.parametrize("case", GOLDEN["it225"], ids=lambda c: c["name"])
def test_it225_additions(case: dict[str, Any]) -> None:  # Any: a YAML case
    assert it225([D(a) for a in case["addbacks"]]).total == D(case["expect"])


def test_it112r_resident_credit_is_the_lesser() -> None:
    g = GOLDEN["it112r"]
    found = it112r(
        D(g["other_state_tax"]), D(g["ny_tax"]), D(g["other_state_income"]), D(g["ny_agi"])
    )
    assert (found.limit, found.credit) == (D(g["expect"]["limit"]), D(g["expect"]["credit"]))


def test_ridgeline_box_2_sources_to_whole_dollars_that_foot() -> None:
    g = GOLDEN["sourcing"]
    found = dict(state_sourcing(D(g["amount"]), [(s, D(w)) for s, w in g["by_state"]]).shares)
    assert found == {s: D(v) for s, v in g["expect"].items()}
    assert sum(found.values()) == D(g["amount"])


def test_the_partner_ptet_shares() -> None:
    g = GOLDEN["ptet_share"]
    found = ptet_share([(s, D(v)) for s, v in g["entity"]], g["tax_year"])
    expect = dict(g["expect"])
    total = D(expect.pop("total"))
    assert dict(found.shares) == {s: D(v) for s, v in expect.items()}
    assert found.total == total


# --- properties ---------------------------------------------------------------------------------

AMOUNTS = st.decimals(min_value=D("0"), max_value=D("100000000"), places=0, allow_nan=False)
WEIGHTS = st.lists(
    st.decimals(min_value=D("0.1"), max_value=D("1000"), places=1, allow_nan=False),
    min_size=1,
    max_size=8,
)


def foots(split: Callable[[Decimal, Sequence[Decimal]], Sequence[Decimal]], amount: Decimal,
          weights: Sequence[Decimal]) -> bool:  # fmt: skip
    """Footing and largest remainder: the shares sum to the amount and each is within one unit
    of its exact share."""
    shares = split(amount, weights)
    if sum(shares, D(0)) != amount:
        return False
    total = sum(weights, D(0))
    return all(abs(s - amount * w / total) < 1 for s, w in zip(shares, weights, strict=True))


def _sourcing(amount: Decimal, weights: Sequence[Decimal]) -> Sequence[Decimal]:
    return [
        v for _, v in state_sourcing(amount, [(str(i), w) for i, w in enumerate(weights)]).shares
    ]


@settings(max_examples=10_000, deadline=None)
@given(AMOUNTS, WEIGHTS)
def test_sourcing_foots_and_rounds_by_largest_remainder(
    amount: Decimal, weights: list[Decimal]
) -> None:
    assert foots(_sourcing, amount, weights)


@settings(max_examples=10_000, deadline=None)
@given(st.lists(AMOUNTS, min_size=0, max_size=10))
def test_allocations_are_conserved(parts: list[Decimal]) -> None:
    assert allocation(parts).total == sum(parts, D(0))
    assert it225(parts).total == sum(parts, D(0))


@settings(max_examples=10_000, deadline=None)
@given(AMOUNTS, AMOUNTS, AMOUNTS, st.lists(AMOUNTS, max_size=4))
def test_it201_is_idempotent_and_never_both_due_and_over(
    agi: Decimal, ny: Decimal, nyc: Decimal, payments: list[Decimal]
) -> None:
    inputs = It201Inputs(agi, D(0), D(0), D(0), ny, nyc, tuple(payments))
    first, again = it201(inputs), it201(inputs)
    assert first == again
    assert first.balance_due == 0 or first.overpayment == 0
    assert first.total_tax - first.total_payments == first.balance_due - first.overpayment


def test_an_off_by_one_rounding_mutation_is_caught() -> None:
    def mutated(amount: Decimal, weights: Sequence[Decimal]) -> Sequence[Decimal]:
        shares = list(allocate(amount, list(weights), places=0))
        shares[0] += 1  # the mutation: one unit too many on the first share
        return shares

    assert not foots(mutated, D("307900"), [D("46.0"), D("31.5"), D("22.5")])
    assert foots(_sourcing, D("307900"), [D("46.0"), D("31.5"), D("22.5")])
