"""T-06-T26 (TASK-8721; ADR-078 independent author; DEC-5715): E10, E11 and E12 against
`other_entities_figures.yaml` as exact Decimal cases with sources, plus the footing properties a
seeded off-by-one breaks. Lakeshore's 87.4% public support has no source table (T-06-T18): it
stays a recorded gap in the figures file, never an invented case."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
from typing import cast

import yaml
from hypothesis import given, settings
from hypothesis import strategies as st

from abacus.modules.tax.compute import exempt as e12
from abacus.modules.tax.compute import provision as e11
from abacus.modules.tax.compute import s_corp as e10

D = Decimal
FIG = cast(
    "Mapping[str, Mapping[str, object]]",
    yaml.safe_load((Path(__file__).parent / "other_entities_figures.yaml").read_text()),
)


def test_golden_e10_bluestem_splits_70_30() -> None:
    f = FIG["e10_bluestem"]
    holders = {
        k: (int(v[0]), int(v[1])) for k, v in cast(dict[str, list[int]], f["shareholders"]).items()
    }
    split = e10.per_share_per_day(D(str(f["aaa"])), holders)
    assert split == {k: D(v) for k, v in cast(dict[str, str], f["split"]).items()}


def test_golden_e11_ashford_provision_and_etr() -> None:
    f = FIG["e11_ashford"]
    rec = e11.reconcile(
        D(str(f["pretax_synthetic"])), current=D(str(f["current"])),
        deferred=D(str(f["deferred"])), federal_rate=D("0.21"), state_rate=D("0.095"), items={},
    )  # fmt: skip
    assert rec.provision == D(str(f["provision"]))
    assert rec.etr_pct == D(str(f["etr_pct"]))


def test_golden_e12_lakeshore_part_ix() -> None:
    f = FIG["e12_lakeshore"]
    # The three columns are synthetic (the handoff gives the total and the ratio only).
    lines = [
        e12.direct("1", "Program services", D("3211200"), "program"),
        e12.direct("2", "Management and general", D("602100"), "management_general"),
        e12.direct("3", "Fundraising", D("200700"), "fundraising"),
    ]
    found = e12.part_ix(lines)
    assert found.total == D(str(f["part_ix_total"]))
    assert found.program_ratio == D(str(f["program_ratio"]))


@settings(max_examples=60, deadline=None)
@given(
    st.integers(min_value=0, max_value=10_000_000),
    st.lists(st.integers(min_value=0, max_value=5_000_000), min_size=4, max_size=4),
)
def test_property_a_distribution_foots_across_its_columns(amount: int, cols: list[int]) -> None:
    balances = dict(zip(("aaa", "pti", "ep", "oaa"), map(D, cols), strict=True))
    out = e10.distribute(D(amount), balances)
    assert sum(out.values()) == D(amount)
    assert all(out[c] <= balances[c] for c in balances)


@settings(max_examples=60, deadline=None)
@given(st.integers(min_value=1, max_value=50_000_000), st.integers(min_value=1, max_value=999))
def test_property_shares_foot_to_the_item(item: int, a_shares: int) -> None:
    split = e10.per_share_per_day(D(item), {"A": (a_shares, 365), "B": (1000 - a_shares, 365)})
    assert sum(split.values()) == D(item)
