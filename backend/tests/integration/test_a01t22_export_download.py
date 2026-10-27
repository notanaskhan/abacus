"""A-01-T22 against Postgres and S3 (TASK-1445; SPEC-344 AC-14, AC-15; DEC-536 to DEC-538):
"Downloads resume with Range, expire with 410 after 7 days, and a withdrawn file voids the ready
bundle."

Reuses A-01-T19's Northwind-like binder (Brightwater Hale, synthetic): the export is created by
the service, built by the workflow's steps on a frozen business clock, then downloaded through
the route function (headers and status), resumed, expired by the sweep and voided by a
withdrawal."""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterator
from contextlib import suppress
from datetime import timedelta

import pytest
from botocore.exceptions import ClientError
from fastapi.responses import StreamingResponse
from starlette.responses import Response
from types_boto3_s3 import S3Client

from abacus.kernel import clock
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.storage import s3_client
from abacus.kernel.uow import OutboxEvent
from abacus.modules.evidence import (
    export_activities,
    export_download,
    export_lifecycle,
    export_storage,
    exports,
)
from abacus.modules.evidence.export_contract import download_export_route
from abacus.modules.evidence.export_models import EngagementExport
from abacus.modules.identity.api import AuthContext, Forbidden

from . import test_a01t19_engagement_export_package as t19
from .test_a01t19_engagement_export_package import EXPORTS, Northwind

# A-01-T19's Northwind binder and its wiring, as this module's fixtures. The buckets are made
# here when this module runs first on a worker, and reused when A-01-T19's made them already.
wired = t19.wired
northwind = t19.northwind


@pytest.fixture(scope="module")
def raw(s3_settings: dict[str, str]) -> Iterator[S3Client]:
    made = s3_client(
        endpoint_url=s3_settings["endpoint_url"],
        access_key=s3_settings["access_key"],
        secret_key=s3_settings["secret_key"],
        region=s3_settings["region"],
    )
    with suppress(ClientError):
        made.create_bucket(Bucket=t19.EVIDENCE, ObjectLockEnabledForBucket=True)
    with suppress(ClientError):
        made.create_bucket(Bucket=EXPORTS)
    yield made


async def _requested(world: Northwind) -> EngagementExport:
    view = await exports.create(
        world.hannah.context(),
        world.work_item,
        kind="binder",
        binder_ids=[],
        include_unaccepted=False,
        include_audit_trail=True,
        idempotency_key=f"key-{uuid.uuid4().hex}",
    )
    return await _row(world, view.id)


async def _ready(world: Northwind) -> EngagementExport:
    row = await _requested(world)
    with clock.frozen(row.not_before + timedelta(seconds=1)):
        await export_activities.start_export(world.tenant, row.id)
        await export_activities.snapshot_export(world.tenant, row.id)
        facts = await export_activities.package_export(world.tenant, row.id, segment_bytes=1024)
        assert await export_activities.ready_export(facts) == "ready"
    return await _row(world, row.id)


async def _row(world: Northwind, export_id: uuid.UUID) -> EngagementExport:
    async with tenant_session(TenantContext(world.tenant, "system", "test")) as session:
        row = await session.get(EngagementExport, export_id)
    assert row is not None
    return row


async def _body(response: Response) -> bytes:
    assert isinstance(response, StreamingResponse)
    parts: list[bytes] = []
    async for chunk in response.body_iterator:
        parts.append(chunk if isinstance(chunk, bytes) else str(chunk).encode())
    return b"".join(parts)


async def _download(
    ctx: AuthContext, export_id: uuid.UUID, rng: str | None = None, if_range: str | None = None
) -> Response:
    return await download_export_route(export_id, ctx, range_header=rng, if_range=if_range)


# --- AC-14: stream, resume, audit ----------------------------------------------------------------


