"""Seeding and HTTP helpers for the Q-03 acceptance back-fill tests: firms, people, engagements,
request items and evidence, written as the superuser (`migrated_db.superuser_dsn`) with fresh
firms per test so nothing needs cleanup, and requests made with fake-identity tokens against
`create_app()`.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Final, Literal, Protocol, cast

import asyncpg
import httpx

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

    tenant_id: uuid.UUID
    client_id: uuid.UUID
    entity_id: uuid.UUID
    engagement_id: uuid.UUID
    item_id: uuid.UUID
    version_id: uuid.UUID
    marker: str


class Seeder:
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

    async def rows(self, sql: str, *args: object) -> list[asyncpg.Record]:
        conn = await asyncpg.connect(self._dsn)
        try:
            return list(await conn.fetch(sql, *args))
        finally:
            await conn.close()

    async def attest(self, tenant_id: uuid.UUID, engagement_id: uuid.UUID) -> None:
        """The engagement becomes an active EBP audit, so its client is an attest client
        (DEC-128); the derivation trigger reads under the tenant, as the app's write does."""
        conn = await asyncpg.connect(self._dsn)
        try:
            async with conn.transaction():
                await conn.execute("SELECT set_config('app.tenant_id', $1, true)", str(tenant_id))
                await conn.execute(
                    "UPDATE engagements SET type = 'ebp_audit', status = 'active' WHERE id = $1",
                    engagement_id,
                )
        finally:
            await conn.close()

    async def blocks_view(self, tenant_id: uuid.UUID, set_by: uuid.UUID) -> None:
        """ADR-164 item 3: the firm restores TASK-045's read gate on attest engagements."""
        await self.run(
            "INSERT INTO firm_setting_values (tenant_id, key, value, set_by) "
            "VALUES ($1, 'g2_blocks_view', true, $2)",
            tenant_id,
            set_by,
        )

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

    async def site(
        self, tenant_id: uuid.UUID, created_by: uuid.UUID, label: str, *, opened: bool = True
    ) -> Site:
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
        if opened:  # SPEC-025 AC-7: open to client data (accepted, independence concluded)
            await self.run(
                "INSERT INTO engagement_acceptance (tenant_id, engagement_id, kind, decision, "
                "decided_by, documented_at, independence_concluded_by, "
                "independence_concluded_at, independence_documented_at) VALUES ($1, $2, "
                "'continuance', 'accepted', 'test-seed', 'Seeded', 'test-seed', "
                "clock_timestamp(), 'Seeded')",
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
        return Site(tenant_id, client_id, entity_id, engagement_id, item_id, version_id, marker)

    async def client_contact(self, site: Site, role: str = "client_admin") -> Person:
        """A client user of the site's engagement (a `client` membership and a client role)."""
        who = await self.person(site.tenant_id)
        await self.run(
            "UPDATE memberships SET kind = 'client' WHERE tenant_id = $1 AND user_id = $2",
            who.tenant_id,
            who.user_id,
        )
        # F-03-T26: a client role on an engagement is an engagement-scope grant.
        await self.run(
            "INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id) "
            "VALUES ($1, $3, CASE $4 WHEN 'client_admin' THEN 'owner' ELSE 'contributor' END, "
            "'engagement', $2)",
            who.tenant_id,
            site.engagement_id,
            who.user_id,
            role,
        )
        return who

    async def item(
        self,
        site: Site,
        description: str,
        *,
        status: str = "requested",  # F-03-T15: asked of the client (was `open`)
        due_on: date | None = None,
        assignee: Person | None = None,
    ) -> uuid.UUID:
        """Another request item on the site's engagement (its list is the site's)."""
        return cast(
            uuid.UUID,
            await self.value(
                "INSERT INTO request_items (tenant_id, engagement_id, request_list_id, "
                "description, audit_area, created_by, status, due_on, client_assignee_user_id) "
                "SELECT i.tenant_id, i.engagement_id, i.request_list_id, $2, 'Cash', "
                "i.created_by, $3, $4, $5 FROM request_items i WHERE i.id = $1 "
                "RETURNING id",
                site.item_id,
                description,
                status,
                due_on,
                assignee.user_id if assignee is not None else None,
            ),
        )

    async def actions(self, tenant_id: uuid.UUID) -> list[str]:
        """The firm's audit trail, oldest first (actions only)."""
        rows = await self.rows(
            "SELECT action FROM audit_events WHERE tenant_id = $1 ORDER BY seq", tenant_id
        )
        return [str(r["action"]) for r in rows]

    async def revoke(self, who: Person) -> None:
        await self.run(
            "UPDATE memberships SET status = 'revoked', revoked_at = now() "
            "WHERE tenant_id = $1 AND user_id = $2",
            who.tenant_id,
            who.user_id,
        )

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

    def newcomer(self, email: str) -> tuple[str, dict[str, str]]:
        """A sign-in for someone with no account yet: their subject and bearer header, the
        provider vouching for `email`."""
        subject = f"new-{uuid.uuid4().hex}"
        return subject, self.identity(subject, email)

    def identity(self, subject: str, email: str) -> dict[str, str]:
        """The bearer header of a provider-verified identity (it needs no account to join)."""
        token = self.idp.token(subject, email=email, email_verified=True)
        return {"Authorization": f"Bearer {token}"}

    async def wall(self, admin: Person, who: Person, site: Site) -> None:
        response = await self.call(
            "POST",
            "/v1/walls",
            admin,
            body={"user_id": str(who.user_id), "client_id": str(site.client_id)},
        )
        assert response.status_code == 201, response.text
