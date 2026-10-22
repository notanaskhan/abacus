"""F-04-T12 (F-04.27; ADR-078; ch. 03 §10.3): scenario-level golden figures for Brightwater Hale.

Each case in `brightwater_hale/*.yaml` carries `inputs`, `expected`, `source` and `reviewed_by`,
transcribed from the epic and the blueprint, never from the code. Every number is read as YAML
text and compared as `Decimal` with exact equality; a float never appears. A case with a
`scenario` probe is also checked against the scenario package (`abacus_tools.synthetic.scenarios.
brightwater_hale`); the others are arithmetic identities that document the source figure for the
loaded-state golden (F-04-T29). Hypothesis checks footing.

A source conflict (the scenario disagrees with the spec or blueprint) is recorded as an issue
for AY and never "fixed" here: the YAML keeps the spec figure and only that case is marked
xfail(strict=True) with the issue reference.
"""

from __future__ import annotations

import random
import re
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import cast

import pytest
import yaml
from hypothesis import given
from hypothesis import strategies as st

from abacus_tools.synthetic.scenarios.brightwater_hale import build
from abacus_tools.synthetic.scenarios.brightwater_hale.holdouts import held_out
from abacus_tools.synthetic.scenarios.brightwater_hale.people import SEATS

HERE = Path(__file__).parent / "brightwater_hale"
FILES = ("practice_counts", "audits", "northwind", "granite_peak")
REQUIRED = frozenset({"id", "kind", "inputs", "expected", "source", "reviewed_by"})
ALLOWED = REQUIRED | {"scenario", "parameter_set"}
_NUMERIC_TAGS = frozenset({"tag:yaml.org,2002:int", "tag:yaml.org,2002:float"})


class _TextNumbers(yaml.SafeLoader):
    """A SafeLoader that leaves every number as its source text, so Decimal never sees a float."""


_TextNumbers.yaml_implicit_resolvers = {
    first: [(tag, rx) for tag, rx in resolvers if tag not in _NUMERIC_TAGS]
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.copy().items()
}

Figures = dict[str, Decimal]


def parse(text: str) -> object:
    """`yaml.safe_load`, with numbers kept as text (the loader is a SafeLoader subclass)."""
    loader = _TextNumbers(text)
    try:
        return loader.get_single_data()
    finally:
        loader.dispose()


@dataclass(frozen=True)
class Case:
    file: str
    id: str
    kind: str
    inputs: Mapping[str, object]
    expected: Mapping[str, object]
    source: str
    reviewed_by: str
    scenario: Mapping[str, object] | None

    @property
    def name(self) -> str:
        return f"{self.file}::{self.id}"


def dec(value: object) -> Decimal:
    """A YAML scalar as an exact Decimal; anything but number text is a fixture error."""
    if not isinstance(value, str) or not re.fullmatch(r"-?\d+(\.\d+)?", value):
        raise TypeError(f"expected number text, got {value!r}")
    return Decimal(value)


def figures(raw: object) -> Figures:
    """A YAML mapping of label → number text as exact Decimals."""
    if not isinstance(raw, Mapping):
        raise TypeError(f"expected a mapping, got {raw!r}")
    return {str(k): dec(v) for k, v in cast(Mapping[object, object], raw).items()}


def load(file: str) -> list[Case]:
    doc = cast(dict[str, object], parse((HERE / f"{file}.yaml").read_text()))
    assert doc["golden"] == f"brightwater_hale/{file}"
    cases: list[Case] = []
    for raw in cast(list[dict[str, object]], doc["cases"]):
        keys = set(raw)
        assert REQUIRED <= keys <= ALLOWED, f"{file}: case keys {sorted(keys)}"
        assert str(raw["source"]).strip() and str(raw["reviewed_by"]).strip()
        cases.append(
            Case(
                file,
                str(raw["id"]),
                str(raw["kind"]),
                cast(Mapping[str, object], raw["inputs"]),
                cast(Mapping[str, object], raw["expected"]),
                str(raw["source"]),
                str(raw["reviewed_by"]),
                cast(Mapping[str, object] | None, raw.get("scenario")),
            )
        )
    return cases


CASES = [case for file in FILES for case in load(file)]
SCENARIO_CASES = [case for case in CASES if case.scenario is not None]


def by_id(case_id: str) -> Case:
    return next(c for c in CASES if c.id == case_id)


# --- the arithmetic, independent of the code under test --------------------------------------


def foot(parts: list[Decimal]) -> Decimal:
    total = Decimal(0)
    for part in parts:
        total += part
    return total


