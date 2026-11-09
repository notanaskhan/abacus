"""R-02-T11 remainder (TASK-6309; DEC-3009, DEC-3025): C18's approvals service on a real database.

AJE-1, approved and sent to the client, reaches Dana Kowalski's portal list through her owner
grant; her accept moves the entry to `client_approved` and records `proposed_entry.client_accepted`
on the entry. A grant on the client (not its engagement) lists the same entry; a person with no
grant sees nothing.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import cast

import pytest
from sqlalchemy import text

from abacus.kernel.db import TenantContext
from abacus.kernel.uow import Target, uow
from abacus.modules.engagements.api import ClientDecision
from abacus.modules.identity.api import AuthContext
from abacus.modules.portal import approvals as service

from .tb_support import Books, books

pytestmark = pytest.mark.asyncio

SENT = text(
    "INSERT INTO proposed_entry_decisions (tenant_id, engagement_id, work_item_id, entry_id, "
    "decision, actor_principal, channel, seen_version) "
    "VALUES (:t, :e, :wi, :entry, 'sent_to_client', 'firm_user', 'app', 1)"
)


@pytest.fixture
async def world(net: object) -> Books:
    return await books(net)  # pyright: ignore[reportArgumentType] -- the backfill `net` fixture


async def _sent_aje(world: Books) -> uuid.UUID:
    entry = uuid.uuid4()
    await world.seed.run(
        "INSERT INTO proposed_entries (id, tenant_id, engagement_id, work_item_id, kind, number, "
        "ref, threshold_result, is_attest_client, status, created_by_kind, created_by_id) VALUES "
        "($1, $2, $3, $4, 'aje', 1, 'AJE-1', 'review_required', true, 'approved', 'human', 'x')",
        entry,
        world.tenant_id,
        world.site.engagement_id,
        world.work_item_id,
    )
    # The firm's send, as a person through the kernel's unit of work (it sets the actor).
    async with uow(TenantContext(world.tenant_id, "human", "seed")) as tx:
        await tx.session.execute(
            SENT,
            {
                "t": world.tenant_id,
                "e": world.site.engagement_id,
                "wi": world.work_item_id,
                "entry": entry,
            },
        )
        tx.record("proposed_entries.sent_to_client", target=Target("proposed_entry", entry))
    return entry


async def _client(world: Books, scope_kind: str | None) -> AuthContext:
    """Dana Kowalski: a client membership, a contact on the client, and an owner grant on
    `scope_kind` (the work item or the client), or none."""
    who = await world.seed.person(world.tenant_id)
    await world.seed.run(
        "UPDATE memberships SET kind = 'client', level = NULL, office_id = NULL "
        "WHERE tenant_id = $1 AND user_id = $2",
        world.tenant_id,
        who.user_id,
    )
    client = cast(
        uuid.UUID,
        await world.seed.value(
            "SELECT client_id FROM engagements WHERE id = $1", world.site.engagement_id
        ),
    )
    await world.seed.run(
        "INSERT INTO contacts (tenant_id, client_id, display_name, contact_kind, user_id) "
        "VALUES ($1, $2, 'Dana Kowalski', 'client_person', $3)",
        world.tenant_id,
        client,
        who.user_id,
    )
    if scope_kind is not None:
        scope = world.work_item_id if scope_kind == "work_item" else client
        await world.seed.run(
            "INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id) "
            "VALUES ($1, $2, 'owner', $3, $4)",
            world.tenant_id,
            who.user_id,
            scope_kind,
            scope,
        )
    membership = cast(
        uuid.UUID,
        await world.seed.value(
            "SELECT id FROM memberships WHERE tenant_id = $1 AND user_id = $2",
            world.tenant_id,
            who.user_id,
        ),
    )
    return AuthContext(
        TenantContext(world.tenant_id, "human", str(who.user_id)),
        who.user_id,
        membership,
        None,
        datetime.now(UTC),
        client=True,
        portal_session_id=uuid.uuid4(),
        portal_second_step=True,
    )


async def test_danas_grant_lists_aje_1_and_her_accept_reaches_the_entry(world: Books) -> None:
    entry = await _sent_aje(world)
    dana = await _client(world, "work_item")
    listing = await service.approvals(dana, None, None)
    assert [s.item.item_id for s in listing.items] == [entry]
    assert listing.items[0].actions == ("accept", "decline", "ask")
    assert listing.counts["waiting"] == 1
    shown = await service.approval(dana, "proposed_entry", entry)
    decided = await service.client_decide(
        dana,
        "proposed_entry",
        entry,
        ClientDecision("accept", shown.item.seen_hash),
        action="portal.approvals.proposed_entry.decide",
        idempotency_key=f"accept-{entry}",
    )
    assert decided.state == "accepted"
    assert (
        await world.seed.value("SELECT status FROM proposed_entries WHERE id = $1", entry)
    ) == "client_approved"
    actions = await world.seed.rows(
        "SELECT action FROM audit_events WHERE target_id = $1 ORDER BY id", str(entry)
    )
    assert "proposed_entry.client_accepted" in [r["action"] for r in actions]
    assert "client_approval.decided" in [r["action"] for r in actions]


async def test_a_client_grant_lists_the_entry_and_no_grant_lists_nothing(world: Books) -> None:
    entry = await _sent_aje(world)
    on_client = await _client(world, "client")
    assert [s.item.item_id for s in (await service.approvals(on_client, None, None)).items] == [
        entry
    ]
    stranger = await _client(world, None)
    assert (await service.approvals(stranger, None, None)).items == []
