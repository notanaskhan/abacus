"""AC-4 to AC-8 support: migration 0005 (TASK-008 contract, "Database").

Foreign keys, CHECKs and grants of `clients`, `client_entities`, `engagements`, `request_lists`
and `request_items`. Setup rows are written as the superuser (it bypasses row-level security);
the grant and row-level-security checks run as `abacus_app` through `tenant_session`.
"""

from __future__ import annotations

import datetime
import uuid
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from typing import Protocol, cast

import asyncpg
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine, tenant_session
from abacus_tools.fakes.identity import ISSUER

TABLES = ["clients", "client_entities", "engagements", "request_lists", "request_items"]


class Migrated(Protocol):
    app_url: str
    identity_url: str
    superuser_dsn: str


@pytest.fixture(autouse=True)
async def engines(migrated_db: Migrated, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


# --- setup as the superuser ----------------------------------------------------------------------


@dataclass(frozen=True)
class Db:
    dsn: str

    async def run(self, sql: str, *args: object) -> None:
        conn = await asyncpg.connect(self.dsn)
        try:
            await conn.execute(sql, *args)
        finally:
            await conn.close()

    async def value(self, sql: str, *args: object) -> object:
        conn = await asyncpg.connect(self.dsn)
        try:
            return await conn.fetchval(sql, *args)
        finally:
            await conn.close()

    async def firm(self) -> uuid.UUID:
        tenant_id = uuid.uuid4()
        await self.run("INSERT INTO firms (tenant_id, name) VALUES ($1, 'F')", tenant_id)
        return tenant_id

    async def user(self, tenant_id: uuid.UUID | None) -> uuid.UUID:
        """A user; a firm member when `tenant_id` is given."""
        subject = f"sub-{uuid.uuid4().hex}"
        user_id = cast(
            uuid.UUID,
            await self.value(
                "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
                "VALUES ($1, $2, $3, 'U') RETURNING id",
                ISSUER,
                subject,
                f"{subject}@example.test",
            ),
        )
        if tenant_id is not None:
            await self.run(
                "INSERT INTO memberships (tenant_id, user_id, firm_role, status) "
                "VALUES ($1, $2, NULL, 'active')",
                tenant_id,
                user_id,
            )
        return user_id

    async def client(self, tenant_id: uuid.UUID) -> uuid.UUID:
        return cast(
            uuid.UUID,
            await self.value(
                "INSERT INTO clients (tenant_id, name) VALUES ($1, 'C') RETURNING id", tenant_id
            ),
        )

    async def entity(self, tenant_id: uuid.UUID, client_id: uuid.UUID) -> uuid.UUID:
        return cast(
            uuid.UUID,
            await self.value(
                "INSERT INTO client_entities (tenant_id, client_id, name) "
                "VALUES ($1, $2, 'E') RETURNING id",
                tenant_id,
                client_id,
            ),
        )

    async def engagement(self, firm: Firm) -> uuid.UUID:
        return cast(
            uuid.UUID,
            await self.value(
                "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
                "fiscal_period_start, fiscal_period_end, created_by) "
                "VALUES ($1, $2, $3, 'N', '2025-01-01', '2025-12-31', $4) RETURNING id",
                firm.tenant_id,
                firm.client_id,
                firm.entity_id,
                firm.user_id,
            ),
        )

    async def request_list(self, tenant_id: uuid.UUID, engagement_id: uuid.UUID) -> uuid.UUID:
        return cast(
            uuid.UUID,
            await self.value(
                "INSERT INTO request_lists (tenant_id, engagement_id) VALUES ($1, $2) "
                "RETURNING id",
                tenant_id,
                engagement_id,
            ),
        )


@dataclass(frozen=True)
class Firm:
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    client_id: uuid.UUID
    entity_id: uuid.UUID

    @property
    def ctx(self) -> TenantContext:
        return TenantContext(self.tenant_id, "human", str(self.user_id))


@pytest.fixture
def db(migrated_db: Migrated) -> Db:
    return Db(migrated_db.superuser_dsn)


async def _firm(db: Db) -> Firm:
    tenant_id = await db.firm()
    user_id = await db.user(tenant_id)
    client_id = await db.client(tenant_id)
    return Firm(tenant_id, user_id, client_id, await db.entity(tenant_id, client_id))


@pytest.fixture
async def firm(db: Db) -> Firm:
    return await _firm(db)


ENGAGEMENT_SQL = (
    "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, fiscal_period_start, "
    "fiscal_period_end, created_by) VALUES (:t, :c, :e, 'N', :s, :f, :u)"
)
ITEM_SQL = (
    "INSERT INTO request_items (tenant_id, engagement_id, request_list_id, description, "
    "audit_area, created_by) VALUES (:t, :g, :l, :d, :a, :u)"
)


async def _as_superuser_fails(db: Db, sql: str, *args: object) -> str:
    with pytest.raises(asyncpg.PostgresError) as caught:
        await db.run(sql, *args)
    return str(caught.value).lower()


async def _as_app(
    ctx: TenantContext, sql: str, params: Mapping[str, object] | None = None
) -> None:
    async with tenant_session(ctx) as session:
        await session.execute(text(sql), params or {})


async def _app_error(
    ctx: TenantContext, sql: str, params: Mapping[str, object] | None = None
) -> str:
    with pytest.raises(DBAPIError) as caught:
        await _as_app(ctx, sql, params)
    return str(caught.value).lower()


def _engagement_params(firm: Firm, **overrides: object) -> dict[str, object]:
    params: dict[str, object] = {
        "t": firm.tenant_id,
        "c": firm.client_id,
        "e": firm.entity_id,
        "s": datetime.date(2025, 1, 1),
        "f": datetime.date(2025, 12, 31),
        "u": firm.user_id,
    }
    params.update(overrides)
    return params


# --- the tables exist with forced row-level security ---------------------------------------------


@pytest.mark.parametrize("table", TABLES)
async def test_ac20_the_new_tenant_tables_have_forced_row_level_security(
    db: Db, table: str
) -> None:
    flags = await db.value(
        "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class "
        "WHERE relname = $1 AND relkind = 'r'",
        table,
    )
    assert flags is True


@pytest.mark.parametrize("table", TABLES)
async def test_ac20_the_new_tables_have_a_not_null_tenant_id(db: Db, table: str) -> None:
    nullable = await db.value(
        "SELECT NOT attnotnull FROM pg_attribute "
        "WHERE attrelid = $1::regclass AND attname = 'tenant_id'",
        table,
    )
    assert nullable is False


async def test_ac20_the_app_cannot_insert_a_row_for_another_tenant(firm: Firm, db: Db) -> None:
    other = await _firm(db)
    message = await _app_error(
        firm.ctx,
        "INSERT INTO clients (tenant_id, name) VALUES (:t, 'X')",
        {"t": other.tenant_id},
    )
    assert "row-level security" in message


async def test_ac20_the_app_can_insert_its_own_rows(firm: Firm) -> None:
    async with tenant_session(firm.ctx) as session:
        await session.execute(
            text("INSERT INTO clients (tenant_id, name) VALUES (:t, 'Mine')"),
            {"t": firm.tenant_id},
        )
        names = (await session.execute(text("SELECT name FROM clients"))).scalars().all()
    assert "Mine" in names


# --- foreign keys keep rows within one firm and consistent ---------------------------------------


async def test_ac20_an_entity_of_another_client_is_a_foreign_key_error(db: Db, firm: Firm) -> None:
    second_client = await db.client(firm.tenant_id)
    message = await _app_error(
        firm.ctx,
        ENGAGEMENT_SQL,
        _engagement_params(firm, c=second_client),
    )
    assert "foreign key" in message


async def test_ac20_an_entity_of_another_firms_client_is_a_foreign_key_error(
    db: Db, firm: Firm
) -> None:
    other = await _firm(db)
    message = await _as_superuser_fails(
        db,
        "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, 'E')",
        firm.tenant_id,
        other.client_id,
    )
    assert "foreign key" in message


async def test_ac20_an_engagement_pointing_into_another_firm_is_a_foreign_key_error(
    db: Db, firm: Firm
) -> None:
    other = await _firm(db)
    message = await _as_superuser_fails(
        db,
        "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
        "fiscal_period_start, fiscal_period_end, created_by) "
        "VALUES ($1, $2, $3, 'N', '2025-01-01', '2025-12-31', $4)",
        firm.tenant_id,
        other.client_id,
        other.entity_id,
        firm.user_id,
    )
    assert "foreign key" in message


async def test_ac20_a_matching_client_and_entity_is_accepted(db: Db, firm: Firm) -> None:
    await _as_app(firm.ctx, ENGAGEMENT_SQL, _engagement_params(firm))


async def test_ac20_an_engagement_creator_who_is_not_a_firm_member_is_a_foreign_key_error(
    db: Db, firm: Firm
) -> None:
    stranger = await db.user(None)
    message = await _app_error(firm.ctx, ENGAGEMENT_SQL, _engagement_params(firm, u=stranger))
    assert "foreign key" in message


async def test_ac20_an_engagement_creator_who_belongs_to_another_firm_is_a_foreign_key_error(
    db: Db, firm: Firm
) -> None:
    other = await _firm(db)
    message = await _app_error(firm.ctx, ENGAGEMENT_SQL, _engagement_params(firm, u=other.user_id))
    assert "foreign key" in message


async def test_ac20_a_request_item_whose_list_belongs_to_another_engagement_is_a_foreign_key_error(
    db: Db, firm: Firm
) -> None:
    first, second = await db.engagement(firm), await db.engagement(firm)
    list_of_first = await db.request_list(firm.tenant_id, first)
    message = await _app_error(
        firm.ctx,
        ITEM_SQL,
        {
            "t": firm.tenant_id,
            "g": second,
            "l": list_of_first,
            "d": "d",
            "a": "a",
            "u": firm.user_id,
        },
    )
    assert "foreign key" in message


async def test_ac20_a_request_item_in_its_own_engagements_list_is_accepted(
    db: Db, firm: Firm
) -> None:
    engagement = await db.engagement(firm)
    request_list = await db.request_list(firm.tenant_id, engagement)
    await _as_app(
        firm.ctx,
        ITEM_SQL,
        {
            "t": firm.tenant_id,
            "g": engagement,
            "l": request_list,
            "d": "d",
            "a": "a",
            "u": firm.user_id,
        },
    )


async def test_ac20_a_request_item_creator_who_is_not_a_firm_member_is_a_foreign_key_error(
    db: Db, firm: Firm
) -> None:
    engagement = await db.engagement(firm)
    request_list = await db.request_list(firm.tenant_id, engagement)
    stranger = await db.user(None)
    message = await _app_error(
        firm.ctx,
        ITEM_SQL,
        {
            "t": firm.tenant_id,
            "g": engagement,
            "l": request_list,
            "d": "d",
            "a": "a",
            "u": stranger,
        },
    )
    assert "foreign key" in message


async def test_ac20_a_request_list_for_a_missing_engagement_is_a_foreign_key_error(
    firm: Firm,
) -> None:
    message = await _app_error(
        firm.ctx,
        "INSERT INTO request_lists (tenant_id, engagement_id) VALUES (:t, :g)",
        {"t": firm.tenant_id, "g": uuid.uuid4()},
    )
    assert "foreign key" in message


async def test_ac20_an_engagement_member_of_a_missing_engagement_is_a_foreign_key_error(
    firm: Firm,
) -> None:
    message = await _app_error(
        firm.ctx,
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES (:t, :g, :u, 'staff')",
        {"t": firm.tenant_id, "g": uuid.uuid4(), "u": firm.user_id},
    )
    assert "foreign key" in message


async def test_ac20_an_engagement_member_of_another_firms_engagement_is_a_foreign_key_error(
    db: Db, firm: Firm
) -> None:
    other = await _firm(db)
    theirs = await db.engagement(other)
    message = await _as_superuser_fails(
        db,
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES ($1, $2, $3, 'staff')",
        firm.tenant_id,
        theirs,
        firm.user_id,
    )
    assert "foreign key" in message


async def test_ac20_an_engagement_member_of_an_existing_engagement_is_accepted(
    db: Db, firm: Firm
) -> None:
    engagement = await db.engagement(firm)
    await _as_app(
        firm.ctx,
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES (:t, :g, :u, 'engagement_partner')",
        {"t": firm.tenant_id, "g": engagement, "u": firm.user_id},
    )


async def test_ac20_a_second_request_list_for_an_engagement_is_a_unique_violation(
    db: Db, firm: Firm
) -> None:
    engagement = await db.engagement(firm)
    await db.request_list(firm.tenant_id, engagement)
    message = await _app_error(
        firm.ctx,
        "INSERT INTO request_lists (tenant_id, engagement_id) VALUES (:t, :g)",
        {"t": firm.tenant_id, "g": engagement},
    )
    assert "unique" in message or "duplicate" in message


# --- CHECK constraints ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("start", "end"),
    [("2025-12-31", "2025-01-01"), ("2025-06-30", "2025-06-30")],
)
async def test_ac20_fiscal_period_end_must_be_after_start(
    db: Db, firm: Firm, start: str, end: str
) -> None:
    message = await _app_error(
        firm.ctx,
        ENGAGEMENT_SQL,
        _engagement_params(
            firm, s=datetime.date.fromisoformat(start), f=datetime.date.fromisoformat(end)
        ),
    )
    assert "check constraint" in message


