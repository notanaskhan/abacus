"""G-02-T18 to T20 (SPEC-349 AC-21 to AC-27, AC-30; DEC-623 to DEC-627): what the independent
suite (`test_g02t12_security_center_ac_suite.py`) does not reach.

- T18: the clock and reminder dates for a Sep 10 discovery read on Sep 14 (Day 4, Oct 10); a
  start-notification decision; a second decider who decides the other kind; the database refusing
  a status change without both decisions; the reminders sent once each on day 20.
- T19: the next run date, a paused schedule refusing approval, and a run with no firm export
  starter recording `run_skipped`.
- T20: imported and published controls counted "18 of 20 evidenced"; the same staff member cannot
  publish their own import; an unknown control 404; the WISP pack zipped from the linked
  documents as the requester reads them, sealed and downloadable with an audit event.
"""

from __future__ import annotations

import io
import uuid
import zipfile
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Final, cast

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from abacus.api import create_app
from abacus.kernel import export_bundles
from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine, tenant_connection
from abacus.kernel.flags import forget_flags
from abacus.kernel.storage import s3_client
from abacus.modules.evidence import firm_export_schedule
from abacus.modules.identity.api import AuthContext, current_context
from abacus.modules.platform import incident_register, safeguards
from abacus.modules.platform.workflow_types import WispPackInput

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

if TYPE_CHECKING:
    from types_boto3_s3 import S3Client

EXPORTS: Final = "wisp-pack-bundles"
MASTER: Final = bytes(range(32))
Call = Callable[..., Awaitable[httpx.Response]]


@pytest.fixture(scope="module")
def raw(s3_settings: dict[str, str]) -> Iterator[S3Client]:
    client = s3_client(
        endpoint_url=s3_settings["endpoint_url"],
        access_key=s3_settings["access_key"],
        secret_key=s3_settings["secret_key"],
        region=s3_settings["region"],
    )
    client.create_bucket(Bucket=EXPORTS)
    yield client


@pytest.fixture(autouse=True)
async def wired(
    migrated_db: MigratedDatabase, raw: S3Client, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    forget_flags()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    reset_key_service()
    configure_key_service(LocalKeyService(MASTER))
    export_bundles.configure_export_bundles(raw, EXPORTS)
    yield
    export_bundles.reset_export_bundles()
    reset_key_service()
    await dispose_engine()
    settings.cache_clear()
    forget_flags()


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


@dataclass(frozen=True)
class World:
    tenant: uuid.UUID
    felix: AuthContext  # security_admin, the QI
    margaret: AuthContext  # quality_partner, partner level
    daniel: AuthContext  # partner level


async def _member(
    seed: Seeder, tenant: uuid.UUID, name: str, *, firm_role: str | None, level: str | None
) -> AuthContext:
    user = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
            "VALUES ('https://probe.test', $1, $2, $3) RETURNING id",
            uuid.uuid4().hex,
            f"{uuid.uuid4().hex}@example.test",
            name,
        ),
    )
    membership = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO memberships (tenant_id, user_id, firm_role, status, level, kind) "
            "VALUES ($1, $2, $3, 'active', $4, 'staff') RETURNING id",
            tenant,
            user,
            firm_role,
            level,
        ),
    )
    return AuthContext(
        tenant=TenantContext(tenant, "human", str(user)),
        user_id=user,
        membership_id=membership,
        firm_role=firm_role,  # pyright: ignore[reportArgumentType] -- a seeded firm role code
        mfa_at=datetime.now(UTC) - timedelta(minutes=1),
    )


@pytest.fixture
async def world(seed: Seeder) -> World:
    tenant = await seed.firm()
    for flag in ("security_center.v1", "compliance.incidents"):
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test', 'G-02-T18')",
            tenant,
            flag,
        )
    return World(
        tenant,
        felix=await _member(
            seed, tenant, "Felix Andersen", firm_role="security_admin", level=None
        ),
        margaret=await _member(
            seed, tenant, "Margaret Okonkwo", firm_role="quality_partner", level="partner"
        ),
        daniel=await _member(seed, tenant, "Daniel Reyes", firm_role=None, level="partner"),
    )


def bind(principal: AuthContext) -> Call:
    async def call(method: str, path: str, **kwargs: object) -> httpx.Response:
        app = create_app()
        app.dependency_overrides[current_context] = lambda: principal
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, **kwargs)  # pyright: ignore[reportArgumentType] -- httpx's keyword arguments

    return call


async def _incident(
    world: World, *, discovered: datetime, consumers: int = 0, unencrypted: bool = False
) -> dict[str, object]:
    response = await bind(world.felix)(
        "POST",
        "/v1/firm/security/incidents",
        json={
            "title": "Credential-stuffing attempts against client portal sign-in",
            "event_kind": "credential_attack",
            "discovered_at": discovered.isoformat(),
            "consumers_affected": consumers,
            "unencrypted": unencrypted,
        },
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, object], response.json())


# --- T18 -----------------------------------------------------------------------------------------