async def test_ac14_the_zip_streams_no_store_and_resumes_with_range(northwind: Northwind) -> None:
    row = await _ready(northwind)
    assert row.bytes is not None and row.bundle_sha256 is not None
    ctx = northwind.hannah.context()
    whole = await _download(ctx, row.id)
    assert whole.status_code == 200
    assert whole.headers["cache-control"] == "no-store"
    assert whole.headers["content-type"] == "application/zip"
    assert whole.headers["accept-ranges"] == "bytes"
    assert whole.headers["content-disposition"] == (
        f'attachment; filename="accrued-binder-{row.id}.zip"'
    )
    assert "x-amz" not in "".join(whole.headers.keys()).lower()  # no presigned link anywhere
    bundle = await _body(whole)
    assert len(bundle) == row.bytes
    assert hashlib.sha256(bundle).hexdigest() == row.bundle_sha256
    # An interrupted download resumes where it stopped (segments of 1 KiB: across boundaries).
    first = await _download(ctx, row.id, "bytes=0-1499")
    assert first.status_code == 206
    assert first.headers["content-range"] == f"bytes 0-1499/{row.bytes}"
    rest = await _download(ctx, row.id, "bytes=1500-", whole.headers["etag"])
    assert rest.headers["content-range"] == f"bytes 1500-{row.bytes - 1}/{row.bytes}"
    assert await _body(first) + await _body(rest) == bundle
    suffix = await _download(ctx, row.id, "bytes=-10")
    assert await _body(suffix) == bundle[-10:]
    # An If-Range for another bundle is the whole bundle again.
    stale = await _download(ctx, row.id, "bytes=5-9", '"' + "0" * 64 + '"')
    assert stale.status_code == 200 and len(await _body(stale)) == row.bytes
    downloads = await northwind.seed.count("engagement_export_downloads", northwind.tenant)
    assert downloads == 5
    actions = await northwind.seed.actions(northwind.tenant)
    assert actions.count("engagement_export.downloaded") == 5


async def test_dec536_ranges_the_api_does_not_serve_answer_416(northwind: Northwind) -> None:
    row = await _ready(northwind)
    assert row.bytes is not None
    ctx = northwind.hannah.context()
    for bad in (
        "bytes=0-1,5-9",
        "bytes=abc",
        f"bytes={row.bytes}-",
        "bytes=-0",
        "bytes=99999999999999999999-",
        "items=0-1",
    ):
        answer = await _download(ctx, row.id, bad)
        assert answer.status_code == 416, bad
        assert answer.headers["content-range"] == f"bytes */{row.bytes}"
    assert await northwind.seed.count("engagement_export_downloads", northwind.tenant) == 0


async def test_ac14_who_may_download(northwind: Northwind) -> None:
    row = await _ready(northwind)
    hannah = northwind.hannah.context()
    stale = AuthContext(
        tenant=hannah.tenant,
        user_id=hannah.user_id,
        membership_id=hannah.membership_id,
        firm_role=None,
        mfa_at=hannah.mfa_at - timedelta(hours=2) if hannah.mfa_at else None,
    )
    with pytest.raises(exports.ExportNeedsMfa):  # the step-up's own 403 (DEC-547)
        await _download(stale, row.id)
    agent = AuthContext(
        tenant=TenantContext(northwind.tenant, "agent", "engagement_agent"),
        user_id=hannah.user_id,
        membership_id=hannah.membership_id,
        firm_role=None,
        mfa_at=hannah.mfa_at,
    )
    with pytest.raises(Forbidden):
        await _download(agent, row.id)
    stranger = await northwind.seed.person(northwind.tenant)
    with pytest.raises((Forbidden, NotFound)):
        await _download(stranger.context(), row.id)
    assert await northwind.seed.count("engagement_export_downloads", northwind.tenant) == 0


async def test_ac14_a_queued_export_is_409_export_not_ready(northwind: Northwind) -> None:
    row = await _requested(northwind)
    with pytest.raises(export_download.ExportNotReady):
        await _download(northwind.hannah.context(), row.id)


# --- AC-15: 7 days -------------------------------------------------------------------------------


