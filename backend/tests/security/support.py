"""Seeding and HTTP helpers for the security suite (Q-03): firms, people, engagements, request
items and evidence, written as the superuser (`migrated_db.superuser_dsn`) with fresh firms per
test so nothing needs cleanup, and requests made with fake-identity tokens against `create_app()`.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Literal, Protocol, cast

import asyncpg
import httpx

from abacus.kernel.db import TenantContext
from abacus_tools.fakes.identity import ISSUER, FakeIdentityProvider

Json = dict[str, object]
Role = Literal["engagement_partner", "manager", "senior", "staff", "reviewer"]
FirmRole = Literal["firm_admin", "practice_leader", "quality_partner"]
TENANT_HEADER: Final = "X-Abacus-Tenant"
# Staff engagement roles bound by independence (SPEC-025 AC-7); firm and client roles aren't.
STAFF_ROLES: Final = ("engagement_partner", "manager", "senior", "staff", "reviewer")
FIRM_ROLES: Final = ("firm_admin", "practice_leader", "quality_partner")
ROLES: Final = (*FIRM_ROLES, *STAFF_ROLES)


class Migrated(Protocol):
    @property
    def app_url(self) -> str: ...
    @property
    def relay_url(self) -> str: ...
    @property
    def identity_url(self) -> str: ...
    @property
    def superuser_dsn(self) -> str: ...


@dataclass(frozen=True)
class Person:
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    subject: str


@dataclass(frozen=True)
class Site:
    """One client with one entity and one open engagement holding one request item."""

    client_id: uuid.UUID
    entity_id: uuid.UUID
    engagement_id: uuid.UUID
    item_id: uuid.UUID
    version_id: uuid.UUID
    marker: str


class Seeder:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    @property
    def dsn_key(self) -> str:
        """Which database this seeds (a cache key; never logged)."""
        return self._dsn

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

    async def rows(self, sql: str, *args: object) -> list[asyncpg.Record]:
        conn = await asyncpg.connect(self._dsn)
        try:
            return list(await conn.fetch(sql, *args))
        finally:
            await conn.close()

    async def firm(self) -> uuid.UUID:
        tenant_id = uuid.uuid4()
        await self.run(
            "INSERT INTO firms (tenant_id, name) VALUES ($1, $2)",
            tenant_id,
            f"Firm {tenant_id.hex[:8]}",
        )
        return tenant_id

    async def person(
        self, tenant_id: uuid.UUID, firm_role: str | None = None, *, also: uuid.UUID | None = None
    ) -> Person:
        """A user with an active membership of the firm (and of `also`, a second firm)."""
        subject = f"sub-{uuid.uuid4().hex}"
        user_id = cast(
            uuid.UUID,
            await self.value(
                "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
                "VALUES ($1, $2, $3, 'Test person') RETURNING id",
                ISSUER,
                subject,
                f"{subject}@example.test",
            ),
        )
        for firm in (tenant_id, also):
            if firm is not None:
                await self.run(
                    "INSERT INTO memberships (tenant_id, user_id, firm_role, status) "
                    "VALUES ($1, $2, $3, 'active')",
                    firm,
                    user_id,
                    firm_role,
                )
        return Person(user_id, tenant_id, subject)

    async def site(self, tenant_id: uuid.UUID, created_by: uuid.UUID, label: str) -> Site:
        """A client named `label` with an open engagement, a request item and an evidence
        version; `label` (unique per call) is the text no other firm or client may ever see."""
        marker = f"{label}-{uuid.uuid4().hex[:8]}"
        client_id = cast(
            uuid.UUID,
            await self.value(
                "INSERT INTO clients (tenant_id, name) VALUES ($1, $2) RETURNING id",
                tenant_id,
                f"Client {marker}",
            ),
        )
        entity_id = cast(
            uuid.UUID,
            await self.value(
                "INSERT INTO client_entities (tenant_id, client_id, name) "
                "VALUES ($1, $2, $3) RETURNING id",
                tenant_id,
                client_id,
                f"Entity {marker}",
            ),
        )
        engagement_id = cast(
            uuid.UUID,
            await self.value(
                "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
                "fiscal_period_start, fiscal_period_end, created_by) "
                "VALUES ($1, $2, $3, $4, '2025-01-01', '2025-12-31', $5) RETURNING id",
                tenant_id,
                client_id,
                entity_id,
                f"Engagement {marker}",
                created_by,
            ),
        )
        # SPEC-025 AC-7: open to client data (accepted, independence concluded).
        await self.run(
            "INSERT INTO engagement_acceptance (tenant_id, engagement_id, kind, decision, "
            "decided_by, documented_at, independence_concluded_by, independence_concluded_at, "
            "independence_documented_at) VALUES ($1, $2, 'continuance', 'accepted', 'test-seed', "
            "'Seeded', 'test-seed', clock_timestamp(), 'Seeded')",
            tenant_id,
            engagement_id,
        )
        list_id = await self.value(
            "INSERT INTO request_lists (tenant_id, engagement_id) VALUES ($1, $2) RETURNING id",
            tenant_id,
            engagement_id,
        )
        item_id = cast(
            uuid.UUID,
            await self.value(
                "INSERT INTO request_items (tenant_id, engagement_id, request_list_id, "
                "description, audit_area, created_by) VALUES ($1, $2, $3, $4, 'Cash', $5) "
                "RETURNING id",
                tenant_id,
                engagement_id,
                list_id,
                f"Bank confirmation {marker}",
                created_by,
            ),
        )
        evidence_id = await self.value(
            "INSERT INTO evidence_items (tenant_id, engagement_id, title, created_by_kind, "
            "created_by_id) VALUES ($1, $2, $3, 'system', 'seed') RETURNING id",
            tenant_id,
            engagement_id,
            f"Evidence {marker}",
        )
        fingerprint = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
        version_id = cast(
            uuid.UUID,
            await self.value(
                "INSERT INTO evidence_versions (tenant_id, engagement_id, evidence_item_id, "
                "version_no, fingerprint, storage_key, storage_version_id, size_bytes, "
                "media_type, source, method) VALUES ($1, $2, $3, 1, $4, $5, 'v1', 10, "
                "'application/pdf', 'upload', 'uploaded') RETURNING id",
                tenant_id,
                engagement_id,
                evidence_id,
                fingerprint,
                f"tenants/{tenant_id}/sha256/{fingerprint}",
            ),
        )
        return Site(client_id, entity_id, engagement_id, item_id, version_id, marker)

    async def member(self, site: Site, who: Person, role: Role) -> None:
        """`who` joins the site's engagement; staff roles have confirmed independence."""
        await self.run(
            "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
            "VALUES ($1, $2, $3, $4)",
            who.tenant_id,
            site.engagement_id,
            who.user_id,
            role,
        )
        if role in STAFF_ROLES:
            await self.run(
                "INSERT INTO independence_confirmations (tenant_id, engagement_id, user_id, "
                "status, statement_version, answered_at) VALUES ($1, $2, $3, 'confirmed', 'v1', "
                "clock_timestamp()) ON CONFLICT DO NOTHING",
                who.tenant_id,
                site.engagement_id,
                who.user_id,
            )


