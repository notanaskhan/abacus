"""Fixtures for the security suite: a throwaway migrated Postgres (a testcontainer, as the
integration suite's), the app on that database, and fake sign-in tokens."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import httpx
import pytest

from abacus.api import create_app
from abacus.kernel.config import settings
from abacus.kernel.db import (
    configure_engine,
    configure_identity_engine,
    configure_relay_engine,
    dispose_engine,
)
from abacus.modules.identity.api import configure_verifier, reset_verifier
from abacus_tools.fakes.identity import FakeIdentityProvider
from abacus_tools.quality.schema_check import provisioned_database

from .support import Env, Migrated, Net, Seeder


@pytest.fixture(scope="session")
def migrated_db() -> Iterator[Migrated]:
    """Fresh Postgres in a container, migrated to head (the same path as `schema_check`)."""
    with provisioned_database() as database:
        configure_engine(database.app_url)
        configure_relay_engine(database.relay_url)
        configure_identity_engine(database.identity_url)
        yield database


@pytest.fixture
def seed(migrated_db: Migrated) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


@pytest.fixture(autouse=True)
async def engines(migrated_db: Migrated, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    """Each test has its own event loop: rebuild the engines for it, from the test database."""
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    configure_relay_engine(migrated_db.relay_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
def idp() -> Iterator[FakeIdentityProvider]:
    provider = FakeIdentityProvider()
    configure_verifier(provider.verifier())
    yield provider
    reset_verifier()


@pytest.fixture
async def http(idp: FakeIdentityProvider) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app(), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def net(seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider) -> Net:
    return Net(seed, http, idp)


@pytest.fixture
async def env(net: Net, seed: Seeder) -> Env:
    tenant_id = await seed.firm()
    admin = await seed.person(tenant_id, "firm_admin")
    a = await seed.site(tenant_id, admin.user_id, "walled")
    b = await seed.site(tenant_id, admin.user_id, "other")
    for site in (a, b):  # past due, for the overdue counts
        await seed.run(
            "UPDATE request_items SET due_on = '2020-01-01' WHERE id = $1", site.item_id
        )
    return Env(net, tenant_id, admin, a, b)