async def test_ac20_one_day_of_fiscal_period_is_accepted(firm: Firm) -> None:
    await _as_app(
        firm.ctx,
        ENGAGEMENT_SQL,
        _engagement_params(firm, s=datetime.date(2025, 1, 1), f=datetime.date(2025, 1, 2)),
    )


SUPERUSER_ENGAGEMENT = (
    "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, fiscal_period_start, "
    "fiscal_period_end, created_by, status, type) "
    "VALUES ($1, $2, $3, 'N', '2025-01-01', '2025-12-31', $4, $5, $6)"
)


@pytest.mark.parametrize(("status", "kind"), [("paused", "audit"), ("active", "review")])
async def test_ac20_engagement_status_and_type_outside_the_allowed_values_are_check_errors(
    db: Db, firm: Firm, status: str, kind: str
) -> None:
    message = await _as_superuser_fails(
        db, SUPERUSER_ENGAGEMENT, firm.tenant_id, firm.client_id, firm.entity_id, firm.user_id,
        status, kind,
    )  # fmt: skip
    assert "check constraint" in message


@pytest.mark.parametrize("status", ["active", "archived"])
async def test_ac20_engagement_statuses_active_and_archived_are_accepted(
    db: Db, firm: Firm, status: str
) -> None:
    await db.run(
        SUPERUSER_ENGAGEMENT,
        firm.tenant_id,
        firm.client_id,
        firm.entity_id,
        firm.user_id,
        status,
        "audit",
    )