def test_ac21_the_clock_reads_day_4_and_the_reminders_days_20_25_29() -> None:
    discovered = datetime(2026, 9, 10, 14, 0, tzinfo=UTC)
    zone = "America/Chicago"
    assert incident_register.reminders_on(discovered, zone) == [
        date(2026, 9, 30),
        date(2026, 10, 5),
        date(2026, 10, 9),
    ]


async def test_ac22_the_named_partner_starts_the_notification(world: World) -> None:
    recorded = await _incident(world, discovered=datetime.now(UTC) - timedelta(days=4))
    path = f"/v1/firm/security/incidents/{recorded['id']}/decisions"
    first = await bind(world.margaret)(
        "POST",
        path,
        json={"kind": "start_notification", "second_decider_user_id": str(world.felix.user_id)},
    )
    assert first.status_code == 200, first.text
    assert first.json()["pending_decision"]["waiting_for_seat"] == "qualified_individual"
    other = await bind(world.felix)("POST", path, json={"kind": "close_not_reportable"})
    assert other.status_code == 409 and other.json()["detail"] == "decision_kind_differs"
    second = await bind(world.felix)("POST", path, json={"kind": "start_notification"})
    assert second.status_code == 200
    assert second.json()["status"] == "investigating"
    assert second.json()["notification_started_at"] is not None


async def test_ac22_the_database_refuses_a_status_change_without_both_decisions(
    world: World,
) -> None:
    recorded = await _incident(world, discovered=datetime.now(UTC) - timedelta(days=1))
    with pytest.raises(DBAPIError):
        async with tenant_connection(world.felix.tenant) as conn:
            await conn.execute(
                text("UPDATE security_incidents SET status = 'closed' WHERE id = :id"),
                {"id": uuid.UUID(str(recorded["id"]))},
            )


async def test_ac23_reminders_go_once_on_day_20(world: World, seed: Seeder) -> None:
    recorded = await _incident(
        world,
        discovered=datetime.now(UTC) - timedelta(days=21),
        consumers=812,
        unencrypted=True,
    )
    assert recorded["notification_event"] is True
    assert await incident_register.remind_firm(world.tenant) == 1
    assert await incident_register.remind_firm(world.tenant) == 0  # once each
    days = await seed.rows(
        "SELECT day FROM security_incident_reminders WHERE incident_id = $1",
        uuid.UUID(str(recorded["id"])),
    )
    assert [r["day"] for r in days] == [20]
    outbox = await seed.value(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 "
        "AND event_type = 'incident.deadline_approaching'",
        world.tenant,
    )
    assert outbox == 1


# --- T19 -----------------------------------------------------------------------------------------

_SCHEDULE: Final = {"contents": ["clients", "files", "audit_log"], "version": 0}


def test_ac25_the_next_run_is_the_first_at_two_in_the_firms_zone() -> None:
    zone = "America/Chicago"
    assert firm_export_schedule.next_run_on(zone, datetime(2026, 9, 14, 12, tzinfo=UTC)) == date(
        2026, 10, 1
    )
    assert firm_export_schedule.next_run_on(zone, datetime(2026, 12, 20, tzinfo=UTC)) == date(
        2027, 1, 1
    )


async def test_ac25_a_paused_schedule_is_not_approved_and_a_run_without_a_starter_skips(
    world: World, seed: Seeder
) -> None:
    put = await bind(world.felix)(
        "PUT", "/v1/firm/data-exports/schedule", json={**_SCHEDULE, "paused": True}
    )
    assert put.status_code == 200 and put.json()["status"] == "paused"
    refused = await bind(world.margaret)("POST", "/v1/firm/data-exports/schedule/approve")
    assert refused.status_code == 409 and refused.json()["detail"] == "schedule_paused"
    running = await bind(world.felix)(
        "PUT", "/v1/firm/data-exports/schedule", json={**_SCHEDULE, "version": 1}
    )
    assert running.json()["status"] == "pending_approval"
    for who in (world.felix, world.margaret):
        assert (
            await bind(who)("POST", "/v1/firm/data-exports/schedule/approve")
        ).status_code == 200
    active = (await bind(world.daniel)("GET", "/v1/firm/data-exports/schedule")).json()
    assert active["status"] == "active" and active["next_run_on"] is not None
    assert await firm_export_schedule.run_scheduled(world.tenant) == "skipped"
    skipped = await seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'firm_export_schedule.run_skipped' AND actor_kind = 'system'",
        world.tenant,
    )
    assert skipped == 1
    # Security review: an approver who left the partner seat no longer stands behind the run.
    await seed.run(
        "UPDATE memberships SET level = 'manager' WHERE tenant_id = $1 AND user_id = $2",
        world.tenant,
        world.margaret.user_id,
    )
    assert await firm_export_schedule.run_scheduled(world.tenant) == "lapsed"
    lapsed = (await bind(world.felix)("GET", "/v1/firm/data-exports/schedule")).json()
    assert lapsed["status"] == "pending_approval"
    assert [a["seat"] for a in lapsed["approvals"]] == ["security_admin"]


