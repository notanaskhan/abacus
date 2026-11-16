"""A-08-T12 (TASK-8086; SPEC-657 AC-1.4; ADR P-57; DEC-5068): Granite Peak's JE selection.

The firm's criteria score the FY2026 population (236 flagged, 34 at 61 or more); a selection of
score ≥ 61 plus 6 unpredictable picks draws 34 + 6 = 40 items with a recorded seed and the frozen
`je_select/1.0` version, and the same seed re-draws the same items (re-performance).
"""

from __future__ import annotations

from functools import cache

from abacus.modules.sampling.compute import je_scoring as js
from abacus.modules.sampling.compute import je_selection as sel
from abacus_tools.synthetic.scenarios.brightwater_hale import granite_peak_gl as g

SEED = 0x2A61F3


@cache
def _scores() -> tuple[sel.Scored, ...]:
    scored = js.score(g.inputs(), g.je_entries(list(g.entries())))
    return tuple(sel.Scored(s.entry_ref, s.score) for s in scored.scores)


def _draw(seed: int = SEED) -> sel.ScoreDraw:
    return sel.select(_scores(), score_min=g.SCORE_MIN, top_n=None, unpredictable_n=6, seed=seed)


def test_ac1_4_score_61_plus_6_unpredictable_draws_40() -> None:
    selection = _draw()
    assert (selection.by_score, selection.unpredictable, len(selection.picks)) == (34, 6, 40)
    assert selection.sampler_version == "je_select/1.0"
    assert [p.position for p in selection.picks] == list(range(1, 41))
    assert all(p.reason == "risk_score" and p.score >= 61 for p in selection.picks[:34])
    assert all(p.reason == "unpredictable" for p in selection.picks[34:])
    assert len({p.entry_ref for p in selection.picks}) == 40


def test_ac1_4_the_unpredictable_picks_come_from_outside_the_by_score_part() -> None:
    selection = _draw()
    top = {p.entry_ref for p in selection.picks[:34]}
    assert not top & {p.entry_ref for p in selection.picks[34:]}


def test_ac1_4_the_recorded_seed_redraws_the_same_items() -> None:
    first, again = _draw(), _draw()
    assert first == again
    assert first.inputs_hash == again.inputs_hash and first.items_hash == again.items_hash
    other = _draw(SEED + 1)
    assert other.picks[:34] == first.picks[:34]
    assert other.picks[34:] != first.picks[34:]
    assert other.inputs_hash != first.inputs_hash
