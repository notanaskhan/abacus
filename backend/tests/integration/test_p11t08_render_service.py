"""P-11-T08 (TASK-2408; C11 v1; P-11 §4.2 to §4.4) against Postgres: the generated-document
service.

The row's acceptance: a missing variable refuses with `missing_variable` instead of a blank, an
agent-requested render is always a draft, a final render without a matching human approval is
refused, and a source change marks the document out of date within one relay cycle. Also: only
declared keys reach the snapshot, the content hash is stable for the same inputs, and a locked
document takes no render.

The kind registered here is a probe (`notice_response`), its values synthetic; the template
version's declared keys come from a stub of methodology's read (its table is K-01's).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator, Mapping
from typing import cast

import pytest

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.uow import uow
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.reporting import api as c11
from abacus.modules.reporting import documents as docs

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

KIND = "notice_response"
DECLARED = ("client.name", "notice.number")
SOURCE_EVENT = "notice.changed"


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> object:
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


class Values:
    """The probe kind's provider answers; a test sets them."""

    def __init__(self) -> None:
        self.values: dict[str, str] = {"client.name": "Probe client", "notice.number": "N-1"}
        self.approved: tuple[uuid.UUID, str] | None = None


@pytest.fixture
def values(monkeypatch: pytest.MonkeyPatch) -> Iterator[Values]:
    state = Values()

    async def provider(owner: c11.OwnerRef, scope: c11.RenderScope) -> Mapping[str, str]:
        return {**state.values, "undeclared.key": "never rendered"}

    async def approval(ref: c11.ApprovalRef) -> tuple[uuid.UUID, str] | None:
        return state.approved

    async def keys(session: object, version_id: uuid.UUID) -> tuple[str, ...]:
        return DECLARED

    monkeypatch.setattr(docs, "report_template_variable_keys", keys)
    monkeypatch.setattr(c11, "_REGISTRY", {})
    c11.register_document_kind(
        c11.DocumentKind(
            kind=KIND,
            layout="letter",
            variables_provider=provider,
            approval_provider=approval,
            source_events=(SOURCE_EVENT,),
        )
    )
    yield state


async def _world(seed: Seeder) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    tenant = await seed.firm()
    person = await seed.person(tenant)
    await seed.entity(tenant)
    client = cast(
        uuid.UUID, await seed.value("SELECT id FROM clients WHERE tenant_id = $1", tenant)
    )
    return tenant, person.user_id, client


def _request(
    client: uuid.UUID,
    owner: uuid.UUID,
    requester: c11.Requester,
    **over: object,
) -> c11.RenderRequest:
    base: dict[str, object] = {
        "kind": KIND,
        "owner_ref": c11.OwnerRef("notice", owner),
        "scope": c11.RenderScope(client_id=client),
        "template_version_id": uuid.uuid4(),
        "requested_by": requester,
    }
    return c11.RenderRequest(**{**base, **over})  # pyright: ignore[reportArgumentType] -- test overrides


async def test_ac1_a_missing_variable_refuses_instead_of_a_blank(
    seed: Seeder, values: Values
) -> None:
    tenant, user, client = await _world(seed)
    values.values["notice.number"] = "   "
    person = c11.Requester("human", user_id=user)
    with pytest.raises(c11.RenderRefused) as refused:
        async with uow(TenantContext(tenant, "human", str(user))) as tx:
            await c11.render(tx, _request(client, uuid.uuid4(), person))
    assert refused.value.code == "missing_variable"
    assert "notice.number" in str(refused.value)
    assert await seed.value("SELECT count(*) FROM generated_document_versions") == 0


async def test_ac2_an_agents_render_is_always_a_draft(seed: Seeder, values: Values) -> None:
    tenant, user, client = await _world(seed)
    run = uuid.uuid4()
    agent = c11.Requester("agent", run_id=run, on_behalf_of_user_id=user)
    with pytest.raises(c11.RenderRefused):
        c11.check_render_request(
            _request(
                client,
                uuid.uuid4(),
                agent,
                mode="final",
                approval_ref=c11.ApprovalRef("probe", uuid.uuid4(), "0" * 64),
            )
        )
    async with uow(TenantContext(tenant, "agent", str(user))) as tx:
        ticket = await c11.render(tx, _request(client, uuid.uuid4(), agent))
    row = await seed.rows(
        "SELECT mode, requested_by_kind, requested_by_run_id FROM generated_document_versions "
        "WHERE generated_document_id = $1",
        ticket.generated_document_id,
    )
    assert [(r["mode"], r["requested_by_kind"], r["requested_by_run_id"]) for r in row] == [
        ("draft", "agent", run)
    ]


