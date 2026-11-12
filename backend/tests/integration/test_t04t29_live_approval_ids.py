"""TASK-7322 (T-04-T29 rest): `LIVE_APPROVAL_IDS` on Postgres. Each document's live approval at
a level is the latest one not reversed; a reversed approval, or one at another level, names
nothing. The rows go in as the superuser with foreign-key triggers off (the query reads
`document_approvals` alone)."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest

from abacus.modules.tax.review_tree import LIVE_APPROVAL_IDS
from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import provisioned_database

TENANT, ENGAGEMENT, RETURN, USER = (uuid.uuid4() for _ in range(4))
A, B, C = (uuid.uuid4() for _ in range(3))
T0 = datetime(2026, 9, 14, 9, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _query() -> str:
    return str(LIVE_APPROVAL_IDS).replace(":r", "$1").replace(":l", "$2")


def test_the_latest_unreversed_approval_at_the_level_is_named(db: sc.Database) -> None:
    async def go() -> tuple[dict[uuid.UUID, uuid.UUID], uuid.UUID]:
        conn = await asyncpg.connect(db.superuser_dsn)
        try:
            await conn.execute("SET session_replication_role = replica")
            await conn.execute("SELECT set_config('app.actor_kind', 'human', false)")
            await conn.execute("SELECT set_config('app.actor_id', $1, false)", str(USER))

            async def row(
                version: uuid.UUID,
                level: str,
                at: datetime,
                kind: str = "approve",
                reverses: uuid.UUID | None = None,
            ) -> uuid.UUID:
                return await conn.fetchval(
                    "INSERT INTO document_approvals (tenant_id, engagement_id, tax_return_id, "
                    "evidence_version_id, level, kind, reverses_id, actor_user_id, seen_version, "
                    "decided_at) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 1, $9) RETURNING id",
                    TENANT,
                    ENGAGEMENT,
                    RETURN,
                    version,
                    level,
                    kind,
                    reverses,
                    USER,
                    at,
                )

            first = await row(A, "manager", T0)
            latest = await row(A, "manager", T0 + timedelta(minutes=5))
            assert first != latest
            gone = await row(B, "manager", T0)
            await row(B, "manager", T0 + timedelta(minutes=1), "reverse", gone)
            await row(C, "detail", T0)
            rows = await conn.fetch(_query(), RETURN, "manager")
            return {r["evidence_version_id"]: r["id"] for r in rows}, latest
        finally:
            await conn.close()

    found, latest = asyncio.run(go())
    assert found == {A: latest}
