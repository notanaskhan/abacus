"""TASK-1252 against Postgres (C5 §12, SHL-20 b; DEC-220, DEC-351, DEC-368): the screening-return
follow-up is drafted from the published Return template with the files it returns; its send
records a `send_back` per file and returns the request in the grant's unit of work; delivery,
after the 10-s Undo window, sends the email and posts the shared comment; Undo puts everything
back.

The services run as the app role inside a request scope (`recording_checks`), as the routes run
them: a review decision is a person's, made while serving a request (ADR-005). Seed rows go
through the superuser; the clock is frozen, and delivery is driven by hand.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from datetime import timedelta
from typing import cast

import pytest

from abacus.kernel import clock
from abacus.kernel.config import settings
from abacus.kernel.db import configure_engine, configure_relay_engine, dispose_engine
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import forget_flags
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.agents import api as agents_api
from abacus.modules.agents import follow_up_drafts as follow_ups
from abacus.modules.agents.follow_up_drafts import FollowUpSendAlone
from abacus.modules.communications import follow_ups as composing
from abacus.modules.communications.api import RETURN_TEMPLATE
from abacus.modules.communications.follow_ups import FollowUpTemplateMissing
from abacus.modules.communications.transport import configure_transport
from abacus.modules.evidence.service import ReturnSpansRequests, Superseded
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.identity.authz import recording_checks

from .agent_tests.support import Seeder
from .backfill.follow_up_template import import_reminder_template, import_return_template
from .conftest import MigratedDatabase
from .test_binder_lifecycle import T0, World, make_world
from .test_binder_lifecycle import drain as _drain
from .test_binder_lifecycle import relay as _relay
from .test_follow_ups_v2 import Mailbox

TITLE = "Brokerage statements"
_ = agents_api  # importing the agents module registers the proposal source the send reads


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
    await import_reminder_template()
    await import_return_template()
    yield
    await dispose_engine()
    settings.cache_clear()
    forget_flags()


@pytest.fixture(autouse=True)
def mailbox() -> Iterator[Mailbox]:
    box = Mailbox()
    configure_transport(box)
    yield box
    configure_transport(None)


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


@dataclass(frozen=True)
class Upload:
    world: World
    item: uuid.UUID
    files: tuple[uuid.UUID, uuid.UUID]
    claire: AuthContext  # the client admin

    @property
    def partner(self) -> AuthContext:
        return self.world.partner

    @property
    def seed(self) -> Seeder:
        return self.world.seed

    async def status(self) -> str:
        return cast(
            str, await self.seed.value("SELECT status FROM request_items WHERE id = $1", self.item)
        )

    async def decisions(self) -> list[tuple[uuid.UUID, str, str | None]]:
        rows = await self.seed.rows(
            "SELECT evidence_version_id, decision, reason_code FROM review_decisions "
            "WHERE request_item_id = $1 ORDER BY decision_seq, created_at",
            self.item,
        )
        return [(r["evidence_version_id"], r["decision"], r["reason_code"]) for r in rows]

    async def comments(self) -> list[dict[str, object]]:
        rows = await self.seed.rows(
            "SELECT author_user_id, author_side, visibility, body_fingerprint FROM comments "
            "WHERE request_item_id = $1",
            self.item,
        )
        return [dict(r) for r in rows]


async def _file(world: World, item: uuid.UUID, name: str) -> uuid.UUID:
    """A client's file fulfilling the request (seeded: no route uploads without storage)."""
    evidence = await world.seed.value(
        "INSERT INTO evidence_items (tenant_id, engagement_id, title, created_by_kind, "
        "created_by_id) VALUES ($1, $2, $3, 'system', 'seed') RETURNING id",
        world.tenant,
        world.engagement,
        name,
    )
    fingerprint = uuid.uuid4().hex * 2
    version = cast(
        uuid.UUID,
        await world.seed.value(
            "INSERT INTO evidence_versions (tenant_id, engagement_id, evidence_item_id, "
            "version_no, fingerprint, storage_key, storage_version_id, size_bytes, media_type, "
            "source, method) VALUES ($1, $2, $3, 1, $4, $5, 'v1', 10, 'application/pdf', "
            "'upload', 'uploaded') RETURNING id",
            world.tenant,
            world.engagement,
            evidence,
            fingerprint,
            f"tenants/{world.tenant}/sha256/{fingerprint}",
        ),
    )
    await world.seed.run(
        "INSERT INTO fulfilments (tenant_id, engagement_id, request_item_id, "
        "evidence_version_id, created_by_kind, created_by_id) "
        "VALUES ($1, $2, $3, $4, 'human', 'seed')",
        world.tenant,
        world.engagement,
        item,
        version,
    )
    return version


