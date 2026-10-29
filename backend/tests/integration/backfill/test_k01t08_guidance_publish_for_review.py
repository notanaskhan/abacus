"""K-01-T08 (DEC-901): with `methodology.lifecycle` on, a published guidance draft lands in Needs
review (Margaret's review queue) instead of becoming the current version; with it off, TASK-074's
behaviour stands (the drafted version is published and becomes the default)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.uow import uow
from abacus.modules.identity.api import AuthContext
from abacus.modules.methodology.api import ApprovedGuidance, publish_drafted_version

from .support import Net, Person
from .test_k01t05_methodology_programs import (
    _flags,  # pyright: ignore[reportPrivateUsage] -- K-01-T05's flag seeding
    _import,  # pyright: ignore[reportPrivateUsage] -- K-01-T05's workbook import
    _workbook,  # pyright: ignore[reportPrivateUsage] -- K-01-T05's BH EBP workbook
)

pytestmark = pytest.mark.asyncio


def _ctx(who: Person) -> AuthContext:
    return AuthContext(
        tenant=TenantContext(who.tenant_id, "human", str(who.user_id)),
        user_id=who.user_id,
        membership_id=uuid.uuid4(),
        firm_role="firm_admin",
        mfa_at=datetime.now(UTC) - timedelta(minutes=1),
    )


async def _publish(admin: Person, version: uuid.UUID) -> uuid.UUID:
    ctx = _ctx(admin)
    approved = [
        ApprovedGuidance(
            position=0,
            why="Supports the planning conclusion.",
            good_looks_like="The signed engagement letter for the year.",
            effort=None,
            blocks_fieldwork=False,
            approved_by=admin.user_id,
        )
    ]
    async with uow(ctx.tenant) as tx:
        summary = await publish_drafted_version(tx, ctx, version, approved)
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


async def test_ac38_lifecycle_on_a_published_guidance_draft_waits_in_needs_review(
    net: Net,
) -> None:
    seed = net.seed
    tenant = await seed.firm()
    admin = await seed.person(tenant, "firm_admin")
    v2 = await _import(net, admin, "BH EBP", _workbook())
    await _flags(net, tenant, "methodology.lifecycle")

    drafted = await _publish(admin, v2)

    assert await _state(net, drafted) == ("needs_review", False)
    assert await _state(net, v2) == ("published", True)  # still the current version
    queued = await seed.rows(
        "SELECT payload FROM outbox WHERE tenant_id = $1 "
        "AND event_type = 'methodology.review_requested'",
        tenant,
    )
    assert len(queued) == 1 and str(drafted) in str(queued[0]["payload"])  # quality partners
    audited = await seed.rows(
        "SELECT after_ref FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'methodology.published' AND target_id = $2",
        tenant,
        str(drafted),
    )
    assert len(audited) == 1 and "needs_review" in str(audited[0]["after_ref"])


async def test_lifecycle_off_keeps_task_074_the_drafted_version_is_published(net: Net) -> None:
    seed = net.seed
    tenant = await seed.firm()
    admin = await seed.person(tenant, "firm_admin")
    v2 = await _import(net, admin, "BH EBP", _workbook())

    drafted = await _publish(admin, v2)

    status, default = await _state(net, drafted)
    assert status == "published" and default is True
