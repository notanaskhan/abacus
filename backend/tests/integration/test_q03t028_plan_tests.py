"""Q-03-T028 (Q-03 §3.5 E3; chapter 10 §10.11.1): plan tests for the top 20 list endpoints on a
10k-row synthetic fixture. "All 20 plan tests pass in stage 2 and an index drop fails the build."

Each case loads 10,000 synthetic rows for the probed firm and 10,000 for a second firm into the
endpoint's table, inside one superuser transaction on the test database that is rolled back
afterwards (foreign keys and triggers off for the load, `ANALYZE`d inside it), then asks Postgres
for the plan of the endpoint's driving query, as `abacus_app` under the firm's `app.tenant_id`, so
row-level security adds the tenant predicate as it does in production. The plan must use the
named composite index, which leads with `tenant_id` and carries the endpoint's scope column, and
must never sequentially scan the table.

A probe is the endpoint's own predicate on its own table: the scope it filters on, its status
filter and its sort and page size (TASK-1245 traces each to its repository function). The
visibility subqueries (`visible()` on `engagement_members` and `ethical_walls`) are not repeated.
Three endpoints are 501 stubs; their probes read the table and index their contracts name.

A case marked `gap` has no index for its driving predicate today (TASK-1245 lists the six and the
index each needs; adding one takes a migration). Its test asserts the gap still holds: the named
index is absent and the table is scanned. When the migration lands that test fails, and clearing
the case's `gap` puts it under the plan test with the others.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import cast
from uuid import UUID, uuid4

import asyncpg
import pytest

from .conftest import MigratedDatabase

ROWS = 10_000
APP_ROLE = "abacus_app"


@dataclass(frozen=True)
class Case:
    endpoint: str
    table: str
    probe: str  # `{s}`: one scope value; `{some}`: an array of fifty
    index: str  # the composite index the plan must use (for a gap: the one it needs)
    scope: str | None  # the scope column the index must carry
    fill: dict[str, str] = field(default_factory=lambda: dict[str, str]())
    scopes: int = 100  # distinct scope values per firm
    gap: str | None = None  # why no index serves the probe today
    # Indexes with the same leading columns that serve the probe as well; the planner may take
    # either, so dropping one of them alone is not a regression.
    equivalent: tuple[str, ...] = ()


SCOPED = "($2::uuid[])[1 + g % array_length($2::uuid[], 1)]"


def _cycle(*values: str) -> str:
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"(ARRAY[{quoted}])[1 + g % {len(values)}]"


AUDIT_TARGET = (
    "No index on audit_events (tenant_id, target_type, target_id, seq): the activity feeds read "
    "the firm's whole log backwards (TASK-1245; needs a migration)"
)

CASES: tuple[Case, ...] = (
    Case(
        "GET /v1/audits",
        "work_items",
        "SELECT id FROM work_items WHERE kind = 'assurance' AND engagement_id = ANY({some}) "
        "ORDER BY due_on, id LIMIT 51",
        "work_items_one_assurance",
        "engagement_id",
        {"engagement_id": SCOPED, "kind": _cycle("assurance", "close"), "status": "'active'"},
        scopes=ROWS,
    ),
    Case(
        "GET /v1/binders",
        "request_lists",
        "SELECT id FROM request_lists WHERE engagement_id = '{s}' "
        "AND status = 'published' ORDER BY id LIMIT 51",
        "request_lists_tenant_id_engagement_id_id_key",
        "engagement_id",
        {
            "engagement_id": SCOPED,
            "kind": "'pbc'",
            "status": _cycle("draft", "published", "complete", "closed"),
            "created_from": "'blank'",
        },
    ),
    Case(
        "GET /v1/binders/{binder_id}/activity",
        "audit_events",
        "SELECT id FROM audit_events WHERE target_type = 'request_list' "
        "AND target_id = '{s}' ORDER BY seq DESC LIMIT 51",
        "audit_events_target",
        "target_id",
        {"target_type": "'request_list'", "target_id": f"{SCOPED}::text"},
        gap=AUDIT_TARGET,
    ),
    Case(
        "GET /v1/binders/{binder_id}/requests",
        "request_items",
        "SELECT id FROM request_items WHERE request_list_id = '{s}' AND deleted_at IS NULL "
        "ORDER BY created_at, id LIMIT 201",
        "request_items_by_list",
        "request_list_id",
        {"request_list_id": SCOPED, "status": "'requested'", "client_visible": "true"},
        gap="No index on request_items (tenant_id, request_list_id, created_at, id) WHERE "
        "deleted_at IS NULL (TASK-1245; needs a migration)",
    ),
    Case(
        "GET /v1/citations",
        "citations",
        "SELECT id FROM citations WHERE cited_from_type = 'workpaper' "
        "AND cited_from_id = '{s}' ORDER BY n, id LIMIT 51",
        "citations_by_anchor",
        "cited_from_id",
        {
            "cited_from_type": "'workpaper'",
            "cited_from_id": SCOPED,
            "kind": "'document_text'",
            "created_by_kind": "'system'",
            "verified": "true",
        },
    ),
    Case(
        "GET /v1/clients (CLI-01)",
        "clients",
        "SELECT id FROM clients WHERE status = 'active' ORDER BY normalised_name, id LIMIT 51",
        "clients_normalised_name",
        None,
        {
            "status": _cycle("prospect", "active", "inactive", "former"),
            "portal_status": "'not_invited'",
        },
    ),
    Case(
        "GET /v1/clients/{client_id}/contacts",
        "contacts",
        "SELECT id FROM contacts WHERE client_id = '{s}' ORDER BY display_name, id",
        "contacts_tenant_id_client_id_id_key",
        "client_id",
        {
            "client_id": SCOPED,
            "contact_kind": "'client_person'",
            "portal_state": "'not_invited'",
            "party_kind": "'person'",
        },
    ),
    Case(
        "GET /v1/clients/{client_id}/relationships",
        "entity_relationships",
        "SELECT id FROM entity_relationships WHERE from_entity_id = '{s}' "
        "ORDER BY effective_from, id LIMIT 51",
        "entity_relationships_from",
        "from_entity_id",
        {"from_entity_id": SCOPED, "kind": "'owner_of'"},
    ),
    Case(
        "GET /v1/decision-cards (stub)",
        "decision_cards",
        "SELECT id FROM decision_cards WHERE engagement_id = '{s}' "
        "AND status = 'awaiting_role' ORDER BY created_at, id LIMIT 51",
        "decision_cards_open",
        "engagement_id",
        {
            "engagement_id": SCOPED,
            "status": _cycle("awaiting_role", "decided", "superseded"),
            "reserved_role": "'manager'",
            "options": "'[]'::jsonb",
            "context": "'[]'::jsonb",
            "factors": "'[]'::jsonb",
            "blocking_refs": "'[]'::jsonb",
            "raised_by_kind": "'system'",
        },
    ),
    Case(
        "GET /v1/engagements/index (ENG-01)",
        "engagements",
        "SELECT id FROM engagements WHERE status NOT IN ('archived', 'declined') "
        "ORDER BY created_at DESC LIMIT 51",
        "engagements_tenant",
        None,
        {
            "type": "'fs_audit'",
            "service_line": "'audit'",
            "status": _cycle("prospect", "accepted", "active", "on_hold", "delivered", "archived"),
            "fiscal_period_start": "date '2025-01-01'",
            "fiscal_period_end": "date '2025-12-31'",
        },
    ),
    Case(
        "GET /v1/engagements/{engagement_id}/request-items/{item_id}/activity",
        "audit_events",
        "SELECT id FROM audit_events WHERE target_type = 'request_item' "
        "AND target_id = '{s}' ORDER BY seq DESC LIMIT 51",
        "audit_events_target",
        "target_id",
        {"target_type": "'request_item'", "target_id": f"{SCOPED}::text"},
        gap=AUDIT_TARGET,
    ),
    Case(
        "GET /v1/firm/staff",
        "memberships",
        "SELECT id FROM memberships WHERE kind = 'staff' ORDER BY created_at, user_id",
        "memberships_staff",
        "kind",
        {
            "kind": _cycle("staff", "client"),
            "status": "'active'",
            "firm_role": "NULL",
            "service_lines": "'{}'::text[]",
        },
        gap="No index on memberships (tenant_id, kind, created_at, user_id); the roster is read "
        "whole and paged in Python (TASK-1245; needs a migration or paging in SQL)",
    ),
    Case(
        "GET /v1/human-gates",
        "human_gates",
        "SELECT id FROM human_gates WHERE assignee_user_id = '{s}' AND state = 'open' "
        "ORDER BY updated_at, id LIMIT 51",
        "human_gates_open",
        "assignee_user_id",
        {
            "assignee_user_id": SCOPED,
            "kind": "'decision'",
            "state": _cycle("open", "done", "voided"),
        },
    ),
    Case(
        "GET /v1/issues (stub)",
        "issues",
        "SELECT id FROM issues WHERE engagement_id = '{s}' AND status = 'open' "
        "ORDER BY created_at, id LIMIT 51",
        "issues_open",
        "engagement_id",
        {
            "engagement_id": SCOPED,
            "kind": "'review_point'",
            "priority": "'medium'",
            "status": _cycle("open", "in_progress", "resolved", "verified"),
            "blocks": "'{}'::text[]",
        },
    ),
    Case(
        "GET /v1/notifications/feed",
        "notifications",
        "SELECT id FROM notifications WHERE recipient_user_id = '{s}' "
        "AND created_at >= timestamptz '2026-01-01' ORDER BY created_at DESC, id LIMIT 500",
        "notifications_recipient",
        "recipient_user_id",
        {"recipient_user_id": SCOPED, "category": "'other'"},
    ),
    Case(
        "GET /v1/portal/binders",
        "request_lists",
        "SELECT id FROM request_lists WHERE status IN ('published', 'complete') "
        "ORDER BY published_at DESC, id",
        "request_lists_portal",
        "status",
        {
            "engagement_id": SCOPED,
            "kind": "'pbc'",
            "status": _cycle("draft", "published", "complete", "closed"),
            "published_at": "timestamptz '2026-01-01' + g * interval '1 minute'",
            "created_from": "'blank'",
        },
        gap="No index on request_lists (tenant_id, status, published_at); the portal's binders "
        "are found through request_items, which has no request_list_id index either "
        "(TASK-1245; needs a migration)",
    ),
    Case(
        "GET /v1/review-notes (stub)",
        "review_notes",
        "SELECT id FROM review_notes WHERE procedure_id = '{s}' ORDER BY created_at, id LIMIT 51",
        "review_notes_by_procedure",
        "procedure_id",
        {"procedure_id": SCOPED},
    ),
    Case(
        "GET /v1/walls/{wall_id}/events",
        "audit_events",
        "SELECT id FROM audit_events WHERE target_type = 'wall' "
        "AND target_id = '{s}' ORDER BY seq DESC LIMIT 500",
        "audit_events_target",
        "target_id",
        {"target_type": "'wall'", "target_id": f"{SCOPED}::text"},
        gap=AUDIT_TARGET,
    ),
    Case(
        "GET /v1/work-items",
        "work_items",
        "SELECT id FROM work_items WHERE engagement_id = '{s}' "
        "ORDER BY created_at DESC, id DESC LIMIT 51",
        "work_items_by_engagement",
        "engagement_id",
        {
            "engagement_id": SCOPED,
            "kind": _cycle("tax_return", "close", "notice"),
            "status": "'active'",
        },
        equivalent=("work_items_tenant_id_engagement_id_id_key",),
    ),
    Case(
        "GET /v1/engagements/{engagement_id}/request-items",
        "request_items",
        "SELECT id FROM request_items WHERE engagement_id = '{s}' ORDER BY created_at, id",
        "request_items_engagement",
        "engagement_id",
        {"engagement_id": SCOPED, "status": "'requested'", "client_visible": "true"},
        equivalent=("request_items_tenant_id_engagement_id_id_key",),
    ),
)

# The filler for a NOT NULL column without a default that a case does not set. Text is letters
# only, so it passes the schema's `^[a-z][a-z_]*$` code checks; every value varies with `g`.
_FILLER: dict[str, str] = {
    "uuid": "gen_random_uuid()",
    "text": "'p' || translate(g::text, '0123456789', 'abcdefghij')",
    "integer": "1 + g % 20",
    "smallint": "1 + g % 20",
    "bigint": "g",
    "boolean": "true",
    "date": "date '2026-01-01' + g % 300",
    "timestamp with time zone": "timestamptz '2026-01-01' + g * interval '1 minute'",
    "jsonb": "jsonb_build_object('id', g)",
    "text[]": "'{}'::text[]",
    "bytea": "decode(md5(g::text), 'hex')",
}

_COLUMNS = """
SELECT a.attname AS name, format_type(a.atttypid, a.atttypmod) AS type,
       (a.atthasdef OR a.attidentity <> '' OR a.attgenerated <> '') AS has_default