async def test_ac20_an_engagement_status_and_type_default_to_active_and_audit(
    db: Db, firm: Firm
) -> None:
    engagement = await db.engagement(firm)
    row = await db.value("SELECT status || '/' || type FROM engagements WHERE id = $1", engagement)
    assert row == "active/audit"


@pytest.mark.parametrize("name", ["", "x" * 201])
async def test_ac20_client_entity_and_engagement_names_are_1_to_200_characters(
    db: Db, firm: Firm, name: str
) -> None:
    for sql, args in (
        ("INSERT INTO clients (tenant_id, name) VALUES ($1, $2)", (firm.tenant_id, name)),
        (
            "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, $3)",
            (firm.tenant_id, firm.client_id, name),
        ),
        (
            "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
            "fiscal_period_start, fiscal_period_end, created_by) "
            "VALUES ($1, $2, $3, $4, '2025-01-01', '2025-12-31', $5)",
            (firm.tenant_id, firm.client_id, firm.entity_id, name, firm.user_id),
        ),
    ):
        assert "check constraint" in await _as_superuser_fails(db, sql, *args)


@pytest.mark.parametrize("name", ["x", "x" * 200])
async def test_ac20_names_at_the_limits_are_accepted(db: Db, firm: Firm, name: str) -> None:
    await db.run("INSERT INTO clients (tenant_id, name) VALUES ($1, $2)", firm.tenant_id, name)