@dataclass(frozen=True)
class Net:
    seed: Seeder
    http: httpx.AsyncClient
    idp: FakeIdentityProvider

    def headers(
        self, who: Person, *, mfa: bool = True, tenant: uuid.UUID | None = None
    ) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self.idp.token(who.subject, mfa=mfa)}"}
        if tenant is not None:
            headers[TENANT_HEADER] = str(tenant)
        return headers

    async def call(
        self,
        method: str,
        path: str,
        who: Person,
        *,
        body: Mapping[str, object] | None = None,
        mfa: bool = True,
        tenant: uuid.UUID | None = None,
    ) -> httpx.Response:
        return await self.http.request(
            method, path, json=body, headers=self.headers(who, mfa=mfa, tenant=tenant)
        )

    async def wall(self, admin: Person, who: Person, site: Site) -> None:
        response = await self.call(
            "POST",
            "/v1/walls",
            admin,
            body={"user_id": str(who.user_id), "client_id": str(site.client_id)},
        )
        assert response.status_code == 201, response.text


@dataclass(frozen=True)
class Env:
    net: Net
    tenant_id: uuid.UUID
    admin: Person
    a: Site
    b: Site

    async def walled(self, role: str) -> Person:
        """A person with `role`, on both engagements, walled off from client A."""
        firm_role = role if role in FIRM_ROLES else None
        who = await self.net.seed.person(self.tenant_id, firm_role)
        member = cast(Role, "manager" if firm_role else role)
        for site in (self.a, self.b):
            await self.net.seed.member(site, who, member)
        await self.net.wall(self.admin, who, self.a)
        return who

    async def get(self, who: Person, path: str) -> httpx.Response:
        return await self.net.call("GET", path, who)

    def leaks(self, response: httpx.Response) -> list[str]:
        """What of client A is in the body: its ids and its names."""
        body = response.text
        return [
            token
            for token in (
                str(self.a.engagement_id),
                str(self.a.client_id),
                str(self.a.item_id),
                str(self.a.version_id),
                self.a.marker,
            )
            if token in body
        ]


@dataclass(frozen=True)
class TwoFirms:
    """Two firms with a site each, for the generated isolation test (Q-02-T13)."""

    a_ctx: TenantContext
    b: uuid.UUID


_TWO_FIRMS: dict[str, TwoFirms] = {}


async def two_firms(seed: Seeder) -> TwoFirms:
    """Seeded once per database: the generated test reads, it never writes."""
    known = _TWO_FIRMS.get(seed.dsn_key)
    if known is not None:
        return known
    a, b = await seed.firm(), await seed.firm()
    admin_a = await seed.person(a, "firm_admin")
    admin_b = await seed.person(b, "firm_admin")
    await seed.site(a, admin_a.user_id, "isolation-a")
    await seed.site(b, admin_b.user_id, "isolation-b")
    firms = TwoFirms(TenantContext(a, "human", str(admin_a.user_id)), b)
    _TWO_FIRMS[seed.dsn_key] = firms
    return firms
