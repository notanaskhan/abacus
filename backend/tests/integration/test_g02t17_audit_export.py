"""G-02-T17 (SPEC-349 AC-12 to AC-14; G-02 §4.5; DEC-620 to DEC-622): the audit-log export.

Over HTTP as the screen calls it, with the workflow's steps run in-process (`exports.build`,
`mark_ready`; the workflow itself is covered by its replay histories): Felix's Sep-style range
exports as a ZIP of the CSV, `manifest.json` and `manifest.sig`; the CSV's SHA-256 is the
manifest's; the signature verifies with the environment's public key; the CSV holds only what
Felix sees; the request and the download each write an audit event naming Felix; the agent and
the system are refused and a client principal finds nothing.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import uuid
import zipfile
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Final, cast

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from abacus.api import create_app
from abacus.kernel import export_bundles
from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.crypto.signing import (
    LocalExportSigner,
    configure_export_signer,
    verify_signature,
)
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine, tenant_connection
from abacus.kernel.flags import forget_flags
from abacus.kernel.storage import s3_client
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.audit_trail import exports
from abacus.modules.audit_trail.workflows import AuditExportFailure, AuditExportInput
from abacus.modules.identity.api import AuthContext, current_context

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

if TYPE_CHECKING:
    from types_boto3_s3 import S3Client

EXPORTS: Final = "audit-export-bundles"
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


@pytest.fixture
def signer() -> LocalExportSigner:
    return LocalExportSigner(MASTER)


@pytest.fixture(autouse=True)
async def wired(
    migrated_db: MigratedDatabase,
    raw: S3Client,
    signer: LocalExportSigner,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    forget_flags()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    reset_key_service()
    configure_key_service(LocalKeyService(MASTER))
    export_bundles.configure_export_bundles(raw, EXPORTS)
    configure_export_signer(signer)
    yield
    configure_export_signer(None)
    export_bundles.reset_export_bundles()
    reset_key_service()
    await dispose_engine()
    settings.cache_clear()
    forget_flags()


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


async def _member(
    seed: Seeder, tenant: uuid.UUID, name: str, *, firm_role: str | None, kind: str = "staff"
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
            "INSERT INTO memberships (tenant_id, user_id, firm_role, status, kind) "
            "VALUES ($1, $2, $3, 'active', $4) RETURNING id",
            tenant,
            user,
            firm_role,
            kind,
        ),
    )
    return AuthContext(
        tenant=TenantContext(tenant, "human", str(user)),
        user_id=user,
        membership_id=membership,
        firm_role=firm_role,  # pyright: ignore[reportArgumentType] -- a seeded firm role code
        mfa_at=datetime.now(UTC) - timedelta(minutes=1),
        client=kind == "client",
    )


def bind(principal: AuthContext) -> Call:
    async def call(method: str, path: str, **kwargs: object) -> httpx.Response:
        app = create_app()
        app.dependency_overrides[current_context] = lambda: principal
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, **kwargs)  # pyright: ignore[reportArgumentType] -- httpx's keyword arguments

    return call


async def _firm(seed: Seeder) -> tuple[uuid.UUID, AuthContext, AuthContext]:
    tenant = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'audit_log.explorer', 'true', 'test', 'G-02-T17')",
        tenant,
    )
    felix = await _member(seed, tenant, "Felix Andersen", firm_role="security_admin")
    client = await _member(seed, tenant, "Claire Feld", firm_role=None, kind="client")
    # Firm-level events Felix reads (a firm-level reader, DEC-434).
    for _ in range(3):
        async with uow(felix.tenant) as tx:
            tx.record(
                "security_policy.updated",
                target=Target("security_policy", tenant),
                after=Ref(version=1),
            )
    return tenant, felix, client


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


async def _audited(seed: Seeder, tenant: uuid.UUID, action: str) -> list[tuple[str, str]]:
    rows = await seed.rows(
        "SELECT actor_kind, actor_id FROM audit_events WHERE tenant_id = $1 AND action = $2 "
        "ORDER BY seq",
        tenant,
        action,
    )
    return [(cast(str, r["actor_kind"]), cast(str, r["actor_id"])) for r in rows]


async def _ready(felix: AuthContext, export_id: str) -> None:
    facts = await exports.build(AuditExportInput(str(felix.tenant_id), export_id))
    assert await exports.mark_ready(facts) == "ready"


async def test_ac12_ac13_ac47_felix_exports_verifies_and_downloads(
    seed: Seeder, signer: LocalExportSigner
) -> None:
    tenant, felix, _client = await _firm(seed)
    as_felix = bind(felix)
    body = {"from_date": _today(), "to_date": _today()}
    requested = await as_felix(
        "POST", "/v1/audit-events/exports", json=body, headers={"Idempotency-Key": "k1"}
    )
    assert requested.status_code == 202, requested.text
    export = requested.json()
    assert export["status"] == "requested"
    again = await as_felix(
        "POST", "/v1/audit-events/exports", json=body, headers={"Idempotency-Key": "k1"}
    )
    assert again.json()["id"] == export["id"]  # one job per key
    early = await as_felix("POST", f"/v1/audit-events/exports/{export['id']}/link")
    assert early.status_code == 409 and early.json()["detail"] == "export_not_ready"

    await _ready(felix, export["id"])
    status = (await as_felix("GET", f"/v1/audit-events/exports/{export['id']}")).json()
    assert status["status"] == "ready"
    assert status["file_name"] == f"audit-log-{_today()}-{_today()}.zip"
    assert status["row_count"] >= 3
    expires = datetime.fromisoformat(status["expires_at"])
    assert timedelta(days=6) < expires - datetime.now(UTC) <= timedelta(days=7)

    link = await as_felix("POST", f"/v1/audit-events/exports/{export['id']}/link")
    assert link.status_code == 200
    assert link.json()["url"] == f"/v1/audit-events/exports/{export['id']}/download"
    downloaded = await as_felix("GET", link.json()["url"])
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"] == "application/zip"
    assert downloaded.headers["cache-control"] == "no-store"
    archive = zipfile.ZipFile(io.BytesIO(downloaded.content))
    stem = f"audit-log-{_today()}-{_today()}"
    assert sorted(archive.namelist()) == sorted([f"{stem}.csv", "manifest.json", "manifest.sig"])
    content = archive.read(f"{stem}.csv")
    manifest_bytes = archive.read("manifest.json")
    manifest = json.loads(manifest_bytes)
    # AC-13: shasum of the CSV is the manifest's; the signature verifies with the public key.
    assert manifest["format"] == "accrued.audit-log-export"
    assert manifest["files"][0]["sha256"] == hashlib.sha256(content).hexdigest()
    assert verify_signature(signer.public_key_pem(), manifest_bytes, archive.read("manifest.sig"))
    assert not verify_signature(
        signer.public_key_pem(), manifest_bytes + b" ", archive.read("manifest.sig")
    )
    assert hashlib.sha256(manifest_bytes).hexdigest() == status["manifest_sha256"]
    # Security review: the manifest names the key that signed it, not only its alias.
    assert manifest["signature"]["key_id"] == signer.key_ref
    assert (manifest["seq_from"], manifest["seq_to"]) == (status["seq_from"], status["seq_to"])
    assert manifest["requested_by"] == {
        "user_id": str(felix.user_id),
        "display_name": "Felix Andersen",
    }
    rows = list(csv.DictReader(io.StringIO(content.decode("utf-8"))))
    assert len(rows) == manifest["row_count"] == status["row_count"]
    assert {r["action"] for r in rows} >= {"security_policy.updated"}
    # AC-12, AC-47: requested and downloaded name Felix; ready is the system's.
    assert await _audited(seed, tenant, "audit_export.requested") == [
        ("human", str(felix.user_id))
    ]
    assert await _audited(seed, tenant, "audit_export.downloaded") == [
        ("human", str(felix.user_id))
    ]
    assert [k for k, _ in await _audited(seed, tenant, "audit_export.ready")] == ["system"]
    shown = (await as_felix("GET", f"/v1/audit-events/exports/{export['id']}")).json()
    assert shown["status"] == "downloaded"


async def test_ac14_the_csv_holds_only_what_the_requester_sees(seed: Seeder) -> None:
    _tenant, felix, _client = await _firm(seed)
    other = await seed.firm()  # another firm's events never appear
    stranger = await _member(seed, other, "Other Person", firm_role="security_admin")
    async with uow(stranger.tenant) as tx:
        tx.record("security_policy.updated", target=Target("security_policy", other))
    as_felix = bind(felix)
    requested = await as_felix(
        "POST",
        "/v1/audit-events/exports",
        json={"from_date": _today(), "to_date": _today(), "include_values": True},
        headers={"Idempotency-Key": "k2"},
    )
    export_id = requested.json()["id"]
    await _ready(felix, export_id)
    downloaded = await as_felix("GET", f"/v1/audit-events/exports/{export_id}/download")
    archive = zipfile.ZipFile(io.BytesIO(downloaded.content))
    name = next(n for n in archive.namelist() if n.endswith(".csv"))
    rows = list(csv.DictReader(io.StringIO(archive.read(name).decode("utf-8"))))
    assert rows and "values_status" in rows[0]
    assert all(str(other) not in r["target_id"] for r in rows)
    assert all(r["values_status"] in ("resolved", "withheld", "unavailable") for r in rows)


async def test_ac14_another_person_cannot_read_or_download_felixs_export(seed: Seeder) -> None:
    tenant, felix, _client = await _firm(seed)
    nora = await _member(seed, tenant, "Nora Lindqvist", firm_role="security_admin")
    requested = await bind(felix)(
        "POST",
        "/v1/audit-events/exports",
        json={"from_date": _today(), "to_date": _today()},
        headers={"Idempotency-Key": "k3"},
    )
    export_id = requested.json()["id"]
    await _ready(felix, export_id)
    as_nora = bind(nora)
    assert (await as_nora("GET", f"/v1/audit-events/exports/{export_id}")).status_code == 404
    assert (
        await as_nora("GET", f"/v1/audit-events/exports/{export_id}/download")
    ).status_code == 404


@pytest.mark.parametrize("kind", ["agent", "system"])
async def test_ac14_the_agent_and_the_system_are_refused(seed: Seeder, kind: str) -> None:
    tenant, felix, _client = await _firm(seed)
    actor = "agent:probe:run" if kind == "agent" else "system:probe"
    principal = AuthContext(
        TenantContext(tenant, kind, actor, felix.user_id if kind == "agent" else None),  # pyright: ignore[reportArgumentType] -- an actor kind code
        felix.user_id,
        uuid.uuid4(),
        None,
        None,
    )
    response = await bind(principal)(
        "POST",
        "/v1/audit-events/exports",
        json={"from_date": _today(), "to_date": _today()},
        headers={"Idempotency-Key": "k4"},
    )
    assert response.status_code == 403


async def test_ac14_a_client_principal_finds_nothing(seed: Seeder) -> None:
    _tenant, _felix, client = await _firm(seed)
    response = await bind(client)(
        "POST",
        "/v1/audit-events/exports",
        json={"from_date": _today(), "to_date": _today()},
        headers={"Idempotency-Key": "k5"},
    )
    assert response.status_code == 404


async def test_ac12_a_stale_second_factor_is_refused(seed: Seeder) -> None:
    _tenant, felix, _client = await _firm(seed)
    stale = AuthContext(
        felix.tenant,
        felix.user_id,
        felix.membership_id,
        felix.firm_role,
        datetime.now(UTC) - timedelta(hours=2),
    )
    response = await bind(stale)(
        "POST",
        "/v1/audit-events/exports",
        json={"from_date": _today(), "to_date": _today()},
        headers={"Idempotency-Key": "k6"},
    )
    assert response.status_code == 403


async def test_a_range_over_92_days_is_refused(seed: Seeder) -> None:
    _tenant, felix, _client = await _firm(seed)
    response = await bind(felix)(
        "POST",
        "/v1/audit-events/exports",
        json={"from_date": "2026-01-01", "to_date": "2026-06-30"},
        headers={"Idempotency-Key": "k7"},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "export_range_invalid"


async def test_a_failed_build_is_never_downloadable(seed: Seeder) -> None:
    tenant, felix, _client = await _firm(seed)
    requested = await bind(felix)(
        "POST",
        "/v1/audit-events/exports",
        json={"from_date": _today(), "to_date": _today()},
        headers={"Idempotency-Key": "k8"},
    )
    export_id = requested.json()["id"]
    failed = AuditExportFailure(str(tenant), export_id, "requester_not_member")
    assert await exports.mark_failed(failed) == "failed"
    assert await exports.mark_failed(failed) == "unchanged"
    link = await bind(felix)("POST", f"/v1/audit-events/exports/{export_id}/link")
    assert link.status_code == 409


async def test_an_expired_export_answers_410(seed: Seeder) -> None:
    _tenant, felix, _client = await _firm(seed)
    requested = await bind(felix)(
        "POST",
        "/v1/audit-events/exports",
        json={"from_date": _today(), "to_date": _today()},
        headers={"Idempotency-Key": "k9"},
    )
    export_id = requested.json()["id"]
    await _ready(felix, export_id)
    await seed.run(
        "UPDATE audit_exports SET expires_at = now() - interval '1 minute' WHERE id = $1",
        uuid.UUID(export_id),
    )
    link = await bind(felix)("POST", f"/v1/audit-events/exports/{export_id}/link")
    assert link.status_code == 410 and link.json()["detail"] == "export_expired"
    status = (await bind(felix)("GET", f"/v1/audit-events/exports/{export_id}")).json()
    assert status["status"] == "expired"


async def test_a_job_never_moves_backwards(seed: Seeder) -> None:
    """0243's guard: the app cannot re-open a finished job."""
    _tenant, felix, _client = await _firm(seed)
    requested = await bind(felix)(
        "POST",
        "/v1/audit-events/exports",
        json={"from_date": _today(), "to_date": _today()},
        headers={"Idempotency-Key": "k10"},
    )
    export_id = requested.json()["id"]
    await _ready(felix, export_id)
    with pytest.raises(DBAPIError):
        async with tenant_connection(felix.tenant) as conn:
            await conn.execute(
                text("UPDATE audit_exports SET status = 'requested' WHERE id = :id"),
                {"id": uuid.UUID(export_id)},
            )
