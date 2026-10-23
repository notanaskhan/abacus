"""P-03-T04 against Postgres (migration 0109; SPEC-322; ADR-166): the trust kit's tables take the
app's inserts and refuse every change. A citation is verified or names its reason, and only a
person relinks one. Statements run as the app role through the unit of work,
so the column grants are what production uses."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.uow import Target, uow

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

CITE = (
    "INSERT INTO citations (id, tenant_id, cited_from_type, cited_from_id, n, kind, "
    "source_type, source_id, locator, verified, verification_reason, verifier_version, "
    "created_by_kind, created_by_user_id) VALUES (:id, :t, 'workpaper_cell', :anchor, 1, "
    "'document_text', 'evidence_version', :source, CAST('{\"page\": 3}' AS jsonb), :verified, "
    ":reason, 'v1', 'human', :person)"
)


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


async def _as(ctx: TenantContext, statement: str, **params: object) -> None:
    async with uow(ctx) as tx:
        await tx.session.execute(text(statement), params)
        tx.record("citation.created", target=Target("citation", ctx.tenant_id))


async def test_p03t04_a_citation_is_written_once_and_never_changed(
    migrated_db: MigratedDatabase,
) -> None:
    tenant = await Seeder(migrated_db.superuser_dsn).firm()
    person = uuid.uuid4()
    ctx = TenantContext(tenant, "human", str(person))
    cited = uuid.uuid4()
    params = {"t": tenant, "anchor": uuid.uuid4(), "source": uuid.uuid4(), "person": person}
    await _as(ctx, CITE, id=cited, verified=True, reason=None, **params)
    with pytest.raises(DBAPIError, match="check"):  # unverified without a reason
        await _as(ctx, CITE, id=uuid.uuid4(), verified=False, reason=None, **params)
    await _as(ctx, CITE, id=uuid.uuid4(), verified=False, reason="quote_not_found", **params)
    for change in ("UPDATE citations SET verified = false", "DELETE FROM citations"):
        with pytest.raises(DBAPIError, match=r"permission denied|insert-only"):
            await _as(ctx, change)


async def test_p03t04_only_a_person_relinks(migrated_db: MigratedDatabase) -> None:
    tenant = await Seeder(migrated_db.superuser_dsn).firm()
    person = uuid.uuid4()
    human = TenantContext(tenant, "human", str(person))
    original, successor = uuid.uuid4(), uuid.uuid4()
    params = {"t": tenant, "anchor": uuid.uuid4(), "source": uuid.uuid4(), "person": person}
    for cid in (original, successor):
        await _as(human, CITE, id=cid, verified=True, reason=None, **params)
    relinked = (
        "INSERT INTO citation_events (tenant_id, citation_id, kind, successor_citation_id, "
        "actor_kind, actor_user_id) VALUES (:t, :c, 'relinked', :s, :kind, :who)"
    )
    with pytest.raises(DBAPIError, match="check"):
        await _as(human, relinked, t=tenant, c=original, s=successor, kind="system", who=None)
    await _as(human, relinked, t=tenant, c=original, s=successor, kind="human", who=person)
    async with uow(human) as tx:
        state = (
            await tx.session.execute(
                text("SELECT state FROM citation_current WHERE id = :c"), {"c": original}
            )
        ).scalar_one()
        tx.record("citation.read", target=Target("citation", original))
    assert state == "relinked"
