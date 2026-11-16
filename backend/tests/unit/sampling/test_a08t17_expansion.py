"""A-08-T17: an approved expansion appends; the first items keep their positions (AC-3.3)."""

from __future__ import annotations

import pytest

from abacus.modules.sampling import expansions
from abacus.modules.sampling.compute import je_selection as sel

SCORES = [sel.Scored(f"JE-26-{17900 + n}", (n * 37) % 11) for n in range(200)]


def _base() -> sel.ScoreDraw:
    return sel.select(SCORES, score_min=None, top_n=30, unpredictable_n=10, seed=4127)


def test_ac_approving_10_more_by_score_gives_50_with_the_first_40_in_place() -> None:
    base = _base()
    assert len(base.picks) == 40
    out = expansions.expand(base.picks, SCORES, add_by_score=10, add_unpredictable=0, seed=1)
    assert len(out.picks) == 50
    assert out.picks[:40] == base.picks
    assert out.prefix_hash == sel.items_hash(list(base.picks))
    added = out.picks[40:]
    assert [p.position for p in added] == list(range(41, 51))
    assert all(p.reason == "risk_score" for p in added)
    chosen = {p.entry_ref for p in base.picks}
    best_left = sorted((s for s in SCORES if s.entry_ref not in chosen and s.score >= 1),
                       key=lambda s: (-s.score, s.entry_ref))[:10]  # fmt: skip
    assert [p.entry_ref for p in added] == [s.entry_ref for s in best_left]


def test_the_same_seed_gives_the_same_expansion() -> None:
    base = _base()
    a = expansions.expand(base.picks, SCORES, add_by_score=5, add_unpredictable=5, seed=99)
    b = expansions.expand(base.picks, SCORES, add_by_score=5, add_unpredictable=5, seed=99)
    assert a.items_hash == b.items_hash and len(a.picks) == 50
    assert len({p.entry_ref for p in a.picks}) == 50


def test_named_keys_and_oversized_draws_are_refused() -> None:
    base = _base()
    with pytest.raises(expansions.ExpansionTooLarge):
        expansions.expand(base.picks, SCORES, add_by_score=0, add_unpredictable=0,
                          add_keys=["JE-26-17950"], seed=1)  # fmt: skip
    with pytest.raises(expansions.ExpansionTooLarge):
        expansions.expand(base.picks, SCORES, add_by_score=0, add_unpredictable=500, seed=1)
