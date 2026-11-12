"""P-02-T06 (TASK-7615; DEC-4612): the search index's store against a migrated database.

A rebuilt document upserts once (a second rebuild of the same state writes the same row: the
reindex is idempotent), a None builder deletes, a firm sees only its own rows, a deactivated
member's recents go, and offboarding leaves no row of the firm in either table."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from abacus.kernel.config import settings
from abacus.kernel.db import configure_engine, dispose_engine
from abacus.modules.platform.search import store
from abacus.modules.platform.search.spec import SearchIndexDocument, SearchProjection

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

NOW = datetime(2026, 9, 14, 14, 24, tzinfo=UTC)


async def _build(tenant: object, object_id: UUID) -> SearchIndexDocument | None:
    return None


PROJECTION = SearchProjection(
    object_type="client",
    group="clients",
    read_action="reference_set.read",
    scope_kind="client",
    build=_build,
    target="CLI-02",
)


def _doc(object_id: UUID, title: str) -> SearchIndexDocument:
    return SearchIndexDocument(
        object_id=object_id,
        title=title,
        source_updated_at=NOW,
        target_params={"clientId": str(object_id)},
        client_id=object_id,
        identifiers=("BH-CLI-0042",),
    )


@pytest.fixture(autouse=True)
async def wired(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()


_COUNTS = {
    "search_documents": "SELECT count(*) FROM search_documents WHERE tenant_id = $1",
    "search_recents": "SELECT count(*) FROM search_recents WHERE tenant_id = $1",
}


async def _count(seed: Seeder, tenant_id: UUID, table: str) -> int:
    return int(str(await seed.value(_COUNTS[table], tenant_id)))


async def test_upsert_is_idempotent_and_delete_removes(migrated_db: MigratedDatabase) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await seed.firm()
    object_id = uuid4()
    await store.upsert(tenant, PROJECTION, _doc(object_id, "Jonah & Claire Feld"))
    first = await store.stored_hash(tenant, PROJECTION, object_id)
    await store.upsert(tenant, PROJECTION, _doc(object_id, "Jonah & Claire Feld"))
    assert await store.stored_hash(tenant, PROJECTION, object_id) == first
    assert first == store.document_hash(PROJECTION, _doc(object_id, "Jonah & Claire Feld"))
    assert await _count(seed, tenant, "search_documents") == 1
    await store.upsert(tenant, PROJECTION, _doc(object_id, "Jonah and Claire Feld"))
    assert await store.stored_hash(tenant, PROJECTION, object_id) != first
    assert await store.delete(tenant, "client", object_id) is True
    assert await _count(seed, tenant, "search_documents") == 0


async def test_a_firm_sees_only_its_own_rows(migrated_db: MigratedDatabase) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    a, b = await seed.firm(), await seed.firm()
    await store.upsert(a, PROJECTION, _doc(uuid4(), "Granite Peak Outdoor Supply, Inc."))
    assert await store.count(a, "client") == 1
    assert await store.count(b, "client") == 0


async def test_recents_purge_and_offboarding_leave_nothing(migrated_db: MigratedDatabase) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await seed.firm()
    person = await seed.person(tenant)
    await store.upsert(tenant, PROJECTION, _doc(uuid4(), "Ridgeline Property Partners, LP"))
    await seed.run(
        "INSERT INTO search_recents (tenant_id, user_id, object_type, object_id) "
        "VALUES ($1, $2, 'client', $3)",
        tenant,
        person.user_id,
        uuid4(),
    )
    assert await store.purge_recents(tenant, [person.user_id]) == 1
    assert await _count(seed, tenant, "search_recents") == 0
    assert await store.purge_tenant(tenant) == 1
    assert await _count(seed, tenant, "search_documents") == 0
