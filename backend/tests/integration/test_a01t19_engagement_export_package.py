"""A-01-T19 against Postgres and S3 (TASK-1335; SPEC-344 AC-9 to AC-13; DEC-436): "Northwind's
export lists 24 requests and 12 files whose SHA-256 match their fingerprints, and two builds are
byte-identical."

A Northwind-like binder (Brightwater Hale, synthetic): four categories of six requests, 12
accepted files (3 + 5 + 3 + 1) stored sealed under Object Lock, 12 requests still requested. Two
of the files carry hostile names. The export is created by the service, then the workflow's
steps run in order on a frozen business clock past the Undo window (the workflow itself is
covered by its replay history)."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import uuid
import zipfile
from collections.abc import AsyncIterator, Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from types_boto3_s3 import S3Client

from abacus.kernel import clock
from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine, tenant_session
from abacus.kernel.flags import forget_flags
from abacus.kernel.storage import s3_client
from abacus.modules.agents import api as agents_api
from abacus.modules.evidence import (
    export_activities,
    export_package,
    export_sections,
    export_storage,
    exports,
    storage,
)
from abacus.modules.evidence.export_manifest import (
    INDEX_COLUMNS,
    EngagementExportManifest,
    archive_path_problem,
)
from abacus.modules.evidence.export_models import EngagementExport
from abacus.modules.evidence.workflow_types import INTEGRITY_MISMATCH, SECTION_MISSING
from abacus.modules.identity.api import AuthContext

from .agent_tests.support import Person, Seeder
from .conftest import MigratedDatabase

assert agents_api.ROUTERS  # registers the `screening` section
EVIDENCE = "export-evidence"
EXPORTS = "export-bundles"
MASTER = bytes(range(32))
FILES_PER_CATEGORY = (3, 5, 3, 1)
CATEGORIES = ("Plan documents", "Investments", "Contributions", "Benefit payments")
HOSTILE = ('=HYPERLINK("http://x","y").pdf', "../../etc/passwd")


@pytest.fixture(scope="module")
def raw(s3_settings: dict[str, str]) -> Iterator[S3Client]:
    client = s3_client(
        endpoint_url=s3_settings["endpoint_url"],
        access_key=s3_settings["access_key"],
        secret_key=s3_settings["secret_key"],
        region=s3_settings["region"],
    )
    client.create_bucket(Bucket=EVIDENCE, ObjectLockEnabledForBucket=True)
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
    storage.configure_storage(raw, EVIDENCE)
    export_storage.configure_exports(raw, EXPORTS)

    async def on(_tenant: object, _flag: object) -> bool:
        return True

    monkeypatch.setattr(exports, "flag_enabled", on)
    monkeypatch.setattr(export_sections, "_audit_trail", _audit_trail)
    yield
    export_storage.reset_exports()
    storage.reset_storage()
    reset_key_service()
    await dispose_engine()
    settings.cache_clear()
    forget_flags()


# --- an audit-trail reader shaped as audit_trail's rows ------------------------------------------


@dataclass(frozen=True)
class _P:
    user_id: uuid.UUID


@dataclass(frozen=True)
class _A:
    kind: str
    person: _P | None
    on_behalf_of: _P | None
    agent_id: str | None


@dataclass(frozen=True)
class _T:
    type: str
    id: str


@dataclass(frozen=True)
class _Row:
    seq: int
    effective_at: datetime
    action: str
    actor: _A
    target: _T


async def _audit_trail(
    ctx: AuthContext, work_item_id: uuid.UUID, *, as_of_seq: int | None = None
) -> Sequence[_Row]:
    at = datetime(2026, 9, 14, 14, 0, tzinfo=UTC)
    rows = [
        _Row(
            n,
            at,
            "request_item.received",
            _A("person", _P(ctx.user_id), None, None),
            _T("request_item", str(work_item_id)),
        )
        for n in (1, 2, 3)
    ]
    return [r for r in rows if as_of_seq is None or r.seq <= as_of_seq]


# --- the Northwind-like binder -------------------------------------------------------------------


@dataclass(frozen=True)
class Northwind:
    seed: Seeder
    tenant: uuid.UUID
    hannah: Person
    work_item: uuid.UUID
    versions: dict[uuid.UUID, str]  # evidence version -> fingerprint


@pytest.fixture
async def northwind(migrated_db: MigratedDatabase) -> Northwind:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await seed.firm()
    await seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", tenant)
    hannah = await seed.person(tenant)
    entity = await seed.entity(tenant, "Northwind Labs, Inc.")
    engagement = await seed.engagement(tenant, entity, hannah.user_id)
    await seed.member(engagement, hannah, "engagement_partner")
    work_item = cast(
        uuid.UUID,
        await seed.value(
            "SELECT id FROM work_items WHERE engagement_id = $1 AND kind = 'assurance'",
            engagement,
        ),
    )
    binder = await seed.value(
        "INSERT INTO request_lists (tenant_id, engagement_id, created_at, kind, status, "
        "published_at, published_by) VALUES ($1, $2, clock_timestamp(), 'pbc', 'published', "
        "clock_timestamp(), $3) RETURNING id",
        tenant,
        engagement,
        hannah.user_id,
    )
    versions: dict[uuid.UUID, str] = {}
    n = 0
    for position, (name, files) in enumerate(zip(CATEGORIES, FILES_PER_CATEGORY, strict=True)):
        category = await seed.value(
            "INSERT INTO request_categories (tenant_id, request_list_id, name, position, "
            "family) VALUES ($1, $2, $3, $4, 'audit_area') RETURNING id",
            tenant,
            binder,
            name,
            position,
        )
        for r in range(6):
            status = "received" if r < files else "requested"
            item = cast(
                uuid.UUID,
                await seed.value(
                    "INSERT INTO request_items (tenant_id, engagement_id, request_list_id, "
                    "description, title, audit_area, category_id, status, created_by, "
                    "created_at, client_visible, due_on, requested_at) VALUES ($1, $2, $3, $4, "
                    "$4, 'Area', $5, $6, $7, clock_timestamp(), true, '2026-09-18', "
                    "clock_timestamp() + make_interval(secs => $8)) RETURNING id",
                    tenant,
                    engagement,
                    binder,
                    f"{name} request {r + 1}",
                    category,
                    status,
                    hannah.user_id,
                    float(n),
                ),
            )
            n += 1
            if status != "received":
                continue
            title = HOSTILE[len(versions)] if len(versions) < len(HOSTILE) else f"file {n}.pdf"
            content = f"Northwind evidence {n}".encode()
            stored = await storage.put(tenant, content)
            evidence_item = await seed.value(
                "INSERT INTO evidence_items (tenant_id, engagement_id, title, created_by_kind, "
                "created_by_id) VALUES ($1, $2, $3, 'human', 'seed') RETURNING id",
                tenant,
                engagement,
                title,
            )
            version = cast(
                uuid.UUID,
                await seed.value(
                    "INSERT INTO evidence_versions (tenant_id, engagement_id, evidence_item_id, "
                    "version_no, fingerprint, storage_key, storage_version_id, size_bytes, "
                    "media_type, source, method) VALUES ($1, $2, $3, 1, $4, $5, $6, $7, "
                    "'application/pdf', 'client_upload', 'uploaded') RETURNING id",
                    tenant,
                    engagement,
                    evidence_item,
                    stored.fingerprint,
                    stored.key,
                    stored.version_id,
                    stored.size,
                ),
            )
            await seed.run(
                "INSERT INTO fulfilments (tenant_id, engagement_id, request_item_id, "
                "evidence_version_id, created_by_kind, created_by_id) "
                "VALUES ($1, $2, $3, $4, 'human', 'seed')",
                tenant,
                engagement,
                item,
                version,
            )
            await seed.as_actor(
                tenant,
                ("human", str(hannah.user_id)),
                "INSERT INTO review_decisions (tenant_id, engagement_id, evidence_version_id, "
                "request_item_id, decision, corrects_proposal, actor_kind, actor_id, "
                "decision_seq) VALUES ($1, $2, $3, $4, 'accept', false, 'human', $5, 1)",
                tenant,
                engagement,
                version,
                item,
                str(hannah.user_id),
            )
            versions[version] = stored.fingerprint
    return Northwind(seed, tenant, hannah, work_item, versions)


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
    async with tenant_session(TenantContext(world.tenant, "system", "test")) as session:
        row = await session.get(EngagementExport, view.id)
    assert row is not None
    return row


async def _bundle(world: Northwind, export_id: uuid.UUID, segments: int) -> bytes:
    parts = [await export_storage.get_segment(world.tenant, export_id, n) for n in range(segments)]
    return b"".join(parts)


# --- AC-9 and AC-10 ------------------------------------------------------------------------------


async def test_ac9_ac10_northwind_lists_24_requests_and_12_verified_files_byte_identically(
    northwind: Northwind,
) -> None:
    row = await _requested(northwind)
    with clock.frozen(row.not_before + timedelta(seconds=1)):
        assert await export_activities.start_export(northwind.tenant, row.id) == "packaging"
        as_of_seq = await export_activities.snapshot_export(northwind.tenant, row.id)
        first = await export_activities.package_export(
            northwind.tenant, row.id, segment_bytes=1024
        )
        second = await export_activities.package_export(
            northwind.tenant, row.id, segment_bytes=1024
        )
        assert await export_activities.ready_export(first) == "ready"
    assert as_of_seq > 0
    # AC-10: two builds of the same export are byte-identical.
    assert (first.bundle_sha256, first.manifest_sha256) == (
        second.bundle_sha256,
        second.manifest_sha256,
    )
    assert first.segment_count > 1  # cut into sealed segments
    bundle = await _bundle(northwind, row.id, first.segment_count)
    assert hashlib.sha256(bundle).hexdigest() == first.bundle_sha256
    with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
        contents = {i.filename: archive.read(i) for i in archive.infolist()}
    # AC-9: 24 index rows, 12 files whose SHA-256 is their fingerprint, checksums verify.
    index = list(csv.reader(io.StringIO(contents["index.csv"].decode())))
    assert tuple(index[0]) == INDEX_COLUMNS and len(index) - 1 == 24
    assert sum(1 for r in index[1:] if r[8] == "0") == 12
    evidence = {p: c for p, c in contents.items() if p.startswith("evidence/")}
    assert len(evidence) == 12
    manifest = EngagementExportManifest.model_validate_json(contents["manifest.json"])
    assert (manifest.counts.request_count, manifest.counts.file_count) == (24, 12)
    assert manifest.counts.requests_without_file == 12
    assert manifest.as_of_seq == as_of_seq
    for f in manifest.files:
        if f.evidence is not None:
            assert hashlib.sha256(evidence[f.path]).hexdigest() == f.sha256
            assert northwind.versions[f.evidence.evidence_version_id] == f.sha256
    per_category = [
        sum(1 for p in evidence if p.startswith(f"evidence/{n:02d} ")) for n in range(1, 5)
    ]
    assert per_category == list(FILES_PER_CATEGORY)
    for line in contents["checksums.sha256"].decode().splitlines():
        digest, path = line.split("  ", 1)
        assert hashlib.sha256(contents[path]).hexdigest() == digest
    for name in (
        "provenance/fulfilments.csv",
        "provenance/review_decisions.csv",
        "provenance/screening.csv",
        "provenance/citations.csv",
        "audit_trail/events.jsonl",
        "README.txt",
        "index.xlsx",
    ):
        assert name in contents
    decisions = list(csv.reader(io.StringIO(contents["provenance/review_decisions.csv"].decode())))
    assert len(decisions) - 1 == 12
    events = [json.loads(line) for line in contents["audit_trail/events.jsonl"].splitlines()]
    assert [e["seq"] for e in events] == [1, 2, 3]
    assert set(events[0]) == {"seq", "effective_at", "action", "actor", "target"}
    ready = await exports.read(northwind.hannah.context(), row.id)
    assert (ready.status, ready.file_count, ready.request_count) == ("ready", 12, 24)
    assert ready.expires_at is not None and ready.ready_at is not None
    assert ready.expires_at - ready.ready_at == timedelta(days=7)
    assert ready.allowed_actions == ["download"]
    actions = await northwind.seed.actions(northwind.tenant)
    assert {"engagement_export.started", "engagement_export.packaged"} <= set(actions)
    contents_rows = await northwind.seed.count("engagement_export_contents", northwind.tenant)
    assert contents_rows == 12


# --- AC-11: hostile names ------------------------------------------------------------------------


async def test_ac11_hostile_names_are_safe_paths_and_literal_cells(northwind: Northwind) -> None:
    row = await _requested(northwind)
    with clock.frozen(row.not_before + timedelta(seconds=1)):
        await export_activities.start_export(northwind.tenant, row.id)
        await export_activities.snapshot_export(northwind.tenant, row.id)
        facts = await export_activities.package_export(northwind.tenant, row.id)
    bundle = await _bundle(northwind, row.id, facts.segment_count)
    with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
        names = archive.namelist()
        index = archive.read("index.csv").decode()
    assert all(archive_path_problem(n) is None for n in names)
    assert not any(".." in n.split("/") or n.startswith("/") for n in names)
    assert any("passwd" in n for n in names) and any("HYPERLINK" in n for n in names)
    paths = [r[9] for r in csv.reader(io.StringIO(index)) if "HYPERLINK" in r[9]]
    assert paths and all(not p.startswith("=") for p in paths)


# --- AC-12: integrity ----------------------------------------------------------------------------


async def test_ac12_a_swapped_object_fails_integrity_mismatch_and_publishes_nothing(
    northwind: Northwind, raw: S3Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = await _requested(northwind)
    real = storage.get

    async def swapped(tenant_id: uuid.UUID, stored: storage.StoredObject) -> bytes:
        content = await real(tenant_id, stored)
        return content + b" tampered"

    monkeypatch.setattr(storage, "get", swapped)
    with clock.frozen(row.not_before + timedelta(seconds=1)):
        await export_activities.start_export(northwind.tenant, row.id)
        await export_activities.snapshot_export(northwind.tenant, row.id)
        with pytest.raises(export_activities.ExportBuildFailed) as failed:
            await export_activities.package_export(northwind.tenant, row.id)
        assert failed.value.code == INTEGRITY_MISMATCH
        assert await export_activities.fail_export(
            northwind.tenant, row.id, failed.value.code
        ) == ("failed")
    stored = raw.list_objects_v2(Bucket=EXPORTS, Prefix=f"exports/{northwind.tenant}/{row.id}/")
    assert stored.get("KeyCount", 0) == 0
    view = await exports.read(northwind.hannah.context(), row.id)
    assert (view.status, view.failure_code, view.bundle_sha256) == (
        "failed",
        INTEGRITY_MISMATCH,
        None,
    )


# --- AC-13: a missing section --------------------------------------------------------------------


async def test_ac13_a_core_section_without_a_provider_fails_the_build(
    northwind: Northwind, monkeypatch: pytest.MonkeyPatch
) -> None:
    registered = dict(export_package._SECTIONS)  # pyright: ignore[reportPrivateUsage] -- the slot
    registered.pop("citations")
    monkeypatch.setattr(export_package, "_SECTIONS", registered)
    row = await _requested(northwind)
    with clock.frozen(row.not_before + timedelta(seconds=1)):
        await export_activities.start_export(northwind.tenant, row.id)
        await export_activities.snapshot_export(northwind.tenant, row.id)
        with pytest.raises(export_activities.ExportBuildFailed) as failed:
            await export_activities.package_export(northwind.tenant, row.id)
    assert failed.value.code == SECTION_MISSING


async def test_ac13_no_audit_trail_reader_fails_a_build_that_asks_for_the_trail(
    northwind: Northwind, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(export_sections, "_audit_trail", None)
    row = await _requested(northwind)
    with clock.frozen(row.not_before + timedelta(seconds=1)):
        await export_activities.start_export(northwind.tenant, row.id)
        await export_activities.snapshot_export(northwind.tenant, row.id)
        with pytest.raises(export_activities.ExportBuildFailed) as failed:
            await export_activities.package_export(northwind.tenant, row.id)
    assert failed.value.code == SECTION_MISSING