FROM pg_attribute a
WHERE a.attrelid = $1::regclass AND a.attnum > 0 AND NOT a.attisdropped AND a.attnotnull
ORDER BY a.attnum
"""
_INDEX_COLUMNS = """
SELECT array_agg(a.attname ORDER BY k.ord) AS columns
FROM pg_index i
JOIN pg_class c ON c.oid = i.indexrelid
CROSS JOIN LATERAL unnest(i.indkey) WITH ORDINALITY AS k(attnum, ord)
JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = k.attnum
WHERE c.relname = $1
"""


async def _insert(conn: asyncpg.Connection, case: Case, tenant: UUID, scopes: list[UUID]) -> None:
    values = dict(case.fill)
    values["tenant_id"] = "$1::uuid"
    if case.table == "audit_events":  # the row's actor is the transaction's (its CHECK)
        values.setdefault("actor_kind", "current_setting('app.actor_kind')")
        values.setdefault("actor_id", "current_setting('app.actor_id')")
        values.setdefault("action", "'plan.probed'")
    for row in await conn.fetch(_COLUMNS, case.table):
        name, kind = cast(str, row["name"]), cast(str, row["type"])
        if name in values or row["has_default"]:
            continue
        if kind.startswith("numeric"):
            kind = "integer"
        assert kind in _FILLER, f"{case.table}.{name}: no synthetic filler for {kind}"
        values[name] = _FILLER[kind]
    columns = ", ".join(values)
    exprs = ", ".join(values.values())
    sql = f"INSERT INTO {case.table} ({columns}) SELECT {exprs} FROM generate_series(1, {ROWS}) g"
    await conn.execute(sql, tenant, scopes) if "$2" in sql else await conn.execute(sql, tenant)


class _RolledBack(Exception):
    """Raised to leave the fixture's transaction by rolling it back."""


