"""Q-02-T47 (TASK-1500; DEC-640): the firm export carries one A-01 engagement export package per
engagement, and its manifest verifies.

AC: a canary firm export contains one verified package per engagement and its manifest hashes match
the archive. Each package is the engagement as the approver may read it (INV-5); an engagement the
approver may not read, or one without an assurance work item, is named in `omitted` with its
reason, so every engagement of the firm is accounted for exactly once.
"""

from __future__ import annotations

import hashlib
import io
import json
import uuid
import zipfile
from collections.abc import AsyncIterator, Iterator
from contextlib import suppress
from dataclasses import dataclass, replace
from typing import cast

import pytest
from botocore.exceptions import ClientError
from fastapi.responses import StreamingResponse
from starlette.responses import Response
from types_boto3_s3 import S3Client

from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine, tenant_session
from abacus.kernel.flags import forget_flags
from abacus.kernel.storage import s3_client
from abacus.modules.agents import api as agents_api
from abacus.modules.evidence import (
    export_storage,
    exports,
    firm_export_activities,
    firm_export_contract,
    firm_exports,
    storage,
)
from abacus.modules.evidence.firm_export_models import FirmExport
from abacus.modules.identity.api import AuthContext

from .agent_tests.support import Person, Seeder
from .conftest import MigratedDatabase

EVIDENCE = "q02t47-evidence"
ARCHIVES = "q02t47-archives"
MASTER = bytes(range(32))
# Importing agents registers its screening section, a core section of every package.
SECTION_OWNERS = (agents_api,)
REASONS = {"not_readable", "not_an_audit", "no_binders", "unsafe_contents"}


@pytest.fixture(scope="module")
def raw(s3_settings: dict[str, str]) -> Iterator[S3Client]:
    made = s3_client(
        endpoint_url=s3_settings["endpoint_url"],
        access_key=s3_settings["access_key"],
        secret_key=s3_settings["secret_key"],
        region=s3_settings["region"],
    )
    with suppress(ClientError):
        made.create_bucket(Bucket=EVIDENCE, ObjectLockEnabledForBucket=True)
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
    storage.configure_storage(raw, EVIDENCE)
    export_storage.configure_exports(raw, ARCHIVES)

    async def on(_tenant: object, _flag: object) -> bool:
        return True

    monkeypatch.setattr(firm_exports, "flag_enabled", on)
    monkeypatch.setattr(exports, "flag_enabled", on)
    yield
    export_storage.reset_exports()
    storage.reset_storage()
    reset_key_service()
    await dispose_engine()
    settings.cache_clear()
    forget_flags()


@dataclass(frozen=True)
class Firm:
    seed: Seeder
    tenant: uuid.UUID
    admin: Person  # security admin: requests
    partner: Person  # partner level, engagement partner on the first engagement: approves
    engagements: tuple[uuid.UUID, ...]
    packaged: uuid.UUID  # the one the partner reads
    fingerprints: dict[uuid.UUID, str]  # evidence version -> fingerprint, in the packaged one


async def _engagement_with_a_file(
    seed: Seeder, tenant: uuid.UUID, partner: Person, name: str
) -> tuple[uuid.UUID, dict[uuid.UUID, str]]:
    entity = await seed.entity(tenant, name)
    engagement = await seed.engagement(tenant, entity, partner.user_id)
    await seed.member(engagement, partner, "engagement_partner")
    binder = await seed.value(
        "INSERT INTO request_lists (tenant_id, engagement_id, created_at, kind, status, "
        "published_at, published_by) VALUES ($1, $2, clock_timestamp(), 'pbc', 'published', "
        "clock_timestamp(), $3) RETURNING id",
        tenant,
        engagement,
        partner.user_id,
    )
    category = await seed.value(
        "INSERT INTO request_categories (tenant_id, request_list_id, name, position, family) "
        "VALUES ($1, $2, 'Plan documents', 0, 'audit_area') RETURNING id",
        tenant,
        binder,
    )
    item = await seed.value(
        "INSERT INTO request_items (tenant_id, engagement_id, request_list_id, description, "
        "title, audit_area, category_id, status, created_by, created_at, client_visible, "
        "due_on, requested_at) VALUES ($1, $2, $3, 'Plan document', 'Plan document', 'Area', "
        "$4, 'received', $5, clock_timestamp(), true, '2026-09-18', clock_timestamp()) "
        "RETURNING id",
        tenant,
        engagement,
        binder,
        category,
        partner.user_id,
    )
    stored = await storage.put(tenant, f"{name} plan document".encode())
    evidence_item = await seed.value(
        "INSERT INTO evidence_items (tenant_id, engagement_id, title, created_by_kind, "
        "created_by_id) VALUES ($1, $2, 'plan.pdf', 'human', 'seed') RETURNING id",
        tenant,
        engagement,
    )
    version = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO evidence_versions (tenant_id, engagement_id, evidence_item_id, "
            "version_no, fingerprint, storage_key, storage_version_id, size_bytes, media_type, "
            "source, method) VALUES ($1, $2, $3, 1, $4, $5, $6, $7, 'application/pdf', "
            "'client_upload', 'uploaded') RETURNING id",
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
        "INSERT INTO fulfilments (tenant_id, engagement_id, request_item_id, evidence_version_id, "
        "created_by_kind, created_by_id) VALUES ($1, $2, $3, $4, 'human', 'seed')",
        tenant,
        engagement,
        item,
        version,
    )
    return engagement, {version: stored.fingerprint}