async def _item_params(db: Db, firm: Firm, **overrides: object) -> dict[str, object]:
    engagement = await db.engagement(firm)
    params: dict[str, object] = {
        "t": firm.tenant_id,
        "g": engagement,
        "l": await db.request_list(firm.tenant_id, engagement),
        "d": "d",
        "a": "a",
        "u": firm.user_id,
    }
    params.update(overrides)
    return params


@pytest.mark.parametrize(
    "overrides",
    [
        {"d": ""},
        {"d": "x" * 2001},
        {"a": ""},
        {"a": "x" * 101},
    ],
)
async def test_ac20_request_item_checks_reject_bad_values(
    db: Db, firm: Firm, overrides: dict[str, object]
) -> None:
    params = await _item_params(db, firm, **overrides)
    assert "check constraint" in await _app_error(firm.ctx, ITEM_SQL, params)


@pytest.mark.parametrize(
    "overrides",
    [{"d": "x"}, {"d": "x" * 2000}, {"a": "x"}, {"a": "x" * 100}],
)
async def test_ac20_request_item_checks_accept_the_limits(
    db: Db, firm: Firm, overrides: dict[str, object]
) -> None:
    await _as_app(firm.ctx, ITEM_SQL, await _item_params(db, firm, **overrides))


ITEM_WITH_STATUS = (
    "INSERT INTO request_items (tenant_id, engagement_id, request_list_id, description, "
    "audit_area, created_by, status) VALUES ($1, $2, $3, 'd', 'a', $4, $5)"
)