async def test_ac15_after_7_days_410_then_the_sweep_expires_it_and_deletes_its_segments(
    northwind: Northwind,
) -> None:
    row = await _ready(northwind)
    assert row.expires_at is not None and row.segment_count is not None
    late = row.expires_at + timedelta(seconds=1)
    with clock.frozen(late):
        gone = await _download(northwind.hannah.context(), row.id)
        assert gone.status_code == 410  # before the sweep ran
        assert await export_lifecycle.expire_due(northwind.tenant) == 1
        assert await export_lifecycle.expire_due(northwind.tenant) == 0  # idempotent
    expired = await _row(northwind, row.id)
    assert (expired.status, expired.void_reason) == ("expired", "expired")
    gone = await _download(northwind.hannah.context(), row.id)
    assert gone.status_code == 410
    await export_lifecycle.on_closed(_event(northwind.tenant, "engagement_export.expired", row))
    with pytest.raises(ClientError):
        await export_storage.get_segment(northwind.tenant, row.id, 0)
    assert "engagement_export.expired" in await northwind.seed.actions(northwind.tenant)


async def test_ac15_the_sweep_leaves_an_export_inside_its_days(northwind: Northwind) -> None:
    row = await _ready(northwind)
    assert row.expires_at is not None
    with clock.frozen(row.expires_at - timedelta(minutes=1)):
        assert await export_lifecycle.expire_due(northwind.tenant) == 0
    assert (await _row(northwind, row.id)).status == "ready"
    await export_lifecycle.on_closed(_event(northwind.tenant, "engagement_export.expired", row))
    assert await export_storage.get_segment(northwind.tenant, row.id, 0)  # not deleted


def _event(tenant: uuid.UUID, kind: str, row: EngagementExport) -> OutboxEvent:
    return OutboxEvent(
        event_id=uuid.uuid4(),
        tenant_id=tenant,
        event_type=kind,
        payload={"export_id": str(row.id), "engagement_id": str(row.engagement_id)},
    )


# --- AC-15: a withdrawn file voids the ready bundle ----------------------------------------------


