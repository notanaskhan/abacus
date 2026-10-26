"""Seeding for the trust kit's word-layer and citation tests (P-03-T05, T06): a firm with an
engagement whose uploads are real stored files (wiring in `conftest.py`). Rows are seeded as the
superuser with a fresh firm per test, so tests never need cleanup."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol, cast

import asyncpg

from abacus.kernel.db import TenantContext
from abacus.kernel.uow import uow
from abacus.modules.evidence.api import (
    UPLOAD_INBOX,
    UPLOAD_VERSION,
    NewItem,
    Provenance,
    UploadInput,
    add_version,
    stage_content,
)
from abacus.modules.evidence.pii import DETECTOR_VERSION
from abacus.modules.identity.api import AuthContext

MASTER = b"trust-layer-test-master-key-0123456789abcd"
BUCKET = f"trust-layer-{uuid.uuid4().hex[:12]}"
PDF = "application/pdf"


class Migrated(Protocol):
    app_url: str
    identity_url: str
    superuser_dsn: str


class Seeder:
    """Superuser statements, one connection each."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    async def run(self, sql: str, *args: object) -> None:
        conn = await asyncpg.connect(self._dsn)
        try:
            await conn.execute(sql, *args)
        finally:
            await conn.close()

    async def value(self, sql: str, *args: object) -> object:
        conn = await asyncpg.connect(self._dsn)
        try:
            return await conn.fetchval(sql, *args)
        finally:
            await conn.close()

    async def run_untriggered(self, sql: str, *args: object) -> None:
        """A row no route makes in this shape (a withdrawal of a version that isn't a detached-key
        client upload, P-03-T12): one transaction with its triggers off."""
        conn = await asyncpg.connect(self._dsn)
        try:
            async with conn.transaction():
                await conn.execute("SET LOCAL session_replication_role = replica")
                await conn.execute(sql, *args)
        finally:
            await conn.close()

    async def rows(self, sql: str, *args: object) -> list[asyncpg.Record]:
        conn = await asyncpg.connect(self._dsn)
        try:
            return list(await conn.fetch(sql, *args))
        finally:
            await conn.close()

    async def id(self, sql: str, *args: object) -> uuid.UUID:
        return cast(uuid.UUID, await self.value(sql, *args))


@dataclass(frozen=True)
class Firm:
    tenant_id: uuid.UUID
    engagement_id: uuid.UUID
    user_id: uuid.UUID
    seed: Seeder

    @property
    def system(self) -> TenantContext:
        return TenantContext(self.tenant_id, "system", "evidence.upload_processing")

    def person(self, user_id: uuid.UUID | None = None) -> AuthContext:
        """The firm's staff member (or another of its people) as a signed-in person."""
        who = user_id or self.user_id
        return AuthContext(
            tenant=TenantContext(self.tenant_id, "human", str(who)),
            user_id=who,
            membership_id=uuid.uuid4(),
            firm_role=None,
            mfa_at=datetime.now(UTC) - timedelta(minutes=1),
        )

    async def outsider(self) -> uuid.UUID:
        """Another active member of the firm, on none of its engagements."""
        subject = f"sub-{uuid.uuid4().hex}"
        user_id = await self.seed.id(
            "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
            "VALUES ('https://identity.abacus.local', $1, $2, 'Outsider') RETURNING id",
            subject,
            f"{subject}@example.test",
        )
        await self.seed.run(
            "INSERT INTO memberships (tenant_id, user_id, firm_role, status) "
            "VALUES ($1, $2, NULL, 'active')",
            self.tenant_id,
            user_id,
        )
        return user_id

    async def version(
        self,
        content: bytes,
        media_type: str = PDF,
        *,
        engagement_id: uuid.UUID | None = None,
    ) -> uuid.UUID:
        """An uploaded evidence version holding `content`, stored for real."""
        stored = await stage_content(self.tenant_id, content)
        async with uow(self.system) as tx:
            ref = await add_version(
                tx,
                engagement_id=engagement_id or self.engagement_id,
                item=NewItem(f"Upload {uuid.uuid4().hex[:6]}"),
                stored=stored,
                media_type=media_type,
                provenance=Provenance(source="upload", method="uploaded"),
            )
        return ref.id

    async def inbox_file(self, content: bytes, media_type: str = PDF) -> uuid.UUID:
        stored = await stage_content(self.tenant_id, content)
        return cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO inbox_files (tenant_id, engagement_id, file_name, media_type, "
                "size_bytes, fingerprint, storage_key, storage_version_id, uploaded_by, "
                "uploaded_by_staff) VALUES ($1, $2, 'dropped.pdf', $3, $4, $5, $6, $7, $8, true) "
                "RETURNING id",
                self.tenant_id,
                self.engagement_id,
                media_type,
                stored.size,
                stored.fingerprint,
                stored.key,
                stored.version_id,
                self.user_id,
            ),
        )

    async def extracted(self, version_id: uuid.UUID, status: str = "extracted") -> None:
        """An extraction row (the backfill reads only uploads an extraction could read)."""
        await self.seed.run(
            "INSERT INTO upload_extractions (tenant_id, engagement_id, evidence_version_id, "
            "extractor_version, status) VALUES ($1, $2, $3, 'v3', $4)",
            self.tenant_id,
            self.engagement_id,
            version_id,
            status,
        )