@pytest.mark.parametrize("status", ["open", "received", "ready_for_review", "needs_revision"])
async def test_ac20_every_request_item_status_is_accepted(db: Db, firm: Firm, status: str) -> None:
    p = await _item_params(db, firm)
    await db.run(ITEM_WITH_STATUS, p["t"], p["g"], p["l"], p["u"], status)


@pytest.mark.parametrize("status", ["done", "closed", ""])
async def test_ac20_a_request_item_status_outside_the_allowed_values_is_a_check_error(
    db: Db, firm: Firm, status: str
) -> None:
    p = await _item_params(db, firm)
    message = await _as_superuser_fails(
        db, ITEM_WITH_STATUS, p["t"], p["g"], p["l"], p["u"], status
    )
    assert "check constraint" in message


async def test_ac20_a_request_item_status_defaults_to_open(db: Db, firm: Firm) -> None:
    engagement = await db.engagement(firm)
    request_list = await db.request_list(firm.tenant_id, engagement)
    status = await db.value(
        "INSERT INTO request_items (tenant_id, engagement_id, request_list_id, description, "
        "audit_area, created_by) VALUES ($1, $2, $3, 'd', 'a', $4) RETURNING status",
        firm.tenant_id,
        engagement,
        request_list,
        firm.user_id,
    )
    assert status == "open"


# --- grants for abacus_app -----------------------------------------------------------------------


async def _row_ids(db: Db, firm: Firm) -> dict[str, uuid.UUID]:
    engagement = await db.engagement(firm)
    request_list = await db.request_list(firm.tenant_id, engagement)
    item = cast(
        uuid.UUID,
        await db.value(
            "INSERT INTO request_items (tenant_id, engagement_id, request_list_id, description, "
            "audit_area, created_by) VALUES ($1, $2, $3, 'd', 'a', $4) RETURNING id",
            firm.tenant_id,
            engagement,
            request_list,
            firm.user_id,
        ),
    )
    return {
        "clients": firm.client_id,
        "client_entities": firm.entity_id,
        "engagements": engagement,
        "request_lists": request_list,
        "request_items": item,
    }