# --- T20 -----------------------------------------------------------------------------------------


async def _controls(n: int = 20) -> int:
    version = int(uuid.uuid4().int % 1_000_000) + 1
    rows = [
        {"control_key": f"control_{i:02d}", "title": f"Control {i}", "position": i}
        for i in range(1, n + 1)
    ]
    await safeguards.import_controls(version, rows, "staff-a")
    with pytest.raises(safeguards.ControlSetSamePerson):
        await safeguards.publish_controls(version, "staff-a")
    assert await safeguards.publish_controls(version, "staff-b") == n
    return version


async def test_ac27_ac30_eighteen_of_twenty_evidenced_and_the_posture_agrees(
    world: World,
) -> None:
    await _controls()
    for i in range(1, 19):
        response = await bind(world.felix)(
            "PUT", f"/v1/firm/safeguards/controls/control_{i:02d}", json={"status": "evidenced"}
        )
        assert response.status_code == 200, response.text
    unknown = await bind(world.felix)(
        "PUT", "/v1/firm/safeguards/controls/not_a_control", json={"status": "evidenced"}
    )
    assert unknown.status_code == 404
    record = (await bind(world.margaret)("GET", "/v1/firm/safeguards")).json()
    assert (record["controls_evidenced"], record["controls_total"]) == (18, 20)
    assert [c["control_key"] for c in record["open_controls"]] == ["control_19", "control_20"]
    posture = (await bind(world.felix)("GET", "/v1/firm/security/posture")).json()
    assert posture["pub4557_open"] == 2


async def test_ac27_the_record_is_saved_against_its_version(world: World) -> None:
    saved = await bind(world.felix)(
        "PUT",
        "/v1/firm/safeguards",
        json={
            "qualified_individual_user_id": str(world.felix.user_id),
            "wisp_name": "BH WISP v4",
            "wisp_approved_by_user_id": str(world.margaret.user_id),
            "wisp_approved_on": "2026-01-15",
            "annual_report_next_due_month": "2026-12",
            "version": 0,
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["wisp"]["approved_by"]["display_name"] == "Margaret Okonkwo"
    stale = await bind(world.felix)("PUT", "/v1/firm/safeguards", json={"version": 0})
    assert stale.status_code == 409 and stale.json()["detail"] == "stale_version"


@dataclass(frozen=True)
class _Doc:
    content: bytes
    file_name: str


async def test_ac27_the_wisp_pack_zips_the_linked_documents(
    world: World, seed: Seeder, monkeypatch: pytest.MonkeyPatch
) -> None:
    wisp, linked = uuid.uuid4(), uuid.uuid4()
    read_as: list[uuid.UUID] = []

    async def reader(ctx: AuthContext, item: uuid.UUID) -> _Doc:
        read_as.append(ctx.user_id)
        return _Doc(f"document {item}".encode(), "BH WISP v4.pdf" if item == wisp else "pen.pdf")

    monkeypatch.setattr(safeguards, "_documents", [reader])
    await _controls(2)
    await bind(world.felix)(
        "PUT",
        "/v1/firm/safeguards",
        json={"wisp_name": "BH WISP v4", "wisp_evidence_item_id": str(wisp), "version": 0},
    )
    await bind(world.felix)(
        "PUT",
        "/v1/firm/safeguards/controls/control_01",
        json={"status": "evidenced", "evidence_item_id": str(linked)},
    )
    requested = await bind(world.felix)("POST", "/v1/firm/safeguards/wisp-pack")
    assert requested.status_code == 202 and requested.json()["status"] == "preparing"
    pack_id = requested.json()["id"]
    facts = await safeguards.build_pack(WispPackInput(str(world.tenant), pack_id))
    assert facts.document_count == 2
    assert await safeguards.mark_pack_ready(facts) == "ready"
    assert set(read_as) == {world.felix.user_id}  # as the requester
    ready = (await bind(world.felix)("GET", f"/v1/firm/safeguards/wisp-pack/{pack_id}")).json()
    assert ready["status"] == "ready" and ready["document_count"] == 2
    downloaded = await bind(world.felix)("GET", ready["download_url"])
    assert downloaded.status_code == 200
    names = zipfile.ZipFile(io.BytesIO(downloaded.content)).namelist()
    assert names == ["01 BH WISP v4.pdf", "02 pen.pdf"]
    other = await bind(world.margaret)("GET", f"/v1/firm/safeguards/wisp-pack/{pack_id}")
    assert other.status_code == 403  # security.manage is the QI's
    prepared = await seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND action = 'wisp_pack.prepared' "
        "AND actor_id = $2",
        world.tenant,
        str(world.felix.user_id),
    )
    assert prepared == 1
    # Security review M1: the download names the requester before the first byte.
    downloaded_events = await seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'wisp_pack.downloaded' AND actor_id = $2",
        world.tenant,
        str(world.felix.user_id),
    )
    assert downloaded_events == 1
