"""Fixtures for the shared C3 Undo conformance suite (P-04-T13): a private migrated Postgres, the
app on it, fake sign-in tokens and a superuser seeder, as the security suite has them."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import httpx
import pytest

from abacus.api import create_app
from abacus.kernel.config import settings
from abacus.kernel.db import configure_engine, configure_relay_engine, dispose_engine
from abacus.kernel.flags import forget_flags
from abacus.modules.identity.api import configure_verifier, reset_verifier
from abacus_tools.fakes.identity import FakeIdentityProvider
from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import provisioned_database

from .support import Seeder


@pytest.fixture(scope="session")
def undo_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


@pytest.fixture
def seed(undo_db: sc.Database) -> Seeder:
    return Seeder(undo_db.superuser_dsn)


@pytest.fixture(autouse=True)
async def engines(undo_db: sc.Database, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", undo_db.identity_url)
    settings.cache_clear()
    forget_flags()
    await dispose_engine()
    configure_engine(undo_db.app_url)
    configure_relay_engine(undo_db.relay_url)
    yield
    await dispose_engine()
    settings.cache_clear()
    forget_flags()


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