async def test_ac3_a_final_render_needs_a_matching_human_approval(
    seed: Seeder, values: Values
) -> None:
    tenant, user, client = await _world(seed)
    person = c11.Requester("human", user_id=user)
    ctx = TenantContext(tenant, "human", str(user))
    owner = uuid.uuid4()
    async with uow(ctx) as tx:
        ticket = await c11.render(tx, _request(client, owner, person))
    content_hash = cast(
        str,
        await seed.value(
            "SELECT content_hash FROM generated_document_versions "
            "WHERE generated_document_id = $1",
            ticket.generated_document_id,
        ),
    )
    approval = c11.ApprovalRef("probe_approval", uuid.uuid4(), content_hash)
    # Not a person's approval: refused.
    values.approved = None
    with pytest.raises(c11.RenderRefused) as not_human:
        async with uow(ctx) as tx:
            await c11.render_final(tx, ticket.generated_document_id, approval, person)
    assert not_human.value.code == "final_requires_approval"
    # An approval of another hash: refused.
    stale = c11.ApprovalRef("probe_approval", uuid.uuid4(), "f" * 64)
    with pytest.raises(c11.RenderRefused) as mismatch:
        async with uow(ctx) as tx:
            await c11.render_final(tx, ticket.generated_document_id, stale, person)
    assert mismatch.value.code == "approval_hash_mismatch"
    # A person's approval of this draft's hash: the final version.
    values.approved = (user, content_hash)
    async with uow(ctx) as tx:
        final = await c11.render_final(tx, ticket.generated_document_id, approval, person)
    assert final.version_no == 2
    modes = await seed.rows(
        "SELECT version_no, mode, content_hash FROM generated_document_versions "
        "WHERE generated_document_id = $1 ORDER BY version_no",
        ticket.generated_document_id,
    )
    assert [(r["version_no"], r["mode"], r["content_hash"]) for r in modes] == [
        (1, "draft", content_hash),
        (2, "final", content_hash),
    ]


async def test_ac4_a_source_change_marks_the_document_out_of_date(
    seed: Seeder, values: Values
) -> None:
    tenant, user, client = await _world(seed)
    person = c11.Requester("human", user_id=user)
    ctx = TenantContext(tenant, "human", str(user))
    owner = uuid.uuid4()
    async with uow(ctx) as tx:
        ticket = await c11.render(tx, _request(client, owner, person))
    assert SOURCE_EVENT in c11.SUBSCRIPTIONS
    event = OutboxEvent(
        event_id=uuid.uuid4(),
        tenant_id=tenant,
        event_type=SOURCE_EVENT,
        payload={"notice_id": str(owner)},
    )
    await c11.SUBSCRIPTIONS[SOURCE_EVENT](event)
    # A redelivery of the same event marks nothing twice.
    await c11.SUBSCRIPTIONS[SOURCE_EVENT](event)
    events = await seed.rows(
        "SELECT kind, changed_keys FROM generated_document_events "
        "WHERE generated_document_id = $1",
        ticket.generated_document_id,
    )
    assert [(e["kind"], e["changed_keys"]) for e in events] == [("out_of_date", [SOURCE_EVENT])]
    async with uow(ctx) as tx:
        view = await docs.generated_document(tx, ticket.generated_document_id)
    assert view is not None
    assert view.out_of_date is True


async def test_only_declared_keys_reach_the_snapshot_and_the_hash_is_stable(
    seed: Seeder, values: Values
) -> None:
    snapshot = docs.snapshot_of(
        layout="letter",
        template_version_id=None,
        variables=docs.declared_values(DECLARED, {**values.values, "undeclared.key": "x"})[0],
        clause_states={},
        overrides={},
    )
    assert set(cast(dict[str, str], snapshot["variables"])) == set(DECLARED)
    again = docs.snapshot_of(
        layout="letter",
        template_version_id=None,
        variables=dict(reversed(list(values.values.items()))),
        clause_states={},
        overrides={},
    )
    assert docs.canonical(snapshot) == docs.canonical(again)


async def test_a_locked_document_takes_no_render(seed: Seeder, values: Values) -> None:
    tenant, user, client = await _world(seed)
    person = c11.Requester("human", user_id=user)
    ctx = TenantContext(tenant, "human", str(user))
    owner = uuid.uuid4()
    async with uow(ctx) as tx:
        ticket = await c11.render(tx, _request(client, owner, person))
    async with uow(ctx) as tx:
        await c11.lock(tx, ticket.generated_document_id, "envelope:probe")
    with pytest.raises(c11.RenderRefused) as locked:
        async with uow(ctx) as tx:
            await c11.render(tx, _request(client, owner, person))
    assert locked.value.code == "document_locked"