DELETES = {
    "clients": "DELETE FROM clients WHERE id = :i",
    "client_entities": "DELETE FROM client_entities WHERE id = :i",
    "engagements": "DELETE FROM engagements WHERE id = :i",
    "request_lists": "DELETE FROM request_lists WHERE id = :i",
    "request_items": "DELETE FROM request_items WHERE id = :i",
}
COUNTS = {
    "clients": "SELECT count(*) FROM clients WHERE id = $1",
    "client_entities": "SELECT count(*) FROM client_entities WHERE id = $1",
    "engagements": "SELECT count(*) FROM engagements WHERE id = $1",
    "request_lists": "SELECT count(*) FROM request_lists WHERE id = $1",
    "request_items": "SELECT count(*) FROM request_items WHERE id = $1",
}
SELECTS = {
    "clients": "SELECT id FROM clients",
    "client_entities": "SELECT id FROM client_entities",
    "engagements": "SELECT id FROM engagements",
    "request_lists": "SELECT id FROM request_lists",
    "request_items": "SELECT id FROM request_items",
}
UPDATES_DENIED = {
    "clients": "UPDATE clients SET name = 'renamed' WHERE id = :i",
    "client_entities": "UPDATE client_entities SET name = 'renamed' WHERE id = :i",
    "request_lists": "UPDATE request_lists SET created_at = now() WHERE id = :i",
}
UPDATES_ALLOWED = {
    "engagements": "UPDATE engagements SET status = 'archived' WHERE id = :i",
    "request_items": "UPDATE request_items SET status = 'received' WHERE id = :i",
}


@pytest.mark.parametrize("table", TABLES)
async def test_ac20_the_app_has_no_delete_on_the_new_tables(
    db: Db, firm: Firm, table: str
) -> None:
    ids = await _row_ids(db, firm)
    message = await _app_error(firm.ctx, DELETES[table], {"i": ids[table]})
    assert "permission denied" in message
    assert await db.value(COUNTS[table], ids[table]) == 1


@pytest.mark.parametrize("table", sorted(UPDATES_DENIED))
async def test_ac20_the_app_has_no_update_on_clients_entities_or_request_lists(
    db: Db, firm: Firm, table: str
) -> None:
    ids = await _row_ids(db, firm)
    message = await _app_error(firm.ctx, UPDATES_DENIED[table], {"i": ids[table]})
    assert "permission denied" in message


@pytest.mark.parametrize("table", sorted(UPDATES_ALLOWED))
async def test_ac20_the_app_keeps_update_on_engagements_and_request_items(
    db: Db, firm: Firm, table: str
) -> None:
    ids = await _row_ids(db, firm)
    await _as_app(firm.ctx, UPDATES_ALLOWED[table], {"i": ids[table]})


@pytest.mark.parametrize("table", TABLES)
async def test_ac20_the_app_can_select_its_own_rows_in_the_new_tables(
    db: Db, firm: Firm, table: str
) -> None:
    ids = await _row_ids(db, firm)
    async with tenant_session(firm.ctx) as session:
        found = (await session.execute(text(SELECTS[table]))).scalars().all()
    assert ids[table] in found


# --- column grants (contract revision 1) ---------------------------------------------------------

SERVER_SET_INSERTS = {
    "clients": "INSERT INTO clients (tenant_id, name, created_at) VALUES (:t, 'n', now())",
    "client_entities": (
        "INSERT INTO client_entities (tenant_id, client_id, name, created_at) "
        "VALUES (:t, :c, 'n', now())"
    ),
    "engagements_status": (
        "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
        "fiscal_period_start, fiscal_period_end, created_by, status) "
        "VALUES (:t, :c, :e, 'n', '2025-01-01', '2025-12-31', :u, 'archived')"
    ),
    "engagements_type": (
        "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
        "fiscal_period_start, fiscal_period_end, created_by, type) "
        "VALUES (:t, :c, :e, 'n', '2025-01-01', '2025-12-31', :u, 'audit')"
    ),
    "engagements_created_at": (
        "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
        "fiscal_period_start, fiscal_period_end, created_by, created_at) "
        "VALUES (:t, :c, :e, 'n', '2025-01-01', '2025-12-31', :u, now())"
    ),
    "request_lists": (
        "INSERT INTO request_lists (tenant_id, engagement_id, created_at) VALUES (:t, :g, now())"
    ),
}


@pytest.mark.parametrize("case", sorted(SERVER_SET_INSERTS))
async def test_ac20_the_app_cannot_insert_server_set_columns(
    db: Db, firm: Firm, case: str
) -> None:
    engagement = await db.engagement(firm)
    params = {
        "t": firm.tenant_id,
        "c": firm.client_id,
        "e": firm.entity_id,
        "u": firm.user_id,
        "g": engagement,
    }
    message = await _app_error(firm.ctx, SERVER_SET_INSERTS[case], params)
    assert "permission denied" in message


