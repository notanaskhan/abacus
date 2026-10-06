"""AC-4: the unit of work commits a change, its audit events and its outbox rows together.

Everything runs against a real Postgres. A probe tenant table stands in for domain state; it is
created as `abacus_owner` through the real `tenant_table` helper (recording stub plus
`exec_driver_sql`, as in test_tenancy). Reads go through `tenant_session`; raw statements that must
be rejected by the database go through `tenant_connection`, which never commits.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import Annotated, ClassVar, Protocol, cast

import pytest
from alembic.operations import Operations
from sqlalchemy import Column, MetaData, Table, Text, Uuid, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from abacus.kernel.classification import classified
from abacus.kernel.db import (
    TenantContext,
    configure_engine,
    dispose_engine,
    tenant_connection,
    tenant_session,
)
from abacus.kernel.db.migration import tenant_table
from abacus.kernel.uow import DomainEvent, MissingAuditEvent, Ref, Target, uow


class Migrated(Protocol):
    owner_url: str
    app_url: str


METADATA = MetaData()
PROBE = Table(
    "uow_probe",
    METADATA,
    Column("id", Uuid(), primary_key=True),
    Column("tenant_id", Uuid(), nullable=False),
    Column("body", Text()),
)

AUDIT_SELECT = text(
    "SELECT tenant_id, actor_kind, actor_id, action, target_type, target_id, before_ref, "
    "after_ref, trace_id FROM audit_events ORDER BY seq"
)
OUTBOX_SELECT = text(
    "SELECT id, tenant_id, event_type, payload, published_at, attempts, last_error "
    "FROM outbox ORDER BY seq"
)
INSERT_AUDIT = text(
    "INSERT INTO audit_events (tenant_id, actor_kind, actor_id, action, target_type, target_id) "
    "VALUES (:tenant_id, :actor_kind, :actor_id, 'probe.checked', 'probe', '1')"
)


# Test-only triggers (created and dropped by the owner) make exactly the marked inserts fail.
FAILURE_TRIGGERS = [
    "CREATE OR REPLACE FUNCTION probe_forced_failure() RETURNS trigger LANGUAGE plpgsql AS "
    "$$ BEGIN RAISE EXCEPTION 'probe_forced_failure'; END $$",
    "CREATE TRIGGER probe_fail_audit BEFORE INSERT ON audit_events FOR EACH ROW "
    "WHEN (NEW.target_type = 'probe_fail') EXECUTE FUNCTION probe_forced_failure()",
    "CREATE TRIGGER probe_fail_outbox BEFORE INSERT ON outbox FOR EACH ROW "
    "WHEN (NEW.event_type = 'probe.outbox_failure') EXECUTE FUNCTION probe_forced_failure()",
]
FAILURE_TRIGGERS_DOWN = [
    "DROP TRIGGER IF EXISTS probe_fail_audit ON audit_events",
    "DROP TRIGGER IF EXISTS probe_fail_outbox ON outbox",
    "DROP FUNCTION IF EXISTS probe_forced_failure()",
]


class ProbeDone(DomainEvent):
    event_type: ClassVar[str] = "probe.done"
    probe_id: Annotated[uuid.UUID, classified("internal")]
    label: Annotated[str, classified("public")]


class SecretEvent(DomainEvent):
    event_type: ClassVar[str] = "probe.secret"
    probe_id: Annotated[uuid.UUID, classified("internal")]
    taxpayer_note: Annotated[str, classified("restricted")]


class UntaggedEvent(DomainEvent):
    event_type: ClassVar[str] = "probe.untagged"
    probe_id: Annotated[uuid.UUID, classified("internal")]
    note: str


class FailingOutbox(DomainEvent):
    event_type: ClassVar[str] = "probe.outbox_failure"
    probe_id: Annotated[uuid.UUID, classified("internal")]


class RecordingOp:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def execute(self, sql: str) -> None:
        self.statements.append(sql)


def _ctx(
    tenant_id: uuid.UUID | None = None, actor_kind: str = "human", actor_id: str = "u-1"
) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id or uuid.uuid4(),
        actor_kind=actor_kind,  # pyright: ignore[reportArgumentType] -- literal kinds are checked at runtime
        actor_id=actor_id,
    )


@pytest.fixture(autouse=True)
async def engine_for_this_loop(migrated_db: Migrated) -> AsyncIterator[None]:
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()


@pytest.fixture(autouse=True)
async def probe_table(migrated_db: Migrated) -> AsyncIterator[None]:
    engine = create_async_engine(migrated_db.owner_url, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(METADATA.drop_all)
            await conn.run_sync(METADATA.create_all)
            op = RecordingOp()
            tenant_table(cast(Operations, op), "uow_probe")
            for statement in op.statements:
                await conn.exec_driver_sql(statement)
            for statement in FAILURE_TRIGGERS:
                await conn.exec_driver_sql(statement)
        yield
        async with engine.begin() as conn:
            for statement in FAILURE_TRIGGERS_DOWN:
                await conn.exec_driver_sql(statement)
            await conn.run_sync(METADATA.drop_all)
    finally:
        await engine.dispose()


async def _probe_ids(ctx: TenantContext) -> list[uuid.UUID]:
    async with tenant_session(ctx) as session:
        return list((await session.execute(select(PROBE.c.id))).scalars().all())


async def _audit(ctx: TenantContext) -> list[dict[str, object]]:
    async with tenant_session(ctx) as session:
        return [dict(r) for r in (await session.execute(AUDIT_SELECT)).mappings().all()]


async def _outbox(ctx: TenantContext) -> list[dict[str, object]]:
    async with tenant_session(ctx) as session:
        return [dict(r) for r in (await session.execute(OUTBOX_SELECT)).mappings().all()]


async def _commit_one(ctx: TenantContext, action: str = "probe.created") -> ProbeDone:
    probe_id = uuid.uuid4()
    event = ProbeDone(probe_id=probe_id, label="made")
    async with uow(ctx) as tx:
        await tx.session.execute(
            PROBE.insert().values(id=probe_id, tenant_id=ctx.tenant_id, body="x")
        )
        tx.record(action, target=Target("probe", probe_id))
        tx.emit(event)
    return event


# --- AC-4: atomic commit ----------------------------------------------------------------------


async def test_ac4_change_audit_event_and_outbox_row_commit_together() -> None:
    ctx = _ctx()
    probe_id = uuid.uuid4()
    event = ProbeDone(probe_id=probe_id, label="made")
    async with uow(ctx) as tx:
        await tx.session.execute(
            PROBE.insert().values(id=probe_id, tenant_id=ctx.tenant_id, body="x")
        )
        tx.record("probe.created", target=Target("probe", probe_id))
        tx.emit(event)
    assert await _probe_ids(ctx) == [probe_id]
    audit = await _audit(ctx)
    assert [(a["action"], a["target_type"], a["target_id"]) for a in audit] == [
        ("probe.created", "probe", str(probe_id))
    ]
    outbox = await _outbox(ctx)
    assert [(o["event_type"]) for o in outbox] == ["probe.done"]


async def test_ac4_nothing_is_visible_to_others_until_the_block_exits() -> None:
    ctx = _ctx()
    probe_id = uuid.uuid4()
    async with uow(ctx) as tx:
        await tx.session.execute(
            PROBE.insert().values(id=probe_id, tenant_id=ctx.tenant_id, body="x")
        )
        tx.record("probe.created", target=Target("probe", probe_id))
        tx.emit(ProbeDone(probe_id=probe_id, label="made"))
        assert await _probe_ids(ctx) == []
        assert await _audit(ctx) == []
        assert await _outbox(ctx) == []
    assert await _probe_ids(ctx) == [probe_id]
    assert len(await _audit(ctx)) == 1
    assert len(await _outbox(ctx)) == 1


async def test_ac4_a_block_without_emit_writes_audit_but_no_outbox_row() -> None:
    ctx = _ctx()
    async with uow(ctx) as tx:
        tx.record("probe.touched", target=Target("probe", "1"))
    assert len(await _audit(ctx)) == 1
    assert await _outbox(ctx) == []


async def test_ac4_several_events_are_all_written_in_order() -> None:
    ctx = _ctx()
    first, second = (
        ProbeDone(probe_id=uuid.uuid4(), label="1"),
        ProbeDone(probe_id=uuid.uuid4(), label="2"),
    )
    async with uow(ctx) as tx:
        tx.record("probe.created", target=Target("probe", "1"))
        tx.record("probe.renamed", target=Target("probe", "1"))
        tx.emit(first)
        tx.emit(second)
    assert [a["action"] for a in await _audit(ctx)] == ["probe.created", "probe.renamed"]
    assert [o["id"] for o in await _outbox(ctx)] == [first.event_id, second.event_id]


async def test_ac4_an_exception_inside_the_block_rolls_everything_back() -> None:
    ctx = _ctx()
    probe_id = uuid.uuid4()
    marker = RuntimeError("boom")
    with pytest.raises(RuntimeError) as raised:
        async with uow(ctx) as tx:
            await tx.session.execute(
                PROBE.insert().values(id=probe_id, tenant_id=ctx.tenant_id, body="x")
            )
            tx.record("probe.created", target=Target("probe", probe_id))
            tx.emit(ProbeDone(probe_id=probe_id, label="made"))
            raise marker
    assert raised.value is marker
    assert await _probe_ids(ctx) == []
    assert await _audit(ctx) == []
    assert await _outbox(ctx) == []


async def test_ac4_an_exception_is_not_replaced_by_missing_audit_event() -> None:
    with pytest.raises(RuntimeError, match="boom"):
        async with uow(_ctx()):
            raise RuntimeError("boom")


async def test_ac4_a_block_without_record_raises_and_writes_nothing() -> None:
    ctx = _ctx()
    probe_id = uuid.uuid4()
    with pytest.raises(MissingAuditEvent):
        async with uow(ctx) as tx:
            await tx.session.execute(
                PROBE.insert().values(id=probe_id, tenant_id=ctx.tenant_id, body="x")
            )
            tx.emit(ProbeDone(probe_id=probe_id, label="made"))
    assert await _probe_ids(ctx) == []
    assert await _audit(ctx) == []
    assert await _outbox(ctx) == []


async def test_ac4_an_empty_block_raises_missing_audit_event() -> None:
    with pytest.raises(MissingAuditEvent):
        async with uow(_ctx()):
            pass


async def test_ac4_a_failing_audit_insert_rolls_back_the_change_and_the_outbox_row() -> None:
    ctx = _ctx()
    probe_id = uuid.uuid4()
    with pytest.raises(DBAPIError, match="probe_forced_failure"):
        async with uow(ctx) as tx:
            await tx.session.execute(
                PROBE.insert().values(id=probe_id, tenant_id=ctx.tenant_id, body="x")
            )
            tx.record("probe.created", target=Target("probe_fail", probe_id))
            tx.emit(ProbeDone(probe_id=probe_id, label="made"))
    assert await _probe_ids(ctx) == []
    assert await _audit(ctx) == []
    assert await _outbox(ctx) == []


async def test_ac4_a_failing_outbox_insert_after_the_audit_insert_rolls_both_back() -> None:
    ctx = _ctx()
    probe_id = uuid.uuid4()
    with pytest.raises(DBAPIError, match="probe_forced_failure"):
        async with uow(ctx) as tx:
            await tx.session.execute(
                PROBE.insert().values(id=probe_id, tenant_id=ctx.tenant_id, body="x")
            )
            tx.record("probe.created", target=Target("probe", probe_id))
            tx.emit(FailingOutbox(probe_id=probe_id))
    assert await _probe_ids(ctx) == []
    assert await _audit(ctx) == []
    assert await _outbox(ctx) == []


async def test_ac4_emitting_the_same_event_twice_rolls_the_whole_unit_of_work_back() -> None:
    ctx = _ctx()
    probe_id = uuid.uuid4()
    event = ProbeDone(probe_id=probe_id, label="made")
    with pytest.raises((DBAPIError, ValueError)):
        async with uow(ctx) as tx:
            await tx.session.execute(
                PROBE.insert().values(id=probe_id, tenant_id=ctx.tenant_id, body="x")
            )
            tx.record("probe.created", target=Target("probe", probe_id))
            tx.emit(event)
            tx.emit(event)
    assert await _probe_ids(ctx) == []
    assert await _audit(ctx) == []
    assert await _outbox(ctx) == []


async def test_ac4_a_failed_unit_of_work_does_not_poison_the_next_one() -> None:
    ctx = _ctx()
    with pytest.raises(MissingAuditEvent):
        async with uow(ctx):
            pass
    await _commit_one(ctx)
    assert len(await _audit(ctx)) == 1


# --- audit rows carry the context ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "actor"), [("human", "u-1"), ("agent", "agent-7"), ("system", "relay")]
)
async def test_ac4_audit_rows_carry_the_contexts_tenant_and_actor(kind: str, actor: str) -> None:
    ctx = _ctx(actor_kind=kind, actor_id=actor)
    await _commit_one(ctx)
    [row] = await _audit(ctx)
    assert row["tenant_id"] == ctx.tenant_id
    assert (row["actor_kind"], row["actor_id"]) == (kind, actor)


async def test_ac4_outbox_rows_carry_the_contexts_tenant() -> None:
    ctx = _ctx()
    await _commit_one(ctx)
    [row] = await _outbox(ctx)
    assert row["tenant_id"] == ctx.tenant_id


async def test_ac4_audit_target_and_references_round_trip_without_record_contents() -> None:
    ctx = _ctx()
    target_id, fingerprint, digest = uuid.uuid4(), uuid.uuid4(), "ab" * 32
    async with uow(ctx) as tx:
        tx.record(
            "request_item.received",
            target=Target("request_item", target_id),
            before=Ref(version=3),
            after=Ref(version=4, fingerprint=fingerprint, content_hash=digest),
        )
    [row] = await _audit(ctx)
    assert row["action"] == "request_item.received"
    assert (row["target_type"], row["target_id"]) == ("request_item", str(target_id))
    assert row["before_ref"] == {"version": 3}
    assert row["after_ref"] == {
        "version": 4,
        "fingerprint": str(fingerprint),
        "content_hash": digest,
    }
    assert row["trace_id"] is None


async def test_ac4_omitted_references_are_stored_as_null() -> None:
    ctx = _ctx()
    async with uow(ctx) as tx:
        tx.record("probe.created", target=Target("probe", "1"))
    [row] = await _audit(ctx)
    assert row["before_ref"] is None
    assert row["after_ref"] is None


async def test_ac4_target_accepts_a_string_or_uuid_id() -> None:
    ctx = _ctx()
    uid = uuid.uuid4()
    async with uow(ctx) as tx:
        tx.record("probe.created", target=Target("probe", uid))
        tx.record("probe.created", target=Target("probe", "12345"))
    assert [a["target_id"] for a in await _audit(ctx)] == [str(uid), "12345"]


# --- the database checks actor and tenant ------------------------------------------------------


async def test_ac4_a_matching_audit_row_inserted_directly_is_accepted() -> None:
    ctx = _ctx()
    async with tenant_connection(ctx) as conn:
        await conn.execute(
            INSERT_AUDIT,
            {"tenant_id": ctx.tenant_id, "actor_kind": ctx.actor_kind, "actor_id": ctx.actor_id},
        )


@pytest.mark.parametrize(
    "overrides",
    [{"actor_id": "someone-else"}, {"actor_kind": "system"}, {"actor_kind": "agent"}],
    ids=["other-actor-id", "other-kind-system", "other-kind-agent"],
)
async def test_ac4_the_database_rejects_an_audit_row_with_another_actor(
    overrides: dict[str, str],
) -> None:
    ctx = _ctx(actor_kind="human", actor_id="u-1")
    params: dict[str, object] = {
        "tenant_id": ctx.tenant_id,
        "actor_kind": ctx.actor_kind,
        "actor_id": ctx.actor_id,
        **overrides,
    }
    with pytest.raises(DBAPIError, match=r"check constraint|violates"):
        async with tenant_connection(ctx) as conn:
            await conn.execute(INSERT_AUDIT, params)


async def test_ac4_the_database_rejects_an_audit_row_for_another_tenant() -> None:
    ctx = _ctx()
    with pytest.raises(DBAPIError, match="row-level security"):
        async with tenant_connection(ctx) as conn:
            await conn.execute(
                INSERT_AUDIT,
                {
                    "tenant_id": uuid.uuid4(),
                    "actor_kind": ctx.actor_kind,
                    "actor_id": ctx.actor_id,
                },
            )


async def test_ac4_the_database_rejects_an_audit_action_that_is_not_entity_dot_verb() -> None:
    ctx = _ctx()
    with pytest.raises(DBAPIError, match=r"check constraint|violates"):
        async with tenant_connection(ctx) as conn:
            await conn.execute(
                text(
                    "INSERT INTO audit_events (tenant_id, actor_kind, actor_id, action, "
                    "target_type, target_id) VALUES (:t, :k, :a, 'NotAnAction', 'p', '1')"
                ),
                {"t": ctx.tenant_id, "k": ctx.actor_kind, "a": ctx.actor_id},
            )


# --- insert-only for the app role -------------------------------------------------------------

DENIED = {
    "update-audit-action": "UPDATE audit_events SET action = 'probe.hacked'",
    "update-audit-target": "UPDATE audit_events SET target_id = 'x' WHERE target_id IS NOT NULL",
    "delete-audit": "DELETE FROM audit_events",
    "update-outbox-payload": "UPDATE outbox SET payload = '{}'::jsonb",
    "update-outbox-published": "UPDATE outbox SET published_at = now()",
    "delete-outbox": "DELETE FROM outbox",
}


@pytest.mark.parametrize("statement", list(DENIED.values()), ids=list(DENIED))
async def test_ac4_the_app_cannot_update_or_delete_audit_events_or_the_outbox(
    statement: str,
) -> None:
    ctx = _ctx()
    await _commit_one(ctx)
    audit_before, outbox_before = await _audit(ctx), await _outbox(ctx)
    with pytest.raises(DBAPIError, match="permission denied"):
        async with tenant_connection(ctx) as conn:
            await conn.execute(text(statement))
    assert await _audit(ctx) == audit_before
    assert await _outbox(ctx) == outbox_before


# --- tenant isolation of audit rows and outbox rows ---------------------------------------------


async def test_ac4_another_tenants_unit_of_work_cannot_see_audit_rows_or_outbox_rows() -> None:
    a, b = _ctx(), _ctx()
    await _commit_one(a)
    await _commit_one(b)
    assert [r["tenant_id"] for r in await _audit(a)] == [a.tenant_id]
    assert [r["tenant_id"] for r in await _audit(b)] == [b.tenant_id]
    assert [r["tenant_id"] for r in await _outbox(a)] == [a.tenant_id]
    assert [r["tenant_id"] for r in await _outbox(b)] == [b.tenant_id]


async def test_ac4_inside_another_tenants_unit_of_work_the_first_tenants_rows_are_invisible() -> (
    None
):
    a, b = _ctx(), _ctx()
    await _commit_one(a)
    async with uow(b) as tx:
        tx.record("probe.touched", target=Target("probe", "1"))
        seen = (await tx.session.execute(text("SELECT count(*) FROM audit_events"))).scalar_one()
        assert seen == 0
        seen_outbox = (await tx.session.execute(text("SELECT count(*) FROM outbox"))).scalar_one()
        assert seen_outbox == 0


# --- outbox rows ------------------------------------------------------------------------------


async def test_ac4_outbox_row_id_equals_the_events_event_id_and_payload_round_trips() -> None:
    ctx = _ctx()
    event = await _commit_one(ctx)
    [row] = await _outbox(ctx)
    assert row["id"] == event.event_id
    assert row["event_type"] == "probe.done"
    payload = cast(dict[str, object], row["payload"])
    assert payload["probe_id"] == str(event.probe_id)
    assert payload["label"] == "made"
    assert row["published_at"] is None
    assert row["attempts"] == 0
    assert row["last_error"] is None


async def test_ac4_every_emitted_event_gets_its_own_outbox_row() -> None:
    ctx = _ctx()
    events = [await _commit_one(ctx) for _ in range(3)]
    assert [o["id"] for o in await _outbox(ctx)] == [e.event_id for e in events]


# --- validation at record and emit -----------------------------------------------------------


@pytest.mark.parametrize(
    "action", ["created", "Probe.created", "probe.Created", "probe.created.now", "1probe.x", ""]
)
async def test_ac4_an_invalid_action_raises_value_error_and_nothing_is_written(
    action: str,
) -> None:
    ctx = _ctx()
    with pytest.raises(ValueError):
        async with uow(ctx) as tx:
            tx.record(action, target=Target("probe", "1"))
    assert await _audit(ctx) == []


async def test_ac4_emitting_an_event_with_a_restricted_field_raises_and_writes_nothing() -> None:
    ctx = _ctx()
    probe_id = uuid.uuid4()
    with pytest.raises(ValueError):
        async with uow(ctx) as tx:
            await tx.session.execute(
                PROBE.insert().values(id=probe_id, tenant_id=ctx.tenant_id, body="x")
            )
            tx.record("probe.created", target=Target("probe", probe_id))
            tx.emit(SecretEvent(probe_id=probe_id, taxpayer_note="n"))
    assert await _probe_ids(ctx) == []
    assert await _audit(ctx) == []
    assert await _outbox(ctx) == []


async def test_ac4_emitting_an_event_with_an_unclassified_field_raises() -> None:
    ctx = _ctx()
    with pytest.raises(ValueError):
        async with uow(ctx) as tx:
            tx.record("probe.created", target=Target("probe", "1"))
            tx.emit(UntaggedEvent(probe_id=uuid.uuid4(), note="n"))
    assert await _audit(ctx) == []
    assert await _outbox(ctx) == []


# --- column-level INSERT for the app ------------------------------------------------------------

AUDIT_FORBIDDEN_COLUMNS = {
    "seq": "INSERT INTO audit_events (seq, tenant_id, actor_kind, actor_id, action, target_type, "
    "target_id) OVERRIDING SYSTEM VALUE VALUES (1, :t, :k, :a, 'probe.checked', 'probe', '1')",
    "id": "INSERT INTO audit_events (id, tenant_id, actor_kind, actor_id, action, target_type, "
    "target_id) VALUES (gen_random_uuid(), :t, :k, :a, 'probe.checked', 'probe', '1')",
    "occurred_at": "INSERT INTO audit_events (occurred_at, tenant_id, actor_kind, actor_id, "
    "action, target_type, target_id) VALUES (now(), :t, :k, :a, 'probe.checked', 'probe', '1')",
}
OUTBOX_FORBIDDEN_COLUMNS = {
    "published_at": "now()",
    "attempts": "3",
    "last_error": "'ValueError'",
    "next_attempt_at": "now()",
}
OUTBOX_INSERT = (
    "INSERT INTO outbox (id, tenant_id, event_type, payload{extra_cols}) "
    "VALUES (:id, :t, 'probe.direct', CAST('{{}}' AS jsonb){extra_vals})"
)
OUTBOX_PLAIN_INSERT = OUTBOX_INSERT.format(extra_cols="", extra_vals="")
OUTBOX_FORBIDDEN_INSERTS = {
    column: OUTBOX_INSERT.format(extra_cols=f", {column}", extra_vals=f", {value}")
    for column, value in OUTBOX_FORBIDDEN_COLUMNS.items()
}


@pytest.mark.parametrize(
    "statement", list(AUDIT_FORBIDDEN_COLUMNS.values()), ids=list(AUDIT_FORBIDDEN_COLUMNS)
)
async def test_ac4_the_app_cannot_insert_audit_columns_it_does_not_own(statement: str) -> None:
    ctx = _ctx()
    with pytest.raises(DBAPIError, match="permission denied"):
        async with tenant_connection(ctx) as conn:
            await conn.execute(
                text(statement),
                {"t": ctx.tenant_id, "k": ctx.actor_kind, "a": ctx.actor_id},
            )


async def test_ac4_the_app_can_insert_a_plain_outbox_row_directly() -> None:
    ctx = _ctx()
    async with tenant_connection(ctx) as conn:
        await conn.execute(
            text(OUTBOX_PLAIN_INSERT),
            {"id": uuid.uuid4(), "t": ctx.tenant_id},
        )


@pytest.mark.parametrize("column", list(OUTBOX_FORBIDDEN_COLUMNS))
async def test_ac4_the_app_cannot_insert_an_outbox_row_that_is_already_processed(
    column: str,
) -> None:
    ctx = _ctx()
    statement = OUTBOX_FORBIDDEN_INSERTS[column]
    with pytest.raises(DBAPIError, match="permission denied"):
        async with tenant_connection(ctx) as conn:
            await conn.execute(text(statement), {"id": uuid.uuid4(), "t": ctx.tenant_id})


# --- CHECK constraints ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "target_id", ["abc", "p-1", "", "1 2", "12a", "-1", "DROP TABLE x", "x" * 100]
)
async def test_ac4_the_database_rejects_a_target_id_that_is_neither_a_uuid_nor_digits(
    target_id: str,
) -> None:
    ctx = _ctx()
    with pytest.raises(DBAPIError, match=r"check constraint|violates"):
        async with tenant_connection(ctx) as conn:
            await conn.execute(
                text(
                    "INSERT INTO audit_events (tenant_id, actor_kind, actor_id, action, "
                    "target_type, target_id) VALUES (:t, :k, :a, 'probe.checked', 'probe', :id)"
                ),
                {"t": ctx.tenant_id, "k": ctx.actor_kind, "a": ctx.actor_id, "id": target_id},
            )


@pytest.mark.parametrize("target_id", ["1", "0042", str(uuid.uuid4())])
async def test_ac4_the_database_accepts_a_uuid_or_digit_target_id(target_id: str) -> None:
    ctx = _ctx()
    async with tenant_connection(ctx) as conn:
        await conn.execute(
            text(
                "INSERT INTO audit_events (tenant_id, actor_kind, actor_id, action, "
                "target_type, target_id) VALUES (:t, :k, :a, 'probe.checked', 'probe', :id)"
            ),
            {"t": ctx.tenant_id, "k": ctx.actor_kind, "a": ctx.actor_id, "id": target_id},
        )


# --- outbox primary key is (tenant_id, id) ----------------------------------------------------


async def test_ac4_two_tenants_can_commit_the_same_event_id() -> None:
    a, b = _ctx(), _ctx()
    event = ProbeDone(probe_id=uuid.uuid4(), label="shared")
    for ctx in (a, b):
        async with uow(ctx) as tx:
            tx.record("probe.created", target=Target("probe", "1"))
            tx.emit(event)
    assert [o["id"] for o in await _outbox(a)] == [event.event_id]
    assert [o["id"] for o in await _outbox(b)] == [event.event_id]


# --- no nesting -------------------------------------------------------------------------------


@pytest.mark.parametrize("same_tenant", [True, False], ids=["same-tenant", "other-tenant"])
async def test_ac4_a_nested_unit_of_work_raises_and_the_inner_one_writes_nothing(
    same_tenant: bool,
) -> None:
    outer_ctx = _ctx()
    inner_ctx = outer_ctx if same_tenant else _ctx()
    async with uow(outer_ctx) as outer:
        outer.record("probe.created", target=Target("probe", "1"))
        with pytest.raises(RuntimeError, match="nested unit of work"):
            async with uow(inner_ctx) as inner:
                inner.record("probe.nested", target=Target("probe", "2"))
    assert [a["action"] for a in await _audit(outer_ctx)] == ["probe.created"]
    if not same_tenant:
        assert await _audit(inner_ctx) == []


async def test_ac4_units_of_work_can_run_one_after_another_and_concurrently() -> None:
    ctx = _ctx()
    await _commit_one(ctx)
    await _commit_one(ctx)
    await asyncio.gather(_commit_one(_ctx()), _commit_one(_ctx()))
    assert len(await _audit(ctx)) == 2
