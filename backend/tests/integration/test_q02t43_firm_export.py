"""Q-02-T43 against Postgres and S3 (TASK-1403; DEC-72, conflict C-11; compliance-kernel §2 to §7):
"A same-person approval is refused, a second distinct approver starts the export, and the link
stops working after 7 days."

A synthetic firm with a security admin (the requester), a partner-level member (the approver),
a second security admin and a staff member. The service runs as each person; the workflow's steps
run directly; the database's own refusals are tried with direct statements as each actor."""

from __future__ import annotations

import hashlib
import io
import json
import uuid
import zipfile
from collections.abc import AsyncIterator, Iterator
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import cast

import asyncpg
import pytest
from botocore.exceptions import ClientError
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.responses import Response
from types_boto3_s3 import S3Client

from abacus.kernel import clock
from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import forget_flags
from abacus.kernel.storage import s3_client
from abacus.kernel.uow import OutboxEvent
from abacus.modules.evidence import (
    export_storage,
    firm_export_activities,
    firm_export_contract,
    firm_exports,
)
from abacus.modules.evidence.export_download import ExportExpired, ExportNotReady
from abacus.modules.evidence.firm_export_models import FirmExport
from abacus.modules.identity.api import AuthContext, Forbidden

from .agent_tests.support import Person, Seeder
from .conftest import MigratedDatabase

ARCHIVES = "firm-export-archives"
MASTER = bytes(range(32))


@pytest.fixture(scope="module")
def raw(s3_settings: dict[str, str]) -> Iterator[S3Client]:
    made = s3_client(
        endpoint_url=s3_settings["endpoint_url"],
        access_key=s3_settings["access_key"],
        secret_key=s3_settings["secret_key"],
        region=s3_settings["region"],
    )
    with suppress(ClientError):
        made.create_bucket(Bucket=ARCHIVES)
    yield made


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
    export_storage.configure_exports(raw, ARCHIVES)

    async def on(_tenant: object, _flag: object) -> bool:
        return True

    monkeypatch.setattr(firm_exports, "flag_enabled", on)
    yield
    export_storage.reset_exports()
    reset_key_service()
    await dispose_engine()
    settings.cache_clear()
    forget_flags()


@dataclass(frozen=True)
class Firm:
    seed: Seeder
    tenant: uuid.UUID
    admin: Person  # the security admin who asks
    partner: Person  # the partner-level approver
    other_admin: Person  # a second security admin, not named
    staff: Person  # no role on firm exports


def ctx_of(person: Person, firm_role: str | None = None) -> AuthContext:
    return replace(person.context(), firm_role=firm_role)


async def _firm(seed: Seeder) -> Firm:
    tenant = await seed.firm()
    await seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", tenant)
    admin, partner, other, staff = [await seed.person(tenant) for _ in range(4)]
    for who in (admin, other):
        await seed.run(
            "UPDATE memberships SET firm_role = 'security_admin' "
            "WHERE tenant_id = $1 AND user_id = $2",
            tenant,
            who.user_id,
        )
    await seed.run(
        "UPDATE memberships SET level = 'partner' WHERE tenant_id = $1 AND user_id = $2",
        tenant,
        partner.user_id,
    )
    return Firm(seed, tenant, admin, partner, other, staff)


@pytest.fixture
async def firm(migrated_db: MigratedDatabase) -> Firm:
    return await _firm(Seeder(migrated_db.superuser_dsn))


def admin_ctx(firm: Firm) -> AuthContext:
    return ctx_of(firm.admin, "security_admin")


def partner_ctx(firm: Firm) -> AuthContext:
    return ctx_of(firm.partner)


async def _row(firm: Firm, export_id: uuid.UUID) -> FirmExport:
    async with tenant_session(TenantContext(firm.tenant, "system", "test")) as session:
        row = await session.get(FirmExport, export_id, populate_existing=True)
    assert row is not None
    return row


async def _requested(firm: Firm) -> uuid.UUID:
    view = await firm_exports.request(
        admin_ctx(firm), firm.partner.user_id, idempotency_key=f"key-{uuid.uuid4().hex}"
    )
    assert view.status == "awaiting_approval"
    return view.id


async def _ready(firm: Firm) -> FirmExport:
    export_id = await _requested(firm)
    await firm_exports.decide(partner_ctx(firm), export_id, approve=True)
    facts = await firm_export_activities.package_export(firm.tenant, export_id, segment_bytes=512)
    assert await firm_export_activities.ready_export(facts) == "ready"
    return await _row(firm, export_id)