async def test_ac15_a_withdrawn_file_voids_the_ready_bundle(
    northwind: Northwind, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = await _ready(northwind)
    version = next(iter(northwind.versions))
    other = await _ready(northwind)  # a second ready bundle holding the same version

    async def withdrawn(_tenant: object, ids: list[uuid.UUID]) -> frozenset[uuid.UUID]:
        return frozenset(ids) & {version}

    # The download refuses it before the withdrawal's subscriber ran.
    monkeypatch.setattr(export_download, "withdrawn_among", withdrawn)
    assert (await _download(northwind.hannah.context(), row.id)).status_code == 410
    assert await export_lifecycle.void_holding(northwind.tenant, version) == 2
    assert await export_lifecycle.void_holding(northwind.tenant, version) == 0  # redelivered
    for export_id in (row.id, other.id):
        voided = await _row(northwind, export_id)
        assert (voided.status, voided.void_reason) == ("expired", "withdrawn_content")
    assert (await northwind.seed.actions(northwind.tenant)).count("engagement_export.voided") == 2
    await export_lifecycle.on_closed(_event(northwind.tenant, "engagement_export.voided", row))
    with pytest.raises(ClientError):
        await export_storage.get_segment(northwind.tenant, row.id, 0)


async def test_ac15_a_file_withdrawn_while_packaging_voids_the_bundle_at_ready(
    northwind: Northwind, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = await _requested(northwind)
    version = next(iter(northwind.versions))
    with clock.frozen(row.not_before + timedelta(seconds=1)):
        await export_activities.start_export(northwind.tenant, row.id)
        await export_activities.snapshot_export(northwind.tenant, row.id)
        facts = await export_activities.package_export(northwind.tenant, row.id)
        # The subscriber ran while it was packaging: nothing ready to void yet.
        assert await export_lifecycle.void_holding(northwind.tenant, version) == 0

        async def withdrawn(_tenant: object, ids: list[uuid.UUID]) -> frozenset[uuid.UUID]:
            return frozenset(ids) & {version}

        monkeypatch.setattr(export_lifecycle, "withdrawn_among", withdrawn)
        assert await export_activities.ready_export(facts) == "expired"
    settled = await _row(northwind, row.id)
    assert (settled.status, settled.void_reason) == ("expired", "withdrawn_content")
    actions = await northwind.seed.actions(northwind.tenant)
    assert "engagement_export.voided" in actions
    assert EXPORTS  # the bundle bucket of A-01-T19's fixture


# --- security review fix round (M1, M2, L4, L5; DEC-545, DEC-546) --------------------------------


async def test_m1_a_withdrawal_mid_stream_stops_the_download(
    northwind: Northwind, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = await _ready(northwind)
    assert row.segment_count is not None and row.segment_count > 2
    plan = await export_download.prepare(northwind.hannah.context(), row.id, None, None)
    stream = plan.stream()
    first = await anext(stream)  # the first segment needs no re-check
    assert first
    version = next(iter(northwind.versions))

    async def withdrawn(_tenant: object, ids: list[uuid.UUID]) -> frozenset[uuid.UUID]:
        return frozenset(ids) & {version}

    monkeypatch.setattr(export_download, "withdrawn_among", withdrawn)
    with pytest.raises(export_download.DownloadRevoked):
        async for _ in stream:
            pass


async def test_m1_losing_the_engagement_mid_stream_stops_the_download(
    northwind: Northwind,
) -> None:
    row = await _ready(northwind)
    plan = await export_download.prepare(northwind.hannah.context(), row.id, None, None)
    stream = plan.stream()
    await anext(stream)
    await northwind.seed.run(
        "DELETE FROM engagement_members WHERE engagement_id = $1 AND user_id = $2",
        row.engagement_id,
        northwind.hannah.user_id,
    )
    with pytest.raises(export_download.DownloadRevoked):
        async for _ in stream:
            pass


async def test_m2_bytes_leave_in_bounded_chunks_and_requests_are_capped(
    northwind: Northwind, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = await _ready(northwind)
    monkeypatch.setattr(export_download, "CHUNK_BYTES", 100)
    plan = await export_download.prepare(northwind.hannah.context(), row.id, None, None)
    parts = [p async for p in plan.stream()]
    assert max(len(p) for p in parts) <= 100
    assert sum(len(p) for p in parts) == row.bytes
    monkeypatch.setattr(export_download, "DOWNLOAD_LIMIT", 2)
    await export_download.prepare(northwind.hannah.context(), row.id, "bytes=0-9", None)
    with pytest.raises(export_download.DownloadRateLimited):
        await export_download.prepare(northwind.hannah.context(), row.id, "bytes=0-9", None)


async def test_l5_the_system_clock_expires_a_bundle_whatever_the_business_clock(
    northwind: Northwind,
) -> None:
    row = await _ready(northwind)
    assert row.expires_at is not None
    # A business clock held a week back does not keep the bundle once real time passed it.
    with clock.frozen(row.expires_at - timedelta(days=7, seconds=1)):
        assert not export_download._expired(  # pyright: ignore[reportPrivateUsage] -- the rule
            row.expires_at, await clock.now(TenantContext(northwind.tenant, "system", "t"))
        )
    assert export_download._expired(  # pyright: ignore[reportPrivateUsage] -- the rule
        row.expires_at - timedelta(days=30), row.expires_at - timedelta(days=31)
    )


async def test_l4_a_voided_rule_link_voids_the_ready_bundle(
    northwind: Northwind, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = await _ready(northwind)
    version = next(iter(northwind.versions))

    async def retired(_tenant: object, ids: list[uuid.UUID]) -> frozenset[uuid.UUID]:
        return frozenset(ids) & {version}

    monkeypatch.setattr(export_lifecycle, "withdrawn_among", retired)
    await export_lifecycle.on_fulfilment_voided(
        OutboxEvent(
            event_id=uuid.uuid4(),
            tenant_id=northwind.tenant,
            event_type="fulfilment.voided",
            payload={"evidence_version_id": str(version), "engagement_id": str(row.engagement_id)},
        )
    )
    voided = await _row(northwind, row.id)
    assert (voided.status, voided.void_reason) == ("expired", "withdrawn_content")
