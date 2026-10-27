# ac-test-author: claude (main session, S12 build batch; ADR-078 note in TASK-1501)
"""A-01-T25 (TASK-1501): the engagement export's lifecycle and refusals, from SPEC-344 and
`docs/contracts/engagement-export-v1.md`, black-box at the public service boundary.

- A ready export expires once its 7 days pass: status `expired`, reason `expired`.
- A ready export holding a version that is withdrawn is voided: status `expired`, reason
  `withdrawn_content`; an export not holding it is untouched.
- The agent and the system never create an export (I-AGENT-NEVER); a stale second factor asks for
  a step-up (`mfa_required`) and writes nothing.
- Two builds of one export are byte-identical (AC-10) on real storage.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from abacus.kernel import clock
from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.evidence import export_activities, export_lifecycle, exports
from abacus.modules.evidence.export_models import EngagementExport
from abacus.modules.identity.api import Forbidden

from .test_a01t19_engagement_export_package import Northwind, northwind, raw, wired

# The A-01-T19 module's fixtures: storage, buckets and the seeded Northwind engagement.
FIXTURES = (northwind, raw, wired)


async def _create(world: Northwind, ctx: object | None = None) -> uuid.UUID:
    view = await exports.create(
        ctx if ctx is not None else world.hannah.context(),  # type: ignore[arg-type]
        world.work_item,
        kind="binder",
        binder_ids=[],
        include_unaccepted=True,
        include_audit_trail=False,
        idempotency_key=f"key-{uuid.uuid4().hex}",
    )
    return view.id


async def _row(world: Northwind, export_id: uuid.UUID) -> EngagementExport:
    async with tenant_session(TenantContext(world.tenant, "system", "test")) as session:
        row = await session.get(EngagementExport, export_id, populate_existing=True)
    assert row is not None
    return row


async def _ready(world: Northwind) -> EngagementExport:
    export_id = await _create(world)
    row = await _row(world, export_id)
    with clock.frozen(row.not_before + timedelta(seconds=1)):
        assert await export_activities.start_export(world.tenant, export_id) == "packaging"
        await export_activities.snapshot_export(world.tenant, export_id)
        facts = await export_activities.package_export(world.tenant, export_id)
        assert await export_activities.ready_export(facts) == "ready"
    return await _row(world, export_id)


async def test_ac_a_ready_export_expires_after_its_seven_days(northwind: Northwind) -> None:
    row = await _ready(northwind)
    assert row.status == "ready" and row.expires_at is not None
    with clock.frozen(row.expires_at - timedelta(minutes=1)):
        assert await export_lifecycle.expire_due(northwind.tenant) == 0
    assert (await _row(northwind, row.id)).status == "ready"
    with clock.frozen(row.expires_at + timedelta(minutes=1)):
        assert await export_lifecycle.expire_due(northwind.tenant) >= 1
    gone = await _row(northwind, row.id)
    assert (gone.status, gone.void_reason) == ("expired", export_lifecycle.EXPIRED)


async def test_ac_a_withdrawn_version_voids_the_ready_export_holding_it(
    northwind: Northwind,
) -> None:
    row = await _ready(northwind)
    held = next(iter(northwind.versions))
    assert await export_lifecycle.void_holding(northwind.tenant, uuid.uuid4()) == 0
    assert (await _row(northwind, row.id)).status == "ready"
    assert await export_lifecycle.void_holding(northwind.tenant, held) == 1
    voided = await _row(northwind, row.id)
    assert (voided.status, voided.void_reason) == ("expired", export_lifecycle.WITHDRAWN)
    assert await export_lifecycle.void_holding(northwind.tenant, held) == 0  # once


async def test_i_agent_never_the_agent_and_the_system_never_create_an_export(
    northwind: Northwind,
) -> None:
    hannah = northwind.hannah.context()
    agent = TenantContext(northwind.tenant, "agent", "agent:screener:1")
    system = TenantContext(northwind.tenant, "system", "system:test")
    for tenant in (agent, system):
        who = replace(hannah, tenant=tenant)
        with pytest.raises(Forbidden):
            await _create(northwind, who)
    assert await northwind.seed.count("engagement_exports", northwind.tenant) == 0


async def test_a_stale_second_factor_asks_for_a_step_up_and_writes_nothing(
    northwind: Northwind,
) -> None:
    stale = replace(northwind.hannah.context(), mfa_at=datetime.now(UTC) - timedelta(hours=2))
    with pytest.raises(exports.ExportNeedsMfa) as stepping_up:
        await _create(northwind, stale)
    assert stepping_up.value.facts == {"reason": "mfa_required"}
    assert await northwind.seed.count("engagement_exports", northwind.tenant) == 0


async def test_ac10_two_builds_of_one_export_are_byte_identical(northwind: Northwind) -> None:
    export_id = await _create(northwind)
    row = await _row(northwind, export_id)
    with clock.frozen(row.not_before + timedelta(seconds=1)):
        await export_activities.start_export(northwind.tenant, export_id)
        await export_activities.snapshot_export(northwind.tenant, export_id)
        first = await export_activities.package_export(northwind.tenant, export_id)
        second = await export_activities.package_export(northwind.tenant, export_id)
    assert (first.bundle_sha256, first.manifest_sha256, first.bytes) == (
        second.bundle_sha256,
        second.manifest_sha256,
        second.bytes,
    )
