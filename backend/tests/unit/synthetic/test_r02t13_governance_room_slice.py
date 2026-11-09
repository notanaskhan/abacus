"""R-02-T13 remainder (DEC-3029): the `governance_room` slice seeds the room the figures book
names, with the ids the fixture slice reads, and the loader knows its event."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from abacus_tools.synthetic.scenarios.brightwater_hale import governance_room_slice as room
from abacus_tools.synthetic.scenarios.brightwater_hale import loader
from abacus_tools.synthetic.scenarios.brightwater_hale.audits import PORTAL_USERS

BOOK = (
    Path(__file__).parents[2] / "golden" / "scenario" / "brightwater_hale" / "portal_figures.json"
)


def test_the_room_is_the_books_committee_chair_first() -> None:
    book = cast(dict[str, object], json.loads(BOOK.read_text())["governance"])
    [event] = room.governance_room_events()
    assert event.data["body"] == book["body"]
    members = cast(list[list[str]], event.data["members"])
    assert [m[0] for m in members] == book["members"]
    assert [m[0] for m in members if m[1] == "chair"] == [book["chair"]]
    assert event.client == room.CLIENT


def test_every_member_is_a_seeded_portal_user_and_the_event_is_handled() -> None:
    seeded = {u.name for u in PORTAL_USERS}
    assert {name for name, _ in room.MEMBERS} <= seeded
    assert "assurance.governance_body_seeded" in loader.HANDLERS
    assert loader.expand_slices((room.SLICE,))[-1] == room.SLICE


def test_the_body_id_is_the_fixture_slices() -> None:
    fixture = (
        Path(__file__).parents[4] / "apps" / "web" / "src" / "fixtures" / "seed" / "portal-r02.ts"
    ).read_text()
    assert 'room: stableId("governance-body:northwind-benefits-committee")' in fixture
    assert room.stable_id("governance-body:northwind-benefits-committee") == room.BODY_ID