def round_to(amount: Decimal, increment: Decimal) -> Decimal:
    """Nearest multiple of `increment`, halves up (A-04 AC3.1: 252,186 → 252,200)."""
    return (amount / increment).quantize(Decimal(1), rounding=ROUND_HALF_UP) * increment


def compute_sum(inputs: Mapping[str, object]) -> Figures:
    return {"total": foot(list(figures(inputs["terms"]).values()))}


def compute_materiality(inputs: Mapping[str, object]) -> Figures:
    i = figures(inputs)
    overall = round_to(i["benchmark"] * i["rate"], i["increment"])
    return {"overall": overall, "pm": overall * i["pm_rate"], "ct": overall * i["ct_rate"]}


def compute_lost_earnings(inputs: Mapping[str, object]) -> Figures:
    i = figures(inputs)
    growth = (1 + i["annual_rate"] / i["day_count"]) ** int(i["days"]) - 1
    amount = (i["principal"] * growth).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {"amount": amount}


def compute_progress(inputs: Mapping[str, object]) -> Figures:
    match = re.fullmatch(r"(\d+) of (\d+)", str(inputs["text"]))
    assert match is not None
    return {"done": Decimal(match[1]), "of": Decimal(match[2])}


Row = tuple[str, str, str, str, str]


def rows_of(inputs: Mapping[str, object]) -> list[Row]:
    return [
        cast(Row, tuple(str(x) for x in row)) for row in cast(list[list[object]], inputs["rows"])
    ]


def tally(inputs: Mapping[str, object], rows: list[Row]) -> dict[str, Figures]:
    groups = cast(Mapping[str, str], inputs["groups"])
    by_group = Counter(groups[kind] for _, _, kind, _, _ in rows)
    by_phase = Counter(phase for _, _, _, phase, _ in rows)
    return {
        "total": {"total": Decimal(len(rows))},
        "by_group": {k: Decimal(v) for k, v in by_group.items()},
        "by_phase": {k: Decimal(v) for k, v in by_phase.items()},
    }


COMPUTE: dict[str, Callable[[Mapping[str, object]], Figures]] = {
    "sum": compute_sum,
    "materiality": compute_materiality,
    "lost_earnings": compute_lost_earnings,
    "progress": compute_progress,
}


@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_golden_case_holds_by_exact_decimal_equality(case: Case) -> None:
    if case.kind == "tally":
        actual = tally(case.inputs, rows_of(case.inputs))
        assert actual["total"] == {"total": dec(case.expected["total"])}
        assert actual["by_group"] == figures(case.expected["by_group"])
        assert actual["by_phase"] == figures(case.expected["by_phase"])
        return
    expected = figures(case.expected)
    actual = COMPUTE[case.kind](case.inputs)
    assert expected.keys() <= actual.keys(), f"{case.name}: unknown expected keys"
    assert {k: actual[k] for k in expected} == expected


# --- the scenario package, read through its public functions ----------------------------------


def _counted(counter: Mapping[str, int]) -> Figures:
    out = {k: Decimal(v) for k, v in counter.items()}
    return out | {"total": foot(list(out.values()))}


def probe_clients_by_origin(_: Mapping[str, object]) -> Figures:
    return _counted(Counter(c.origin for c in build().clients))


def probe_seats_by_kind(_: Mapping[str, object]) -> Figures:
    return _counted(Counter("named" if s.named else "generator" for s in build().seats))


def probe_seats_by_office(_: Mapping[str, object]) -> Figures:
    return _counted(Counter(s.office for s in build().seats))


def probe_offices_by_kind(_: Mapping[str, object]) -> Figures:
    return _counted(Counter("hq" if o.hq else "branch" for o in build().offices))


def probe_clients_less_holdout(args: Mapping[str, object]) -> Figures:
    holdout = str(args["holdout"])
    before = build().clients
    names = held_out((holdout,))
    after = build(holdouts=(holdout,)).clients
    return {
        "before": Decimal(len(before)),
        "held_out": -Decimal(sum(c.name in names for c in before)),
        "total": Decimal(len(after)),
    }