async def _outbox(firm: Firm, event_type: str) -> list[dict[str, object]]:
    rows = await firm.seed.rows(
        "SELECT payload::text AS p FROM outbox WHERE tenant_id = $1 AND event_type = $2",
        firm.tenant,
        event_type,
    )
    return [cast(dict[str, object], json.loads(r["p"])) for r in rows]


async def _body(response: Response) -> bytes:
    assert isinstance(response, StreamingResponse)
    parts: list[bytes] = []
    async for chunk in response.body_iterator:
        parts.append(chunk if isinstance(chunk, bytes) else str(chunk).encode())
    return b"".join(parts)


def _link_id(url: str) -> uuid.UUID:
    return uuid.UUID(url.rsplit("/", 1)[1])


async def _archive(ctx: AuthContext, export_id: uuid.UUID, rng: str | None = None) -> Response:
    link = await firm_exports.issue_link(ctx, export_id)
    return await firm_export_contract.firm_export_archive_route(
        export_id, _link_id(link.url), ctx, range_header=rng, if_range=None
    )


# --- AC 1: a same-person approval is refused -----------------------------------------------------


async def test_ac1_a_same_person_approval_is_refused(firm: Firm) -> None:
    # The requester can't name themself, and can't approve or decline their own export.
    with pytest.raises(firm_exports.ApproverInvalid):
        await firm_exports.request(
            admin_ctx(firm), firm.admin.user_id, idempotency_key=f"key-{uuid.uuid4().hex}"
        )
    export_id = await _requested(firm)
    with pytest.raises(firm_exports.ApproverMustDiffer):
        await firm_exports.decide(admin_ctx(firm), export_id, approve=True)
    with pytest.raises(firm_exports.ApproverMustDiffer):
        await firm_exports.decide(admin_ctx(firm), export_id, approve=False)
    assert (await _row(firm, export_id)).status == "awaiting_approval"
    assert await _outbox(firm, "firm_export.approved") == []


async def test_ac1_the_database_refuses_one_person_as_both_halves(firm: Firm) -> None:
    admin = firm.admin.user_id
    # An insert naming the requester as approver: the CHECK.
    with pytest.raises(asyncpg.CheckViolationError):
        await firm.seed.as_actor(
            firm.tenant,
            ("human", str(admin)),
            "INSERT INTO firm_exports (tenant_id, requested_by, requested_by_kind, "
            "request_mfa_at, approver_id) VALUES ($1, $2, 'human', now(), $2)",
            firm.tenant,
            admin,
        )
    # An insert for someone else, or by a person who is no security admin: the requester trigger.
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await firm.seed.as_actor(
            firm.tenant,
            ("human", str(firm.staff.user_id)),
            "INSERT INTO firm_exports (tenant_id, requested_by, requested_by_kind, "
            "request_mfa_at, approver_id) VALUES ($1, $2, 'human', now(), $3)",
            firm.tenant,
            admin,
            firm.partner.user_id,
        )
    # An approver who is neither a security admin nor partner level.
    with pytest.raises(asyncpg.CheckViolationError, match="approver_invalid"):
        await firm.seed.as_actor(
            firm.tenant,
            ("human", str(admin)),
            "INSERT INTO firm_exports (tenant_id, requested_by, requested_by_kind, "
            "request_mfa_at, approver_id) VALUES ($1, $2, 'human', now(), $3)",
            firm.tenant,
            admin,
            firm.staff.user_id,
        )
    export_id = await _requested(firm)
    decide = (
        "UPDATE firm_exports SET status = 'building', decided_by = $2, decided_at = now(), "
        "decided_mfa_at = now() WHERE id = $1"
    )
    # The requester deciding (naming either person), another admin, and the system: the guard.
    for actor, decided_by in (
        (("human", str(admin)), admin),
        (("human", str(admin)), firm.partner.user_id),
        (("human", str(firm.other_admin.user_id)), firm.partner.user_id),
        (("system", "firm_export:test"), firm.partner.user_id),
    ):
        with pytest.raises((asyncpg.InsufficientPrivilegeError, asyncpg.CheckViolationError)):
            await firm.seed.as_actor(firm.tenant, actor, decide, export_id, decided_by)
    assert (await _row(firm, export_id)).status == "awaiting_approval"


async def test_ac1_only_the_named_approver_decides(firm: Firm) -> None:
    export_id = await _requested(firm)
    with pytest.raises(Forbidden):  # a security admin who wasn't named
        await firm_exports.decide(
            ctx_of(firm.other_admin, "security_admin"), export_id, approve=True
        )
    with pytest.raises(Forbidden):  # no role at all
        await firm_exports.decide(ctx_of(firm.staff), export_id, approve=True)
    declined = await firm_exports.decide(
        partner_ctx(firm), export_id, approve=False, reason="Not this month"
    )
    assert declined.status == "declined"
    with pytest.raises(firm_exports.ExportNotAwaitingApproval):
        await firm_exports.decide(partner_ctx(firm), export_id, approve=True)


