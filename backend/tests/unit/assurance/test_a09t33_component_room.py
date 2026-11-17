"""A-09-T33 (TASK-8408; SPEC-658 F7; POR-23): every projection field of the room is on the
component allowlist, and deliverables read in the client's words only."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from abacus.modules.assurance import component_room as room
from abacus.modules.portal import component_room_contract as contract

ROOM_MODELS: tuple[type[BaseModel], ...] = (
    contract.ComponentRoomOut,
    contract.RoomDeliverableOut,
    contract.RoomInstructionsOut,
    contract.RoomSectionOut,
)
FIRM_ONLY = {"group_materiality", "consolidation", "eliminations", "component_pm_group", "agent"}


def test_every_room_field_is_on_the_allowlist() -> None:
    for model in ROOM_MODELS:
        assert set(model.model_fields) <= room.ROOM_FIELDS, model.__name__
        assert not (set(model.model_fields) & FIRM_ONLY)


def test_client_words() -> None:
    today = date(2026, 12, 1)
    assert room.client_word("expected", date(2026, 12, 5), False, today) == "due"
    assert room.client_word("expected", date(2026, 11, 30), False, today) == "overdue"
    assert room.client_word("received", date(2026, 11, 30), False, today) == "you_uploaded"
    assert room.client_word("reviewed", date(2026, 11, 30), False, today) == "you_uploaded"
    assert room.client_word("expected", date(2026, 12, 5), True, today) == "returned"
