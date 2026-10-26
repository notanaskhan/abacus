"""R-01-T19 against Postgres (TASK-1352; C16 v1.1; migration 0196).

Acceptance: the same version and variables render byte-identical HTML and text, a key with no
published version blocks the send, and v3 stays readable after v4 publishes. Around it: a stale
draft answers 409, the lint refuses "$3,200" and the platform's name at publish, a firm's wording
is sealed at rest, the app role can neither read the global tables nor change a version, another
firm sees none of it, the agent and a staff member are refused, and a retried send sends once.
Brightwater Hale's own words are not used here: these are probe strings."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import cast

import asyncpg
import pytest

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine, tenant_session
from abacus.kernel.errors import NotFound
from abacus.modules.communications import template_service, template_store
from abacus.modules.communications.api import (
    RecipientRef,
    SendOutcome,
    SendScope,
    configure_transport,
    send_templated,
)
from abacus.modules.communications.render import (
    Block,
    RenderedEmail,
    TemplateContent,
    render_email,
)
from abacus.modules.communications.template_keys import REMINDER
from abacus.modules.communications.template_registry import VARIABLES
from abacus.modules.identity.api import AuthContext, Forbidden

from .agent_tests.support import Person, Seeder
from .conftest import MigratedDatabase

LINK = "https://portal.example.test/l/AbCdEf0123456789"
VALUES = {
    "client_first_name": "Claire",
    "firm_name": "Probe Firm",
    "work_item": "2025 tax return",
    "open_items": "Form W-2\nForm 1099-INT",
    "due_date": "Sep 21",
    "portal_link": LINK,
    "staff_name": "Marcus Delaney",
}
BLOCKS = frozenset(n for n, v in VARIABLES.items() if v.block)


def content(word: str) -> TemplateContent:
    return TemplateContent(
        subject=f"{word}: {{work_item}} needs {{client_first_name}}",
        preheader="Two things are still open",
        blocks=(
            Block("h1", "heading", "Hi {client_first_name}"),
            Block("p1", "paragraph", f"{word} from {{firm_name}} about {{work_item}}."),
            Block("l1", "item_list", "{open_items}"),
            Block("n1", "note", "Questions? Ask {staff_name}."),
        ),
        cta_label="Open documents",
        cta_target="documents",
    )


@dataclass
class Recorder:
    sent: list[dict[str, object]] = field(default_factory=lambda: list[dict[str, object]]())

    def send(self, **kwargs: object) -> None:
        self.sent.append(kwargs)


@dataclass(frozen=True)
class Firm:
    tenant: uuid.UUID
    admin: AuthContext
    manager: AuthContext
    staff: AuthContext
    recipient: Person
    engagement: uuid.UUID


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
def recorder() -> Iterator[Recorder]:
    found = Recorder()
    configure_transport(found)
    yield found
    configure_transport(None)


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


def _ctx(who: Person, firm_role: str | None) -> AuthContext:
    return AuthContext(
        tenant=TenantContext(who.tenant_id, "human", str(who.user_id)),
        user_id=who.user_id,
        membership_id=uuid.uuid4(),
        firm_role=firm_role,  # pyright: ignore[reportArgumentType] -- a seeded role code
        mfa_at=datetime.now(UTC) - timedelta(minutes=1),
    )


async def _firm(seed: Seeder, *, editor: bool = True) -> Firm:
    tenant = await seed.firm()
    admin, manager, staff, recipient = [await seed.person(tenant) for _ in range(4)]
    await seed.run(
        "UPDATE memberships SET firm_role = 'firm_admin' WHERE tenant_id = $1 AND user_id = $2",
        tenant,
        admin.user_id,
    )
    entity = await seed.entity(tenant)
    engagement = await seed.engagement(tenant, entity, admin.user_id)
    await seed.member(engagement, manager, "manager")
    if editor:
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, 'portal.settings_editor', 'true', 'r01t19', 'TASK-1352')",
            tenant,
        )
    return Firm(
        tenant,
        _ctx(admin, "firm_admin"),
        _ctx(manager, None),
        _ctx(staff, None),
        recipient,
        engagement,
    )


@pytest.fixture
async def firm(seed: Seeder) -> Firm:
    return await _firm(seed)


async def _publish(firm: Firm, word: str) -> int:
    state = await template_service.template_state(firm.admin, "reminder")
    expected = state.draft.draft_version if state.draft is not None else 0
    await template_service.save_draft(firm.admin, "reminder", content(word), expected)
    return (await template_service.publish(firm.admin, "reminder")).version


def _attempt(n: int) -> str:
    """A retry's identifier: the same `n` is the same send."""
    return f"probe-send-{n}"


async def _send(firm: Firm, attempt: int = 1, **override: str) -> SendOutcome:
    return await send_templated(
        firm.manager,
        "reminder",
        RecipientRef("user", firm.recipient.user_id),
        {**VALUES, **override},
        scope=SendScope(engagement_id=firm.engagement),
        idempotency_key=_attempt(attempt),
    )


