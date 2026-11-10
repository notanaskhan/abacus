"""TASK-6543 (DEC-3145, DEC-3146): a governance letter sent by the engagement partner becomes a
final C11 document in the send's own transaction, on a real database.

The manager sets the Benefits Committee as the recipient, composes the planning letter and asks
for approval; the partner approves and sends it with a fresh second factor. The letter's version
then owns one `governance_letter` document with a draft and a final, the final approved by that
send.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.assurance import governance_comms as gc
from abacus.modules.identity.api import AuthContext

from .tb_support import Books, Person, books

pytestmark = pytest.mark.asyncio

LIVE_FLAGS = ("audits.letters", "audits.completion")


@pytest.fixture
async def world(net: object) -> Books:
    found = await books(net)  # pyright: ignore[reportArgumentType] -- the backfill `net` fixture
    for flag in LIVE_FLAGS:
        await found.seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'TASK-6543') ON CONFLICT DO NOTHING",
            found.tenant_id,
            flag,
        )
    return found


async def _committee(world: Books) -> tuple[uuid.UUID, uuid.UUID]:
    """The client's Benefits Committee with one member contact (an email to invite)."""
    client = cast(
        uuid.UUID,
        await world.seed.value(
            "SELECT client_id FROM engagements WHERE id = $1", world.site.engagement_id
        ),
    )
    contact = cast(
        uuid.UUID,
        await world.seed.value(
            "INSERT INTO contacts (tenant_id, client_id, display_name, email, contact_kind) "
            "VALUES ($1, $2, 'Victoria Lam', 'victoria.lam@northwind.example', 'client_person') "
            "RETURNING id",
            world.tenant_id,
            client,
        ),
    )
    body = cast(
        uuid.UUID,
        await world.seed.value(
            "INSERT INTO governance_bodies (tenant_id, client_id, name, kind) "
            "VALUES ($1, $2, 'Benefits Committee', 'benefits_committee') RETURNING id",
            world.tenant_id,
            client,
        ),
    )
    await world.seed.run(
        "INSERT INTO governance_body_members (tenant_id, body_id, contact_id, member_role, "
        "started_on) VALUES ($1, $2, $3, 'chair', '2026-09-01')",
        world.tenant_id,
        body,
        contact,
    )
    return body, contact


async def _as(world: Books, who: Person) -> AuthContext:
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
    )


async def test_the_partners_send_leaves_a_draft_and_a_final_approved_by_the_send(
    world: Books,
) -> None:
    body, contact = await _committee(world)
    ep = await _as(world, world.partner)
    manager = await _as(world, world.manager)
    await gc.set_recipients(manager, world.work_item_id, [body])
    communication = await gc.create(manager, world.work_item_id, "planning_260")
    await gc.request_approval(manager, world.work_item_id, communication)
    seen = cast(
        str,
        await world.seed.value(
            "SELECT v.content_hash FROM governance_communications c "
            "JOIN governance_communication_versions v ON v.id = c.current_version_id "
            "WHERE c.id = $1",
            communication,
        ),
    )
    send = await gc.approve_and_send(
        ep,
        world.work_item_id,
        communication,
        governance_body_id=body,
        recipient_contact_ids=[contact],
        channel="governance_room",
        seen_hash=seen,
    )
    version = cast(
        uuid.UUID,
        await world.seed.value(
            "SELECT version_id FROM governance_communication_sends WHERE id = $1", send
        ),
    )
    rows = await world.seed.rows(
        "SELECT v.mode, v.approval_ref FROM generated_documents d "
        "JOIN generated_document_versions v ON v.generated_document_id = d.id "
        "WHERE d.owner_type = 'governance_communication_version' AND d.owner_id = $1 "
        "AND d.kind = 'governance_letter' ORDER BY v.version_no",
        version,
    )
    assert [r["mode"] for r in rows] == ["draft", "final"]
    approval = str(rows[1]["approval_ref"])
    assert gc.APPROVAL_KIND in approval and str(send) in approval
