"""A-01-T23 against Postgres and S3 (TASK-1443; A-01 §3.5 Stories 5.2, 5.3; DEC-590, DEC-591):
"Meridian archives only against a fresh final export, becomes read-only, and keeps
`archive_locked_at` NULL."

Reuses A-01-T19's binder (Brightwater Hale, synthetic). The final binder export is created by
the service and built by the workflow's steps; the release and the archive are recorded through
the services as the app role. The audit is placed in In review by the superuser (record mode cannot
reach Ready to release while SPEC-314's G6 and G7 are registered, DEC-590).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from typing import cast

import asyncpg
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from abacus.kernel import clock
from abacus.kernel._human_only_actions import HUMAN_ONLY_ACTIONS
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.uow import Ref, Target, uow

# The app imports `assurance.api` at startup, which registers the G8 and G9 providers the phase
# move computes; run on its own, this file must import it too (the gates read unmet otherwise).
from abacus.modules.assurance import api as _assurance_api  # noqa: F401  # pyright: ignore[reportUnusedImport]
from abacus.modules.assurance import archive_gate, phase, release
from abacus.modules.assurance.record_auth import RecordNeedsMfa
from abacus.modules.engagements.api import gate_fact
from abacus.modules.evidence import export_activities, exports
from abacus.modules.evidence.api import ExportStale, FinalExportRequired
from abacus.modules.evidence.export_models import EngagementExport
from abacus.modules.identity.api import AuthContext, Forbidden

from . import test_a01t19_engagement_export_package as t19
from .agent_tests.support import Person
from .test_a01t19_engagement_export_package import Northwind

wired = t19.wired
raw = t19.raw
northwind = t19.northwind

RELEASED_ON = date(2026, 4, 17)
REFERENCE = "CaseWare BH-2025-031"


@dataclass(frozen=True)
class Meridian:
    world: Northwind
    engagement: uuid.UUID
    manager: Person

    @property
    def hannah(self) -> AuthContext:
        return self.world.hannah.context()

    @property
    def work_item(self) -> uuid.UUID:
        return self.world.work_item

    async def item_row(self) -> asyncpg.Record:
        rows = await self.world.seed.rows(
            "SELECT w.archived_at, w.archive_locked_at, e.status, a.phase "
            "FROM work_items w JOIN engagements e ON e.id = w.engagement_id "
            "JOIN assurance_work_items a ON a.work_item_id = w.id WHERE w.id = $1",
            self.work_item,
        )
        return rows[0]


@pytest.fixture
async def meridian(northwind: Northwind) -> Meridian:
    seed = northwind.seed
    engagement = cast(
        uuid.UUID,
        await seed.value(
            "SELECT engagement_id FROM work_items WHERE id = $1", northwind.work_item
        ),
    )
    manager = await seed.person(northwind.tenant)
    await seed.member(engagement, manager, "manager")
    await seed.run(
        "UPDATE assurance_work_items SET phase = 'in_review' WHERE work_item_id = $1",
        northwind.work_item,
    )
    return Meridian(northwind, engagement, manager)


async def _export(world: Meridian, kind: str) -> EngagementExport:
    view = await exports.create(
        world.hannah,
        world.work_item,
        kind=kind,
        binder_ids=[],
        include_unaccepted=False,
        include_audit_trail=True,
        idempotency_key=f"key-{uuid.uuid4().hex}",
    )
    row = await _row(world, view.id)
    with clock.frozen(row.not_before + timedelta(seconds=1)):
        await export_activities.start_export(world.world.tenant, row.id)
        await export_activities.snapshot_export(world.world.tenant, row.id)
        facts = await export_activities.package_export(
            world.world.tenant, row.id, segment_bytes=1 << 20
        )
        assert await export_activities.ready_export(facts) == "ready"
    return await _row(world, row.id)


async def _row(world: Meridian, export_id: uuid.UUID) -> EngagementExport:
    async with tenant_session(TenantContext(world.world.tenant, "system", "test")) as session:
        row = await session.get(EngagementExport, export_id)
    assert row is not None
    return row


async def _released(world: Meridian) -> None:
    made = await release.record_release(world.hannah, world.work_item, RELEASED_ON, "opinion")
    assert (made.phase, made.archive_due_on) == ("released", RELEASED_ON + timedelta(days=60))


# --- the acceptance line -------------------------------------------------------------------------


async def test_ac_meridian_archives_only_against_a_fresh_final_export_and_becomes_read_only(
    meridian: Meridian,
) -> None:
    await _released(meridian)
    assert (
        await gate_fact(
            TenantContext(meridian.world.tenant, "system", "t"), meridian.engagement, "G8"
        )
    ).met
    # A ready export that is not the final binder does not archive.
    plain = await _export(meridian, "binder")
    with pytest.raises(FinalExportRequired):
        await archive_gate.record_archive(meridian.hannah, meridian.work_item, plain.id, REFERENCE)
    final = await _export(meridian, "final_binder")
    assert final.manifest_sha256 is not None
    made = await archive_gate.record_archive(
        meridian.hannah, meridian.work_item, final.id, REFERENCE
    )
    assert (made.phase, made.export_id, made.manifest_sha256) == (
        "archived",
        final.id,
        final.manifest_sha256,
    )
    row = await meridian.item_row()
    assert row["archived_at"] is not None
    assert row["archive_locked_at"] is None  # not A-07's seal (P-43)
    assert (row["status"], row["phase"]) == ("archived", "archived")
    stored = await meridian.world.seed.rows(
        "SELECT export_id, manifest_sha256, firm_tool_ref_sealed, actor_kind, mfa_at "
        "FROM assurance_external_archives WHERE work_item_id = $1",
        meridian.work_item,
    )
    assert stored[0]["export_id"] == final.id
    assert REFERENCE.encode() not in bytes(stored[0]["firm_tool_ref_sealed"])  # sealed
    assert stored[0]["actor_kind"] == "human" and stored[0]["mfa_at"] is not None
    assert (
        await gate_fact(
            TenantContext(meridian.world.tenant, "system", "t"), meridian.engagement, "G9"
        )
    ).met
    actions = await meridian.world.seed.actions(meridian.world.tenant)
    assert "assurance.release_recorded" in actions and "assurance.archive_recorded" in actions
    # Read-only: every write on the engagement is refused.
    with pytest.raises(Forbidden):
        await phase.update_profile(meridian.hannah, meridian.work_item, 99, {})
    with pytest.raises(Forbidden):
        await archive_gate.record_archive(meridian.hannah, meridian.work_item, final.id, REFERENCE)


async def test_ac_an_export_older_than_the_evidence_is_stale(meridian: Meridian) -> None:
    await _released(meridian)
    final = await _export(meridian, "final_binder")
    request_item = cast(
        uuid.UUID,
        await meridian.world.seed.value(
            "SELECT id FROM request_items WHERE engagement_id = $1 AND status = 'received' "
            "ORDER BY created_at LIMIT 1",
            meridian.engagement,
        ),
    )
    # A change about one of its requests after the snapshot (a person edits the request).
    async with uow(meridian.hannah.tenant) as tx:
        tx.record(
            "request_item.updated",
            target=Target("request_item", request_item),
            after=Ref(version=2),
        )
    with pytest.raises(ExportStale) as stale:
        await archive_gate.record_archive(meridian.hannah, meridian.work_item, final.id, REFERENCE)
    assert stale.value.facts["reason"] == "newer_event"
    # A read is not a change: a fresh export after it archives.
    fresh = await _export(meridian, "final_binder")
    version = next(iter(meridian.world.versions))
    async with uow(meridian.hannah.tenant) as tx:
        tx.record("evidence_version.read", target=Target("evidence_version", version))
    await archive_gate.record_archive(meridian.hannah, meridian.work_item, fresh.id, REFERENCE)
    assert (await meridian.item_row())["archive_locked_at"] is None


async def test_ac_a_request_added_after_the_snapshot_makes_the_export_stale(
    meridian: Meridian,
) -> None:
    await _released(meridian)
    final = await _export(meridian, "final_binder")
    seed = meridian.world.seed
    await seed.run(
        "INSERT INTO request_items (tenant_id, engagement_id, request_list_id, description, "
        "title, audit_area, category_id, status, created_by, created_at, client_visible, "
        "due_on, requested_at) SELECT tenant_id, engagement_id, request_list_id, 'Late', 'Late', "
        "'Area', category_id, 'requested', created_by, clock_timestamp(), true, due_on, "
        "clock_timestamp() FROM request_items WHERE engagement_id = $1 LIMIT 1",
        meridian.engagement,
    )
    with pytest.raises(ExportStale) as stale:
        await archive_gate.record_archive(meridian.hannah, meridian.work_item, final.id, REFERENCE)
    assert stale.value.facts["reason"] == "selection_changed"


# --- who, when, and the refusals --------------------------------------------------------------


async def test_a_stale_second_factor_is_mfa_required_and_a_manager_may_not_release(
    meridian: Meridian,
) -> None:
    stale = replace(meridian.hannah, mfa_at=datetime.now(UTC) - timedelta(minutes=16))
    with pytest.raises(RecordNeedsMfa) as refused:
        await release.record_release(stale, meridian.work_item, RELEASED_ON, "opinion")
    assert refused.value.facts == {"reason": "mfa_required"}
    with pytest.raises(Forbidden):  # the engagement partner only, however fresh
        await release.record_release(
            meridian.manager.context(), meridian.work_item, RELEASED_ON, "opinion"
        )
    agent = replace(
        meridian.hannah,
        tenant=TenantContext(meridian.world.tenant, "agent", str(meridian.world.hannah.user_id)),
    )
    with pytest.raises(Forbidden):
        await release.record_release(agent, meridian.work_item, RELEASED_ON, "opinion")
    assert (await meridian.item_row())["phase"] == "in_review"


async def test_a_manager_records_the_archive_with_fresh_mfa(meridian: Meridian) -> None:
    await _released(meridian)
    final = await _export(meridian, "final_binder")
    stale = replace(meridian.manager.context(), mfa_at=None)
    with pytest.raises(RecordNeedsMfa):
        await archive_gate.record_archive(stale, meridian.work_item, final.id, REFERENCE)
    made = await archive_gate.record_archive(
        meridian.manager.context(), meridian.work_item, final.id, REFERENCE
    )
    assert made.phase == "archived"


async def test_release_date_phase_and_mode_refusals(meridian: Meridian) -> None:
    future = date.today() + timedelta(days=400)
    with pytest.raises(release.ReleaseDateFuture):
        await release.record_release(meridian.hannah, meridian.work_item, future, "opinion")
    # DEC-598: a report on a period is released after the period ends.
    period_end = await meridian.world.seed.value(
        "SELECT fiscal_period_end FROM engagements WHERE id = $1", meridian.engagement
    )
    assert isinstance(period_end, date)
    with pytest.raises(release.ReleaseDateBeforePeriodEnd):
        await release.record_release(meridian.hannah, meridian.work_item, period_end, "opinion")
    assert (await meridian.item_row())["phase"] == "in_review"
    final_too_early = await _export(meridian, "final_binder")
    with pytest.raises(release.RecordOutOfPhase):  # not released yet
        await archive_gate.record_archive(
            meridian.hannah, meridian.work_item, final_too_early.id, REFERENCE
        )
    await _released(meridian)
    with pytest.raises(release.RecordOutOfPhase):  # released once
        await release.record_release(meridian.hannah, meridian.work_item, RELEASED_ON, "opinion")
    await meridian.world.seed.run(
        "INSERT INTO firm_settings (tenant_id, section, key, value, updated_by) "
        "VALUES ($1, 'defaults', 'assurance_release_mode', '\"in_app\"'::jsonb, $2)",
        meridian.world.tenant,
        meridian.world.hannah.user_id,
    )
    final = await _export(meridian, "final_binder")
    with pytest.raises(release.ReleaseModeInApp):
        await archive_gate.record_archive(meridian.hannah, meridian.work_item, final.id, REFERENCE)


# --- the data layer -----------------------------------------------------------------------------


async def test_the_tables_bind_the_person_and_re_check_the_export(meridian: Meridian) -> None:
    plain = await _export(meridian, "binder")
    other = uuid.uuid4()
    insert = text(
        "INSERT INTO assurance_external_archives (work_item_id, tenant_id, engagement_id, "
        "export_id, manifest_sha256, firm_tool_ref_sealed, recorded_by, actor_kind, mfa_at) "
        "VALUES (:w, :t, :e, :x, :m, '\\x00'::bytea, :by, 'human', clock_timestamp())"
    )
    values = {
        "w": meridian.work_item,
        "t": meridian.world.tenant,
        "e": meridian.engagement,
        "x": plain.id,
        "m": plain.manifest_sha256,
    }
    with pytest.raises(DBAPIError, match="person acting"):  # another person's name
        async with tenant_session(meridian.hannah.tenant) as session:
            await session.execute(insert, {**values, "by": other})
    with pytest.raises(DBAPIError, match="final_export_required"):  # not a final binder
        async with tenant_session(meridian.hannah.tenant) as session:
            await session.execute(insert, {**values, "by": meridian.world.hannah.user_id})


def test_the_records_are_human_only_actions() -> None:
    assert {"assurance.release_recorded", "assurance.archive_recorded"} <= HUMAN_ONLY_ACTIONS
