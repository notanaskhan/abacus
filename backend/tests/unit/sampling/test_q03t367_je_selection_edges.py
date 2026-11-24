"""Q-03-T367 (TASK-8959): JE score selection's edges (A-08-T12; SPEC-657 AC-1.4; ADR P-57).

The quarterly mutation sweep left the selection's refusals, its tie order, its zero-score floor
and the unpredictable pick's score unguarded. Each is held here by its exact value.
"""

from __future__ import annotations

import pytest

from abacus.modules.sampling.compute import je_selection as sel
from abacus.modules.sampling.compute.draw import SEED_MAX


def _s(*pairs: tuple[str, int]) -> tuple[sel.Scored, ...]:
    return tuple(sel.Scored(ref, score) for ref, score in pairs)


POP = _s(("je-a", 70), ("je-c", 70), ("je-b", 90), ("je-z", 0), ("je-y", 0), ("je-d", 1))


@pytest.mark.parametrize(
    ("kw", "code"),
    [
        (
            {"score_min": None, "top_n": None, "unpredictable_n": 0, "seed": 1},
            "score_min_or_top_n",
        ),
        ({"score_min": 1, "top_n": None, "unpredictable_n": -1, "seed": 1}, "parameters"),
        ({"score_min": 1, "top_n": None, "unpredictable_n": 0, "seed": -1}, "parameters"),
        (
            {"score_min": 1, "top_n": None, "unpredictable_n": 0, "seed": SEED_MAX + 1},
            "parameters",
        ),
        (
            {"score_min": 1, "top_n": None, "unpredictable_n": 9, "seed": 1},
            "unpredictable_exceeds_population",
        ),
    ],
)
def test_each_refusal_names_its_code(kw: dict[str, int | None], code: str) -> None:
    with pytest.raises(sel.SelectionInvalid) as refused:
        sel.select(POP, **kw)  # type: ignore[arg-type]  # the keyword set is select()'s
    assert str(refused.value) == code


def test_a_duplicate_entry_is_refused_by_name() -> None:
    with pytest.raises(sel.SelectionInvalid) as refused:
        sel.select(
            _s(("je-a", 5), ("je-a", 6)), score_min=1, top_n=None, unpredictable_n=0, seed=1
        )
    assert str(refused.value) == "duplicate_entry"


def test_the_seed_bounds_are_inclusive() -> None:
    for seed in (0, SEED_MAX):
        draw = sel.select(POP, score_min=1, top_n=None, unpredictable_n=1, seed=seed)
        assert draw.unpredictable == 1


def test_score_order_then_reference_and_a_zero_score_is_never_by_score() -> None:
    draw = sel.select(POP, score_min=0, top_n=None, unpredictable_n=0, seed=1)
    assert [(p.position, p.entry_ref, p.reason, p.score) for p in draw.picks] == [
        (1, "je-b", "risk_score", 90),
        (2, "je-a", "risk_score", 70),  # a tie reads in reference order
        (3, "je-c", "risk_score", 70),
        (4, "je-d", "risk_score", 1),  # score_min 0 still floors at 1
    ]
    assert draw.by_score == 4
    top = sel.select(POP, score_min=None, top_n=2, unpredictable_n=0, seed=1)
    assert [p.entry_ref for p in top.picks] == ["je-b", "je-a"]
    # With top_n only, the floor is 1: a single positive score is still by score.
    every = sel.select(POP, score_min=None, top_n=10, unpredictable_n=0, seed=1)
    assert [p.entry_ref for p in every.picks] == ["je-b", "je-a", "je-c", "je-d"]
    # score_min 2 leaves the 1 out.
    high = sel.select(POP, score_min=2, top_n=None, unpredictable_n=0, seed=1)
    assert [p.entry_ref for p in high.picks] == ["je-b", "je-a", "je-c"]


def test_the_unpredictable_picks_follow_with_their_own_scores_and_the_draws_hash() -> None:
    draw = sel.select(POP, score_min=70, top_n=None, unpredictable_n=3, seed=7)
    later = draw.picks[3:]
    assert [p.position for p in later] == [4, 5, 6]
    assert all(p.reason == "unpredictable" for p in later)
    left = {"je-d": 1, "je-y": 0, "je-z": 0}
    assert {p.entry_ref for p in later} == set(left)
    assert all(p.score == left[p.entry_ref] for p in later)
    assert draw.inputs_hash == sel.inputs_hash(
        POP, score_min=70, top_n=None, unpredictable_n=3, seed=7
    )
    assert draw.items_hash == sel.items_hash(draw.picks)
