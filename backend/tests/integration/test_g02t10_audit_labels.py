"""G-02-T10 (TASK-1331; SPEC-349 AC-6, AC-11; DEC-436): the audit label index and search.

- The indexer is idempotent on replay: the same range written twice leaves the same rows.
- `q` finds events by people's labels, every word required, and "pell street iii" finds none.
- A seeded SSN, in a client's name and on its event, is never findable, in whole or in part, and
  no label row holds it (AC-11).
- The projection is the firm's own (RLS) and keeps up with new events when a search runs.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Final, cast

import httpx
import pytest

from abacus.api import create_app
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.audit_trail.api import backfill_labels, index_labels
from abacus.modules.identity.api import AuthContext, current_context

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

LIST: Final = "/v1/audit-events"
SSN: Final = "900-00-2208"
Call = Callable[..., Awaitable[httpx.Response]]


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


async def _admin(seed: Seeder, tenant: uuid.UUID, name: str) -> AuthContext:
    user = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
            "VALUES ('https://probe.test', $1, $2, $3) RETURNING id",
            uuid.uuid4().hex,
            f"{uuid.uuid4().hex}@example.test",
            name,
        ),
    )
    membership = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO memberships (tenant_id, user_id, firm_role, status, kind) "
            "VALUES ($1, $2, 'security_admin', 'active', 'staff') RETURNING id",
            tenant,
            user,
        ),
    )
    return AuthContext(
        TenantContext(tenant, "human", str(user)),
        user,
        membership,
        "security_admin",
        datetime.now(UTC) - timedelta(minutes=1),
    )


async def _record(
    ctx: TenantContext, action: str, target: Target, scope: Scope | None = None
) -> None:
    async with uow(ctx) as tx:
        tx.record(action, target=target, after=Ref(version=1), scope=scope)


@pytest.fixture
async def firm(seed: Seeder) -> tuple[uuid.UUID, AuthContext]:
    tenant = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'audit_log.explorer', 'true', 'g02t10', 'G-02-T10')",
        tenant,
    )
    felix = await _admin(seed, tenant, "Felix Andersen")
    entity = await seed.entity(tenant, SSN)  # client content is hostile (ADR-052)
    engagement = await seed.engagement(tenant, entity, felix.user_id)
    await _record(felix.tenant, "wall.created", Target("ethical_wall", uuid.uuid4()))
    await _record(
        felix.tenant,
        "engagement.updated",
        Target("engagement", engagement),
        Scope(engagement_id=engagement),
    )
    await _record(felix.tenant, "client_entity.updated", Target("client_entity", entity))
    return tenant, felix


def _as(ctx: AuthContext) -> Call:
    async def call(method: str, path: str, **kwargs: object) -> httpx.Response:
        app = create_app()
        app.dependency_overrides[current_context] = lambda: ctx
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, **kwargs)  # pyright: ignore[reportArgumentType] -- httpx's keyword arguments, passed through

    return call


async def _labels(seed: Seeder, tenant: uuid.UUID) -> list[tuple[object, ...]]:
    rows = await seed.rows(
        "SELECT seq, actor_label, target_label, keywords::text AS k, engagement_id "
        "FROM audit_event_labels WHERE tenant_id = $1 ORDER BY seq",
        tenant,
    )
    return [tuple(r.values()) for r in rows]


async def test_g02t10_the_indexer_is_idempotent_on_replay(
    firm: tuple[uuid.UUID, AuthContext], seed: Seeder
) -> None:
    tenant, _ = firm
    written, last = await index_labels(tenant)
    assert written == 3 and last is not None
    first = await _labels(seed, tenant)
    assert await index_labels(tenant) == (0, None)  # caught up
    assert await backfill_labels(tenant) == 3  # a replay from the start rewrites the same rows
    assert await _labels(seed, tenant) == first
    assert [r[1] for r in first] == ["Felix Andersen"] * 3


async def test_ac6_a_search_finds_by_label_and_pell_street_iii_finds_nothing(
    firm: tuple[uuid.UUID, AuthContext],
) -> None:
    _, felix = firm
    found = await _as(felix)("GET", LIST, params={"q": "felix andersen"})
    assert found.status_code == 200
    assert found.json()["total"] == 3
    by_action = await _as(felix)("GET", LIST, params={"q": "wall created"})
    assert [r["action"] for r in by_action.json()["items"]] == ["wall.created"]
    none = await _as(felix)("GET", LIST, params={"q": "pell street iii"})
    assert none.json()["items"] == [] and none.json()["total"] == 0


@pytest.mark.parametrize("q", [SSN, "2208", "900-00", "900 00 2208"])
async def test_ac11_a_seeded_ssn_is_never_findable(
    firm: tuple[uuid.UUID, AuthContext], seed: Seeder, q: str
) -> None:
    tenant, felix = firm
    response = await _as(felix)("GET", LIST, params={"q": q})
    assert response.status_code == 200
    assert response.json()["items"] == []
    for row in await _labels(seed, tenant):
        assert all("2208" not in str(part) for part in row)


async def test_g02t10_a_search_catches_the_index_up_with_new_events(
    firm: tuple[uuid.UUID, AuthContext], seed: Seeder
) -> None:
    tenant, felix = firm
    await index_labels(tenant)
    await _record(felix.tenant, "staff.unlocked", Target("user", felix.user_id))
    found = await _as(felix)("GET", LIST, params={"q": "unlocked"})
    assert [r["action"] for r in found.json()["items"]] == ["staff.unlocked"]
    other = await seed.firm()
    assert await index_labels(other) == (0, None)
    assert await _labels(seed, other) == []


async def test_m2_an_event_committed_late_below_the_indexed_seq_is_still_indexed(
    firm: tuple[uuid.UUID, AuthContext], seed: Seeder
) -> None:
    """`seq` commits out of order: an event whose lower `seq` commits after a higher one was
    indexed has no label row although `max(seq)` is past it. The next batch re-reads the settle
    window and indexes it (the missing row stands in for the late commit)."""
    tenant, _ = firm
    await index_labels(tenant)
    late = cast(
        int,
        await seed.value("SELECT min(seq) FROM audit_event_labels WHERE tenant_id = $1", tenant),
    )
    await seed.run(
        "DELETE FROM audit_event_labels WHERE tenant_id = $1 AND seq = $2", tenant, late
    )
    written, _ = await index_labels(tenant)
    assert written == 1
    assert [r[0] for r in await _labels(seed, tenant)].count(late) == 1
