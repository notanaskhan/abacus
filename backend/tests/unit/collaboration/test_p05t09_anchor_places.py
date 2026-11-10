"""P-05-T09: the workpaper anchor's places and a converted note's pin (SPEC-650 AC-1, AC-15)."""

from __future__ import annotations

import pytest

from abacus.modules.collaboration.threads import note_anchor
from abacus.modules.workpapers.anchors import WORKPAPER_ANCHORS, place_of


@pytest.mark.parametrize(
    ("locator", "place"),
    [
        (None, ""),
        ({"sheet": "Exceptions", "cell": "A3"}, "Exceptions!A3"),
        ({"sheet": "Exceptions", "row": 6}, "Exceptions row 6"),
        ({"sheet": "Exceptions"}, "Exceptions"),
        ({"sheet": "Exceptions", "cell": "A0"}, None),
        ({"sheet": "Exceptions", "cell": "a3"}, None),
        ({"sheet": "Exceptions", "row": 0}, None),
        ({"sheet": "Exceptions", "row": True}, None),
        ({"sheet": "Exceptions", "cell": "A3", "row": 3}, None),
        ({"sheet": "", "cell": "A3"}, None),
        ({"sheet": "x" * 61}, None),
        ({"cell": "A3"}, None),
    ],
)
def test_places_on_a_paper(locator: dict[str, str | int] | None, place: str | None) -> None:
    assert place_of(locator) == place


def test_the_provider_accepts_sheet_cell_and_row_only() -> None:
    assert WORKPAPER_ANCHORS.locator_keys == frozenset({"sheet", "cell", "row"})


def test_ac15_the_note_is_pinned_to_the_cell_or_the_region() -> None:
    assert note_anchor({"sheet": "Exceptions", "cell": "A3"}) == ("cell", "Exceptions!A3")
    assert note_anchor({"sheet": "Exceptions", "row": 6}) == ("region", "Exceptions row 6")
    assert note_anchor({"sheet": "Exceptions"}) == ("region", "Exceptions")
    assert note_anchor(None) == (None, None)