async def test_the_approver_must_be_a_security_admin_or_partner(firm: Firm) -> None:
    with pytest.raises(firm_exports.ApproverInvalid):
        await firm_exports.request(
            admin_ctx(firm), firm.staff.user_id, idempotency_key=f"key-{uuid.uuid4().hex}"
        )
    with pytest.raises(firm_exports.ApproverInvalid):
        await firm_exports.request(
            admin_ctx(firm), uuid.uuid4(), idempotency_key=f"key-{uuid.uuid4().hex}"
        )
    with pytest.raises(Forbidden):  # only a security admin asks
        await firm_exports.request(
            ctx_of(firm.partner), firm.admin.user_id, idempotency_key=f"key-{uuid.uuid4().hex}"
        )


async def test_a_stale_second_factor_is_refused_with_mfa_required(firm: Firm) -> None:
    stale = replace(admin_ctx(firm), mfa_at=datetime.now(UTC) - timedelta(hours=1))
    with pytest.raises(Forbidden) as refused:
        await firm_exports.request(
            stale, firm.partner.user_id, idempotency_key=f"key-{uuid.uuid4().hex}"
        )
    assert getattr(refused.value, "facts", {}).get("reason") == "mfa_required"


async def test_a_retried_key_returns_the_same_export(firm: Firm) -> None:
    key = f"key-{uuid.uuid4().hex}"
    first = await firm_exports.request(admin_ctx(firm), firm.partner.user_id, idempotency_key=key)
    again = await firm_exports.request(admin_ctx(firm), firm.partner.user_id, idempotency_key=key)
    assert again.id == first.id
    assert len(await _outbox(firm, "firm_export.requested")) == 1


# --- AC 2: a second distinct approver starts the export ------------------------------------------


async def test_ac2_a_second_distinct_approver_starts_the_export(
    firm: Firm, monkeypatch: pytest.MonkeyPatch
) -> None:
    export_id = await _requested(firm)
    [asked] = await _outbox(firm, "firm_export.requested")
    assert asked["approver_user_id"] == str(firm.partner.user_id)
    approved = await firm_exports.decide(partner_ctx(firm), export_id, approve=True)
    assert approved.status == "building"
    assert approved.approver.user_id == firm.partner.user_id
    [event] = await _outbox(firm, "firm_export.approved")
    started: list[str] = []

    async def dispatch(_workflow: object, given: object, **kw: object) -> None:
        started.append(str(kw["id"]))

    monkeypatch.setattr(firm_export_activities, "dispatch", dispatch)
    await firm_export_activities.on_approved(
        OutboxEvent(uuid.uuid4(), firm.tenant, "firm_export.approved", event)
    )
    assert started == [f"firm_export:{firm.tenant}:{export_id}"]

    facts = await firm_export_activities.package_export(firm.tenant, export_id, segment_bytes=512)
    assert await firm_export_activities.ready_export(facts) == "ready"
    row = await _row(firm, export_id)
    assert row.ready_at is not None and row.available_until == row.ready_at + timedelta(days=7)
    [ready] = await _outbox(firm, "firm_export.ready")
    assert ready["requested_by"] == str(firm.admin.user_id)

    # The archive streams, its digest and manifest match the row, and it resumes with Range.
    whole = await _archive(admin_ctx(firm), export_id)
    assert whole.status_code == 200
    assert whole.headers["cache-control"] == "no-store"
    assert "x-amz" not in "".join(whole.headers.keys()).lower()
    archive = await _body(whole)
    assert hashlib.sha256(archive).hexdigest() == row.bundle_sha256 and len(archive) == row.bytes
    with zipfile.ZipFile(io.BytesIO(archive)) as opened:
        manifest = opened.read("manifest.json")
        index = opened.read("index.json")
    assert hashlib.sha256(manifest).hexdigest() == row.manifest_sha256
    [listed] = json.loads(manifest)["files"]
    assert listed == {
        "path": "index.json",
        "bytes": len(index),
        "sha256": hashlib.sha256(index).hexdigest(),
    }
    assert json.loads(index)["approved_by"] == str(firm.partner.user_id)
    part = await _archive(partner_ctx(firm), export_id, "bytes=10-")
    assert part.status_code == 206 and await _body(part) == archive[10:]
    assert (await _row(firm, export_id)).status == "downloaded"
    actions = [a for a in await firm.seed.actions(firm.tenant) if a.startswith("firm_export.")]
    assert actions[:3] == ["firm_export.requested", "firm_export.approved", "firm_export.ready"]
    assert actions.count("firm_export.downloaded") == 2
    assert actions.count("firm_export.streamed") == 2