@pytest.fixture
async def firm(migrated_db: MigratedDatabase) -> Firm:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await seed.firm()
    await seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", tenant)
    admin, partner, other = [await seed.person(tenant) for _ in range(3)]
    await seed.run(
        "UPDATE memberships SET firm_role = 'security_admin' "
        "WHERE tenant_id = $1 AND user_id = $2",
        tenant,
        admin.user_id,
    )
    await seed.run(
        "UPDATE memberships SET level = 'partner' WHERE tenant_id = $1 AND user_id = $2",
        tenant,
        partner.user_id,
    )
    packaged, fingerprints = await _engagement_with_a_file(seed, tenant, partner, "Northwind")
    # A second engagement the partner is not on: packaged if the partner may read it, otherwise
    # named in `omitted`; either way accounted for once.
    other_entity = await seed.entity(tenant, "Harborline Trust")
    unstaffed = await seed.engagement(tenant, other_entity, other.user_id)
    return Firm(seed, tenant, admin, partner, (packaged, unstaffed), packaged, fingerprints)


def _ctx(person: Person, firm_role: str | None = None) -> AuthContext:
    return replace(person.context(), firm_role=firm_role)


async def _body(response: Response) -> bytes:
    assert isinstance(response, StreamingResponse)
    parts: list[bytes] = []
    async for chunk in response.body_iterator:
        parts.append(chunk if isinstance(chunk, bytes) else str(chunk).encode())
    return b"".join(parts)


async def _ready_archive(firm: Firm) -> tuple[FirmExport, bytes]:
    view = await firm_exports.request(
        _ctx(firm.admin, "security_admin"),
        firm.partner.user_id,
        idempotency_key=f"key-{uuid.uuid4().hex}",
    )
    await firm_exports.respond(_ctx(firm.partner), view.id, approve=True)
    facts = await firm_export_activities.package_export(firm.tenant, view.id, segment_bytes=4096)
    assert await firm_export_activities.ready_export(facts) == "ready"
    async with tenant_session(TenantContext(firm.tenant, "system", "test")) as session:
        row = await session.get(FirmExport, view.id, populate_existing=True)
    assert row is not None
    link = await firm_exports.issue_link(_ctx(firm.admin, "security_admin"), view.id)
    response = await firm_export_contract.firm_export_archive_route(
        view.id,
        uuid.UUID(link.url.rsplit("/", 1)[1]),
        _ctx(firm.admin, "security_admin"),
        range_header=None,
        if_range=None,
    )
    return row, await _body(response)


async def test_ac_a_canary_firm_export_holds_one_verified_package_per_engagement(
    firm: Firm,
) -> None:
    row, archive = await _ready_archive(firm)
    assert hashlib.sha256(archive).hexdigest() == row.bundle_sha256
    with zipfile.ZipFile(io.BytesIO(archive)) as opened:
        manifest_bytes = opened.read("manifest.json")
        index = json.loads(opened.read("index.json"))
        manifest = json.loads(manifest_bytes)
        # The manifest's digest is the row's, and every file it names matches the archive.
        assert hashlib.sha256(manifest_bytes).hexdigest() == row.manifest_sha256
        listed = {f["path"]: f for f in manifest["files"]}
        assert set(listed) == set(opened.namelist()) - {"manifest.json"}
        for path, entry in listed.items():
            data = opened.read(path)
            assert entry["bytes"] == len(data)
            assert entry["sha256"] == hashlib.sha256(data).hexdigest()
        # Every engagement of the firm is accounted for exactly once.
        packaged = {p["engagement_id"] for p in index["packages"]}
        omitted = {o["engagement_id"]: o["reason"] for o in index["omitted"]}
        assert packaged.isdisjoint(omitted)
        assert packaged | set(omitted) == {str(e) for e in firm.engagements}
        assert set(omitted.values()) <= REASONS
        assert index["format_version"] == "0.2"
        # The engagement the approver reads is one verified A-01 package.
        [package] = [p for p in index["packages"] if p["engagement_id"] == str(firm.packaged)]
        inner = opened.read(package["path"])
    assert package["path"] == f"packages/{firm.packaged}.zip"
    assert hashlib.sha256(inner).hexdigest() == package["bundle_sha256"]
    assert package["bytes"] == len(inner)
    with zipfile.ZipFile(io.BytesIO(inner)) as nested:
        inner_manifest = nested.read("manifest.json")
        assert hashlib.sha256(inner_manifest).hexdigest() == package["manifest_sha256"]
        files = json.loads(inner_manifest)["files"]
        evidence = [f for f in files if f.get("role") == "evidence"]
        assert {f["sha256"] for f in evidence} == set(firm.fingerprints.values())
        for entry in evidence:
            assert hashlib.sha256(nested.read(entry["path"])).hexdigest() == entry["sha256"]


async def test_a_firm_with_no_engagements_still_verifies(firm: Firm) -> None:
    empty = await firm.seed.firm()  # a fresh firm without engagements
    admin, partner = [await firm.seed.person(empty) for _ in range(2)]
    await firm.seed.run(
        "UPDATE memberships SET firm_role = 'security_admin' "
        "WHERE tenant_id = $1 AND user_id = $2",
        empty,
        admin.user_id,
    )
    await firm.seed.run(
        "UPDATE memberships SET level = 'partner' WHERE tenant_id = $1 AND user_id = $2",
        empty,
        partner.user_id,
    )
    bare = Firm(firm.seed, empty, admin, partner, (), firm.packaged, {})
    row, archive = await _ready_archive(bare)
    with zipfile.ZipFile(io.BytesIO(archive)) as opened:
        index = json.loads(opened.read("index.json"))
        manifest_bytes = opened.read("manifest.json")
    assert index["packages"] == [] and index["omitted"] == []
    assert hashlib.sha256(manifest_bytes).hexdigest() == row.manifest_sha256
