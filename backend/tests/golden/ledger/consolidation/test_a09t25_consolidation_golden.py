# ac-test-author: ayushkbhatia
"""A-09-T25 (TASK-8413; ADR-078: implementer N, author AY; SPEC-658 F3; AUD-33 a). Goldens for the
consolidation engine on Harlow & Pike FY2026 and Hypothesis properties: every row foots
(consolidated = entities + eliminations), every column nets to zero, and removing any posted
elimination from a level breaks a property. The fixture names its CPA review memo."""

from __future__ import annotations

import importlib.util
from decimal import Decimal as D
from pathlib import Path

import yaml
from hypothesis import given, settings
from hypothesis import strategies as st

from abacus.modules.ledger.compute import consolidation as c

# The engine's Harlow & Pike inputs live with A-09-T19's tests (one copy of the seed figures).
_SPEC = importlib.util.spec_from_file_location(
    "a09t19_inputs",
    Path(__file__).parents[3] / "unit" / "ledger" / "test_a09t19_consolidation_engine.py",
)
assert _SPEC is not None and _SPEC.loader is not None
_INPUTS = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_INPUTS)
ELIMS, ENTITIES, LEVEL2, TB = _INPUTS.ELIMS, _INPUTS.ENTITIES, _INPUTS.LEVEL2, _INPUTS.TB

GOLDEN = yaml.safe_load((Path(__file__).parent / "harlow_pike_fy2026.yaml").read_text())


def _tbs() -> dict[str, list[c.TbLine]]:
    return {
        e: [c.TbLine(cap, sec, D(amounts[i])) for cap, sec, amounts in TB]  # type: ignore[arg-type] -- the section literals
        for i, e in enumerate(ENTITIES)
    }


def _elims(skip: str | None = None) -> list[c.Elimination]:
    return [
        c.Elimination(
            code, level, tuple(c.EliminationLine(cap, D(d), D(cr)) for cap, d, cr in lines)
        )
        for code, level, lines in ELIMS
        if code != skip
    ]


def test_the_fixture_references_the_cpa_memo() -> None:
    assert GOLDEN["reviewed_by"]["memo_id"].startswith("GRM-A09-")
    assert GOLDEN["reviewed_by"]["status"] in {"pending_cpa_signature", "signed"}


def test_level_1_goldens() -> None:
    g = GOLDEN["level_1"]
    level = c.consolidate(_tbs(), ENTITIES, level=1, eliminations=_elims())
    assert level.total_assets == D(g["total_assets"])
    assert level.net_income == D(g["net_income"])
    assert level.eliminations_posted == g["eliminations_posted"]
    asset_elims = sum(
        (
            ln.credit - ln.debit
            for e in _elims()
            for ln in e.lines
            if any(r.caption == ln.caption and r.section == "assets" for r in level.rows)
        ),
        D(0),
    )
    assert asset_elims == D(g["asset_eliminations"])
    debits = sum(
        (r.amount(c.CONSOLIDATED) for r in level.rows if r.amount(c.CONSOLIDATED) > 0), D(0)
    )
    credits = -sum(
        (r.amount(c.CONSOLIDATED) for r in level.rows if r.amount(c.CONSOLIDATED) < 0), D(0)
    )
    assert debits == credits
    total = sum((D(v) for _, v in g["attribution_assets"]), D(0))
    assert total == D(g["total_assets"])


def test_level_2_goldens() -> None:
    g = GOLDEN["level_2"]
    level = c.consolidate(_tbs(), LEVEL2, level=2, eliminations=_elims())
    assert level.total_assets == D(g["total_assets"])
    assert level.net_income == D(g["net_income"])
    assert level.eliminations_posted == g["eliminations_posted"]


def _foots(level: c.Level, members: tuple[str, ...]) -> bool:
    return all(
        r.amount(c.CONSOLIDATED)
        == sum((r.amount(m) for m in members), D(0)) + r.amount(c.ELIMINATIONS)
        for r in level.rows
    )


@settings(max_examples=30, deadline=None)
@given(st.sampled_from([code for code, _, _ in ELIMS]))
def test_removing_any_elimination_breaks_a_property(code: str) -> None:
    full = c.consolidate(_tbs(), ENTITIES, level=1, eliminations=_elims())
    less = c.consolidate(_tbs(), ENTITIES, level=1, eliminations=_elims(skip=code))
    assert _foots(less, ENTITIES)  # rows still foot by construction
    changed = (
        less.total_assets != full.total_assets
        or less.net_income != full.net_income
        or less.eliminations_posted != full.eliminations_posted
    )
    assert changed, code


@settings(max_examples=30, deadline=None)
@given(st.integers(min_value=1, max_value=10_000_000))
def test_columns_net_to_zero_for_any_balanced_shift(shift: int) -> None:
    tbs = _tbs()
    # A balanced reclass inside one entity (debit one caption, credit another) keeps every column
    # netting to zero and the consolidated rows footing.
    rows = tbs["manufacturing"]
    rows[0] = c.TbLine(rows[0].caption, rows[0].section, rows[0].amount + D(shift))
    rows[1] = c.TbLine(rows[1].caption, rows[1].section, rows[1].amount - D(shift))
    level = c.consolidate(tbs, ENTITIES, level=1, eliminations=_elims())
    assert level.ties and all(v == 0 for v in level.column_totals.values())
    assert _foots(level, ENTITIES)
