"""F-03-T05 (migration 0068): every engagement holds one assurance work item and one primary
entity; a second assurance item is refused; assignments and entity links are insert-only."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Protocol, cast

import asyncpg
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine, tenant_session
from abacus_tools.fakes.identity import ISSUER


class Migrated(Protocol):
    app_url: str
    identity_url: str
    superuser_dsn: str


@pytest.fixture(autouse=True)
async def engines(migrated_db: Migrated, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


async def _value(dsn: str, sql: str, *args: object) -> object:
    conn = await asyncpg.connect(dsn)
    try:
        return await conn.fetchval(sql, *args)
    finally:
        await conn.close()


async def _engagement(dsn: str) -> tuple[TenantContext, uuid.UUID]:
    tenant = uuid.uuid4()
    await _value(dsn, "INSERT INTO firms (tenant_id, name) VALUES ($1, 'F')", tenant)
    subject = f"sub-{uuid.uuid4().hex}"
    user = cast(
        uuid.UUID,
        await _value(
            dsn,
            "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
            "VALUES ($1, $2, $3, 'U') RETURNING id",
            ISSUER,
            subject,
            f"{subject}@example.test",
        ),
    )
    await _value(
        dsn,
        "INSERT INTO memberships (tenant_id, user_id, firm_role, status) "
        "VALUES ($1, $2, NULL, 'active')",
        tenant,
        user,
    )
    client = await _value(
        dsn, "INSERT INTO clients (tenant_id, name) VALUES ($1, 'C') RETURNING id", tenant
    )
    entity = await _value(
        dsn,
        "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, 'E') "
        "RETURNING id",
        tenant,
        client,
    )
    engagement = cast(
        uuid.UUID,
        await _value(
            dsn,
            "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
            "fiscal_period_start, fiscal_period_end, created_by) "
            "VALUES ($1, $2, $3, 'N', '2025-01-01', '2025-12-31', $4) RETURNING id",
            tenant,
            client,
            entity,
            user,
        ),
    )
    return TenantContext(tenant, "human", str(user)), engagement


async def _rows(ctx: TenantContext, sql: str, **params: object) -> list[tuple[object, ...]]:
    async with tenant_session(ctx) as session:
        return [tuple(r) for r in (await session.execute(text(sql), params)).all()]


async def test_t05_a_new_engagement_holds_one_assurance_item_and_a_primary_entity(
    migrated_db: Migrated,
) -> None:
    ctx, engagement = await _engagement(migrated_db.superuser_dsn)
    items = await _rows(
        ctx,
        "SELECT w.kind, w.name, a.phase, a.assurance_type FROM work_items w "
        "JOIN assurance_work_items a ON a.work_item_id = w.id WHERE w.engagement_id = :e",
        e=engagement,
    )
    assert items == [("assurance", "N", "planning", "audit")]
    primary = await _rows(
        ctx, "SELECT role FROM engagement_entities WHERE engagement_id = :e", e=engagement
    )
    assert primary == [("primary",)]


async def test_t05_a_second_assurance_item_is_refused(migrated_db: Migrated) -> None:
    ctx, engagement = await _engagement(migrated_db.superuser_dsn)
    with pytest.raises(DBAPIError, match="work_items_one_assurance"):
        async with tenant_session(ctx) as session:
            await session.execute(
                text(
                    "INSERT INTO work_items (tenant_id, engagement_id, client_id, kind, name, "
                    "created_by) SELECT tenant_id, id, client_id, 'assurance', 'Again', "
                    "created_by FROM engagements WHERE id = :e"
                ),
                {"e": engagement},
            )


async def test_t05_entity_links_are_insert_only_and_rls_hides_other_firms(
    migrated_db: Migrated,
) -> None:
    ctx, engagement = await _engagement(migrated_db.superuser_dsn)
    other, _ = await _engagement(migrated_db.superuser_dsn)
    with pytest.raises(DBAPIError, match="permission denied"):
        async with tenant_session(ctx) as session:
            await session.execute(text("DELETE FROM engagement_entities"))
    seen = await _rows(
        other, "SELECT count(*) FROM work_items WHERE engagement_id = :e", e=engagement
    )
    assert seen == [(0,)]
