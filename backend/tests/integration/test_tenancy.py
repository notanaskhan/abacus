"""AC-5, AC-13: tenant isolation and insert-only tables, proven against a real Postgres.

Probe tables are created as `abacus_owner` and protected by the real migration helpers. The helpers
only call `op.execute(<str>)`, so a recording stub captures their SQL and the test executes it on a
real connection (no Alembic runtime or migration context needed). Row-level security is FORCEd, so
even seeding as the owner needs a tenant; seeding goes through `abacus_app` with a tenant set.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Protocol, cast

import pytest
from alembic.operations import Operations
from sqlalchemy import Column, MetaData, Table, Text, Uuid, delete, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.sql.elements import TextClause

from abacus.kernel.db import TenantContext, configure_engine, dispose_engine, tenant_session
from abacus.kernel.db.migration import insert_only, tenant_table


class Migrated(Protocol):
    owner_url: str
    app_url: str


METADATA = MetaData()
PROBE = Table(
    "tenancy_probe",
    METADATA,
    Column("id", Uuid(), primary_key=True),
    Column("tenant_id", Uuid(), nullable=False),
    Column("body", Text()),
)
LEDGER = Table(
    "tenancy_ledger_probe",
    METADATA,
    Column("id", Uuid(), primary_key=True),
    Column("tenant_id", Uuid(), nullable=False),
    Column("body", Text()),
)

SET_TENANT = text("SELECT set_config('app.tenant_id', :t, true)")
CURRENT_TENANT = text("SELECT current_setting('app.tenant_id', true)")
BACKEND_PID = text("SELECT pg_backend_pid()")


class RecordingOp:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def execute(self, sql: str) -> None:
        self.statements.append(sql)


def _ctx(tenant_id: uuid.UUID | None = None) -> TenantContext:
    return TenantContext(tenant_id=tenant_id or uuid.uuid4(), actor_kind="human", actor_id="u-1")


async def _run_helper(conn: AsyncConnection, table: str, *, ledger: bool) -> None:
    op = RecordingOp()
    tenant_table(cast(Operations, op), table)
    if ledger:
        insert_only(cast(Operations, op), table)
    for statement in op.statements:
        await conn.exec_driver_sql(statement)


@pytest.fixture(autouse=True)
async def engine_for_this_loop(migrated_db: Migrated) -> AsyncIterator[None]:
    """Each test runs in its own event loop; give it a process engine bound to that loop."""
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()


@pytest.fixture
async def owner_engine(migrated_db: Migrated) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(migrated_db.owner_url, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest.fixture
async def app_engine(migrated_db: Migrated) -> AsyncIterator[AsyncEngine]:
    """A raw `abacus_app` engine: no tenant is ever set unless a test sets it."""
    engine = create_async_engine(migrated_db.app_url, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest.fixture(autouse=True)
async def probe_tables(owner_engine: AsyncEngine) -> AsyncIterator[None]:
    async with owner_engine.begin() as conn:
        await conn.run_sync(METADATA.drop_all)
        await conn.run_sync(METADATA.create_all)
        await _run_helper(conn, "tenancy_probe", ledger=False)
        await _run_helper(conn, "tenancy_ledger_probe", ledger=True)
    yield
    async with owner_engine.begin() as conn:
        await conn.run_sync(METADATA.drop_all)


async def _seed(
    app_engine: AsyncEngine, table: Table, tenant_id: uuid.UUID, body: str
) -> uuid.UUID:
    row_id = uuid.uuid4()
    async with app_engine.begin() as conn:
        await conn.execute(SET_TENANT, {"t": str(tenant_id)})
        await conn.execute(table.insert().values(id=row_id, tenant_id=tenant_id, body=body))
    return row_id


async def _bodies_as(app_engine: AsyncEngine, table: Table, tenant_id: uuid.UUID) -> list[str]:
    async with app_engine.connect() as conn:
        await conn.execute(SET_TENANT, {"t": str(tenant_id)})
        return sorted((await conn.execute(select(table.c.body))).scalars().all())


# --- AC-5: isolation through tenant_session ----------------------------------------------------


async def test_ac5_tenant_session_sets_the_tenant_for_the_transaction() -> None:
    ctx = _ctx()
    async with tenant_session(ctx) as session:
        value = (await session.execute(CURRENT_TENANT)).scalar_one()
    assert value == str(ctx.tenant_id)


async def test_ac5_tenant_session_connects_as_abacus_app() -> None:
    async with tenant_session(_ctx()) as session:
        user = (await session.execute(text("SELECT current_user"))).scalar_one()
    assert user == "abacus_app"


async def test_ac5_select_returns_only_the_tenants_own_rows(app_engine: AsyncEngine) -> None:
    a, b = _ctx(), _ctx()
    await _seed(app_engine, PROBE, a.tenant_id, "a-row")
    await _seed(app_engine, PROBE, b.tenant_id, "b-row")
    async with tenant_session(a) as session:
        bodies = (await session.execute(select(PROBE.c.body))).scalars().all()
    assert list(bodies) == ["a-row"]


async def test_ac5_select_by_the_other_tenants_id_finds_nothing(app_engine: AsyncEngine) -> None:
    a, b = _ctx(), _ctx()
    b_id = await _seed(app_engine, PROBE, b.tenant_id, "b-row")
    async with tenant_session(a) as session:
        found = (await session.execute(select(PROBE).where(PROBE.c.id == b_id))).all()
    assert found == []


async def test_ac5_update_of_another_tenants_row_affects_zero_rows(
    app_engine: AsyncEngine,
) -> None:
    a, b = _ctx(), _ctx()
    b_id = await _seed(app_engine, PROBE, b.tenant_id, "b-row")
    async with tenant_session(a) as session:
        result = await session.execute(
            update(PROBE).where(PROBE.c.id == b_id).values(body="hacked").returning(PROBE.c.id)
        )
        assert result.all() == []
    assert await _bodies_as(app_engine, PROBE, b.tenant_id) == ["b-row"]


async def test_ac5_delete_of_another_tenants_row_affects_zero_rows(
    app_engine: AsyncEngine,
) -> None:
    a, b = _ctx(), _ctx()
    b_id = await _seed(app_engine, PROBE, b.tenant_id, "b-row")
    async with tenant_session(a) as session:
        result = await session.execute(
            delete(PROBE).where(PROBE.c.id == b_id).returning(PROBE.c.id)
        )
        assert result.all() == []
    assert await _bodies_as(app_engine, PROBE, b.tenant_id) == ["b-row"]


async def test_ac5_unfiltered_update_and_delete_touch_only_own_rows(
    app_engine: AsyncEngine,
) -> None:
    a, b = _ctx(), _ctx()
    await _seed(app_engine, PROBE, a.tenant_id, "a-row")
    await _seed(app_engine, PROBE, b.tenant_id, "b-row")
    async with tenant_session(a) as session:
        updated = await session.execute(update(PROBE).values(body="x").returning(PROBE.c.id))
        assert len(updated.all()) == 1
        deleted = await session.execute(delete(PROBE).returning(PROBE.c.id))
        assert len(deleted.all()) == 1
    assert await _bodies_as(app_engine, PROBE, b.tenant_id) == ["b-row"]


async def test_ac5_own_rows_can_be_updated_and_deleted() -> None:
    ctx = _ctx()
    row_id = uuid.uuid4()
    async with tenant_session(ctx) as session:
        await session.execute(PROBE.insert().values(id=row_id, tenant_id=ctx.tenant_id, body="1"))
        updated = await session.execute(
            update(PROBE).where(PROBE.c.id == row_id).values(body="2").returning(PROBE.c.body)
        )
        assert updated.scalars().all() == ["2"]
        deleted = await session.execute(
            delete(PROBE).where(PROBE.c.id == row_id).returning(PROBE.c.id)
        )
        assert deleted.scalars().all() == [row_id]


async def test_ac5_insert_with_another_tenants_id_is_rejected() -> None:
    a, b = _ctx(), _ctx()
    with pytest.raises(DBAPIError, match="row-level security"):
        async with tenant_session(a) as session:
            await session.execute(
                PROBE.insert().values(id=uuid.uuid4(), tenant_id=b.tenant_id, body="x")
            )


async def test_ac5_changes_made_in_tenant_session_are_rolled_back_on_exit(
    app_engine: AsyncEngine,
) -> None:
    ctx = _ctx()
    async with tenant_session(ctx) as session:
        await session.execute(
            PROBE.insert().values(id=uuid.uuid4(), tenant_id=ctx.tenant_id, body="ephemeral")
        )
        inside = (await session.execute(select(PROBE.c.body))).scalars().all()
        assert list(inside) == ["ephemeral"]
    assert await _bodies_as(app_engine, PROBE, ctx.tenant_id) == []


async def test_ac5_an_exception_inside_the_session_propagates() -> None:
    marker = RuntimeError("boom")
    with pytest.raises(RuntimeError) as raised:
        async with tenant_session(_ctx()):
            raise marker
    assert raised.value is marker


# --- AC-5: fail closed with no tenant ----------------------------------------------------------


async def test_ac5_without_a_tenant_select_returns_no_rows(app_engine: AsyncEngine) -> None:
    await _seed(app_engine, PROBE, uuid.uuid4(), "someone")
    async with app_engine.connect() as conn:
        assert (await conn.execute(select(PROBE))).all() == []


async def test_ac5_without_a_tenant_insert_fails(app_engine: AsyncEngine) -> None:
    async with app_engine.connect() as conn:
        with pytest.raises(DBAPIError, match="row-level security"):
            await conn.execute(PROBE.insert().values(id=uuid.uuid4(), tenant_id=uuid.uuid4()))


async def test_ac5_the_table_owner_is_subject_to_forced_rls(
    owner_engine: AsyncEngine, app_engine: AsyncEngine
) -> None:
    await _seed(app_engine, PROBE, uuid.uuid4(), "someone")
    async with owner_engine.connect() as conn:
        assert (await conn.execute(select(PROBE))).all() == []
    async with owner_engine.connect() as conn:
        with pytest.raises(DBAPIError, match="row-level security"):
            await conn.execute(PROBE.insert().values(id=uuid.uuid4(), tenant_id=uuid.uuid4()))


# --- AC-5: pooled connections do not leak the tenant -------------------------------------------


async def _session_pid_and_engine(ctx: TenantContext) -> tuple[int, AsyncEngine]:
    async with tenant_session(ctx) as session:
        conn = await session.connection()
        pid = (await session.execute(BACKEND_PID)).scalar_one()
        return pid, conn.engine


async def test_ac5_tenant_setting_does_not_survive_to_the_next_checkout() -> None:
    ctx = _ctx()
    pid, engine = await _session_pid_and_engine(ctx)
    async with engine.connect() as conn:
        assert (await conn.execute(BACKEND_PID)).scalar_one() == pid  # same pooled connection
        assert not (await conn.execute(CURRENT_TENANT)).scalar_one()


async def test_ac5_sequential_sessions_on_one_pooled_connection_never_see_each_other() -> None:
    first, second = _ctx(), _ctx()
    pid1, engine = await _session_pid_and_engine(first)
    async with tenant_session(second) as session:
        assert (await session.execute(BACKEND_PID)).scalar_one() == pid1
        assert (await session.execute(CURRENT_TENANT)).scalar_one() == str(second.tenant_id)
    async with engine.connect() as conn:
        assert not (await conn.execute(CURRENT_TENANT)).scalar_one()


async def test_ac5_setting_is_cleared_after_a_failed_session() -> None:
    ctx = _ctx()
    with pytest.raises(DBAPIError):
        async with tenant_session(ctx) as session:
            await session.execute(text("SELECT 1/0"))
    async with tenant_session(_ctx()) as session:
        conn = await session.connection()
        engine = conn.engine
    async with engine.connect() as raw:
        assert not (await raw.execute(CURRENT_TENANT)).scalar_one()


async def test_ac5_no_tenant_select_on_a_reused_pooled_connection_returns_no_rows(
    app_engine: AsyncEngine,
) -> None:
    """A used pooled connection may read the setting as '' not NULL; policies still fail closed."""
    await _seed(app_engine, PROBE, uuid.uuid4(), "someone")
    _, engine = await _session_pid_and_engine(_ctx())
    async with engine.connect() as conn:
        assert (await conn.execute(select(PROBE))).all() == []


async def test_ac5_no_tenant_insert_on_a_reused_pooled_connection_fails() -> None:
    _, engine = await _session_pid_and_engine(_ctx())
    async with engine.connect() as conn:
        with pytest.raises(DBAPIError):
            await conn.execute(PROBE.insert().values(id=uuid.uuid4(), tenant_id=uuid.uuid4()))


# --- AC-5: abacus_app cannot weaken the protection ---------------------------------------------


@pytest.mark.parametrize(
    "statement",
    [
        text("ALTER TABLE tenancy_probe DISABLE ROW LEVEL SECURITY"),
        text("ALTER TABLE tenancy_probe NO FORCE ROW LEVEL SECURITY"),
        text("DROP POLICY tenant_isolation ON tenancy_probe"),
        text("SET ROLE abacus_owner"),
        text("ALTER TABLE tenancy_probe OWNER TO abacus_app"),
        text("DROP TABLE tenancy_probe"),
    ],
    ids=[
        "disable-rls",
        "no-force",
        "drop-policy",
        "set-role-owner",
        "take-ownership",
        "drop-table",
    ],
)
async def test_ac5_abacus_app_cannot_weaken_row_level_security(
    app_engine: AsyncEngine, owner_engine: AsyncEngine, statement: TextClause
) -> None:
    async with app_engine.connect() as conn:
        with pytest.raises(DBAPIError, match=r"must be owner|permission denied"):
            await conn.execute(statement)
    async with owner_engine.connect() as conn:
        flags = (
            await conn.execute(
                text(
                    "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                    "WHERE relname = 'tenancy_probe'"
                )
            )
        ).one()
        policies = (
            (
                await conn.execute(
                    text("SELECT policyname FROM pg_policies WHERE tablename = 'tenancy_probe'")
                )
            )
            .scalars()
            .all()
        )
    assert tuple(flags) == (True, True)
    assert list(policies) == ["tenant_isolation"]


async def test_ac5_roles_are_unprivileged_and_app_owns_nothing(owner_engine: AsyncEngine) -> None:
    async with owner_engine.connect() as conn:
        roles = (
            await conn.execute(
                text(
                    "SELECT rolname, rolsuper, rolbypassrls, rolcreaterole, rolcreatedb, "
                    "rolcanlogin "
                    "FROM pg_roles WHERE rolname IN ('abacus_owner', 'abacus_app') ORDER BY 1"
                )
            )
        ).all()
        owned_by_app = (
            await conn.execute(
                text(
                    "SELECT c.relname FROM pg_class c JOIN pg_roles r ON r.oid = c.relowner "
                    "WHERE r.rolname = 'abacus_app'"
                )
            )
        ).all()
    assert [tuple(r) for r in roles] == [
        ("abacus_app", False, False, False, False, True),
        ("abacus_owner", False, False, False, False, True),
    ]
    assert owned_by_app == []


# --- AC-13 mechanism: insert-only tables -------------------------------------------------------


async def test_ac13_insert_and_select_work_on_an_insert_only_table() -> None:
    ctx = _ctx()
    async with tenant_session(ctx) as session:
        await session.execute(
            LEDGER.insert().values(id=uuid.uuid4(), tenant_id=ctx.tenant_id, body="entry")
        )
        bodies = (await session.execute(select(LEDGER.c.body))).scalars().all()
    assert list(bodies) == ["entry"]


async def test_ac13_update_on_an_insert_only_table_is_refused(app_engine: AsyncEngine) -> None:
    ctx = _ctx()
    await _seed(app_engine, LEDGER, ctx.tenant_id, "entry")
    with pytest.raises(DBAPIError, match="permission denied"):
        async with tenant_session(ctx) as session:
            await session.execute(update(LEDGER).values(body="changed"))
    assert await _bodies_as(app_engine, LEDGER, ctx.tenant_id) == ["entry"]


async def test_ac13_delete_on_an_insert_only_table_is_refused(app_engine: AsyncEngine) -> None:
    ctx = _ctx()
    await _seed(app_engine, LEDGER, ctx.tenant_id, "entry")
    with pytest.raises(DBAPIError, match="permission denied"):
        async with tenant_session(ctx) as session:
            await session.execute(delete(LEDGER))
    assert await _bodies_as(app_engine, LEDGER, ctx.tenant_id) == ["entry"]


async def test_ac13_update_and_delete_privileges_are_revoked_only_where_declared(
    owner_engine: AsyncEngine,
) -> None:
    async with owner_engine.connect() as conn:
        privileges = {
            (table, priv): (
                await conn.execute(
                    text("SELECT has_table_privilege('abacus_app', :t, :p)"),
                    {"t": table, "p": priv},
                )
            ).scalar_one()
            for table in ("tenancy_probe", "tenancy_ledger_probe")
            for priv in ("SELECT", "INSERT", "UPDATE", "DELETE")
        }
    assert privileges == {
        ("tenancy_probe", "SELECT"): True,
        ("tenancy_probe", "INSERT"): True,
        ("tenancy_probe", "UPDATE"): True,
        ("tenancy_probe", "DELETE"): True,
        ("tenancy_ledger_probe", "SELECT"): True,
        ("tenancy_ledger_probe", "INSERT"): True,
        ("tenancy_ledger_probe", "UPDATE"): False,
        ("tenancy_ledger_probe", "DELETE"): False,
    }
