"""SPEC-002 AC-5, ADR-026, DEC-121: which audit events a reader may see. Events about an engagement
the reader cannot see are dropped, whatever the target type; firm-level events stay; anything
unknown or unplaceable is hidden (fail closed). The owners' lookups are faked here; the security
suite runs the real ones against Postgres."""

from __future__ import annotations

import re
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

import abacus.api as app_package  # loading it loads every module: each registers its targets
from abacus.kernel import audit_owners
from abacus.kernel.db import TenantContext
from abacus.kernel.uow import AuditRow
from abacus.modules.audit_trail import targets
from abacus.modules.identity.api import AuthContext

SRC = Path(__file__).resolve().parents[3] / "src" / "abacus"
ENGAGEMENT_OWNED = sorted(audit_owners.engagement_owners())
ENTITY_OWNED = sorted(audit_owners.entity_owners())
MUST_BE_FOUND = [k for k in ENGAGEMENT_OWNED if k not in targets.OPTIONAL_OWNER]
READER = uuid.uuid4()


def _row(kind: str, target: str | uuid.UUID, seq: int = 1) -> AuditRow:
    return AuditRow(
        seq, datetime(2026, 10, 20, tzinfo=UTC), "human", "u", "x.done", kind, str(target),
        None, None, None,
    )  # fmt: skip


def _ctx() -> AuthContext:
    return cast(
        AuthContext,
        SimpleNamespace(tenant=TenantContext(uuid.uuid4(), "human", "u"), user_id=READER),
    )


class World:
    """Who owns what, and which engagements the reader sees."""

    def __init__(self) -> None:
        self.owner: dict[uuid.UUID, uuid.UUID] = {}  # a target row -> its engagement
        self.entity: dict[uuid.UUID, uuid.UUID] = {}  # a connection or snapshot -> its entity
        self.of_entity: dict[uuid.UUID, frozenset[uuid.UUID]] = {}
        self.of_client: dict[uuid.UUID, frozenset[uuid.UUID]] = {}
        self.seen: set[uuid.UUID] = set()
        self.hidden_walls: set[uuid.UUID] = set()
        self.asked: list[str] = []


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch) -> World:
    w = World()

    async def owners(
        _tenant: object, kind: str, ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, uuid.UUID]:
        w.asked.append(kind)
        return {i: w.owner[i] for i in ids if i in w.owner}

    async def entities(
        _tenant: object, kind: str, ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, uuid.UUID]:
        w.asked.append(kind)
        return {i: w.entity[i] for i in ids if i in w.entity}

    async def engagements_of(
        _tenant: object, kind: str, ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, frozenset[uuid.UUID]]:
        w.asked.append(kind)
        if kind == "engagement":
            return {i: frozenset({i}) for i in ids if i in w.seen or i in w.owner.values()}
        source = w.of_entity if kind == "client_entity" else w.of_client
        return {i: source[i] for i in ids if i in source}

    async def visible_among(_ctx: object, ids: Sequence[uuid.UUID]) -> set[uuid.UUID]:
        return {i for i in ids if i in w.seen}

    async def hidden_walls(_ctx: object, ids: Sequence[uuid.UUID]) -> set[uuid.UUID]:
        return {i for i in ids if i in w.hidden_walls}

    monkeypatch.setattr(
        targets, "_engagement_owners", lambda: dict.fromkeys(ENGAGEMENT_OWNED, owners)
    )
    monkeypatch.setattr(targets, "_entity_owners", lambda: dict.fromkeys(ENTITY_OWNED, entities))
    monkeypatch.setattr(targets, "_engagements_of", engagements_of)
    monkeypatch.setattr(targets, "_visible_among", visible_among)
    monkeypatch.setattr(targets, "_hidden_walls", hidden_walls)
    return w


# --- every target type the code can record is placed -------------------------------------------


def _recorded_target_types() -> set[str]:
    found: set[str] = set()
    for path in SRC.rglob("*.py"):
        found |= set(re.findall(r"Target\(\s*\"([a-z_]+)\"", path.read_text()))
    return found


def test_every_target_type_the_code_records_is_placed_so_a_new_one_is_a_decision() -> None:
    assert targets.known_kinds() >= _recorded_target_types()


def test_the_registry_is_not_empty_and_fills_from_the_modules_alone() -> None:
    assert app_package.create_app
    assert len(ENGAGEMENT_OWNED) >= 25
    assert set(ENTITY_OWNED) >= {"connection", "ledger_snapshot", "gl_snapshot"}


# --- engagement-owned targets: shown only with their engagement --------------------------------


@pytest.mark.parametrize("kind", ENGAGEMENT_OWNED)
async def test_a_target_of_an_engagement_the_reader_sees_is_shown(world: World, kind: str) -> None:
    engagement, target = uuid.uuid4(), uuid.uuid4()
    world.owner[target] = engagement
    world.seen.add(engagement)
    row = _row(kind, target)
    assert await targets.readable(_ctx(), [row]) == [row]


@pytest.mark.parametrize("kind", ENGAGEMENT_OWNED)
async def test_a_target_of_an_engagement_the_reader_cannot_see_is_hidden(
    world: World, kind: str
) -> None:
    target = uuid.uuid4()
    world.owner[target] = uuid.uuid4()  # not in `seen`: walled, or not theirs
    assert await targets.readable(_ctx(), [_row(kind, target)]) == []