def _nodes(plan: dict[str, object]) -> list[dict[str, object]]:
    found = [plan]
    for child in cast(list[dict[str, object]], plan.get("Plans", [])):
        found += _nodes(child)
    return found


async def _plan_of(
    conn: asyncpg.Connection, case: Case, *, drop: str | None = None
) -> tuple[list[dict[str, object]], list[str]]:
    """Load the fixture, plan the probe as the app role, and roll everything back."""
    firm, other = uuid4(), uuid4()
    scopes = [uuid4() for _ in range(case.scopes)]
    planned: tuple[list[dict[str, object]], list[str]] | None = None
    try:
        async with conn.transaction():  # rolled back by _RolledBack below: nothing persists
            await conn.execute("SET LOCAL session_replication_role = replica")
            await conn.execute("SELECT set_config('app.actor_kind', 'system', true)")
            await conn.execute("SELECT set_config('app.actor_id', 'plan-tests', true)")
            await _insert(conn, case, firm, scopes)
            await _insert(conn, case, other, [uuid4() for _ in range(case.scopes)])
            await conn.execute(f"ANALYZE {case.table}")
            if drop is not None:
                await conn.execute(f"DROP INDEX {drop}")
            columns = cast(list[str] | None, await conn.fetchval(_INDEX_COLUMNS, case.index)) or []
            await conn.execute("SET LOCAL session_replication_role = origin")
            await conn.execute("SELECT set_config('app.tenant_id', $1, true)", str(firm))
            await conn.execute(f"SET LOCAL ROLE {APP_ROLE}")
            some = "ARRAY[" + ", ".join(f"'{s}'::uuid" for s in scopes[:50]) + "]"
            probe = case.probe.format(s=scopes[0], some=some)
            raw = await conn.fetchval(f"EXPLAIN (FORMAT JSON) {probe}")
            plan = cast(list[dict[str, object]], json.loads(raw))[0]["Plan"]
            planned = (_nodes(cast(dict[str, object], plan)), columns)
            raise _RolledBack
    except _RolledBack:
        pass
    # The rolled-back rows are dead tuples now: reclaim them and restore the table's statistics
    # for whatever runs next on this database.
    await conn.execute(f"VACUUM ANALYZE {case.table}")
    assert planned is not None
    return planned