def as_version(firm: Firm, version_id: uuid.UUID) -> UploadInput:
    return UploadInput(str(firm.tenant_id), UPLOAD_VERSION, str(version_id))


def as_inbox(firm: Firm, inbox_id: uuid.UUID) -> UploadInput:
    return UploadInput(str(firm.tenant_id), UPLOAD_INBOX, str(inbox_id))


async def make_firm(seed: Seeder) -> Firm:
    """A firm, one staff member, a client entity and an accepted engagement."""
    tenant_id = uuid.uuid4()
    await seed.run("INSERT INTO firms (tenant_id, name) VALUES ($1, $2)", tenant_id, "Firm")
    subject = f"sub-{uuid.uuid4().hex}"
    user_id = await seed.id(
        "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
        "VALUES ('https://identity.abacus.local', $1, $2, 'Test person') RETURNING id",
        subject,
        f"{subject}@example.test",
    )
    await seed.run(
        "INSERT INTO memberships (tenant_id, user_id, firm_role, status) "
        "VALUES ($1, $2, NULL, 'active')",
        tenant_id,
        user_id,
    )
    client_id = await seed.id(
        "INSERT INTO clients (tenant_id, name) VALUES ($1, 'Seeded client') RETURNING id",
        tenant_id,
    )
    entity_id = await seed.id(
        "INSERT INTO client_entities (tenant_id, client_id, name) "
        "VALUES ($1, $2, 'Seeded entity') RETURNING id",
        tenant_id,
        client_id,
    )
    engagement_id = await engagement(seed, tenant_id, client_id, entity_id, user_id)
    return Firm(tenant_id, engagement_id, user_id, seed)


async def engagement(
    seed: Seeder,
    tenant_id: uuid.UUID,
    client_id: uuid.UUID,
    entity_id: uuid.UUID,
    user_id: uuid.UUID,
) -> uuid.UUID:
    """An accepted engagement with the person as confirmed staff (SPEC-025 AC-5, AC-7)."""
    engagement_id = await seed.id(
        "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
        "fiscal_period_start, fiscal_period_end, created_by) "
        "VALUES ($1, $2, $3, $4, '2025-01-01', '2025-12-31', $5) RETURNING id",
        tenant_id,
        client_id,
        entity_id,
        f"Seeded {uuid.uuid4().hex[:6]}",
        user_id,
    )
    await seed.run(
        "INSERT INTO engagement_acceptance (tenant_id, engagement_id, kind, decision, "
        "decided_by, documented_at, independence_concluded_by, independence_concluded_at, "
        "independence_documented_at) VALUES ($1, $2, 'continuance', 'accepted', 'test-seed', "
        "'Seeded', 'test-seed', clock_timestamp(), 'Seeded')",
        tenant_id,
        engagement_id,
    )
    await seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES ($1, $2, $3, 'staff')",
        tenant_id,
        engagement_id,
        user_id,
    )
    await seed.run(
        "INSERT INTO independence_confirmations (tenant_id, engagement_id, user_id, status, "
        "statement_version, answered_at) VALUES ($1, $2, $3, 'confirmed', 'v1', "
        "clock_timestamp())",
        tenant_id,
        engagement_id,
        user_id,
    )
    return engagement_id


async def scanned(
    seed: Seeder,
    firm: Firm,
    pages: list[int],
    *,
    version: uuid.UUID | None = None,
    inbox: uuid.UUID | None = None,
) -> None:
    """A PII scan run that lists `pages` as scanned (P-03-T13 writes these; seeded here)."""
    await seed.run(
        "INSERT INTO pii_scan_runs (tenant_id, evidence_version_id, inbox_file_id, "
        "detector_version, pages_scanned, region_count) VALUES ($1, $2, $3, $5, $4, 0)",
        firm.tenant_id,
        version,
        inbox,
        pages,
        DETECTOR_VERSION,
    )