@pytest.mark.parametrize("kind", MUST_BE_FOUND)
async def test_a_target_whose_owner_cannot_be_found_is_hidden(world: World, kind: str) -> None:
    assert await targets.readable(_ctx(), [_row(kind, uuid.uuid4())]) == []


async def test_the_engagement_itself_follows_the_same_rule(world: World) -> None:
    mine, walled = uuid.uuid4(), uuid.uuid4()
    world.seen.add(mine)
    world.owner[uuid.uuid4()] = walled  # exists, not seen
    rows = [_row("engagement", mine, 3), _row("engagement", walled, 2)]
    assert [r.seq for r in await targets.readable(_ctx(), rows)] == [3]


# --- entity-owned targets: shown with any of the entity's engagements --------------------------


@pytest.mark.parametrize("kind", ENTITY_OWNED)
async def test_a_target_of_an_entity_with_a_visible_engagement_is_shown(
    world: World, kind: str
) -> None:
    entity, engagement, target = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    world.entity[target] = entity
    world.of_entity[entity] = frozenset({engagement, uuid.uuid4()})
    world.seen.add(engagement)
    row = _row(kind, target)
    assert await targets.readable(_ctx(), [row]) == [row]


@pytest.mark.parametrize("kind", ENTITY_OWNED)
async def test_a_target_of_an_entity_whose_engagements_are_all_hidden_is_hidden(
    world: World, kind: str
) -> None:
    entity, target = uuid.uuid4(), uuid.uuid4()
    world.entity[target] = entity
    world.of_entity[entity] = frozenset({uuid.uuid4(), uuid.uuid4()})
    assert await targets.readable(_ctx(), [_row(kind, target)]) == []


@pytest.mark.parametrize("kind", ENTITY_OWNED)
async def test_a_target_of_an_entity_with_no_engagements_is_hidden(
    world: World, kind: str
) -> None:
    entity, target = uuid.uuid4(), uuid.uuid4()
    world.entity[target] = entity
    assert await targets.readable(_ctx(), [_row(kind, target)]) == []


@pytest.mark.parametrize("kind", ["client", "client_entity"])
async def test_a_client_or_entity_is_shown_only_with_one_of_its_visible_engagements(
    world: World, kind: str
) -> None:
    open_one, walled_one = uuid.uuid4(), uuid.uuid4()
    engagement = uuid.uuid4()
    world.seen.add(engagement)
    source = world.of_client if kind == "client" else world.of_entity
    source[open_one] = frozenset({engagement})
    source[walled_one] = frozenset({uuid.uuid4()})
    rows = [_row(kind, open_one, 2), _row(kind, walled_one, 1)]
    assert [r.seq for r in await targets.readable(_ctx(), rows)] == [2]


# --- firm-level, walls, notifications, and failing closed --------------------------------------


@pytest.mark.parametrize("kind", sorted(targets.FIRM_LEVEL))
async def test_firm_level_targets_are_always_shown(world: World, kind: str) -> None:
    row = _row(kind, uuid.uuid4())
    assert await targets.readable(_ctx(), [row]) == [row]
    assert world.asked == []  # nothing needed looking up


async def test_a_wall_the_reader_must_not_learn_of_is_hidden_and_another_is_shown(
    world: World,
) -> None:
    mine, other = uuid.uuid4(), uuid.uuid4()
    world.hidden_walls.add(mine)
    rows = [_row("ethical_wall", mine, 2), _row("ethical_wall", other, 1)]
    assert [r.seq for r in await targets.readable(_ctx(), rows)] == [1]


async def test_a_notification_about_no_engagement_is_firm_level_but_one_with_one_follows_it(
    world: World,
) -> None:
    about_none, walled, open_one = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    engagement = uuid.uuid4()
    world.owner[walled] = uuid.uuid4()
    world.owner[open_one] = engagement
    world.seen.add(engagement)
    rows = [
        _row("notification", about_none, 3),
        _row("notification", walled, 2),
        _row("notification", open_one, 1),
    ]
    assert [r.seq for r in await targets.readable(_ctx(), rows)] == [3, 1]


@pytest.mark.parametrize("kind", ["made_up", "", "Engagement", "request_items"])
async def test_an_unknown_target_type_is_hidden(world: World, kind: str) -> None:
    assert await targets.readable(_ctx(), [_row(kind, uuid.uuid4())]) == []


@pytest.mark.parametrize("kind", ["engagement", "request_item", "connection", "ethical_wall"])
async def test_a_target_id_that_is_not_a_uuid_is_hidden(world: World, kind: str) -> None:
    assert await targets.readable(_ctx(), [_row(kind, "not-a-uuid")]) == []


async def test_order_is_kept_and_each_kind_is_asked_once(world: World) -> None:
    engagement = uuid.uuid4()
    world.seen.add(engagement)
    ids = [uuid.uuid4() for _ in range(4)]
    for target in ids:
        world.owner[target] = engagement
    rows = [_row("request_item", t, 10 - n) for n, t in enumerate(ids)]
    shown = cast("list[Any]", await targets.readable(_ctx(), rows))
    assert [r.seq for r in shown] == [10, 9, 8, 7]
    assert world.asked == ["request_item"]