def _problems(case: Case, nodes: list[dict[str, object]], columns: list[str]) -> list[str]:
    found: list[str] = []
    seq = [
        n for n in nodes if n["Node Type"] == "Seq Scan" and n.get("Relation Name") == case.table
    ]
    if seq:
        found.append(f"{case.table} is scanned sequentially")
    used = {str(n["Index Name"]) for n in nodes if "Index Name" in n}
    if not used & {case.index, *case.equivalent}:
        found.append(f"{case.index} is not used (plan uses {sorted(used) or 'no index'})")
    if not columns:
        found.append(f"{case.index} does not exist")
    elif columns[0] != "tenant_id" or (case.scope is not None and case.scope not in columns):
        found.append(f"{case.index} {columns} does not lead with tenant_id and carry {case.scope}")
    return found


@pytest.fixture
async def superuser(migrated_db: MigratedDatabase) -> AsyncIterator[asyncpg.Connection]:
    conn = await asyncpg.connect(migrated_db.superuser_dsn)
    try:
        yield conn
    finally:
        await conn.close()


GAPS = tuple(c for c in CASES if c.gap is not None)
PLANNED = tuple(c for c in CASES if c.gap is None)


def test_t028_twenty_list_endpoints_are_planned() -> None:
    assert len(CASES) == 20
    assert len({c.endpoint for c in CASES}) == 20
    assert any("CLI-01" in c.endpoint for c in CASES) and any(
        "ENG-01" in c.endpoint for c in CASES
    )


