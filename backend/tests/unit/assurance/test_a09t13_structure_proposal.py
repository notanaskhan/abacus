"""A-09-T13 rest (TASK-8365; DEC-5340; SPEC-658 AC-1.1, AC-1.4; AUD-32 c): the structure
proposal's rules, by code.

AUD-32 c: "Agent-proposed 3 tiers from the 5 OneWorld subsidiaries"; ownership 100%; three tiers
at most (X-06).
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from abacus.modules.assurance.compute import group_structure as gs

SOURCE = (
    ("HP Holdings", None),
    ("HP Operating", "HP Holdings"),
    ("HP Manufacturing", "HP Operating"),
    ("HP Distribution", "HP Operating"),
    ("HP Real Estate", "HP Holdings"),
)
IDS = {name: uuid4() for name, _ in SOURCE}
ENTITIES = {IDS[name]: name for name, _ in SOURCE}


def _by_id(placed: tuple[gs.Placed, ...]) -> dict[UUID, tuple[UUID | None, int]]:
    return {p.client_entity_id: (p.parent_client_entity_id, p.level) for p in placed}


def test_aud32_c_five_subsidiaries_make_three_tiers() -> None:
    placed = gs.propose(SOURCE, ENTITIES)
    assert _by_id(placed) == {
        IDS["HP Holdings"]: (None, 1),
        IDS["HP Operating"]: (IDS["HP Holdings"], 2),
        IDS["HP Real Estate"]: (IDS["HP Holdings"], 2),
        IDS["HP Manufacturing"]: (IDS["HP Operating"], 3),
        IDS["HP Distribution"]: (IDS["HP Operating"], 3),
    }
    assert [p.level for p in placed] == [1, 2, 2, 3, 3]  # by level, then name
    assert placed[1].client_entity_id == IDS["HP Operating"]


def test_names_match_whatever_their_case_or_spacing() -> None:
    entities = {IDS[name]: f"  {name.upper()} " for name, _ in SOURCE}
    assert len(gs.propose(SOURCE, entities)) == 5


def test_an_unmatched_subsidiary_leaves_itself_and_its_children_out() -> None:
    entities = {k: v for k, v in ENTITIES.items() if v != "HP Operating"}
    placed = _by_id(gs.propose(SOURCE, entities))
    assert set(placed) == {IDS["HP Holdings"], IDS["HP Real Estate"]}


def test_a_name_two_entities_share_matches_neither() -> None:
    entities = dict(ENTITIES) | {uuid4(): "HP Real Estate"}
    assert IDS["HP Real Estate"] not in _by_id(gs.propose(SOURCE, entities))


def test_a_parent_outside_the_source_makes_its_child_the_top() -> None:
    placed = gs.propose((("HP Operating", "Someone Else"),), ENTITIES)
    assert _by_id(placed) == {IDS["HP Operating"]: (None, 1)}


def test_nothing_matched_proposes_nothing() -> None:
    assert gs.propose(SOURCE, {}) == ()


def test_a_fourth_tier_refuses() -> None:
    deep = (*SOURCE, ("HP Plant", "HP Manufacturing"))
    with pytest.raises(gs.StructureTooDeep):
        gs.propose(deep, ENTITIES | {uuid4(): "HP Plant"})


@pytest.mark.parametrize(
    "source",
    [
        (("A", None), ("a ", None)),  # named twice
        (("A", "B"), ("B", "A")),  # a loop
    ],
)
def test_a_source_the_proposal_cannot_read_refuses(source: tuple[tuple[str, str], ...]) -> None:
    with pytest.raises(gs.HierarchyInvalid):
        gs.propose(source, {uuid4(): "A", uuid4(): "B"})


def test_the_output_round_trips_and_its_digest_is_stable() -> None:
    placed = gs.propose(SOURCE, ENTITIES)
    out = gs.output_of(placed)
    assert gs.from_output(out) == placed
    assert gs.digest(out) == gs.digest(dict(reversed(list(out.items()))))
    assert len(gs.digest(out)) == 64
    moved = gs.output_of((*placed[:-1], gs.Placed(placed[-1].client_entity_id, None, 1)))
    assert gs.digest(moved) != gs.digest(out)


@pytest.mark.parametrize(
    "output",
    [
        {},
        {"entities": []},
        {"entities": ["x"]},
        {"entities": [["a", None]]},
        {"entities": [[1, None, 1]]},
        {"entities": [[str(uuid4()), 2, 1]]},
        {"entities": [[str(uuid4()), None, 4]]},
        {"entities": [[str(uuid4()), None, True]]},
        {"entities": [[str(uuid4()), None, "1"]]},
    ],
)
def test_an_output_of_any_other_shape_refuses(output: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        gs.from_output(output)
