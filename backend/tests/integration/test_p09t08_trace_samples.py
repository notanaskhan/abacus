"""P-09-T08 (TASK-7808): a run step's samples resolve through the owning modules, for the reader.

AC (step detail): `.../trace/steps/{step_id}?records=5` returns visible-filtered samples. Here,
against the database: the resolvers agents registers for engagements, request items and
documents answer only what the reader may see (`visible()`; an outsider gets nothing), with each
record's label and its route, and `samples_for` keeps the step's order.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, replace
from typing import cast

import pytest

from abacus.kernel.config import settings
from abacus.kernel.db import configure_engine, dispose_engine
from abacus.modules.agents import api as agents_api  # registers the resolvers
from abacus.modules.agents.trace import samples_for
from abacus.modules.identity.api import AuthContext

from .agent_tests.support import Person, Seeder
from .conftest import MigratedDatabase

assert agents_api  # imported for its registrations


@pytest.fixture(autouse=True)
async def wired(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@dataclass(frozen=True)
class World:
    partner: Person
    outsider: Person
    engagement: uuid.UUID
    item: uuid.UUID
    evidence_item: uuid.UUID
    version: uuid.UUID


@pytest.fixture
async def world(migrated_db: MigratedDatabase) -> World:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await seed.firm()
    partner, outsider = await seed.person(tenant), await seed.person(tenant)
    entity = await seed.entity(tenant, "Northwind Logistics")
    engagement = await seed.engagement(tenant, entity, partner.user_id)
    await seed.member(engagement, partner, "engagement_partner")
    item = await seed.item(tenant, engagement, partner.user_id)
    evidence_item = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO evidence_items (tenant_id, engagement_id, title, created_by_kind, "
            "created_by_id) VALUES ($1, $2, 'Bank statement March.pdf', 'human', 'seed') "
            "RETURNING id",
            tenant,
            engagement,
        ),
    )
    fingerprint = hashlib.sha256(b"Bank statement March").hexdigest()
    version = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO evidence_versions (tenant_id, engagement_id, evidence_item_id, "
            "version_no, fingerprint, storage_key, storage_version_id, size_bytes, media_type, "
            "source, method) VALUES ($1, $2, $3, 1, $4, $5, 'v1', 10, 'application/pdf', "
            "'client_upload', 'uploaded') RETURNING id",
            tenant,
            engagement,
            evidence_item,
            fingerprint,
            f"tenants/{tenant}/sha256/{fingerprint}",
        ),
    )
    return World(partner, outsider, engagement, item, evidence_item, version)


def _ctx(person: Person) -> AuthContext:
    return replace(person.context(), mfa_at=None)


def _raw(world: World) -> list[dict[str, str]]:
    return [
        {"record_type": "evidence_version", "id": str(world.version)},
        {"record_type": "request_item", "id": str(world.item)},
        {"record_type": "engagement", "id": str(world.engagement)},
        {"record_type": "evidence_item", "id": str(world.evidence_item)},
        {"record_type": "trial_balance_line", "id": str(uuid.uuid4())},  # no resolver: dropped
    ]


async def test_ac_the_reader_sees_each_sample_with_its_label_and_route(world: World) -> None:
    found = await samples_for(_ctx(world.partner), _raw(world), 5)
    by_type = {s.record_type: s for s in found}
    assert list(by_type) == ["evidence_version", "request_item", "engagement", "evidence_item"]
    viewer = f"/engagements/{world.engagement}?ov=viewer:{world.version}"
    assert by_type["evidence_version"].label == "Bank statement March.pdf"
    assert by_type["evidence_version"].open_route == viewer
    assert by_type["evidence_item"].open_route == viewer  # the newest version opens
    assert by_type["request_item"].label == "Trial balance"
    assert by_type["request_item"].open_route == (
        f"/engagements/{world.engagement}/items/{world.item}"
    )
    assert by_type["engagement"].open_route == f"/engagements/{world.engagement}"


async def test_an_outsider_gets_no_sample_at_all(world: World) -> None:
    assert await samples_for(_ctx(world.outsider), _raw(world), 5) == []


async def test_the_limit_and_a_stranger_id_are_honoured(world: World) -> None:
    raw = [{"record_type": "request_item", "id": str(uuid.uuid4())}, *_raw(world)]
    found = await samples_for(_ctx(world.partner), raw, 2)
    assert [s.record_type for s in found] == ["evidence_version"]  # the stranger id is dropped
