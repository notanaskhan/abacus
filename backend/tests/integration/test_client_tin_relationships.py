"""P-07-T07 against Postgres (migration 0103; DEC-52): the app role writes relationships and ends
them but never deletes one, and a TIN is on file only as a whole sealed set. Statements run as the
app role through the unit of work, so the column grants are what production uses."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import cast

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.uow import Target, uow

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


async def _entities(seed: Seeder) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    tenant = await seed.firm()
    first = await seed.entity(tenant, "Feld Household")
    client = await seed.value("SELECT client_id FROM client_entities WHERE id = $1", first)
    second = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO client_entities (tenant_id, client_id, name) "
            "VALUES ($1, $2, 'Feld Family Trust') RETURNING id",
            tenant,
            client,
        ),
    )
    return tenant, first, second


async def _as_app(tenant: uuid.UUID, statement: str, **params: object) -> None:
    async with uow(TenantContext(tenant, "human", str(uuid.uuid4()))) as tx:
        await tx.session.execute(text(statement), params)
        tx.record("relationship.created", target=Target("client_entity", tenant))


_ADD = (
    "INSERT INTO entity_relationships (tenant_id, from_entity_id, to_entity_id, kind, "
    "effective_from, created_by) VALUES (:t, :a, :b, 'trustee_of', DATE '2026-01-01', :by)"
)


async def test_p07t07_the_app_adds_and_ends_a_relationship_but_never_deletes_one(
    migrated_db: MigratedDatabase,
) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant, first, second = await _entities(seed)
    await _as_app(tenant, _ADD, t=tenant, a=first, b=second, by=uuid.uuid4())
    await _as_app(
        tenant,
        "UPDATE entity_relationships SET effective_to = DATE '2026-12-31' WHERE tenant_id = :t",
        t=tenant,
    )
    with pytest.raises(DBAPIError, match="permission denied"):
        await _as_app(tenant, "UPDATE entity_relationships SET kind = 'spouse'")
    with pytest.raises(DBAPIError, match="permission denied"):
        await _as_app(tenant, "DELETE FROM entity_relationships")
    with pytest.raises(DBAPIError, match="check"):  # an entity can't relate to itself
        await _as_app(tenant, _ADD, t=tenant, a=first, b=first, by=uuid.uuid4())


async def test_p07t07_a_tin_is_on_file_only_as_a_whole_sealed_set(
    migrated_db: MigratedDatabase,
) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant, first, second = await _entities(seed)
    whole = (
        "UPDATE client_entities SET tin_sealed = :sealed, tin_last4 = '1234', tin_kind = 'ein', "
        "tin_status = 'on_file', tin_fingerprint = :fp WHERE id = :id"
    )
    fingerprint = b"\x01" * 32
    await _as_app(tenant, whole, sealed=b"envelope", fp=fingerprint, id=first)
    with pytest.raises(DBAPIError, match="client_entities_tin_whole"):
        await _as_app(
            tenant, "UPDATE client_entities SET tin_last4 = NULL WHERE id = :id", id=first
        )
    with pytest.raises(DBAPIError, match="client_entities_one_tin"):  # once per firm
        await _as_app(tenant, whole, sealed=b"envelope", fp=fingerprint, id=second)