async def test_a_build_of_an_unapproved_export_is_refused(firm: Firm) -> None:
    export_id = await _requested(firm)
    with pytest.raises(firm_export_activities.FirmExportNotBuilding):
        await firm_export_activities.package_export(firm.tenant, export_id)
    with pytest.raises(ExportNotReady):
        await firm_exports.issue_link(admin_ctx(firm), export_id)


async def test_links_are_the_requesters_and_the_approvers_only(firm: Firm) -> None:
    row = await _ready(firm)
    with pytest.raises(Forbidden):
        await firm_exports.issue_link(ctx_of(firm.other_admin, "security_admin"), row.id)
    link = await firm_exports.issue_link(admin_ctx(firm), row.id)
    assert link.url == f"/v1/firm/data-exports/{row.id}/links/{_link_id(link.url)}"
    assert link.expires_at <= datetime.now(UTC) + timedelta(minutes=15)
    # The approver can't open the requester's link: a link opens for its own person only.
    with pytest.raises(NotFound):
        await firm_exports.prepare(partner_ctx(firm), row.id, _link_id(link.url), None, None)


async def test_a_link_answers_410_after_its_15_minutes(
    firm: Firm, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = await _ready(firm)
    link = await firm_exports.issue_link(admin_ctx(firm), row.id)
    later = datetime.now(UTC) + timedelta(minutes=16)
    monkeypatch.setattr(firm_exports, "system_now", lambda: later)
    gone = await firm_export_contract.firm_export_archive_route(
        row.id, _link_id(link.url), admin_ctx(firm), range_header=None, if_range=None
    )
    assert isinstance(gone, JSONResponse) and gone.status_code == 410
    assert json.loads(bytes(gone.body)) == {"detail": "link_expired"}


async def test_another_firm_sees_nothing(firm: Firm) -> None:
    row = await _ready(firm)
    stranger = await _firm(firm.seed)
    with pytest.raises(NotFound):
        await firm_exports.read(admin_ctx(stranger), row.id)
    with pytest.raises(NotFound):
        await firm_exports.decide(partner_ctx(stranger), row.id, approve=True)
    with pytest.raises(NotFound):
        await firm_exports.issue_link(admin_ctx(stranger), row.id)
    assert await firm_exports.history(admin_ctx(stranger)) == []
    assert [v.id for v in await firm_exports.history(admin_ctx(firm))] == [row.id]


# --- AC 3: the link stops working after 7 days ---------------------------------------------------


async def test_ac3_the_link_stops_working_after_7_days(firm: Firm, raw: S3Client) -> None:
    row = await _ready(firm)
    assert row.available_until is not None
    assert (await _archive(admin_ctx(firm), row.id)).status_code == 200
    with clock.frozen(row.available_until + timedelta(seconds=1)):
        gone = await firm_export_contract.link_firm_export_route(row.id, admin_ctx(firm))
        assert isinstance(gone, JSONResponse) and gone.status_code == 410
        assert json.loads(bytes(gone.body)) == {"detail": "export_expired"}
        with pytest.raises(ExportExpired):
            await firm_exports.issue_link(partner_ctx(firm), row.id)
        # The sweep marks it expired; its subscriber deletes the archive's segments.
        assert await firm_export_activities.expire_due(firm.tenant) == 1
    assert (await _row(firm, row.id)).status == "expired"
    [event] = await _outbox(firm, "firm_export.expired")
    await firm_export_activities.on_expired(
        OutboxEvent(uuid.uuid4(), firm.tenant, "firm_export.expired", event)
    )
    prefix = export_storage.export_prefix(firm.tenant, row.id, kind="firm_export")
    assert raw.list_objects_v2(Bucket=ARCHIVES, Prefix=prefix).get("KeyCount", 0) == 0
    with pytest.raises(ExportExpired):
        await firm_exports.issue_link(admin_ctx(firm), row.id)


async def test_a_link_opened_within_the_window_still_refuses_after_it(firm: Firm) -> None:
    row = await _ready(firm)
    assert row.available_until is not None
    link = await firm_exports.issue_link(admin_ctx(firm), row.id)
    with clock.frozen(row.available_until), pytest.raises(ExportExpired):
        await firm_exports.prepare(admin_ctx(firm), row.id, _link_id(link.url), None, None)