@pytest.mark.parametrize("case", PLANNED, ids=[c.endpoint for c in PLANNED])
async def test_t028_the_list_query_uses_its_composite_index(
    superuser: asyncpg.Connection, case: Case
) -> None:
    nodes, columns = await _plan_of(superuser, case)
    problems = _problems(case, nodes, columns)
    assert not problems, f"{case.endpoint}: {problems}"


@pytest.mark.parametrize("case", GAPS, ids=[c.endpoint for c in GAPS])
async def test_t028_a_gap_holds_until_its_index_lands(
    superuser: asyncpg.Connection, case: Case
) -> None:
    """A gap's endpoint has no index for its driving predicate (TASK-1245 lists them). When the
    migration that adds the named index lands, this fails: clear the case's `gap` so its plan is
    tested like the others."""
    nodes, columns = await _plan_of(superuser, case)
    assert columns == [], f"{case.index} exists now: clear the gap on {case.endpoint}"
    assert f"{case.table} is scanned sequentially" in _problems(case, nodes, columns)


async def test_t028_dropping_an_index_fails_its_plan_test(superuser: asyncpg.Connection) -> None:
    case = next(c for c in CASES if c.index == "notifications_recipient")
    nodes, columns = await _plan_of(superuser, case, drop=case.index)
    problems = _problems(case, nodes, columns)
    assert "notifications_recipient is not used" in " ".join(problems)
    # Rolled back: the index is still there for every other test.
    nodes, columns = await _plan_of(superuser, case)
    assert _problems(case, nodes, columns) == []