async def _upload(seed: Seeder) -> Upload:
    world = await make_world(seed)
    binder = await world.binder()
    await seed.run(
        "UPDATE request_lists SET status = 'published', published_at = $2, published_by = $3 "
        "WHERE id = $1",
        binder,
        T0 - timedelta(days=7),
        world.partner.user_id,
    )
    item = await world.item(binder, description=TITLE, status="requested")
    claire = await world.client_user("owner")
    first = await _file(world, item, "Granite statement.pdf")
    second = await _file(world, item, "Granite invoice.pdf")
    await seed.run("UPDATE request_items SET status = 'uploaded' WHERE id = $1", item)
    return Upload(world, item, (first, second), claire)


async def _draft(upload: Upload) -> follow_ups.FollowUpView:
    with clock.frozen(T0):
        return await follow_ups.draft_return(
            upload.partner,
            upload.world.engagement,
            upload.item,
            list(upload.files),
            "wrong_document",
        )


async def _send(upload: Upload, follow_up_id: uuid.UUID) -> follow_ups.FollowUpView:
    with clock.frozen(T0 + timedelta(seconds=1)), recording_checks():
        return await follow_ups.send(upload.partner, follow_up_id)


async def _deliver(at: timedelta) -> int:
    sent = [e for e in await _relay(T0 + at) if e.event_type == "follow_up.sent"]
    for event in sent:
        await follow_ups.on_follow_up_sent(event)
    return len(sent)


# --- the draft -----------------------------------------------------------------------------------


async def test_the_draft_is_composed_from_the_return_template_with_its_files(
    seed: Seeder,
) -> None:
    upload = await _upload(seed)
    draft = await _draft(upload)
    assert draft.kind == "screening_return"
    assert draft.status == "drafted"
    assert draft.template_key == RETURN_TEMPLATE
    assert draft.drafted_by_kind == "agent"  # the C-31 marker: composed, never model text
    assert draft.recipient_user_id == upload.claire.user_id
    assert [i.request_item_id for i in draft.items] == [upload.item]
    assert f"- {TITLE}" in draft.body and "don't answer it" in draft.body
    returns = await seed.rows(
        "SELECT evidence_version_id, reason_code FROM follow_up_returns WHERE follow_up_id = $1",
        draft.id,
    )
    assert {(r["evidence_version_id"], r["reason_code"]) for r in returns} == {
        (upload.files[0], "wrong_document"),
        (upload.files[1], "wrong_document"),
    }
    assert "follow_up.drafted" in await seed.actions(upload.world.tenant)
    # Drafting decides nothing: the request and its files are as they were.
    assert await upload.status() == "uploaded"
    assert await upload.decisions() == []


async def test_a_file_that_does_not_answer_this_request_is_refused(seed: Seeder) -> None:
    upload = await _upload(seed)
    other = await upload.world.item(
        cast(
            uuid.UUID,
            await seed.value(
                "SELECT request_list_id FROM request_items WHERE id = $1", upload.item
            ),
        ),
        description="Mortgage interest statement",
        status="requested",
    )
    elsewhere = await _file(upload.world, other, "Granite mortgage.pdf")
    with clock.frozen(T0), pytest.raises(NotFound):
        await follow_ups.draft_return(
            upload.partner, upload.world.engagement, upload.item, [elsewhere], "wrong_year"
        )
    assert not await seed.rows(
        "SELECT 1 FROM follow_up_schedules WHERE engagement_id = $1", upload.world.engagement
    )


