"""Seeding for the Undo conformance suite: synthetic firms (so business time can be frozen),
people, an opened engagement with its work item, written as the superuser."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import cast

import asyncpg

from abacus_tools.fakes.identity import ISSUER


@dataclass(frozen=True)
class Person:
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    subject: str


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

    async def firm(self, *flags: str) -> uuid.UUID:
        tenant = uuid.uuid4()
        await self.run(
            "INSERT INTO firms (tenant_id, name, synthetic) VALUES ($1, $2, true)",
            tenant,
            f"Firm {tenant.hex[:8]}",
        )
        for flag in flags:
            await self.run(
                "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
                "VALUES ($1, $2, 'true', 'test-seed', 'P-04-T13')",
                tenant,
                flag,
            )
        return tenant

    async def person(self, tenant: uuid.UUID, name: str) -> Person:
        subject = f"sub-{uuid.uuid4().hex}"
        user = cast(
            uuid.UUID,
            await self.value(
                "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
                "VALUES ($1, $2, $3, $4) RETURNING id",
                ISSUER,
                subject,
                f"{subject}@example.test",
                name,
            ),
        )
        await self.run(
            "INSERT INTO memberships (tenant_id, user_id, status) VALUES ($1, $2, 'active')",
            tenant,
            user,
        )
        return Person(user, tenant, subject)

    async def engagement(self, tenant: uuid.UUID, by: Person) -> uuid.UUID:
        client = await self.value(
            "INSERT INTO clients (tenant_id, name) VALUES ($1, 'Feld household') RETURNING id",
            tenant,
        )
        entity = await self.value(
            "INSERT INTO client_entities (tenant_id, client_id, name) "
            "VALUES ($1, $2, 'Feld household') RETURNING id",
            tenant,
            client,
        )
        engagement = cast(
            uuid.UUID,
            await self.value(
                "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
                "fiscal_period_start, fiscal_period_end, created_by) "
                "VALUES ($1, $2, $3, 'Feld 2025', '2025-01-01', '2025-12-31', $4) RETURNING id",
                tenant,
                client,
                entity,
                by.user_id,
            ),
        )
        await self.run(
            "INSERT INTO engagement_acceptance (tenant_id, engagement_id, kind, decision, "
            "decided_by, documented_at, independence_concluded_by, independence_concluded_at, "
            "independence_documented_at) VALUES ($1, $2, 'continuance', 'accepted', 'test-seed', "
            "'Seeded', 'test-seed', clock_timestamp(), 'Seeded')",
            tenant,
            engagement,
        )
        return engagement

    async def member(self, engagement: uuid.UUID, who: Person, role: str) -> None:
        await self.run(
            "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
            "VALUES ($1, $2, $3, $4)",
            who.tenant_id,
            engagement,
            who.user_id,
            role,
        )
        await self.run(
            "INSERT INTO independence_confirmations (tenant_id, engagement_id, user_id, status, "
            "statement_version, answered_at) "
            "VALUES ($1, $2, $3, 'confirmed', 'v1', clock_timestamp())",
            who.tenant_id,
            engagement,
            who.user_id,
        )

    async def client(self, tenant: uuid.UUID, engagement: uuid.UUID, name: str) -> Person:
        """A client principal on the engagement: a client membership and an engagement-scope
        owner grant (the matrix's client admin; R-01-T08)."""
        who = await self.person(tenant, name)
        await self.run(
            "UPDATE memberships SET kind = 'client' WHERE tenant_id = $1 AND user_id = $2",
            tenant,
            who.user_id,
        )
        await self.run(
            "INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id) "
            "VALUES ($1, $2, 'owner', 'engagement', $3)",
            tenant,
            who.user_id,
            engagement,
        )
        return who
