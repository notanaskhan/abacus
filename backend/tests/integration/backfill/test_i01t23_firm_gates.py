"""I-01-T23 (TASK-6017; DEC-2613): firm-level human gates, rows with no engagement.

A methodology version in Needs review and a wall waiting on its partner belong to no engagement.
Their C13 sources are `scope="firm"`; what this suite holds true from outside the projector:

- an event naming no engagement reconciles a firm source, and its row carries none;
- an unassigned firm row waits on the firm roles its `decides` action allows (a quality partner
  for `methodology.approve`), and nobody else sees or counts it: not a manager, a partner by
  title, a firm admin, or an engagement partner reading through an engagement;
- an assigned firm row is its assignee's alone, and never shows to them once they are walled
  from the client it names (INV-3); the list and the counts agree throughout;
- the two real sources' reads run on the migrated schema (the wall source on a seeded wall).

Boundary: `create_app()` over HTTP for the read, the projector through `review.api.SUBSCRIPTIONS`,
and the consumer sources registered through the public slot as the P-04 suite does.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final, cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.review.api import SUBSCRIPTIONS, GateSource, OpenGate, register_gate_source
from abacus.modules.review.firm_gates import methodology_open, walls_open

from .support import Json, Net, Person, Site

pytestmark = pytest.mark.asyncio

GATES: Final = "/v1/human-gates"
COUNTS: Final = "/v1/human-gates/counts"
DECIDES: Final = "consumer_firm_decision"  # waits on `methodology.approve`'s firm roles
ASSIGNED: Final = "consumer_firm_assigned"  # waits on its assignee alone
_EVENT: Final = "methodology.review_requested"

_WAITING: dict[uuid.UUID, list[tuple[str, OpenGate]]] = {}


def _open_for(
    subject_type: str,
) -> Callable[[TenantContext, uuid.UUID | None], Awaitable[list[OpenGate]]]:
    async def open_for(tenant: TenantContext, _engagement_id: uuid.UUID | None) -> list[OpenGate]:
        return [g for t, g in _WAITING.get(tenant.tenant_id, []) if t == subject_type]

    open_for.__qualname__ = f"test_i01t23.{subject_type}"
    return open_for


register_gate_source(
    GateSource(
        DECIDES,
        "decision",
        "methodology.read",
        frozenset({_EVENT}),
        _open_for(DECIDES),
        scope="firm",
        decides="methodology.approve",
    )
)
register_gate_source(
    GateSource(
        ASSIGNED,
        "decision",
        "wall.approve",
        frozenset({_EVENT}),
        _open_for(ASSIGNED),
        assigned_only=True,
        scope="firm",
    )
)


@dataclass(frozen=True)
class Firm:
    net: Net
    tenant_id: uuid.UUID
    admin: Person  # firm_admin: no `methodology.approve`
    quality: Person  # quality_partner: `methodology.approve`
    manager: Person  # no firm role; manager on Ashford
    daniel: Person  # no firm role; engagement partner on Ashford
    ashford: Site

    async def listed(self, who: Person) -> list[Json]:
        response = await self.net.call("GET", GATES, who)
        assert response.status_code == 200, response.text
        return cast(list[Json], cast(Json, response.json())["items"])

    async def counted(self, who: Person) -> int:
        response = await self.net.call("GET", COUNTS, who)
        assert response.status_code == 200, response.text
        return cast(int, cast(Json, response.json())["total"])

    async def deliver(self) -> None:
        """An event naming no engagement, as methodology writes it."""
        event = OutboxEvent(
            uuid.uuid4(), self.tenant_id, _EVENT, {"version_id": str(uuid.uuid4())}
        )
        await SUBSCRIPTIONS[_EVENT](event)


@pytest.fixture
async def firm(net: Net) -> Firm:
    seed = net.seed
    tenant_id = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'review.grammar_api', 'true', 'test-seed', 'I-01-T23')",
        tenant_id,
    )
    admin = await seed.person(tenant_id, "firm_admin")
    quality = await seed.person(tenant_id, "quality_partner")
    manager = await seed.person(tenant_id)
    daniel = await seed.person(tenant_id)
    ashford = await seed.site(tenant_id, admin.user_id, "Ashford")
    await seed.member(ashford, manager, "manager")
    await seed.member(ashford, daniel, "engagement_partner")
    return Firm(net, tenant_id, admin, quality, manager, daniel, ashford)


def _waiting(f: Firm, subject_type: str, gate: OpenGate) -> uuid.UUID:
    _WAITING.setdefault(f.tenant_id, []).append((subject_type, gate))
    return gate.subject_id


def _settle(f: Firm, subject: uuid.UUID) -> None:
    _WAITING[f.tenant_id] = [(t, g) for t, g in _WAITING[f.tenant_id] if g.subject_id != subject]


def _subjects(items: list[Json]) -> set[str]:
    return {cast(str, cast(Json, i["subject"])["id"]) for i in items}


async def test_ac_a_firm_row_waits_on_the_firm_role_that_decides_it(firm: Firm) -> None:
    subject = _waiting(firm, DECIDES, OpenGate(uuid.uuid4(), None))
    await firm.deliver()
    stored = await firm.net.seed.rows(
        "SELECT engagement_id, subkind, state FROM human_gates WHERE tenant_id = $1",
        firm.tenant_id,
    )
    assert [tuple(r.values()) for r in stored] == [(None, DECIDES, "open")]

    items = await firm.listed(firm.quality)
    assert _subjects(items) == {str(subject)}
    assert items[0]["engagement_id"] is None
    assert await firm.counted(firm.quality) == 1
    for other in (firm.admin, firm.manager, firm.daniel):
        assert await firm.listed(other) == []
        assert await firm.counted(other) == 0

    _settle(firm, subject)
    await firm.deliver()
    assert await firm.listed(firm.quality) == []
    assert await firm.counted(firm.quality) == 0


async def test_ac_an_assigned_firm_row_is_its_assignees_and_a_wall_hides_it(firm: Firm) -> None:
    gate = OpenGate(
        uuid.uuid4(), None, assignee_user_id=firm.daniel.user_id, client_id=firm.ashford.client_id
    )
    subject = _waiting(firm, ASSIGNED, gate)
    await firm.deliver()
    assert _subjects(await firm.listed(firm.daniel)) == {str(subject)}
    assert await firm.counted(firm.daniel) == 1
    for other in (firm.admin, firm.quality, firm.manager):
        assert await firm.listed(other) == []
        assert await firm.counted(other) == 0

    await firm.net.wall(firm.admin, firm.daniel, firm.ashford)
    assert await firm.listed(firm.daniel) == []
    assert await firm.counted(firm.daniel) == 0


async def test_ac_the_real_sources_read_the_migrated_schema(firm: Firm) -> None:
    tenant = TenantContext(firm.tenant_id, "system", "test-seed")
    assert await methodology_open(tenant, None) == []

    wall_id = cast(
        uuid.UUID,
        await firm.net.seed.value(
            "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by, reason_code, "
            "approver_user_id) VALUES ($1, $2, $3, $4, 'other', $5) RETURNING id",
            firm.tenant_id,
            firm.manager.user_id,
            firm.ashford.client_id,
            firm.admin.user_id,
            firm.daniel.user_id,
        ),
    )
    found = await walls_open(tenant, None)
    assert [(g.subject_id, g.engagement_id, g.assignee_user_id, g.client_id) for g in found] == [
        (wall_id, None, firm.daniel.user_id, firm.ashford.client_id)
    ]
    await firm.net.seed.run_untriggered(
        "UPDATE ethical_walls SET approved_by = $2, approved_at = now() WHERE id = $1",
        wall_id,
        firm.daniel.user_id,
    )
    assert await walls_open(tenant, None) == []
