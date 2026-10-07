"""Helpers for the TASK-016 ethical-walls tests: people with firm roles, clients with
engagements, walls seeded as the superuser, and HTTP with fake-identity tokens.

Everything is seeded through the shared `Seeder` (no connections are opened here).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, cast

import httpx

from abacus.kernel.db import TenantContext
from abacus.modules.identity.api import AuthContext
from abacus_tools.fakes.identity import FakeIdentityProvider

from .support import Person, Seeder

Json = dict[str, object]
FirmRole = Literal["firm_admin", "practice_leader", "quality_partner"]
NOT_FOUND = {"detail": "not found"}
FORBIDDEN = {"detail": "forbidden"}
FIRM_ROLES = ("firm_admin", "practice_leader", "quality_partner")
ENGAGEMENT_ROLES = ("engagement_partner", "manager", "senior", "staff", "reviewer")
WALL_KEYS = {
    "id",
    "user_id",
    "client_id",
    "status",
    "created_by",
    "created_at",
    "removed_by",
    "removed_at",
}


@dataclass(frozen=True)
class Site:
    """One client with one entity and one engagement."""

    client_id: uuid.UUID
    entity_id: uuid.UUID
    engagement_id: uuid.UUID


def firm_role_of(role: str | None) -> FirmRole | None:
    return role if role in FIRM_ROLES else None


def context(who: Person, firm_role: FirmRole | None = None, *, mfa: bool = True) -> AuthContext:
    """A human context for direct `authorise` and service calls."""
    return AuthContext(
        tenant=TenantContext(who.tenant_id, "human", str(who.user_id)),
        user_id=who.user_id,
        membership_id=uuid.uuid4(),
        firm_role=firm_role,
        mfa_at=datetime.now(UTC) - timedelta(minutes=1) if mfa else None,
    )


@dataclass(frozen=True)
class Net:
    seed: Seeder
    http: httpx.AsyncClient
    idp: FakeIdentityProvider

    async def person(self, tenant_id: uuid.UUID, firm_role: str | None = None) -> Person:
        who = await self.seed.person(tenant_id)
        if firm_role is not None:
            await self.seed.run(
                "UPDATE memberships SET firm_role = $3 WHERE tenant_id = $1 AND user_id = $2",
                tenant_id,
                who.user_id,
                firm_role,
            )
        return who

    async def headers(
        self, who: Person, *, mfa: bool = True, mfa_age: timedelta | None = None
    ) -> dict[str, str]:
        subject = str(
            await self.seed.value("SELECT idp_subject FROM users WHERE id = $1", who.user_id)
        )
        if mfa and mfa_age is not None:
            auth_time = int((datetime.now(UTC) - mfa_age).timestamp())
            return {
                "Authorization": f"Bearer {self.idp.token(subject, mfa=True, auth_time=auth_time)}"
            }
        return {"Authorization": f"Bearer {self.idp.token(subject, mfa=mfa)}"}

    async def call(
        self,
        method: str,
        path: str,
        who: Person,
        *,
        body: Json | None = None,
        mfa: bool = True,
        mfa_age: timedelta | None = None,
    ) -> httpx.Response:
        return await self.http.request(
            method, path, json=body, headers=await self.headers(who, mfa=mfa, mfa_age=mfa_age)
        )

    async def create_wall(
        self, admin: Person, user_id: uuid.UUID, client_id: uuid.UUID
    ) -> httpx.Response:
        return await self.call(
            "POST", "/v1/walls", admin, body={"user_id": str(user_id), "client_id": str(client_id)}
        )

    async def wall(self, admin: Person, user_id: uuid.UUID, client_id: uuid.UUID) -> uuid.UUID:
        response = await self.create_wall(admin, user_id, client_id)
        assert response.status_code == 201, response.text
        return uuid.UUID(cast(str, response.json()["id"]))

    async def remove_wall(self, admin: Person, wall_id: object) -> httpx.Response:
        return await self.call("POST", f"/v1/walls/{wall_id}/remove", admin)

    async def list_walls(self, who: Person, *, mfa: bool = True) -> httpx.Response:
        return await self.call("GET", "/v1/walls", who, mfa=mfa)

    async def site(self, tenant_id: uuid.UUID, created_by: uuid.UUID) -> Site:
        entity_id = await self.seed.entity(tenant_id)
        client_id = cast(
            uuid.UUID,
            await self.seed.value(
                "SELECT client_id FROM client_entities WHERE id = $1", entity_id
            ),
        )
        engagement_id = await self.seed.engagement(tenant_id, entity_id, created_by)
        return Site(client_id, entity_id, engagement_id)

    async def later_engagement(
        self, site: Site, tenant_id: uuid.UUID, created_by: uuid.UUID
    ) -> uuid.UUID:
        """Another engagement for the same client, created after any wall (AC-6)."""
        return await self.seed.engagement(tenant_id, site.entity_id, created_by)

    async def wall_rows(self, tenant_id: uuid.UUID) -> int:
        return cast(
            int,
            await self.seed.value(
                "SELECT count(*) FROM ethical_walls WHERE tenant_id = $1", tenant_id
            ),
        )

    async def audit(self, tenant_id: uuid.UUID, action: str) -> list[Json]:
        rows = await self.seed.rows(
            "SELECT actor_kind, actor_id, target_type, target_id::text AS target_id, "
            "before_ref::text AS before_ref, after_ref::text AS after_ref FROM audit_events "
            "WHERE tenant_id = $1 AND action = $2 ORDER BY seq",
            tenant_id,
            action,
        )
        return [dict(row) for row in rows]


def ids(response: httpx.Response) -> list[str]:
    assert response.status_code == 200, response.text
    return [cast(str, row["id"]) for row in cast(list[Json], response.json())]
