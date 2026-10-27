"""R-01-T23 against Postgres (TASK-1420; C16 v1.1): preview, lint, test send and import.

Acceptance: a draft containing $3,200 or the word Accrued cannot be test-sent, published or
imported, and a test send to any address but the admin's is refused. Around it: preview lists
the findings by block and writes nothing; the test send goes to the acting person's own address
with "[Test]", records no message and audits `email_template.test_sent` with identifiers only;
the import's dry run reports and writes nothing, and applying is all or nothing; staff, a
reader and a stale second factor are refused; a contact the viewer can't see answers 404.
Probe strings only (Brightwater Hale's words are the scenario's)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from pydantic import ValidationError

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.errors import NotFound
from abacus.modules.communications import template_import, template_preview, template_service
from abacus.modules.communications.api import configure_transport
from abacus.modules.communications.render import Block, TemplateContent
from abacus.modules.communications.template_service import TemplateLintFailed
from abacus.modules.communications.templates import TemplateInvalid
from abacus.modules.communications.templates_contract import EmailTestSendIn
from abacus.modules.identity.api import AuthContext, Forbidden

from .agent_tests.support import Person, Seeder
from .conftest import MigratedDatabase


def content(word: str) -> TemplateContent:
    return TemplateContent(
        subject="{work_item} needs {client_first_name}",
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
    admin_person: Person
    staff: AuthContext


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


def _ctx(who: Person, firm_role: str | None, *, fresh: bool = True) -> AuthContext:
    return AuthContext(
        tenant=TenantContext(who.tenant_id, "human", str(who.user_id)),
        user_id=who.user_id,
        membership_id=uuid.uuid4(),
        firm_role=firm_role,  # pyright: ignore[reportArgumentType] -- a seeded role code
        mfa_at=datetime.now(UTC) - timedelta(minutes=1) if fresh else None,
    )


@pytest.fixture
async def firm(seed: Seeder) -> Firm:
    tenant = await seed.firm()
    admin, staff = await seed.person(tenant), await seed.person(tenant)
    await seed.run(
        "UPDATE memberships SET firm_role = 'firm_admin' WHERE tenant_id = $1 AND user_id = $2",
        tenant,
        admin.user_id,
    )
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'portal.settings_editor', 'true', 'r01t23', 'TASK-1420')",
        tenant,
    )
    return Firm(tenant, _ctx(admin, "firm_admin"), admin, _ctx(staff, None))


async def _draft(firm: Firm, word: str) -> None:
    state = await template_service.template_state(firm.admin, "reminder")
    expected = state.draft.draft_version if state.draft is not None else 0
    await template_service.save_draft(firm.admin, "reminder", content(word), expected)


async def _publish_clean(firm: Firm) -> int:
    await _draft(firm, "Reminder")
    return (await template_service.publish(firm.admin, "reminder")).version


async def _admin_email(seed: Seeder, firm: Firm) -> str:
    return cast(
        str, await seed.value("SELECT email FROM users WHERE id = $1", firm.admin_person.user_id)
    )


def _codes(error: TemplateLintFailed) -> set[str]:
    return {f.code for f in error.findings}


# --- acceptance --------------------------------------------------------------------------------


@pytest.mark.parametrize(("word", "code"), [("$3,200", "amount"), ("Accrued", "platform_name")])
async def test_ac_an_amount_or_the_platform_name_blocks_test_send_publish_and_import(
    firm: Firm, seed: Seeder, recorder: Recorder, word: str, code: str
) -> None:
    await _publish_clean(firm)
    await _draft(firm, f"Your balance {word}")
    with pytest.raises(TemplateLintFailed) as sent:
        await template_preview.send_test(
            firm.admin, "reminder", sample_contact_id=None, idempotency_key="t-1"
        )
    assert code in _codes(sent.value)
    with pytest.raises(TemplateLintFailed) as published:
        await template_service.publish(firm.admin, "reminder")
    assert code in _codes(published.value)
    entry = template_import.BundleEntry("reminder", content(f"Pay {word} now"), publish=True)
    with pytest.raises(TemplateLintFailed) as imported:
        await template_import.import_bundle(firm.admin, [entry], dry_run=False)
    assert any(f.code == code for f in imported.value.findings)
    # Nothing went out, nothing new was published, and the facts never quote the text.
    assert recorder.sent == []
    state = await template_service.template_state(firm.admin, "reminder")
    assert state.published is not None and state.published.version == 1
    assert word not in str(published.value.facts) and word not in str(imported.value.facts)


async def test_ac_a_test_send_goes_only_to_the_admins_own_address(
    firm: Firm, seed: Seeder, recorder: Recorder
) -> None:
    await _publish_clean(firm)
    sent = await template_preview.send_test(
        firm.admin, "reminder", sample_contact_id=None, idempotency_key="t-2"
    )
    own = await _admin_email(seed, firm)
    assert sent.sent_to == own and sent.subject.startswith("[Test] ")
    assert len(recorder.sent) == 1
    assert recorder.sent[0]["to"] == own
    assert cast(str, recorder.sent[0]["subject"]).startswith("[Test] ")
    # The request names no recipient: any other field is refused before anything runs.
    for other in ({"to": "x@example.test"}, {"recipient": "x@example.test"}, {"bcc": "x@ex.test"}):
        with pytest.raises(ValidationError):
            EmailTestSendIn.model_validate(other)
    rows = await seed.rows(
        "SELECT action, after_ref FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'email_template.test_sent'",
        firm.tenant,
    )
    assert len(rows) == 1 and own not in str(rows[0]["after_ref"])
    messages = await seed.value("SELECT count(*) FROM messages WHERE tenant_id = $1", firm.tenant)
    assert messages == 0  # a test is no engagement message


# --- preview -----------------------------------------------------------------------------------


async def test_preview_lists_findings_by_block_and_writes_nothing(
    firm: Firm, seed: Seeder
) -> None:
    await _publish_clean(firm)
    await _draft(firm, "See the attached file, click here, or ask the agent about 123-45-6789")
    before = await seed.count("audit_events", firm.tenant)
    found = await template_preview.preview(
        firm.admin, "reminder", source="draft", width=390, sample_contact_id=None
    )
    codes = {(getattr(f, "code", ""), getattr(f, "where", "")) for f in found.findings}
    for code in ("attachment", "second_button", "banned_word", "tin_shape"):
        assert (code, "p1") in codes
    assert "width:100%;box-sizing:border-box" in found.rendered.html  # the 390 button
    assert "Sample" in found.rendered.text  # the sample client, not a real person
    assert await seed.count("audit_events", firm.tenant) == before
    published = await template_preview.preview(
        firm.admin, "reminder", source="published", width=600, sample_contact_id=None
    )
    assert published.findings == ()


async def test_preview_of_a_contact_the_viewer_cannot_see_answers_404(firm: Firm) -> None:
    await _publish_clean(firm)
    with pytest.raises(NotFound):
        await template_preview.preview(
            firm.admin, "reminder", source="published", width=600, sample_contact_id=uuid.uuid4()
        )


# --- import ------------------------------------------------------------------------------------


async def test_import_dry_run_reports_and_writes_nothing_then_applies(
    firm: Firm, seed: Seeder
) -> None:
    bundle = [
        template_import.BundleEntry("reminder", content("Reminder"), publish=True),
        template_import.BundleEntry("signature_request", content("Sign"), publish=False),
        template_import.BundleEntry("portal_sign_in_code", content("Code"), publish=False),
    ]
    before = await seed.count("audit_events", firm.tenant)
    report = await template_import.import_bundle(firm.admin, bundle, dry_run=True)
    assert [(r.key, r.change) for r in report] == [
        ("reminder", "add"),
        ("signature_request", "refused"),  # its CTA target and variables are the reminder's
        ("portal_sign_in_code", "refused"),  # not a registered firm-editable key
    ]
    assert await seed.count("audit_events", firm.tenant) == before
    state = await template_service.template_state(firm.admin, "reminder")
    assert state.published is None or state.published.firm is False
    with pytest.raises(TemplateInvalid):  # any refused entry: nothing is applied
        await template_import.import_bundle(firm.admin, bundle, dry_run=False)
    applied = await template_import.import_bundle(firm.admin, bundle[:1], dry_run=False)
    assert [(r.key, r.change) for r in applied] == [("reminder", "add")]
    state = await template_service.template_state(firm.admin, "reminder")
    assert state.published is not None and state.published.firm
    assert "email_template.imported" in await seed.actions(firm.tenant)
    again = await template_import.import_bundle(firm.admin, bundle[:1], dry_run=True)
    assert [(r.key, r.change) for r in again] == [("reminder", "unchanged")]


# --- who may ------------------------------------------------------------------------------------


async def test_staff_a_reader_and_a_stale_second_factor_are_refused(
    firm: Firm, recorder: Recorder
) -> None:
    await _publish_clean(firm)
    with pytest.raises(Forbidden):
        await template_preview.preview(
            firm.staff, "reminder", source="published", width=600, sample_contact_id=None
        )
    leader = AuthContext(
        firm.admin.tenant, firm.admin.user_id, uuid.uuid4(), "practice_leader", datetime.now(UTC)
    )
    with pytest.raises(Forbidden):
        await template_preview.send_test(
            leader, "reminder", sample_contact_id=None, idempotency_key="t-3"
        )
    stale = AuthContext(firm.admin.tenant, firm.admin.user_id, uuid.uuid4(), "firm_admin", None)
    with pytest.raises(Forbidden):  # test send and import need a fresh second factor
        await template_preview.send_test(
            stale, "reminder", sample_contact_id=None, idempotency_key="t-4"
        )
    with pytest.raises(Forbidden):
        await template_import.import_bundle(
            stale,
            [template_import.BundleEntry("reminder", content("R"), publish=False)],
            dry_run=True,
        )
    assert recorder.sent == []
