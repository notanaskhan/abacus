# ac-test-author: ayushkbhatia
"""K-01-T27: independent acceptance tests (ADR-078) for K-01-T08's guidance-draft publish path,
written from the K-01-T27 row and KNW-02, not from the implementing suite
(`test_k01t08_guidance_publish_for_review`).

With `methodology.lifecycle` on:
- a published guidance draft lands in Needs review; the version a firm uses stays the current
  one (still published, still the default for new engagements);
- it reaches Margaret's review queue (the quality partner's KNW-01 Review queue tab);
- the agent principal's approval of it is refused and audited, and the draft does not move.
With the flag off TASK-074's behaviour stands: the drafted version is published and current.

It fails if a published guidance draft becomes the current version, skips Margaret's review queue,
or is approved by the agent principal.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.uow import uow
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.methodology import lifecycle
from abacus.modules.methodology.api import ApprovedGuidance, publish_drafted_version

from .support import Json, Net, Person
from .test_k01t05_methodology_programs import (
    _flags,  # pyright: ignore[reportPrivateUsage] -- K-01-T05's flag seeding
    _import,  # pyright: ignore[reportPrivateUsage] -- K-01-T05's workbook import
    _workbook,  # pyright: ignore[reportPrivateUsage] -- K-01-T05's BH EBP workbook
)

pytestmark = pytest.mark.asyncio


def _person(who: Person, role: str = "firm_admin") -> AuthContext:
    return AuthContext(
        tenant=TenantContext(who.tenant_id, "human", str(who.user_id)),
        user_id=who.user_id,
        membership_id=uuid.uuid4(),
        firm_role=role,  # pyright: ignore[reportArgumentType] -- a seeded firm role code
        mfa_at=datetime.now(UTC) - timedelta(minutes=1),
    )


def _agent_for(who: Person) -> AuthContext:
    """The agent principal acting for `who` (the drafter's run), as services see it."""
    run = uuid.uuid4()
    return AuthContext(
        tenant=TenantContext(
            who.tenant_id,
            "agent",
            f"agent:guidance_drafter:{run}",
            on_behalf_of_user_id=who.user_id,
        ),
        user_id=who.user_id,
        membership_id=uuid.uuid4(),
        firm_role="quality_partner",
        mfa_at=datetime.now(UTC) - timedelta(minutes=1),
    )


async def _drafted(admin: Person, current: uuid.UUID) -> uuid.UUID:
    ctx = _person(admin)
    guidance = [
        ApprovedGuidance(
            position=0,
            why="Grounds the planning memo.",
            good_looks_like="The plan document for the year, signed.",
            effort=None,
            blocks_fieldwork=False,
            approved_by=admin.user_id,
        )
    ]
    async with uow(ctx.tenant) as tx:
        summary = await publish_drafted_version(tx, ctx, current, guidance)
    return summary.version_id


async def _state(net: Net, version: uuid.UUID) -> tuple[str, bool]:
    row = (
        await net.seed.rows(
            "SELECT status, default_for_new_engagements FROM methodology_version_states "
            "WHERE version_id = $1",
            version,
        )
    )[0]
    return cast(str, row["status"]), cast(bool, row["default_for_new_engagements"])


async def test_lifecycle_on_the_draft_waits_in_margarets_queue_and_never_becomes_current(
    net: Net,
) -> None:
    seed = net.seed
    tenant = await seed.firm()
    admin = await seed.person(tenant, "firm_admin")
    margaret = await seed.person(tenant, "quality_partner")
    current = await _import(net, admin, "BH EBP", _workbook())
    await _flags(net, tenant, "methodology.lifecycle", "knowledge.catalog")

    drafted = await _drafted(admin, current)

    assert drafted != current
    assert await _state(net, drafted) == ("needs_review", False)
    assert await _state(net, current) == ("published", True)
    queue = await net.call("GET", "/v1/knowledge/review-queue", margaret)
    assert queue.status_code == 200, queue.text
    items = cast(list[Json], queue.json()["items"])
    assert str(drafted) in {str(i["object_id"]) for i in items}
    assert all(str(i["object_id"]) != str(current) for i in items)


async def test_the_agent_principals_approval_is_refused_audited_and_moves_nothing(
    net: Net,
) -> None:
    seed = net.seed
    tenant = await seed.firm()
    admin = await seed.person(tenant, "firm_admin")
    margaret = await seed.person(tenant, "quality_partner")
    current = await _import(net, admin, "BH EBP", _workbook())
    await _flags(net, tenant, "methodology.lifecycle")
    drafted = await _drafted(admin, current)
    state = await lifecycle.version_state(_person(margaret, "quality_partner"), drafted)

    with pytest.raises(Forbidden):
        await lifecycle.approve_version(
            _agent_for(margaret),
            drafted,
            effective_from=date.today() + timedelta(days=30),
            checklist_hash=state.checklist_hash,
            row_version=state.row_version,
        )

    assert await _state(net, drafted) == ("needs_review", False)
    assert await _state(net, current) == ("published", True)
    refused = await seed.rows(
        "SELECT action, actor_kind, on_behalf_of_user_id FROM audit_events "
        "WHERE tenant_id = $1 AND target_id = $2 AND action = 'decision.refused_non_human'",
        tenant,
        str(drafted),
    )
    assert len(refused) == 1
    assert refused[0]["on_behalf_of_user_id"] == margaret.user_id
    approved = await seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND target_id = $2 "
        "AND action = 'methodology_version.approved'",
        tenant,
        str(drafted),
    )
    assert approved == 0


async def test_lifecycle_off_keeps_task_074_the_drafted_version_is_current(net: Net) -> None:
    seed = net.seed
    tenant = await seed.firm()
    admin = await seed.person(tenant, "firm_admin")
    current = await _import(net, admin, "BH EBP", _workbook())

    drafted = await _drafted(admin, current)

    assert await _state(net, drafted) == ("published", True)