async def test_without_a_return_template_drafting_is_409(
    seed: Seeder, monkeypatch: pytest.MonkeyPatch
) -> None:
    upload = await _upload(seed)
    real = composing.current_version

    async def only_reminder(key: str) -> object:
        return None if key == RETURN_TEMPLATE else await real(key)

    monkeypatch.setattr(composing, "current_version", only_reminder)
    with pytest.raises(FollowUpTemplateMissing):
        await _draft(upload)
    assert not await seed.rows(
        "SELECT 1 FROM follow_up_schedules WHERE engagement_id = $1", upload.world.engagement
    )


# --- the send, delivery and Undo -----------------------------------------------------------------


async def test_the_send_returns_each_file_and_the_request_and_delivery_posts_the_comment(
    seed: Seeder, mailbox: Mailbox
) -> None:
    upload = await _upload(seed)
    draft = await _draft(upload)
    with clock.frozen(T0):
        await follow_ups.edit(upload.partner, draft.id, "Please send the 2025 statements.")
    await _drain()
    sent = await _send(upload, draft.id)
    assert sent.status == "sent" and sent.undo_until == T0 + timedelta(seconds=11)
    assert [i.request_item_id for i in sent.items] == [upload.item]
    # One unit of work with the grant: a send-back per file, the request returned.
    decisions = await upload.decisions()
    assert sorted(decisions) == sorted([(f, "send_back", "wrong_document") for f in upload.files])
    actors = await seed.rows(
        "SELECT DISTINCT actor_kind, actor_id FROM review_decisions WHERE request_item_id = $1",
        upload.item,
    )
    assert [(r["actor_kind"], r["actor_id"]) for r in actors] == [
        ("human", str(upload.partner.user_id))
    ]
    assert await upload.status() == "returned"
    # Nothing reaches the client inside the Undo window.
    assert await _deliver(timedelta(seconds=5)) == 0
    assert mailbox.sent == [] and await upload.comments() == []
    await seed.run(
        "UPDATE outbox SET next_attempt_at = NULL WHERE tenant_id = $1", upload.world.tenant
    )
    assert await _deliver(timedelta(seconds=12)) == 1
    [email] = mailbox.sent
    assert email["body"] == "Please send the 2025 statements."
    body_fp = hashlib.sha256(b"Please send the 2025 statements.").hexdigest()
    assert await upload.comments() == [
        {
            "author_user_id": upload.partner.user_id,
            "author_side": "firm",
            "visibility": "shared",
            "body_fingerprint": body_fp,
        }
    ]
    # A redelivery posts and sends nothing twice.
    await follow_ups.on_follow_up_sent(
        OutboxEvent(
            uuid.uuid4(), upload.world.tenant, "follow_up.sent", {"follow_up_id": str(draft.id)}
        )
    )
    assert len(mailbox.sent) == 1 and len(await upload.comments()) == 1
    assert "comment.posted" in await seed.actions(upload.world.tenant)


async def test_undo_puts_the_files_and_the_request_back_and_nothing_reaches_the_client(
    seed: Seeder, mailbox: Mailbox
) -> None:
    upload = await _upload(seed)
    draft = await _draft(upload)
    await _drain()
    await _send(upload, draft.id)
    assert await upload.status() == "returned"
    with clock.frozen(T0 + timedelta(seconds=6)), recording_checks():
        back = await follow_ups.undo(upload.partner, draft.id)
    assert back.status == "drafted"
    assert await upload.status() == "uploaded"
    assert [d for _, d, _ in await upload.decisions()].count("undone") == 2
    await seed.run(
        "UPDATE outbox SET next_attempt_at = NULL WHERE tenant_id = $1", upload.world.tenant
    )
    assert await _deliver(timedelta(seconds=12)) == 0
    assert mailbox.sent == [] and await upload.comments() == []
    # Sent again, it returns the files again.
    with clock.frozen(T0 + timedelta(seconds=20)), recording_checks():
        again = await follow_ups.send(upload.partner, draft.id)
    assert again.status == "sent" and await upload.status() == "returned"