# --- acceptance --------------------------------------------------------------------------------


async def test_ac9_the_same_version_and_values_render_byte_identical_html_and_text(
    firm: Firm,
) -> None:
    await _publish(firm, "Reminder")
    renders: list[RenderedEmail] = []
    for _ in range(2):
        async with tenant_session(firm.admin.tenant) as session:
            stored = await template_store.resolve(session, firm.tenant, "reminder")
        assert stored is not None and stored.content is not None
        renders.append(
            render_email(
                stored.content,
                VALUES,
                allowed=frozenset(REMINDER.variables),
                block_variables=BLOCKS,
            )
        )
    assert renders[0] == renders[1]
    assert renders[0].html.encode() == renders[1].html.encode()
    assert renders[0].text.encode() == renders[1].text.encode()
    assert "<li" in renders[0].html and f'href="{LINK}"' in renders[0].html


async def test_ac10_a_key_with_no_published_version_blocks_the_send(
    firm: Firm, seed: Seeder, recorder: Recorder
) -> None:
    outcome = await _send(firm)
    assert outcome.status == "blocked"
    assert outcome.blocked_reason == "template_missing"
    row = await seed.rows(
        "SELECT status, template_version_id, kind, body FROM messages WHERE id = $1",
        outcome.message_id,
    )
    assert row[0]["status"] == "blocked" and row[0]["template_version_id"] is None
    assert recorder.sent == []


async def test_ac11_v3_stays_readable_after_v4_publishes(firm: Firm) -> None:
    for n, word in enumerate(("One", "Two", "Three", "Four"), start=1):
        assert await _publish(firm, word) == n
    async with tenant_session(firm.admin.tenant) as session:
        v3 = await template_store.version_at(session, firm.tenant, "reminder", 3)
        current = await template_store.resolve(session, firm.tenant, "reminder")
    assert v3 is not None and v3.content == content("Three")
    assert current is not None and current.version == 4 and current.content == content("Four")
    state = await template_service.template_state(firm.admin, "reminder")
    assert state.published is not None and state.published.version == 4 and state.draft is None


# --- drafts, publish and the lint --------------------------------------------------------------


async def test_ac11_a_stale_draft_answers_409_and_discard_and_empty_publish_are_refused(
    firm: Firm,
) -> None:
    saved = await template_service.save_draft(firm.admin, "reminder", content("A"), 0)
    assert saved.draft_version == 1
    with pytest.raises(template_service.TemplateDraftStale):
        await template_service.save_draft(firm.admin, "reminder", content("B"), 0)
    again = await template_service.save_draft(firm.admin, "reminder", content("B"), 1)
    assert again.draft_version == 2 and again.content == content("B")
    await template_service.discard_draft(firm.admin, "reminder")
    with pytest.raises(NotFound):
        await template_service.discard_draft(firm.admin, "reminder")
    with pytest.raises(template_service.TemplateDraftStale):
        await template_service.publish(firm.admin, "reminder")


async def test_ac11_a_draft_based_on_an_older_version_cannot_publish_over_a_newer_one(
    firm: Firm, seed: Seeder
) -> None:
    await _publish(firm, "One")
    await template_service.save_draft(firm.admin, "reminder", content("Two"), 0)
    # Another publish lands meanwhile (as an import would): the draft's base is no longer in use.
    template = await seed.value(
        "SELECT id FROM email_templates WHERE tenant_id = $1 AND key = 'reminder'", firm.tenant
    )
    await seed.run(
        "UPDATE email_template_drafts SET base_version_id = NULL WHERE template_id = $1", template
    )
    with pytest.raises(template_service.TemplateDraftStale):
        await template_service.publish(firm.admin, "reminder")


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("We received $3,200 from you.", "amount"),
        ("Your SSN 912-34-5678 is on file.", "tin_shape"),
        ("Sent from Accrued.", "platform_name"),
        ("Hello {balance_due}", "unregistered_variable"),
    ],
)
async def test_ac11_publish_refuses_the_lint_findings_naming_the_block_not_the_text(
    firm: Firm, text: str, code: str
) -> None:
    bad = TemplateContent(
        "Subject", "", (Block("b9", "paragraph", text),), "Open documents", "documents"
    )
    await template_service.save_draft(firm.admin, "reminder", bad, 0)
    with pytest.raises(template_service.TemplateLintFailed) as refused:
        await template_service.publish(firm.admin, "reminder")
    assert f"{code}:b9" in refused.value.facts.values()
    assert all(text not in str(v) for v in refused.value.facts.values())


async def test_ac11_a_call_to_action_the_key_does_not_register_is_refused_at_save(
    firm: Firm,
) -> None:
    wrong = TemplateContent("S", "", (Block("p", "paragraph", "x"),), "Sign", "sign")
    with pytest.raises(template_service.TemplateInvalid):
        await template_service.save_draft(firm.admin, "reminder", wrong, 0)


# --- who may, and the flag ---------------------------------------------------------------------