def probe_audit_engagement_clients(args: Mapping[str, object]) -> Figures:
    """Each §9.7 row's client (by name, or a plan entity) exists once, with the EP and attest."""
    case = by_id("audits-27-roster-rows")
    groups = cast(Mapping[str, str], case.inputs["groups"])
    attest_groups = {str(g) for g in cast(list[object], case.inputs["attest_groups"])}
    clients = build().clients
    resolved = ep_matches = attest_matches = 0
    del args  # the rows come from the case itself
    for _, engagement, kind, _, ep in rows_of(case.inputs):
        found = [c for c in clients if engagement == c.name or engagement in c.entities]
        if len(found) != 1:
            continue
        resolved += 1
        ep_matches += found[0].partner == ep
        attest_matches += found[0].attest == (groups[kind] in attest_groups)
    return {
        "resolved": Decimal(resolved),
        "ep_matches": Decimal(ep_matches),
        "attest_matches": Decimal(attest_matches),
    }


PROBES: dict[str, Callable[[Mapping[str, object]], Figures]] = {
    "clients_by_origin": probe_clients_by_origin,
    "seats_by_kind": probe_seats_by_kind,
    "seats_by_office": probe_seats_by_office,
    "offices_by_kind": probe_offices_by_kind,
    "clients_less_holdout": probe_clients_less_holdout,
    "audit_engagement_clients": probe_audit_engagement_clients,
}


@pytest.mark.parametrize("case", SCENARIO_CASES, ids=[c.name for c in SCENARIO_CASES])
def test_scenario_package_agrees_with_the_golden(case: Case) -> None:
    scenario = case.scenario
    assert scenario is not None
    if "expected" in scenario:
        expected = figures(scenario["expected"])
    else:  # a sum: the scenario must give the same parts and the same total
        expected = figures(case.inputs["terms"]) | figures(case.expected)
    assert PROBES[str(scenario["probe"])](scenario) == expected


def test_every_kind_and_probe_is_known() -> None:
    assert {c.kind for c in CASES} <= {*COMPUTE, "tally"}
    assert {str(c.scenario["probe"]) for c in SCENARIO_CASES if c.scenario} <= PROBES.keys()
    assert len({c.name for c in CASES}) == len(CASES)


def test_numbers_are_never_parsed_as_floats() -> None:
    doc = parse("a: 0.015\nb: 16812400\nc: -57450")
    assert doc == {"a": "0.015", "b": "16812400", "c": "-57450"}


def test_scenario_seat_list_is_the_one_the_golden_reads() -> None:
    assert build().seats == SEATS


# --- footing properties (Hypothesis) -----------------------------------------------------------

amounts = st.decimals(
    min_value=Decimal("-100000000"),
    max_value=Decimal("100000000"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)


@given(st.lists(amounts, max_size=40), st.randoms(use_true_random=False))
def test_property_footing_is_order_free_and_splits(
    parts: list[Decimal], rnd: random.Random
) -> None:
    total = foot(parts)
    shuffled = list(parts)
    rnd.shuffle(shuffled)
    assert foot(shuffled) == total
    cut = len(parts) // 2
    assert foot(parts[:cut]) + foot(parts[cut:]) == total
    assert compute_sum({"terms": {str(i): str(p) for i, p in enumerate(parts)}}) == {
        "total": total
    }


@given(
    st.decimals(min_value=Decimal(0), max_value=Decimal("10000000000"), places=2),
    st.integers(min_value=1, max_value=100).map(lambda n: Decimal(n) / 1000),
)
def test_property_materiality_rounds_and_foots(benchmark: Decimal, rate: Decimal) -> None:
    out = compute_materiality(
        {
            "benchmark": str(benchmark),
            "rate": str(rate),
            "increment": "100",
            "pm_rate": "0.75",
            "ct_rate": "0.05",
        }
    )
    overall = out["overall"]
    assert overall % 100 == 0
    assert abs(overall - benchmark * rate) <= 50
    # PM and CT are exact parts of the rounded overall: no rounding residue to lose.
    assert out["pm"] + (overall - out["pm"]) == overall
    assert out["pm"] * 4 == overall * 3
    assert out["ct"] * 20 == overall
    assert out["ct"] <= out["pm"] <= overall


@given(st.sets(st.integers(min_value=0, max_value=26)))
def test_property_any_subset_of_the_27_audits_foots_by_type_and_stage(chosen: set[int]) -> None:
    case = by_id("audits-27-roster-rows")
    rows = rows_of(case.inputs)
    picked = [rows[i] for i in sorted(chosen)]
    rest = [rows[i] for i in range(len(rows)) if i not in chosen]
    for subset in (picked, rest):
        counts = tally(case.inputs, subset)
        n = counts["total"]["total"]
        assert foot(list(counts["by_group"].values())) == n
        assert foot(list(counts["by_phase"].values())) == n
    assert tally(case.inputs, picked)["total"]["total"] + tally(case.inputs, rest)["total"][
        "total"
    ] == Decimal(len(rows))