async def test_only_a_person_serving_a_request_returns_files(seed: Seeder) -> None:
    """ADR-005: outside a request (a worker, a script) the send refuses and writes nothing."""
    upload = await _upload(seed)
    draft = await _draft(upload)
    with clock.frozen(T0 + timedelta(seconds=1)), pytest.raises(Forbidden):
        await follow_ups.send(upload.partner, draft.id)
    assert await upload.decisions() == []
    assert await upload.status() == "uploaded"
    row = await seed.rows("SELECT status FROM follow_up_schedules WHERE id = $1", draft.id)
    assert row[0]["status"] == "drafted"


async def test_the_view_lists_the_files_its_sender_returns(seed: Seeder) -> None:
    """ADR-005: the person who sends a return sees the files it sends back."""
    upload = await _upload(seed)
    draft = await _draft(upload)
    assert [(r.evidence_version_id, r.reason_code) for r in draft.returning] == sorted(
        [(f, "wrong_document") for f in upload.files], key=lambda r: str(r[0])
    )


async def test_a_newer_upload_since_the_draft_is_not_returned(seed: Seeder) -> None:
    """A newer file waits for a review, so the request is not the client's to answer again."""
    upload = await _upload(seed)
    draft = await _draft(upload)
    await _file(upload.world, upload.item, "Granite statement, corrected.pdf")
    with pytest.raises(Superseded):
        await _send(upload, draft.id)
    assert await upload.decisions() == []
    assert await upload.status() == "uploaded"


async def test_a_file_that_also_answers_another_request_is_refused(seed: Seeder) -> None:
    upload = await _upload(seed)
    draft = await _draft(upload)
    binder = cast(
        uuid.UUID,
        await seed.value("SELECT request_list_id FROM request_items WHERE id = $1", upload.item),
    )
    other = await upload.world.item(binder, description="Mortgage interest", status="uploaded")
    await seed.run(
        "INSERT INTO fulfilments (tenant_id, engagement_id, request_item_id, "
        "evidence_version_id, created_by_kind, created_by_id) "
        "VALUES ($1, $2, $3, $4, 'human', 'seed')",
        upload.world.tenant,
        upload.world.engagement,
        other,
        upload.files[0],
    )
    with pytest.raises(ReturnSpansRequests):
        await _send(upload, draft.id)
    assert await upload.decisions() == []
    assert await seed.value("SELECT status FROM request_items WHERE id = $1", other) == "uploaded"


async def test_a_sender_who_may_not_send_files_back_returns_nothing(seed: Seeder) -> None:
    """Staff may send a follow-up but, without the firm's setting, not send a file back."""
    upload = await _upload(seed)
    draft = await _draft(upload)
    staff = await seed.person(upload.world.tenant)
    await seed.member(upload.world.engagement, staff, "staff")
    with clock.frozen(T0 + timedelta(seconds=1)), recording_checks(), pytest.raises(Forbidden):
        await follow_ups.send(staff.context(), draft.id)
    assert await upload.decisions() == []
    assert await upload.status() == "uploaded"


async def test_a_return_is_sent_on_its_own(seed: Seeder) -> None:
    upload = await _upload(seed)
    draft = await _draft(upload)
    with (
        clock.frozen(T0 + timedelta(seconds=1)),
        recording_checks(),
        pytest.raises(FollowUpSendAlone),
    ):
        await follow_ups.send_many(upload.partner, [draft.id])
    assert await upload.decisions() == []
