"""G-02-T06 security review H1, M1, L3 (migration 0172; Q-02 R7; P-43): the hash chain's leaf
version 2.

- A checkpoint sealed at version 1 on the schema before 0172 still verifies after 0172, and a
  version 2 checkpoint chains from it: the mixed chain verifies and anchors end to end.
- Changing `ip`, `session_id` or `client_id` on a version 2 sealed event breaks verification.
- `ip` has one canonical text, whatever form the address arrives in.
- Downgrading 0172 is refused once an event carries request context or a checkpoint is sealed at
  version 2.
"""

from __future__ import annotations

import asyncio
import re
import uuid
from collections.abc import AsyncIterator, Iterator
from ipaddress import IPv4Address, IPv4Interface
from typing import Final

import pytest
from sqlalchemy.exc import DBAPIError

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.request_context import RequestContext, bound
from abacus.kernel.uow import Target, uow
from abacus.kernel.uow.chain import (
    LEAF_V2_COLUMNS,
    chain_hash,
    leaf,
    merkle_root,
    seal_checkpoint,
    verify_anchor,
    verify_chain,
)
from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase


def _parent_of_0172() -> str:
    """0172's `down_revision`, read from the migration, so the test holds wherever the chain puts
    0172 (it follows 0160 on its branch and 0171 once the S9 batch merges)."""
    from pathlib import Path

    [script] = Path(__file__).resolve().parents[2].glob("migrations/versions/0172_*.py")
    found = re.search(r'^down_revision = "(\d{4})"$', script.read_text(), flags=re.M)
    assert found is not None
    return found.group(1)


PARENT_0172 = _parent_of_0172()

IP: Final = "198.51.100.57"


async def _person_event(tenant: uuid.UUID, user: uuid.UUID, session: uuid.UUID) -> None:
    context = RequestContext(
        ip=IP, user_agent_family="Chrome", device_label="Chrome · macOS", session_id=session
    )
    with bound(context):
        async with uow(TenantContext(tenant, "human", str(user))) as tx:
            tx.record("chain_probe.recorded", target=Target("chain_probe", uuid.uuid4()))


async def _forge(
    seed: Seeder, tenant: uuid.UUID, actor: tuple[str, str], sql: str, *args: object
) -> None:
    """A forger with database access: triggers off, acting as the row's own actor (Q-02-T27)."""
    await seed.run("ALTER TABLE audit_events DISABLE TRIGGER USER")
    try:
        await seed.as_actor(tenant, actor, sql, tenant, *args)
    finally:
        await seed.run("ALTER TABLE audit_events ENABLE TRIGGER USER")


# --- on the session database, at head ----------------------------------------------------------