async def test_ac11_staff_and_the_agent_are_refused_and_the_flag_hides_writes(
    seed: Seeder,
) -> None:
    firm = await _firm(seed, editor=False)
    with pytest.raises(Forbidden):
        await template_service.template_state(firm.staff, "reminder")
    agent = AuthContext(
        TenantContext(firm.tenant, "agent", "agent:probe"),
        firm.admin.user_id,
        uuid.uuid4(),
        "firm_admin",
        datetime.now(UTC),
    )
    with pytest.raises(Forbidden):
        await template_service.save_draft(agent, "reminder", content("A"), 0)
    with pytest.raises(NotFound):  # authorised, then the flag: off answers 404
        await template_service.save_draft(firm.admin, "reminder", content("A"), 0)
    with pytest.raises(NotFound):  # not a registered firm-editable key
        await template_service.template_state(firm.admin, "portal.invitation")
    stale = AuthContext(firm.admin.tenant, firm.admin.user_id, uuid.uuid4(), "firm_admin", None)
    with pytest.raises(Forbidden):  # publish needs a fresh second factor
        await template_service.check_publish(stale, "reminder")


async def test_ac11_another_firm_sees_none_of_it(firm: Firm, seed: Seeder) -> None:
    await _publish(firm, "Mine")
    other = await _firm(seed)
    state = await template_service.template_state(other.admin, "reminder")
    assert state.published is None and state.draft is None
    async with tenant_session(other.admin.tenant) as session:
        assert await template_store.version_at(session, other.tenant, "reminder", 1) is None


# --- at rest -----------------------------------------------------------------------------------


async def test_ac11_a_firms_wording_is_sealed_at_rest_and_versions_stay_insert_only(
    firm: Firm, seed: Seeder, migrated_db: MigratedDatabase
) -> None:
    await _publish(firm, "Sealedword")
    await template_service.save_draft(firm.admin, "reminder", content("Draftword"), 0)
    rows = await seed.rows(
        "SELECT v.subject, v.blocks, v.sealed, v.source FROM email_template_versions v "
        "JOIN email_templates t ON t.id = v.template_id WHERE t.tenant_id = $1",
        firm.tenant,
    )
    assert rows[0]["subject"] is None and rows[0]["blocks"] is None
    assert rows[0]["source"] == "editor" and b"Sealedword" not in rows[0]["sealed"]
    draft = await seed.value(
        "SELECT sealed FROM email_template_drafts WHERE tenant_id = $1", firm.tenant
    )
    assert b"Draftword" not in cast(bytes, draft)
    app = await asyncpg.connect(
        migrated_db.app_url.replace("postgresql+asyncpg://", "postgresql://")
    )
    try:
        for sql in (
            "SELECT * FROM email_template_versions",
            "SELECT * FROM email_templates",
            "UPDATE email_template_versions SET source = 'import'",
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await app.execute(sql)
    finally:
        await app.close()
    with pytest.raises(asyncpg.InsufficientPrivilegeError):  # even the superuser: 0092's trigger
        await seed.run("DELETE FROM email_template_versions")


# --- send_templated ----------------------------------------------------------------------------


async def test_ac10_a_send_renders_the_published_version_once_and_stores_no_link(
    firm: Firm, seed: Seeder, recorder: Recorder
) -> None:
    await _publish(firm, "Reminder")
    first = await _send(firm)
    again = await _send(firm)
    assert first.status == "queued" and again == first
    assert len(recorder.sent) == 1
    mail = recorder.sent[0]
    assert LINK in cast(str, mail["body"]) and cast(str, mail["subject"]).startswith("Reminder")
    row = (
        await seed.rows(
            "SELECT status, template_version_id, kind, body FROM messages WHERE id = $1",
            first.message_id,
        )
    )[0]
    assert row["status"] == "sent" and row["kind"] == "client"
    assert row["template_version_id"] is not None
    assert LINK not in row["body"] and "[link removed]" in row["body"]


async def test_ac10_a_value_with_an_amount_or_outside_the_whitelist_blocks_the_send(
    firm: Firm, recorder: Recorder
) -> None:
    await _publish(firm, "Reminder")
    amount = await _send(firm, 2, work_item="Refund of $3,200")
    assert amount.blocked_reason == "template_lint_failed"
    outside = await send_templated(
        firm.manager,
        "reminder",
        RecipientRef("user", firm.recipient.user_id),
        {**VALUES, "connection_name": "American Express"},
        scope=SendScope(engagement_id=firm.engagement),
        idempotency_key=_attempt(3),
    )
    assert outside.blocked_reason == "template_lint_failed"
    assert recorder.sent == []


async def test_ac10_a_person_without_message_send_on_the_engagement_is_refused(
    firm: Firm, recorder: Recorder
) -> None:
    await _publish(firm, "Reminder")
    with pytest.raises((Forbidden, NotFound)):
        await send_templated(
            firm.staff,
            "reminder",
            RecipientRef("user", firm.recipient.user_id),
            VALUES,
            scope=SendScope(engagement_id=firm.engagement),
            idempotency_key=_attempt(4),
        )
    assert recorder.sent == []