ITEM_WITH_STATUS_APP = (
    "INSERT INTO request_items (tenant_id, engagement_id, request_list_id, description, "
    "audit_area, created_by, status) VALUES (:t, :g, :l, 'd', 'a', :u, 'received')"
)
ITEM_WITH_CREATED_AT_APP = (
    "INSERT INTO request_items (tenant_id, engagement_id, request_list_id, description, "
    "audit_area, created_by, created_at) VALUES (:t, :g, :l, 'd', 'a', :u, now())"
)


async def test_ac20_the_app_cannot_insert_a_request_item_status_or_created_at(
    db: Db, firm: Firm
) -> None:
    engagement = await db.engagement(firm)
    request_list = await db.request_list(firm.tenant_id, engagement)
    params = {"t": firm.tenant_id, "g": engagement, "l": request_list, "u": firm.user_id}
    for sql in (ITEM_WITH_STATUS_APP, ITEM_WITH_CREATED_AT_APP):
        assert "permission denied" in await _app_error(firm.ctx, sql, params)


async def test_ac20_the_app_cannot_insert_an_engagement_member_created_at(
    db: Db, firm: Firm
) -> None:
    engagement = await db.engagement(firm)
    message = await _app_error(
        firm.ctx,
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role, created_at) "
        "VALUES (:t, :g, :u, 'staff', now())",
        {"t": firm.tenant_id, "g": engagement, "u": firm.user_id},
    )
    assert "permission denied" in message


async def test_ac20_the_app_may_supply_an_explicit_id_on_the_listed_tables(
    db: Db, firm: Firm
) -> None:
    await _as_app(
        firm.ctx,
        "INSERT INTO clients (id, tenant_id, name) VALUES (:i, :t, 'n')",
        {"i": uuid.uuid4(), "t": firm.tenant_id},
    )


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE engagements SET name = 'x' WHERE id = :i",
        "UPDATE engagements SET fiscal_period_end = '2030-01-01' WHERE id = :i",
        "UPDATE engagements SET created_by = :u WHERE id = :i",
        "UPDATE engagements SET client_id = :c WHERE id = :i",
        "UPDATE engagements SET type = 'audit' WHERE id = :i",
        "UPDATE engagements SET created_at = now() WHERE id = :i",
        "UPDATE engagements SET tenant_id = :t WHERE id = :i",
    ],
)
async def test_ac20_the_app_may_update_only_status_on_engagements(
    db: Db, firm: Firm, sql: str
) -> None:
    ids = await _row_ids(db, firm)
    params = {
        "i": ids["engagements"],
        "u": firm.user_id,
        "c": firm.client_id,
        "t": firm.tenant_id,
    }
    assert "permission denied" in await _app_error(firm.ctx, sql, params)


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE request_items SET description = 'x' WHERE id = :i",
        "UPDATE request_items SET audit_area = 'x' WHERE id = :i",
        "UPDATE request_items SET created_by = :u WHERE id = :i",
        "UPDATE request_items SET request_list_id = :l WHERE id = :i",
        "UPDATE request_items SET created_at = now() WHERE id = :i",
    ],
)
async def test_ac20_the_app_may_update_only_status_on_request_items(
    db: Db, firm: Firm, sql: str
) -> None:
    ids = await _row_ids(db, firm)
    params = {"i": ids["request_items"], "u": firm.user_id, "l": ids["request_lists"]}
    assert "permission denied" in await _app_error(firm.ctx, sql, params)


async def test_ac20_the_app_still_updates_status_and_the_check_applies(db: Db, firm: Firm) -> None:
    ids = await _row_ids(db, firm)
    await _as_app(firm.ctx, UPDATES_ALLOWED["engagements"], {"i": ids["engagements"]})
    message = await _app_error(
        firm.ctx,
        "UPDATE request_items SET status = 'bogus' WHERE id = :i",
        {"i": ids["request_items"]},
    )
    assert "check constraint" in message
