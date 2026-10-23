"""P-06-T10 against Postgres (SPEC-319 AC-11 to AC-14): send needs a due date, passes the scope
check and refuses unchanged model wording, holds the email for the 10-s Undo; delete only a
never-sent Draft; waive with a reason; the client's Ignore leaves the status and the firm's return
clears it; a delegate gets a `request_item` grant on one request; upload intents feed the live
poll; incorporate moves a pending request on."""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator
from datetime import timedelta

import pytest

import abacus.modules.communications.api  # registers the client-text scope check
from abacus.kernel import clock
from abacus.kernel.config import settings
from abacus.kernel.db import configure_engine, configure_relay_engine, dispose_engine
from abacus.kernel.flags import forget_flags
from abacus.modules.requests import lifecycle
from abacus.modules.requests.binders import DueDateRequired, UndoWindowClosed
from abacus.modules.requests.lifecycle import (
    ContactNotPortalUser,
    ItemPatch,
    ModelTextNotPermitted,
    NotIgnored,
    OutOfScope,
    RequestAlreadySent,
    RequestClosed,
)

from .agent_tests.support import Person, Seeder
from .conftest import MigratedDatabase
from .test_binder_lifecycle import T0, World, make_world

assert abacus.modules.communications.api


@pytest.fixture(autouse=True)
async def engines(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    forget_flags()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    configure_relay_engine(migrated_db.relay_url)
    yield
    await dispose_engine()
    settings.cache_clear()
    forget_flags()


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


async def _ready(seed: Seeder) -> tuple[World, uuid.UUID]:
    world = await make_world(seed)
    partner = Person(world.partner.user_id, world.tenant)
    await seed.confirm(world.engagement, partner)  # `request_item.send` needs independence
    return world, await world.binder()


async def _row(seed: Seeder, item: uuid.UUID) -> dict[str, object]:
    return dict(
        (
            await seed.rows(
                "SELECT status, client_visible, sent_at, sent_by, client_ignored_at, deleted_at, "
                "na_reason, incorporation_state FROM request_items WHERE id = $1",
                item,
            )
        )[0]
    )


async def test_ac11_send_holds_the_email_and_undo_puts_the_draft_back(seed: Seeder) -> None:
    world, binder = await _ready(seed)
    item = await world.item(binder, visible=False)
    with clock.frozen(T0):
        await lifecycle.send_item(world.partner, world.engagement, item)
    row = await _row(seed, item)
    assert row["status"] == "requested" and row["sent_by"] == world.partner.user_id
    held = await seed.rows(
        "SELECT not_before, grant_id FROM outbox WHERE tenant_id = $1 "
        "AND event_type = 'request_item.sent' AND payload->>'request_item_id' = $2",
        world.tenant,
        str(item),
    )
    assert len(held) == 1 and held[0]["grant_id"] is not None
    assert held[0]["not_before"] == T0 + timedelta(seconds=10)
    with clock.frozen(T0 + timedelta(seconds=8)):
        await lifecycle.undo_send(world.partner, world.engagement, item)
    row = await _row(seed, item)
    assert row["status"] == "draft" and row["sent_at"] is None
    with clock.frozen(T0 + timedelta(seconds=20)), pytest.raises(UndoWindowClosed):
        await lifecycle.undo_send(world.partner, world.engagement, item)
    assert await world.actions(item) == ["request_item.sent", "request_item.send_undone"]


async def test_ac11_send_needs_a_due_date_and_in_scope_wording(seed: Seeder) -> None:
    world, binder = await _ready(seed)
    undated = await world.item(binder, visible=False, due=None)
    with pytest.raises(DueDateRequired):
        await lifecycle.send_item(world.partner, world.engagement, undated)
    other = await seed.value(
        "INSERT INTO clients (tenant_id, name) VALUES ($1, 'Harbor Ridge Holdings') RETURNING id",
        world.tenant,
    )
    await seed.run(
        "INSERT INTO client_entities (tenant_id, client_id, name) "
        "VALUES ($1, $2, 'Harbor Ridge Holdings')",
        world.tenant,
        other,
    )
    leaky = await world.item(
        binder, visible=False, description="Send the Harbor Ridge Holdings statements too"
    )
    with pytest.raises(OutOfScope):
        await lifecycle.send_item(world.partner, world.engagement, leaky)
    assert (await _row(seed, leaky))["sent_at"] is None  # nothing was sent


async def test_dv11_unchanged_model_wording_is_refused_until_edited(seed: Seeder) -> None:
    world, binder = await _ready(seed)
    wording = "Please upload the 2025 brokerage statements"
    item = await world.item(binder, visible=False, description=wording)
    await seed.run(
        "UPDATE request_items SET drafted_by_run_id = $2, drafted_wording_source = 'model', "
        "drafted_wording_fingerprint = $3 WHERE id = $1",
        item,
        uuid.uuid4(),
        hashlib.sha256(wording.encode()).hexdigest(),
    )
    with pytest.raises(ModelTextNotPermitted):
        await lifecycle.send_item(world.partner, world.engagement, item)
    await lifecycle.update_item(
        world.partner,
        world.engagement,
        item,
        ItemPatch({"description": "Upload your 2025 brokerage statements, every account"}),
    )
    with clock.frozen(T0):
        await lifecycle.send_item(world.partner, world.engagement, item)
    assert (await _row(seed, item))["status"] == "requested"


async def test_ac13_only_a_never_sent_draft_is_deleted(seed: Seeder) -> None:
    world, binder = await _ready(seed)
    draft = await world.item(binder, visible=False)
    await lifecycle.delete_item(world.partner, world.engagement, draft)
    assert (await _row(seed, draft))["deleted_at"] is not None
    sent = await world.item(binder, visible=False)
    with clock.frozen(T0):
        await lifecycle.send_item(world.partner, world.engagement, sent)
    with pytest.raises(RequestAlreadySent):
        await lifecycle.delete_item(world.partner, world.engagement, sent)


async def test_ac12_waive_closes_with_a_reason(seed: Seeder) -> None:
    world, binder = await _ready(seed)
    item = await world.item(binder)
    await lifecycle.waive_item(
        world.partner, world.engagement, item, "firm_waived", "Covered by the custodian file"
    )
    row = await _row(seed, item)
    assert row["status"] == "not_applicable" and row["na_reason"] == "firm_waived"
    with pytest.raises(RequestClosed):
        await lifecycle.update_item(
            world.partner, world.engagement, item, ItemPatch({"title": "Brokerage"})
        )


async def test_ac12_the_clients_ignore_keeps_the_status_and_the_firm_returns_it(
    seed: Seeder,
) -> None:
    world, binder = await _ready(seed)
    item = await world.item(binder)
    owner = await world.client_user("owner")
    with pytest.raises(NotIgnored):
        await lifecycle.return_to_client(world.partner, world.engagement, item)
    await lifecycle.ignore_item(owner, item, "sent_another_way", "Mailed in August")
    row = await _row(seed, item)
    assert row["status"] == "requested" and row["client_ignored_at"] is not None
    await lifecycle.return_to_client(world.partner, world.engagement, item)
    assert (await _row(seed, item))["client_ignored_at"] is None
    assert "request_item.ignored" in await world.actions(item)


async def test_ac13_a_delegate_gets_one_request_grant(seed: Seeder) -> None:
    world, binder = await _ready(seed)
    item = await world.item(binder)
    contact = await world.contact("Tess Moreno")
    with pytest.raises(ContactNotPortalUser):
        await lifecycle.delegate_item(world.partner, world.engagement, item, contact)
    delegate = await seed.person(world.tenant)
    await seed.run(  # a portal user: a client membership
        "UPDATE memberships SET kind = 'client' WHERE tenant_id = $1 AND user_id = $2",
        world.tenant,
        delegate.user_id,
    )
    await seed.run("UPDATE contacts SET user_id = $2 WHERE id = $1", contact, delegate.user_id)
    found = await lifecycle.delegate_item(world.partner, world.engagement, item, contact)
    grant = await seed.rows(
        "SELECT user_id, role, scope_kind, scope_id FROM client_access_grants WHERE id = $1",
        found.grant_id,
    )
    assert dict(grant[0]) == {
        "user_id": delegate.user_id,
        "role": "delegate",
        "scope_kind": "request_item",
        "scope_id": item,
    }
    assert (
        await seed.value(
            "SELECT count(*) FROM request_delegations WHERE request_item_id = $1", item
        )
        == 1
    )


async def test_ac14_upload_intents_feed_the_live_poll(seed: Seeder) -> None:
    world, binder = await _ready(seed)
    item = await world.item(binder)  # client-visible, so already `requested`
    await world.seed.run("UPDATE request_lists SET status = 'published' WHERE id = $1", binder)
    owner = await world.client_user("owner")
    await lifecycle.announce_upload(owner, item, 2)
    live, _at = await lifecycle.binder_live(world.partner, binder)
    [row] = [r for r in live if r.request_item_id == item]
    assert row.uploading_files == 2 and row.inbox_waiting == 0 and not row.screening_running


async def test_incorporate_moves_a_pending_request_on(seed: Seeder) -> None:
    world, binder = await _ready(seed)
    item = await world.item(binder)
    await seed.run(
        "UPDATE request_items SET incorporation_state = 'pending_incorporation' WHERE id = $1",
        item,
    )
    await lifecycle.incorporate_item(world.partner, world.engagement, item)
    assert (await _row(seed, item))["incorporation_state"] == "incorporated"
