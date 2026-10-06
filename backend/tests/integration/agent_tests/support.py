"""Seeding and helpers shared by the TASK-011a integration tests (agents and the AI gateway).

Rows are seeded as the superuser (`migrated_db.superuser_dsn`) with a fresh firm per world, so
tests never need cleanup. A retrieved trial balance is produced by the real retrieval pipeline.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal, Protocol, cast

import asyncpg

from abacus.kernel.db import TenantContext
from abacus.modules.connections.api import (
    Period,
    RunResult,
    load_system_context,
    run_pipeline,
    start_retrieval,
)
from abacus.modules.identity.api import AuthContext
from abacus_tools.synthetic import generate
from abacus_tools.synthetic.connector_fixtures import (
    trial_balance_document,
    write_raw,
    write_trial_balance,
)

ENTITY = generate(1).client_entities[0]
TB = ENTITY.trial_balances[-1]
PERIOD = Period(ENTITY.period_start, TB.as_of)
ENTITY_NAME = "Seeded entity"
Role = Literal["engagement_partner", "manager", "senior", "staff", "reviewer"]


COUNTS = {
    "agent_runs": "SELECT count(*) FROM agent_runs WHERE tenant_id = $1",
    "screening_results": "SELECT count(*) FROM screening_results WHERE tenant_id = $1",
    "usage_records": "SELECT count(*) FROM usage_records WHERE tenant_id = $1",
    "audit_events": "SELECT count(*) FROM audit_events WHERE tenant_id = $1",
    "outbox": "SELECT count(*) FROM outbox WHERE tenant_id = $1",
    "evidence_versions": "SELECT count(*) FROM evidence_versions WHERE tenant_id = $1",
}


class Migrated(Protocol):
    owner_url: str
    app_url: str
    relay_url: str
    identity_url: str
    superuser_dsn: str


@dataclass(frozen=True)
class Person:
    user_id: uuid.UUID
    tenant_id: uuid.UUID

    def context(self) -> AuthContext:
        return AuthContext(
            tenant=TenantContext(self.tenant_id, "human", str(self.user_id)),
            user_id=self.user_id,
            membership_id=uuid.uuid4(),
            firm_role=None,
            mfa_at=datetime.now(UTC) - timedelta(minutes=1),
        )


@dataclass(frozen=True)
class Event:
    action: str
    actor_kind: str
    actor_id: str
    target_id: str | None
    after: dict[str, object]


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

    async def firm(self) -> uuid.UUID:
        tenant_id = uuid.uuid4()
        await self.run(
            "INSERT INTO firms (tenant_id, name) VALUES ($1, $2)",
            tenant_id,
            f"Firm {tenant_id.hex[:8]}",
        )
        return tenant_id

    async def person(self, tenant_id: uuid.UUID) -> Person:
        subject = f"sub-{uuid.uuid4().hex}"
        user_id = cast(
            uuid.UUID,
            await self.value(
                "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
                "VALUES ('https://identity.abacus.local', $1, $2, 'Test person') RETURNING id",
                subject,
                f"{subject}@example.test",
            ),
        )
        await self.run(
            "INSERT INTO memberships (tenant_id, user_id, firm_role, status) "
            "VALUES ($1, $2, NULL, 'active')",
            tenant_id,
            user_id,
        )
        return Person(user_id, tenant_id)

    async def revoke(self, who: Person) -> None:
        await self.run(
            "UPDATE memberships SET status = 'revoked', revoked_at = now() "
            "WHERE tenant_id = $1 AND user_id = $2",
            who.tenant_id,
            who.user_id,
        )

    async def entity(self, tenant_id: uuid.UUID, name: str = ENTITY_NAME) -> uuid.UUID:
        client_id = cast(
            uuid.UUID,
            await self.value(
                "INSERT INTO clients (tenant_id, name) VALUES ($1, 'Seeded client') RETURNING id",
                tenant_id,
            ),
        )
        return cast(
            uuid.UUID,
            await self.value(
                "INSERT INTO client_entities (tenant_id, client_id, name) "
                "VALUES ($1, $2, $3) RETURNING id",
                tenant_id,
                client_id,
                name,
            ),
        )

    async def engagement(
        self, tenant_id: uuid.UUID, entity_id: uuid.UUID, created_by: uuid.UUID
    ) -> uuid.UUID:
        client_id = await self.value(
            "SELECT client_id FROM client_entities WHERE id = $1", entity_id
        )
        return cast(
            uuid.UUID,
            await self.value(
                "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
                "fiscal_period_start, fiscal_period_end, created_by) "
                "VALUES ($1, $2, $3, $4, '2025-01-01', '2025-12-31', $5) RETURNING id",
                tenant_id,
                client_id,
                entity_id,
                f"Seeded {uuid.uuid4().hex[:6]}",
                created_by,
            ),
        )

    async def member(self, engagement_id: uuid.UUID, who: Person, role: Role) -> None:
        await self.run(
            "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
            "VALUES ($1, $2, $3, $4)",
            who.tenant_id,
            engagement_id,
            who.user_id,
            role,
        )

    async def unmember(self, engagement_id: uuid.UUID, who: Person) -> None:
        await self.run(
            "DELETE FROM engagement_members WHERE engagement_id = $1 AND user_id = $2",
            engagement_id,
            who.user_id,
        )

    async def item(
        self, tenant_id: uuid.UUID, engagement_id: uuid.UUID, created_by: uuid.UUID
    ) -> uuid.UUID:
        list_id = cast(
            uuid.UUID,
            await self.value(
                "INSERT INTO request_lists (tenant_id, engagement_id) VALUES ($1, $2) "
                "ON CONFLICT (tenant_id, engagement_id) DO UPDATE SET tenant_id = $1 "
                "RETURNING id",
                tenant_id,
                engagement_id,
            ),
        )
        return cast(
            uuid.UUID,
            await self.value(
                "INSERT INTO request_items (tenant_id, engagement_id, request_list_id, "
                "description, audit_area, created_by) VALUES ($1, $2, $3, 'Trial balance', "
                "'Financial reporting', $4) RETURNING id",
                tenant_id,
                engagement_id,
                list_id,
                created_by,
            ),
        )

    async def connection(self, tenant_id: uuid.UUID, entity_id: uuid.UUID) -> uuid.UUID:
        return cast(
            uuid.UUID,
            await self.value(
                "INSERT INTO connections (tenant_id, client_entity_id, provider, status, "
                "created_by) VALUES ($1, $2, 'fake', 'active', 'test-seed') RETURNING id",
                tenant_id,
                entity_id,
            ),
        )

    async def events(self, tenant_id: uuid.UUID) -> list[Event]:
        rows = await self.rows(
            "SELECT action, actor_kind, actor_id, target_id, after_ref::text AS after "
            "FROM audit_events WHERE tenant_id = $1 ORDER BY seq",
            tenant_id,
        )
        return [
            Event(
                str(r["action"]),
                str(r["actor_kind"]),
                str(r["actor_id"]),
                None if r["target_id"] is None else str(r["target_id"]),
                cast(dict[str, object], json.loads(r["after"])) if r["after"] else {},
            )
            for r in rows
        ]

    async def actions(self, tenant_id: uuid.UUID) -> list[str]:
        return [e.action for e in await self.events(tenant_id)]

    async def count(self, table: str, tenant_id: uuid.UUID) -> int:
        return cast(int, await self.value(COUNTS[table], tenant_id))

    async def item_status(self, item_id: uuid.UUID) -> str:
        return str(await self.value("SELECT status FROM request_items WHERE id = $1", item_id))


@dataclass(frozen=True)
class World:
    tenant_id: uuid.UUID
    engagement_id: uuid.UUID
    entity_id: uuid.UUID
    item_id: uuid.UUID
    connection_id: uuid.UUID
    requester: Person
    directory: Path

    def write_document(self, change: Callable[[dict[str, object]], None]) -> None:
        document = trial_balance_document(
            TB, period_start=ENTITY.period_start, entity_name=ENTITY_NAME
        )
        change(document)
        write_raw(self.directory, self.connection_id, PERIOD, json.dumps(document).encode())


async def make_world(seed: Seeder, directory: Path) -> World:
    tenant_id = await seed.firm()
    requester = await seed.person(tenant_id)
    entity_id = await seed.entity(tenant_id)
    engagement_id = await seed.engagement(tenant_id, entity_id, requester.user_id)
    await seed.member(engagement_id, requester, "staff")
    item_id = await seed.item(tenant_id, engagement_id, requester.user_id)
    connection_id = await seed.connection(tenant_id, entity_id)
    world = World(
        tenant_id, engagement_id, entity_id, item_id, connection_id, requester, directory
    )
    write_trial_balance(
        directory,
        connection_id,
        TB,
        period_start=ENTITY.period_start,
        entity_name=ENTITY_NAME,
    )
    return world


async def retrieve(world: World) -> RunResult:
    """Run a real retrieval for the world's requester; the result holds the evidence version."""
    started = await start_retrieval(
        world.requester.context(),
        engagement_id=world.engagement_id,
        request_item_id=world.item_id,
        period=PERIOD,
    )
    run_id = started.run_id
    return await run_pipeline(await load_system_context(world.tenant_id, run_id))


async def uploaded_version(seed: Seeder, world: World) -> uuid.UUID:
    """An uploaded (not retrieved) evidence version: it has no ledger snapshot."""
    item_id = await seed.value(
        "INSERT INTO evidence_items (tenant_id, engagement_id, title, created_by_kind, "
        "created_by_id) VALUES ($1, $2, 'Uploaded evidence', 'system', 'seed') RETURNING id",
        world.tenant_id,
        world.engagement_id,
    )
    fingerprint = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
    return cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO evidence_versions (tenant_id, engagement_id, evidence_item_id, "
            "version_no, fingerprint, storage_key, storage_version_id, size_bytes, "
            "media_type, source, method) VALUES ($1, $2, $3, 1, $4, $5, 'v1', 10, "
            "'application/pdf', 'upload', 'uploaded') RETURNING id",
            world.tenant_id,
            world.engagement_id,
            item_id,
            fingerprint,
            f"tenants/{world.tenant_id}/sha256/{fingerprint}",
        ),
    )
