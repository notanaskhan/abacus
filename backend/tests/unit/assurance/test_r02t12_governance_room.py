"""R-02-T12 (TASK-6310; SPEC-646 AC-26 to AC-30; DEC-93, DEC-3010): the governance room.

Row acceptance: "Victoria Lam acknowledges once (idempotent), the letter rolls up to Acknowledged
when all three members have, and Dana Kowalski's management grant gets 404 on every governance
route."

The roll-up and the paper are code; the room's opening is tested with the grant and membership
lookups faked; the acknowledgement's insert-only row is in the integration suite (end pass).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.modules.assurance import governance_room as room
from abacus.modules.identity.api import AuthContext

VICTORIA, BEN, CHAIR = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
BENEFITS_COMMITTEE = uuid.uuid4()
ENGAGEMENT, WORK_ITEM = uuid.uuid4(), uuid.uuid4()
SEP_25 = datetime(2026, 9, 25, 15, 0, tzinfo=UTC)


def test_ac_the_letter_rolls_up_only_when_all_three_members_have_acknowledged() -> None:
    members = [CHAIR, VICTORIA, BEN]
    assert room.roll_up(members, {}, [VICTORIA]) == "new"
    assert room.roll_up(members, {VICTORIA: SEP_25}, [VICTORIA]) == "sent_acknowledged"
    assert room.roll_up(members, {VICTORIA: SEP_25, BEN: SEP_25}, [BEN]) == "sent_acknowledged"
    everyone = {CHAIR: SEP_25, VICTORIA: SEP_25, BEN: SEP_25}
    assert room.roll_up(members, everyone, [VICTORIA]) == "acknowledged"
    assert room.roll_up(members, everyone, [uuid.uuid4()]) == "acknowledged"


def test_ac28_the_paper_carries_no_citation_marker() -> None:
    sections = [
        {"heading": "Our responsibilities", "body": "We planned the audit [[cite:au-c-260.12]]."},
        {"heading": None, "body": "Significant risks were [[cite:rk-1]] identified."},
        {"body": 3},
        "not a section",
    ]
    out = room.paper(sections)
    assert [s.body for s in out] == [
        "We planned the audit.",
        "Significant risks were identified.",
    ]
    assert out[0].heading == "Our responsibilities" and out[1].heading is None


@dataclass
class Grant:
    id: uuid.UUID
    role: str
    scope_kind: str
    scope_id: uuid.UUID


def _person(user: uuid.UUID) -> AuthContext:
    return AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)),
        user,
        uuid.uuid4(),
        None,
        None,
        client=True,
    )


@pytest.fixture
def lookups(monkeypatch: pytest.MonkeyPatch) -> dict[uuid.UUID, list[Grant]]:
    grants: dict[uuid.UUID, list[Grant]] = {}

    async def active(_: TenantContext, user_id: uuid.UUID) -> list[Grant]:
        return grants.get(user_id, [])

    async def members(
        _: TenantContext, bodies: list[uuid.UUID]
    ) -> dict[uuid.UUID, list[room.RoomContact]]:
        return {
            BENEFITS_COMMITTEE: [
                room.RoomContact(CHAIR, "Ben Ashby", "chair"),
                room.RoomContact(VICTORIA, "Victoria Lam", "member"),
                room.RoomContact(BEN, "Third member", "member"),
            ]
        }

    async def mine(ctx: AuthContext) -> list[uuid.UUID]:
        return [VICTORIA] if ctx.user_id == VICTORIA_USER else []

    monkeypatch.setattr(room, "active_grants", active)
    monkeypatch.setattr(room, "_members", members)
    monkeypatch.setattr(room, "_my_contacts", mine)
    return grants


VICTORIA_USER = uuid.uuid4()
DANA_USER = uuid.uuid4()


async def test_ac_danas_management_grant_opens_no_room(
    lookups: dict[uuid.UUID, list[Grant]],
) -> None:
    lookups[DANA_USER] = [Grant(uuid.uuid4(), "owner", "engagement", uuid.uuid4())]
    dana = _person(DANA_USER)
    assert await room.rooms(dana) == []
    with pytest.raises(NotFound):
        await room._open(dana, BENEFITS_COMMITTEE)  # pyright: ignore[reportPrivateUsage] -- the rule under test


async def test_a_tcwg_grant_opens_the_room_for_a_current_member(
    lookups: dict[uuid.UUID, list[Grant]],
) -> None:
    lookups[VICTORIA_USER] = [Grant(uuid.uuid4(), "tcwg", "governance_room", BENEFITS_COMMITTEE)]
    contacts = await room._open(_person(VICTORIA_USER), BENEFITS_COMMITTEE)  # pyright: ignore[reportPrivateUsage] -- the rule under test
    assert contacts == [VICTORIA]


async def test_a_tcwg_grant_on_another_room_is_404(
    lookups: dict[uuid.UUID, list[Grant]],
) -> None:
    lookups[VICTORIA_USER] = [Grant(uuid.uuid4(), "tcwg", "governance_room", uuid.uuid4())]
    with pytest.raises(NotFound):
        await room._open(_person(VICTORIA_USER), BENEFITS_COMMITTEE)  # pyright: ignore[reportPrivateUsage] -- the rule under test


async def test_an_agent_or_firm_person_opens_no_room(
    lookups: dict[uuid.UUID, list[Grant]],
) -> None:
    lookups[VICTORIA_USER] = [Grant(uuid.uuid4(), "tcwg", "governance_room", BENEFITS_COMMITTEE)]
    firm = AuthContext(
        TenantContext(uuid.uuid4(), "human", str(VICTORIA_USER)), VICTORIA_USER, uuid.uuid4(),
        None, None, client=False,
    )  # fmt: skip
    assert await room.rooms(firm) == []


class _Result:
    def __init__(self, row: object | None, rows: list[object] | None = None) -> None:
        self._row, self._rows = row, rows or []

    def first(self) -> object | None:
        return self._row

    def all(self) -> list[object]:
        return self._rows


@dataclass
class _Row:
    acknowledged_at: datetime = SEP_25
    engagement_id: uuid.UUID = ENGAGEMENT
    work_item_id: uuid.UUID = WORK_ITEM
    acknowledged_by_contact_id: uuid.UUID = VICTORIA


class _Tx:
    """A unit of work over a fake table: one row per (version, contact)."""

    def __init__(self) -> None:
        self.rows: set[tuple[uuid.UUID, uuid.UUID]] = set()
        self.rolled = False
        self.events: list[str] = []
        self.session = self

    async def execute(self, statement: object, params: dict[str, object]) -> _Result:
        sql = str(statement)
        if sql.startswith("INSERT INTO governance_acknowledgements"):
            key = (params["version"], params["contact"])
            if key in self.rows:
                return _Result(None)
            self.rows.add(key)  # type: ignore[arg-type] -- a test double stands in
            return _Result(_Row(acknowledged_by_contact_id=params["contact"]))  # type: ignore[arg-type] -- a test double stands in
        if sql.startswith("SELECT version_id"):
            return _Result(None, [_Row(acknowledged_by_contact_id=c) for _, c in self.rows])
        if sql.startswith("UPDATE governance_communications"):
            self.rolled = True
        return _Result(None)

    def record(self, action: str, **_: object) -> None:
        self.events.append(action)


async def test_ac_victoria_acknowledges_once_and_the_third_member_rolls_it_up() -> None:
    tx = _Tx()
    letter, version = uuid.uuid4(), uuid.uuid4()
    members = [CHAIR, VICTORIA, BEN]
    ack = room.record_acknowledgement
    assert await ack(tx, letter, version, VICTORIA, members=members) is True  # type: ignore[arg-type] -- a test double stands in
    assert await ack(tx, letter, version, VICTORIA, members=members) is False  # type: ignore[arg-type] -- a test double stands in
    assert len(tx.rows) == 1 and not tx.rolled
    await ack(tx, letter, version, CHAIR, members=members)  # type: ignore[arg-type] -- a test double stands in
    assert not tx.rolled
    await ack(tx, letter, version, BEN, members=members)  # type: ignore[arg-type] -- a test double stands in
    assert tx.rolled
    assert tx.events.count("governance_communication.acknowledged") == 3