@pytest.fixture
async def engines(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


_FORGE: Final = {
    "ip": "UPDATE audit_events SET ip = CAST($2 AS inet) WHERE tenant_id = $1 AND seq = $3",
    "session_id": "UPDATE audit_events SET session_id = CAST($2 AS uuid) "
    "WHERE tenant_id = $1 AND seq = $3",
    "client_id": "UPDATE audit_events SET client_id = CAST($2 AS uuid) "
    "WHERE tenant_id = $1 AND seq = $3",
}


@pytest.mark.parametrize(
    ("column", "forged"),
    [
        ("ip", "203.0.113.9"),
        ("session_id", "6f1d3c8e-2a4b-4c5d-9e7f-0a1b2c3d4e5f"),
        ("client_id", "0b9a8c7d-6e5f-4a3b-8c2d-1e0f9a8b7c6d"),
    ],
)
async def test_h1_changing_a_v2_column_on_a_sealed_event_breaks_verification(
    engines: None, migrated_db: MigratedDatabase, column: str, forged: str
) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await seed.firm()
    person = await seed.person(tenant)
    for _ in range(3):
        await _person_event(tenant, person.user_id, uuid.uuid4())
    sealed = await seal_checkpoint(tenant, settle_seconds=0)
    assert sealed is not None and sealed.leaf_version == 2
    assert await verify_chain(tenant) == []
    actor = ("human", str(person.user_id))  # the row's own actor, as the CHECKs require
    await _forge(seed, tenant, actor, _FORGE[column], forged, sealed.seq_from)
    assert await verify_chain(tenant) == [sealed.checkpoint_no]


def test_l3_an_address_has_one_canonical_text() -> None:
    row: dict[str, object] = {column: None for column in LEAF_V2_COLUMNS}
    forms = (IP, IPv4Address(IP), IPv4Interface(f"{IP}/32"))
    assert len({leaf({**row, "ip": form}, 2) for form in forms}) == 1
    assert leaf({**row, "ip": IP}, 2) != leaf({**row, "ip": "198.51.100.58"}, 2)
    # Version 1 never reads the new columns.
    assert leaf({**row, "ip": IP}, 1) == leaf(row, 1)


# --- on a private database: before 0172, then after ---------------------------------------------


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


_V1_SELECT: Final = (
    "SELECT id, tenant_id, seq, occurred_at, effective_at, actor_kind, actor_id, action, "
    "target_type, target_id, before_ref, after_ref, trace_id, engagement_id, work_item_id, "
    "on_behalf_of_user_id, policy_ref FROM audit_events WHERE tenant_id = $1 ORDER BY seq"
)


async def _seal_v1_by_hand(seed: Seeder, tenant: uuid.UUID) -> bytes:
    """Checkpoint 1 as the pre-0172 sealer wrote it: leaf version 1 over the old columns."""
    rows = [dict(r) for r in await seed.rows(_V1_SELECT, tenant)]
    root = merkle_root([leaf(r, 1) for r in rows])
    lo, hi = int(rows[0]["seq"]), int(rows[-1]["seq"])
    chained = chain_hash(None, root, lo, hi, len(rows))
    await seed.run(
        "INSERT INTO audit_checkpoints (tenant_id, checkpoint_no, seq_from, seq_to, event_count, "
        "leaf_version, merkle_root, prev_chain_hash, chain_hash) "
        "VALUES ($1, 1, $2, $3, $4, 1, $5, NULL, $6)",
        tenant,
        lo,
        hi,
        len(rows),
        root,
        chained,
    )
    return chained


def test_h1_m1_a_v1_chain_survives_0172_grows_to_v2_and_pins_the_downgrade(
    private_db: sc.Database,
) -> None:
    seed = Seeder(private_db.superuser_dsn)
    migrate(private_db.owner_url, PARENT_0172, down=True)

    async def before() -> uuid.UUID:
        tenant = await seed.firm()
        for _ in range(3):
            await seed.as_actor(
                tenant,
                ("system", "chain-probe"),
                "INSERT INTO audit_events (tenant_id, actor_kind, actor_id, action, target_type, "
                "target_id) VALUES ($1, 'system', 'chain-probe', 'chain_probe.recorded', "
                "'chain_probe', $2)",
                tenant,
                str(uuid.uuid4()),
            )
        await _seal_v1_by_hand(seed, tenant)
        return tenant

    tenant = asyncio.run(before())
    migrate(private_db.owner_url, "head")

    async def after_upgrade() -> uuid.UUID:
        configure_engine(private_db.app_url)
        try:
            assert await verify_chain(tenant) == []  # (a) v1 verifies after 0172
            person = await seed.person(tenant)
            await _person_event(tenant, person.user_id, uuid.uuid4())
            return person.user_id
        finally:
            await dispose_engine()

    asyncio.run(after_upgrade())
    # M1: an event carries request context, so the downgrade refuses and changes nothing.
    with pytest.raises(DBAPIError, match="request context"):
        migrate(private_db.owner_url, PARENT_0172, down=True)

    async def mixed_chain() -> None:
        configure_engine(private_db.app_url)
        try:
            second = await seal_checkpoint(tenant, settle_seconds=0)
            assert second is not None and second.leaf_version == 2
            assert second.checkpoint_no == 2
            assert await verify_chain(tenant) == []  # (c) v1 then v2, end to end
            assert await verify_anchor(tenant, 2, second.chain_hash)
            assert not await verify_anchor(tenant, 2, bytes(32))
        finally:
            await dispose_engine()

    asyncio.run(mixed_chain())
    with pytest.raises(DBAPIError, match="leaf version 2"):
        migrate(private_db.owner_url, PARENT_0172, down=True)
    versions = asyncio.run(
        seed.rows(
            "SELECT leaf_version FROM audit_checkpoints WHERE tenant_id = $1 "
            "ORDER BY checkpoint_no",
            tenant,
        )
    )
    assert [v["leaf_version"] for v in versions] == [1, 2]
