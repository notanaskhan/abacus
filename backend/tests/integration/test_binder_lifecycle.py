"""P-06-T07 against Postgres (SPEC-319 AC-5 to AC-9; ADR-161, DEC-24): "Publishing before G3
answers 409 binder_gate_unmet except for intake binders, and Undo within 10 seconds leaves no
email."

The service runs as the app role (grants and row-level security as production uses them); seed
rows go through the superuser (the shared Seeder). The firm is synthetic, so a frozen business
clock moves `abacus_now()` too: the Undo window and the publish grant read the same time.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import cast

import pytest
from sqlalchemy import text

from abacus.kernel import clock
from abacus.kernel.config import settings
from abacus.kernel.db import (
    TenantContext,
    configure_engine,
    configure_relay_engine,
    dispose_engine,
    relay_engine,
)
from abacus.kernel.errors import DomainInvalid, NotFound
from abacus.kernel.flags import forget_flags
from abacus.kernel.uow.relay import InMemoryPublisher, OutboxEvent, relay_once
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.requests import binders, contract
from abacus.modules.requests.binders import (
    BinderGateUnmet,
    BinderNotPublished,
    DueDateRequired,
    EffectStarted,
    ReasonRequired,
    UndoWindowClosed,
)

from .agent_tests.support import Person, Seeder
from .conftest import MigratedDatabase

T0 = datetime(2026, 9, 14, 14, 24, tzinfo=UTC)  # the demo instant, 9:24 AM Central
ATTEMPT = "publish-attempt-0001"  # the Idempotency-Key header value


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


@dataclass(frozen=True)
class World:
    seed: Seeder
    tenant: uuid.UUID
    partner: AuthContext
    engagement: uuid.UUID
    work_item: uuid.UUID
    client: uuid.UUID

    async def item(
        self,
        binder: uuid.UUID,
        *,
        visible: bool = True,
        due: date | None = date(2026, 10, 1),
        category: uuid.UUID | None = None,
        description: str = "Brokerage statements",
        status: str | None = None,
    ) -> uuid.UUID:
        made = cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO request_items (tenant_id, engagement_id, request_list_id, "
                "description, audit_area, created_by, client_visible, due_on, category_id) "
                "VALUES ($1, $2, $3, $4, 'Income', $5, $6, $7, $8) RETURNING id",
                self.tenant,
                self.engagement,
                binder,
                description,
                self.partner.user_id,
                visible,
                due,
                category,
            ),
        )
        if status is not None:
            await self.seed.run("UPDATE request_items SET status = $2 WHERE id = $1", made, status)
        return made

    async def category(self, binder: uuid.UUID, name: str, position: int) -> uuid.UUID:
        return cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO request_categories (tenant_id, request_list_id, name, position) "
                "VALUES ($1, $2, $3, $4) RETURNING id",
                self.tenant,
                binder,
                name,
                position,
            ),
        )

    async def contact(self, name: str) -> uuid.UUID:
        return cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO contacts (tenant_id, client_id, display_name, contact_kind) "
                "VALUES ($1, $2, $3, 'client_person') RETURNING id",
                self.tenant,
                self.client,
                name,
            ),
        )

    async def client_user(self, role: str = "owner") -> AuthContext:
        """A client user with an engagement-scope grant (`owner` is the client admin)."""
        who = await self.seed.person(self.tenant)
        await self.seed.run(
            "UPDATE memberships SET kind = 'client' WHERE tenant_id = $1 AND user_id = $2",
            self.tenant,
            who.user_id,
        )
        await self.seed.run(
            "INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id) "
            "VALUES ($1, $2, $3, 'engagement', $4)",
            self.tenant,
            who.user_id,
            role,
            self.engagement,
        )
        return who.context()

    async def binder(self, kind: str = "pbc", name: str = "2025 Binder") -> uuid.UUID:
        with clock.frozen(T0 - timedelta(minutes=5)):
            view = await binders.create_binder(
                self.partner,
                work_item_id=self.work_item,
                kind=kind,
                name=name,
                from_binder_id=None,
                template_ref=None,
            )
        return view.id

    async def status(self, binder: uuid.UUID) -> str:
        return str(await self.seed.value("SELECT status FROM request_lists WHERE id = $1", binder))

    async def actions(self, target: uuid.UUID) -> list[str]:
        rows = await self.seed.rows(
            "SELECT action FROM audit_events WHERE tenant_id = $1 AND target_id = $2 ORDER BY seq",
            self.tenant,
            str(target),
        )
        return [str(r["action"]) for r in rows]


async def _world(seed: Seeder) -> World:
    tenant = await seed.firm()
    await seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", tenant)
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'binders.engine', 'true', 'test-seed', 'P-06-T07 tests')",
        tenant,
    )
    partner: Person = await seed.person(tenant)
    entity = await seed.entity(tenant)
    engagement = await seed.engagement(tenant, entity, partner.user_id)
    await seed.member(engagement, partner, "engagement_partner")
    work_item = cast(
        uuid.UUID,
        await seed.value("SELECT id FROM work_items WHERE engagement_id = $1", engagement),
    )
    client = cast(
        uuid.UUID, await seed.value("SELECT client_id FROM engagements WHERE id = $1", engagement)
    )
    return World(seed, tenant, partner.context(), engagement, work_item, client)


# P-06-T10's suite builds the same world.
make_world = _world


async def _drain() -> None:
    """Leftovers from other tests are marked published, so a relay pass sees only its own."""
    async with relay_engine().begin() as conn:
        await conn.execute(
            text("UPDATE outbox SET published_at = now() WHERE published_at IS NULL")
        )


async def _relay(at: datetime) -> list[OutboxEvent]:
    publisher = InMemoryPublisher()
    with clock.frozen(at):
        for _ in range(3):
            await relay_once(publisher)
    return publisher.published


def _published(events: list[OutboxEvent], binder: uuid.UUID) -> list[OutboxEvent]:
    return [
        e
        for e in events
        if e.event_type == "binder.published" and e.payload.get("binder_id") == str(binder)
    ]


# --- AC-5: G3 and due dates -------------------------------------------------------------------


async def test_ac5_publishing_before_g3_is_refused_except_an_intake_binder(seed: Seeder) -> None:
    world = await _world(seed)
    await seed.run("UPDATE firms SET require_letter = true WHERE tenant_id = $1", world.tenant)
    pbc, intake = await world.binder("pbc"), await world.binder("intake", "Intake")
    await world.item(pbc)
    with clock.frozen(T0), pytest.raises(BinderGateUnmet) as refused:
        await binders.publish_binder(world.partner, pbc)
    assert refused.value.facts == {"gate": "G3"}
    assert await world.status(pbc) == "draft"
    with clock.frozen(T0):
        published = await binders.publish_binder(world.partner, intake)
    assert published.status == "published"
    await seed.run(
        "INSERT INTO engagement_letters (tenant_id, engagement_id, status, recorded_by) "
        "VALUES ($1, $2, 'signed', 'test-seed')",
        world.tenant,
        world.engagement,
    )
    with clock.frozen(T0):
        assert (await binders.publish_binder(world.partner, pbc)).status == "published"


async def test_ac5_requests_without_a_due_date_are_named_and_nothing_changes(
    seed: Seeder,
) -> None:
    world = await _world(seed)
    binder = await world.binder()
    first, second = await world.item(binder, due=None), await world.item(binder, due=None)
    await world.item(binder, visible=False, due=None)  # internal-only: not sent, no date needed
    with clock.frozen(T0), pytest.raises(DueDateRequired) as refused:
        await binders.publish_binder(world.partner, binder)
    named = {v for k, v in refused.value.facts.items() if k.startswith("request_item_")}
    assert named == {str(first), str(second)} and refused.value.facts["count"] == 2
    assert await world.status(binder) == "draft"
    assert "binder.published" not in await world.actions(binder)


# --- AC-6: publish, the held email and Undo -----------------------------------------------------


async def test_ac6_publish_holds_the_email_and_undo_within_ten_seconds_sends_none(
    seed: Seeder,
) -> None:
    await _drain()
    world = await _world(seed)
    undone, kept = await world.binder(), await world.binder(name="2025 Binder pt 2")
    sent = await world.item(undone)
    internal = await world.item(undone, visible=False)
    await world.item(kept)
    with clock.frozen(T0):
        view = await binders.publish_binder(world.partner, undone)
        await binders.publish_binder(world.partner, kept)
    assert view.status == "published" and view.undo_until == T0 + timedelta(seconds=10)
    assert view.published_by == world.partner.user_id
    sent_at = await seed.value("SELECT sent_at FROM request_items WHERE id = $1", sent)
    assert sent_at == T0
    assert await seed.value("SELECT sent_at FROM request_items WHERE id = $1", internal) is None
    held = await seed.rows(
        "SELECT not_before, grant_id FROM outbox WHERE tenant_id = $1 "
        "AND event_type = 'binder.published' AND payload->>'binder_id' = $2",
        world.tenant,
        str(undone),
    )
    assert len(held) == 1 and held[0]["grant_id"] is not None
    assert held[0]["not_before"] == T0 + timedelta(seconds=10)

    # Nothing goes inside the window, Undo or not: the grant isn't due, so the relay retries.
    assert _published(await _relay(T0 + timedelta(seconds=5)), kept) == []
    await seed.run(  # the retry's backoff (real time) has passed
        "UPDATE outbox SET next_attempt_at = NULL WHERE tenant_id = $1", world.tenant
    )
    with clock.frozen(T0 + timedelta(seconds=9)):
        back = await binders.undo_publish(world.partner, undone)
    assert back.status == "draft" and back.published_at is None and back.undo_until is None
    assert await seed.value("SELECT sent_at FROM request_items WHERE id = $1", sent) is None
    assert await world.actions(undone) == [
        "binder.created",
        "binder.published",
        "binder.publish_undone",
    ]
    assert "request_item.send_undone" in await world.actions(sent)

    delivered = await _relay(T0 + timedelta(seconds=11))
    assert _published(delivered, undone) == []  # Undo within 10 s: no email
    assert len(_published(delivered, kept)) == 1  # the control: its grant was consumed


async def test_ac6_undo_after_ten_seconds_is_refused(seed: Seeder) -> None:
    world = await _world(seed)
    binder = await world.binder()
    await world.item(binder)
    with clock.frozen(T0):
        await binders.publish_binder(world.partner, binder)
    with clock.frozen(T0 + timedelta(seconds=10)), pytest.raises(UndoWindowClosed):
        await binders.undo_publish(world.partner, binder)
    assert await world.status(binder) == "published"
    with clock.frozen(T0), pytest.raises(UndoWindowClosed):  # a draft has nothing to undo
        await binders.undo_publish(world.partner, await world.binder(name="Other"))


async def test_ac6_undo_after_the_delivery_consumed_the_grant_is_refused(seed: Seeder) -> None:
    await _drain()
    world = await _world(seed)
    binder = await world.binder()
    await world.item(binder)
    with clock.frozen(T0):
        await binders.publish_binder(world.partner, binder)
    assert len(_published(await _relay(T0 + timedelta(seconds=11)), binder)) == 1
    with clock.frozen(T0 + timedelta(seconds=12)), pytest.raises(UndoWindowClosed):
        await binders.undo_publish(world.partner, binder)
    # The window by the binder's own stamp open again (a skewed clock): the consumed grant
    # still refuses, and nothing is undone.
    await seed.run(
        "UPDATE request_lists SET published_at = published_at + interval '5 seconds' "
        "WHERE id = $1",
        binder,
    )
    with clock.frozen(T0 + timedelta(seconds=12)), pytest.raises(EffectStarted):
        await binders.undo_publish(world.partner, binder)
    assert await world.status(binder) == "published"


async def test_ac6_a_retried_publish_with_the_same_key_sends_nothing_twice(seed: Seeder) -> None:
    world = await _world(seed)
    binder = await world.binder()
    await world.item(binder)
    with clock.frozen(T0):
        first = await contract.publish_binder_route(binder, world.partner, ATTEMPT)
    with clock.frozen(T0 + timedelta(seconds=2)):
        again = await contract.publish_binder_route(binder, world.partner, ATTEMPT)
    assert again == first and first.status == "published"
    held = await seed.value(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 AND event_type = 'binder.published'",
        world.tenant,
    )
    assert held == 1
    assert (await world.actions(binder)).count("binder.published") == 1


async def test_flag_off_every_binder_route_answers_404(seed: Seeder) -> None:
    world = await _world(seed)
    binder = await world.binder()
    await seed.run(
        "UPDATE feature_flag_states SET value = 'false' WHERE tenant_id = $1", world.tenant
    )
    forget_flags()
    with pytest.raises(NotFound):
        await contract.get_binder_route(binder, world.partner)
    with pytest.raises(NotFound):
        await contract.publish_binder_route(binder, world.partner, ATTEMPT)


# --- AC-7: unpublish ----------------------------------------------------------------------------


async def test_ac7_unpublish_needs_a_reason_seals_it_and_hides_the_binder_from_the_client(
    seed: Seeder,
) -> None:
    world = await _world(seed)
    binder = await world.binder()
    await world.item(binder)
    client = await world.client_user()
    with pytest.raises(NotFound):  # a Draft binder doesn't exist for the client (INV-4)
        await binders.read_binder(client, binder)
    with clock.frozen(T0):
        await binders.publish_binder(world.partner, binder)
    assert (await binders.read_binder(client, binder)).status == "published"
    assert len((await binders.binder_requests(client, binder, None, None)).items) == 1
    with clock.frozen(T0 + timedelta(minutes=1)), pytest.raises(ReasonRequired):
        await binders.unpublish_binder(world.partner, binder, "   ")
    reason = "fixing 2 requests"
    with clock.frozen(T0 + timedelta(minutes=1)):
        view = await binders.unpublish_binder(world.partner, binder, reason)
    assert view.status == "unpublished" and view.unpublish_reason == reason
    assert view.unpublished_by == world.partner.user_id
    assert view.unpublished_at == T0 + timedelta(minutes=1)
    sealed = cast(
        bytes,
        await seed.value(
            "SELECT unpublish_reason_sealed FROM request_lists WHERE id = $1", binder
        ),
    )
    assert reason.encode() not in sealed
    after = await seed.value(
        "SELECT after_ref->>'reason' FROM audit_events WHERE action = 'binder.unpublished' "
        "AND target_id = $1",
        str(binder),
    )
    assert after == hashlib.sha256(reason.encode()).hexdigest()
    with pytest.raises(NotFound):
        await binders.read_binder(client, binder)
    with pytest.raises(NotFound):
        await binders.binder_requests(client, binder, None, None)
    with pytest.raises(BinderNotPublished):
        await binders.unpublish_binder(world.partner, binder, reason)


# --- AC-8: duplicate as part n; recipients -------------------------------------------------------


async def test_ac8_duplicate_is_an_empty_draft_with_the_next_part_sections_and_recipients(
    seed: Seeder,
) -> None:
    world = await _world(seed)
    binder = await world.binder(name="2025 Binder")
    income = await world.category(binder, "Income", 0)
    await world.category(binder, "Deductions", 1)
    await world.item(binder, category=income)
    claire = await world.contact("Claire Feld")
    with clock.frozen(T0):
        await binders.set_recipients(world.partner, binder, [claire])
        second = await binders.duplicate_binder(world.partner, binder)
        third = await binders.duplicate_binder(world.partner, second.id)
    assert (second.name, second.part, second.status) == ("2025 Binder pt 2", 2, "draft")
    assert (third.name, third.part) == ("2025 Binder pt 3", 3)
    assert [c.name for c in second.categories] == ["Income", "Deductions"]
    assert second.total_count == 0
    assert [r.contact_id for r in second.recipients] == [claire]
    assert [r.name for r in second.recipients] == ["Claire Feld"]
    assert await world.actions(second.id) == ["binder.duplicated"]


async def test_recipients_keep_an_insert_only_history(seed: Seeder) -> None:
    world = await _world(seed)
    binder = await world.binder()
    claire, paul = await world.contact("Claire Feld"), await world.contact("Paul Thornbury")
    with clock.frozen(T0):
        await binders.set_recipients(world.partner, binder, [claire, paul])
    with clock.frozen(T0 + timedelta(minutes=1)):
        view = await binders.set_recipients(world.partner, binder, [paul])
    with clock.frozen(T0 + timedelta(minutes=2)):
        back = await binders.set_recipients(world.partner, binder, [paul, claire])
    assert [r.contact_id for r in view.recipients] == [paul]
    assert {r.contact_id for r in back.recipients} == {claire, paul}
    rows = await seed.rows(
        "SELECT contact_id, removed_at FROM binder_recipients WHERE binder_id = $1 "
        "ORDER BY added_at, removed_at NULLS FIRST",
        binder,
    )
    assert [(r["contact_id"], r["removed_at"] is not None) for r in rows] == [
        (claire, False),
        (paul, False),
        (claire, True),
        (claire, False),
    ]
    other = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO clients (tenant_id, name) VALUES ($1, 'Other client') RETURNING id",
            world.tenant,
        ),
    )
    stranger = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO contacts (tenant_id, client_id, display_name, contact_kind) "
            "VALUES ($1, $2, 'Not this client', 'client_person') RETURNING id",
            world.tenant,
            other,
        ),
    )
    with pytest.raises(NotFound):  # another client's contact is never a recipient
        await binders.set_recipients(world.partner, binder, [stranger])
    assert (await world.actions(binder)).count("binder.recipients_changed") == 3


# --- AC-9: the client's mark-done, and close on C1 --------------------------------------------


async def test_ac9_the_client_marks_a_published_binder_done_with_the_open_count(
    seed: Seeder,
) -> None:
    world = await _world(seed)
    binder = await world.binder()
    await world.item(binder)
    await world.item(binder, status="uploaded")
    await world.item(binder, visible=False)
    admin = await world.client_user("owner")
    contributor = await world.client_user("contributor")
    with pytest.raises(NotFound):  # a Draft binder: nothing to mark done
        await binders.mark_done(admin, binder)
    with clock.frozen(T0):
        await binders.publish_binder(world.partner, binder)
    with clock.frozen(T0 + timedelta(minutes=5)), pytest.raises(NotFound):
        await binders.mark_done(contributor, binder)  # nothing of it assigned to them
    with clock.frozen(T0 + timedelta(minutes=5)), pytest.raises(Forbidden):
        await binders.mark_done(world.partner, binder)  # the client's act, no firm role
    with clock.frozen(T0 + timedelta(minutes=5)):
        done = await binders.mark_done(admin, binder)
    assert (done.status, done.open_count) == ("complete", 1)
    assert done.marked_done_at == T0 + timedelta(minutes=5)
    view = await binders.read_binder(world.partner, binder)
    assert view.marked_done_by == admin.user_id and view.marked_done_open_count == 1
    with pytest.raises(BinderNotPublished):
        await binders.mark_done(admin, binder)
    marked = await seed.value(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 AND event_type = 'binder.marked_done'",
        world.tenant,
    )
    assert marked == 1


async def test_ac9_a_terminal_status_closes_the_binders_as_the_system(seed: Seeder) -> None:
    world = await _world(seed)
    draft, published = await world.binder(), await world.binder(name="Second")
    await world.item(published)
    with clock.frozen(T0):
        await binders.publish_binder(world.partner, published)

    def changed(to: str) -> OutboxEvent:
        return OutboxEvent(
            uuid.uuid4(),
            world.tenant,
            "engagement.status_changed",
            {"engagement_id": str(world.engagement), "from_status": "active", "to_status": to},
        )

    await binders.close_on_status_changed(changed("on_hold"))  # not terminal: nothing closes
    assert await world.status(draft) == "draft"
    with clock.frozen(T0 + timedelta(days=30)):
        await binders.close_on_status_changed(changed("delivered"))
        await binders.close_on_status_changed(changed("delivered"))  # a redelivery: no-op
    for binder in (draft, published):
        row = await seed.rows(
            "SELECT status, closed_at, closed_reason FROM request_lists WHERE id = $1", binder
        )
        assert (row[0]["status"], row[0]["closed_reason"]) == ("closed", "work_delivered")
        assert row[0]["closed_at"] == T0 + timedelta(days=30)
        closed = await seed.rows(
            "SELECT actor_kind FROM audit_events WHERE action = 'binder.closed' "
            "AND target_id = $1",
            str(binder),
        )
        assert [r["actor_kind"] for r in closed] == ["system"]


# --- Create from the prior year; reads ----------------------------------------------------------


async def test_create_from_the_prior_year_binder_copies_sections_and_requests(
    seed: Seeder,
) -> None:
    world = await _world(seed)
    prior = await world.binder(name="2024 Binder")
    income = await world.category(prior, "Income", 0)
    await world.item(prior, category=income, description="Form W-2")
    await world.item(prior, visible=False, description="Prior-year return")
    await seed.run(
        "UPDATE request_items SET still_needed = 'Page 2' WHERE request_list_id = $1", prior
    )
    with clock.frozen(T0):
        view = await binders.create_binder(
            world.partner,
            work_item_id=world.work_item,
            kind="pbc",
            name="2025 Binder",
            from_binder_id=prior,
            template_ref=None,
        )
    assert (view.created_from, view.prior_year_source_ref, view.part) == (
        "prior_year_binder",
        prior,
        2,
    )
    assert [c.name for c in view.categories] == ["Income"] and view.total_count == 2
    rows = await seed.rows(
        "SELECT description, source_tag, client_visible, still_needed, due_on, category_id "
        "FROM request_items WHERE request_list_id = $1 ORDER BY description",
        view.id,
    )
    assert [(r["description"], r["client_visible"]) for r in rows] == [
        ("Form W-2", True),
        ("Prior-year return", False),
    ]
    assert {r["source_tag"] for r in rows} == {"prior_year"}
    assert {r["still_needed"] for r in rows} == {None} and {r["due_on"] for r in rows} == {None}
    assert rows[0]["category_id"] == view.categories[0].id
    with pytest.raises(DomainInvalid):
        await binders.create_binder(
            world.partner,
            work_item_id=world.work_item,
            kind="pbc",
            name=None,
            from_binder_id=prior,
            template_ref="firm-template-1",
        )


async def test_the_client_preview_shows_only_client_visible_requests(seed: Seeder) -> None:
    world = await _world(seed)
    binder = await world.binder()
    income = await world.category(binder, "Income", 0)
    shown = await world.item(binder, category=income, description="Form 1099-B")
    await world.item(binder, visible=False, description="Workpaper tie-out")
    preview = await binders.client_preview(world.partner, binder)
    assert [(i.id, i.category_name, i.description) for i in preview.items] == [
        (shown, "Income", "Form 1099-B")
    ]
    out = contract.BinderClientPreviewOut.model_validate(preview, from_attributes=True)
    assert set(out.items[0].model_dump()) == {
        "id",
        "category_name",
        "title",
        "description",
        "status",
        "client_ignored",
        "due_on",
    }


async def test_record_rows_and_activity(seed: Seeder) -> None:
    world = await _world(seed)
    binder = await world.binder()
    income = await world.category(binder, "Income", 0)
    first = await world.item(binder, category=income)
    await world.item(binder, visible=False)
    with clock.frozen(T0):
        await binders.publish_binder(world.partner, binder)
    with clock.frozen(T0 + timedelta(minutes=1)):
        record = await contract.get_binder_route(binder, world.partner)
        rows = await contract.binder_requests_route(binder, world.partner, income, None)
        activity = await contract.binder_activity_route(binder, world.partner)
    assert record.status == "published" and record.undo_until is None
    assert {"binder.publish", "binder.read", "activity.read"} <= set(record.allowed_actions)
    assert "binder.mark_done" not in record.allowed_actions  # a client's act
    assert [(c.name, c.total_count) for c in record.categories] == [("Income", 1)]
    assert [r.id for r in rows.items] == [first] and rows.total == 1
    assert rows.counts == {"requested": 1}
    events = [(e.event_type, e.target_type) for e in activity.items]
    assert events[:2] == [("request_item.sent", "request_item"), ("binder.published", "binder")]
    assert events[-1] == ("binder.created", "binder")
    assert {e.actor_user_id for e in activity.items} == {world.partner.user_id}
    assert activity.total == len(activity.items)


async def test_another_firm_never_reaches_the_binder(seed: Seeder) -> None:
    world, other = await _world(seed), await _world(seed)
    binder = await world.binder()
    with pytest.raises(NotFound):
        await binders.read_binder(other.partner, binder)
    with clock.frozen(T0), pytest.raises(NotFound):
        await binders.publish_binder(other.partner, binder)
    stranger = AuthContext(
        TenantContext(world.tenant, "human", str(other.partner.user_id)),
        other.partner.user_id,
        uuid.uuid4(),
        None,
        datetime.now(UTC),
    )
    with pytest.raises(Forbidden):  # in the firm, but on no team of the engagement
        await binders.read_binder(stranger, binder)
