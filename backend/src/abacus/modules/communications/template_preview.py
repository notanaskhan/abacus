"""POR-20's preview and test send (R-01-T23; C16 v1.1; R-01 Story 7.2, 7.3; DEC-379, DEC-549,
DEC-560).

- **Preview** (`email_template.read`): the draft or the published version of a registered
  firm-editable key, rendered at 600 or 390 with sample values, with the lint's findings on the
  text (by block) and on the filled values (by variable). It writes nothing.
- **Test send** (`email_template.test_send`: firm admin, fresh second factor, onshore; then
  `portal.settings_editor`): the draft if there is one, else the published version, refused 422
  `template_lint_failed` while the lint finds anything, and sent only to the acting person's
  own account address, read from the session's user id, never from the request, with "[Test]"
  before the subject. No `messages` row (a message is about an engagement; a test is about
  none); synthetic firms deliver into the sink; the email pause and suppression apply. Audited
  `email_template.test_sent {key, message_id}` (DEC-549).
- **Sample values** (DEC-560): without `sample_contact_id`, the sample client (fixed neutral
  words and the firm's own name). With one, the contact must relate to an engagement on the
  viewer's own team, as the key's audience allows, else 404 (an unknown contact answers the
  same); its open requests come only through `request_items_for` under the viewer's own
  authorisation (walls, independence), and when nothing is readable the sample client renders
  (`viewer_scoped`). The button's address is a fixed preview address with no token: a preview or
  a test never issues a secure link to a client's portal.
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.clock import now
from abacus.kernel.config import settings
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainRateLimited, NotFound
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Ref, Target, UnitOfWork, audit_of_targets, uow
from abacus.modules.communications import template_store
from abacus.modules.communications.deliveries import send_email
from abacus.modules.communications.lint import LintFinding, lint_template
from abacus.modules.communications.notification_email import display_name
from abacus.modules.communications.preview_scope import viewer_scoped
from abacus.modules.communications.render import RenderedEmail, TemplateContent, render_email
from abacus.modules.communications.template_registry import (
    VARIABLES,
    EmailTemplateRegistration,
    ValueFinding,
    lint_values,
    registered_templates,
)
from abacus.modules.communications.template_service import (
    TemplateLintFailed,
    check_content,
    editable,
    editor_on,
)
from abacus.modules.communications.templates import TemplateInvalid
from abacus.modules.engagements.api import get_ref
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    authorise,
    contact_emails,
    contact_user_ids,
    firm_name,
    my_engagements,
    names_of,
    recipient_relations,
)
from abacus.modules.requests.api import request_items_for

Source = Literal["draft", "published"]
Width = Literal[600, 390]
TEST_PREFIX: Final = "[Test] "
TEST_SEND_LIMIT: Final = 10
TEST_SEND_WINDOW: Final = timedelta(hours=1)
_NAMESPACE: Final = uuid.UUID("2c7a3b41-6e1f-4d55-9a0b-7f23c16e0a23")
_BLOCK_VARIABLES: Final = frozenset(n for n, v in VARIABLES.items() if v.block)
_OPEN: Final = frozenset({"requested", "returned"})
_MAX_ITEMS: Final = 10
# The sample client (DEC-560): neutral words a reader can't mistake for a real person, no digits,
# so the value lint has nothing to find. The firm's name and the viewer's are real.
_SAMPLE: Final[Mapping[str, str]] = {
    "client_first_name": "Sample",
    "work_item": "sample engagement",
    "open_items": "First sample document\nSecond sample document",
    "due_date": "the due date",
    "organisation_name": "Sample Client",
    "scope_summary": "a few documents",
    "document_title": "sample document",
    "deliverable_title": "sample deliverable",
    "respondent_org": "Sample Respondent",
    "connection_name": "sample connection",
}
_log = get_logger(__name__)


@dataclass(frozen=True)
class Preview:
    rendered: RenderedEmail
    from_display: str
    from_address: str
    findings: tuple[LintFinding | ValueFinding, ...]


@dataclass(frozen=True)
class SentTest:
    message_id: UUID
    sent_to: str
    subject: str


def preview_link() -> str:
    """The button's address in a preview or a test: the app's own, with no token (DEC-560)."""
    return f"{settings().app_base_url.rstrip('/')}/portal/preview"


def _firm(ctx: AuthContext) -> Resource:
    return Resource.firm(ctx.tenant_id)


async def _content(ctx: AuthContext, key: str, source: Source | None) -> TemplateContent:
    """The draft or the published version; `None`: the draft if there is one, else published."""
    async with tenant_session(ctx.tenant) as session:
        draft = None
        if source != "published":
            firm_id = await template_store.firm_template_id(session, key)
            if firm_id is not None:
                found = await template_store.draft_of(session, ctx.tenant_id, firm_id)
                draft = None if found is None else found.content
        if draft is not None:
            return draft
        if source == "draft":
            raise NotFound("email_template_draft")
        published = await template_store.resolve(session, ctx.tenant_id, key)
    if published is None or published.content is None:
        raise NotFound("email_template_version")
    return published.content


def _items_text(titles: Sequence[str]) -> str:
    lines = [" ".join(t.split()) for t in titles if t.strip()]
    shown = lines[:_MAX_ITEMS]
    if len(lines) > _MAX_ITEMS:
        shown.append(f"and {len(lines) - _MAX_ITEMS} more")
    return "\n".join(shown)


async def _contact_values(
    ctx: AuthContext, registration: EmailTemplateRegistration, contact_id: UUID
) -> dict[str, str]:
    """What a real contact contributes, as far as the viewer may read it (DEC-379, DEC-560)."""
    async with tenant_session(ctx.tenant) as session:
        people = await contact_user_ids(session, contact_id)
    audience = set(registration.audience)
    related: list[UUID] = []
    for engagement_id in sorted(await my_engagements(ctx)):
        try:  # security review: a team member walled off the engagement does not see it here
            await get_ref(ctx, engagement_id)
        except (Forbidden, NotFound):
            continue
        for person in people:
            if await recipient_relations(ctx.tenant, person, engagement_id) & audience:
                related.append(engagement_id)
                break
    if not related:
        raise NotFound("contact")  # unknown and not visible answer the same
    titles: list[str] = []
    work_item: str | None = None
    for engagement_id in related:
        try:
            views = await request_items_for(ctx, engagement_id)
        except (Forbidden, NotFound):
            continue  # the viewer can't read it: dropped, with no count
        mine = [
            v.description
            for v in views
            if v.status in _OPEN
            and v.client_visible
            and (v.client_assignee_user_id is None or v.client_assignee_user_id in people)
        ]
        if mine and work_item is None:
            work_item = await display_name(ctx.tenant_id, engagement_id)
        titles.extend(mine)
    selection = viewer_scoped(titles, lambda _t: True, contact_visible=True)
    if selection.use_sample:
        return {}
    values: dict[str, str] = {"open_items": _items_text(selection.items)}
    name = (await names_of(people[:1])).get(people[0], "") if people else ""
    first = " ".join(name.split()).partition(" ")[0]
    if first:
        values["client_first_name"] = first
    if work_item:
        values["work_item"] = " ".join(work_item.split())
    return values


async def sample_values(
    ctx: AuthContext, registration: EmailTemplateRegistration, contact_id: UUID | None
) -> dict[str, str]:
    """A value for every variable the key registers."""
    me = (await names_of([ctx.user_id])).get(ctx.user_id, "") or "Your firm"
    base = {
        **_SAMPLE,
        "firm_name": await firm_name(ctx.tenant_id),
        "staff_name": me,
        "inviter_name": me,
        "portal_link": preview_link(),
    }
    if contact_id is not None:
        base.update(await _contact_values(ctx, registration, contact_id))
    return {name: base[name] for name in registration.variables}


def _render(
    registration: EmailTemplateRegistration,
    content: TemplateContent,
    values: Mapping[str, str],
    width: Width,
) -> RenderedEmail:
    return render_email(
        content,
        values,
        allowed=frozenset(registration.variables),
        block_variables=_BLOCK_VARIABLES,
        width=width,
    )


def _findings(
    registration: EmailTemplateRegistration, content: TemplateContent, values: Mapping[str, str]
) -> list[LintFinding | ValueFinding]:
    found: list[LintFinding | ValueFinding] = [*lint_template(content, registration)]
    found.extend(lint_values(values))
    return found


async def preview(
    ctx: AuthContext,
    key: str,
    *,
    source: Source | None,
    width: Width,
    sample_contact_id: UUID | None,
) -> Preview:
    await authorise(ctx, "email_template.read", _firm(ctx))
    registration = editable(key)
    content = await _content(ctx, key, source)
    check_content(content, registration)
    values = await sample_values(ctx, registration, sample_contact_id)
    findings = _findings(registration, content, values)
    rendered = _render(registration, content, values, width)
    return Preview(
        rendered,
        await firm_name(ctx.tenant_id),
        settings().ses_from_address or "",
        tuple(findings),
    )


async def check_test_send(ctx: AuthContext, key: str) -> EmailTemplateRegistration:
    """Authorise first (fresh MFA, onshore: the matrix), then the flag, then the key (ED-026)."""
    await authorise(ctx, "email_template.test_send", _firm(ctx))
    await editor_on(ctx)
    return editable(key)


class TestSendRateLimited(DomainRateLimited):
    """Security review L4: at most `TEST_SEND_LIMIT` test sends per person per firm in a rolling
    hour; retry after `retry_after` seconds."""

    __test__ = False  # not a pytest class
    code = "test_send_rate_limited"


_LOCK_PERSON: Final = text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))")


async def _template_ids(session: AsyncSession, tenant_id: UUID) -> list[UUID]:
    """Every row a test send's audit event can name: each firm-editable key's firm row and the
    template in use."""
    found: set[UUID] = set()
    for registration in registered_templates():
        if not registration.firm_editable:
            continue
        firm_id = await template_store.firm_template_id(session, registration.key)
        if firm_id is not None:
            found.add(firm_id)
        published = await template_store.resolve(session, tenant_id, registration.key)
        if published is not None:
            found.add(published.template_id)
    return sorted(found)


async def _under_cap(tx: UnitOfWork, ctx: AuthContext) -> None:
    """Counted one at a time per person, so parallel test sends can't pass the cap."""
    await tx.session.execute(
        _LOCK_PERSON, {"key": f"email_test_send:{ctx.tenant_id}:{ctx.user_id}"}
    )
    ids = await _template_ids(tx.session, ctx.tenant_id)
    events = await audit_of_targets(
        tx.session,
        [("email_template", i) for i in ids],
        None,
        500,
        action="email_template.test_sent",
    )
    at = await now(ctx.tenant)
    mine = sorted(
        e.at for e in events if e.actor_id == str(ctx.user_id) and at - e.at < TEST_SEND_WINDOW
    )
    if len(mine) >= TEST_SEND_LIMIT:
        retry = TEST_SEND_WINDOW - (at - mine[-TEST_SEND_LIMIT])
        raise TestSendRateLimited(
            facts={
                "limit": TEST_SEND_LIMIT,
                "retry_after": max(1, math.ceil(retry.total_seconds())),
            }
        )


def message_id_for_test(tenant_id: UUID, key: str, user_id: UUID, idempotency_key: str) -> UUID:
    return uuid.uuid5(_NAMESPACE, f"{tenant_id}:{key}:{user_id}:{idempotency_key}")


async def own_address(ctx: AuthContext) -> str:
    """The acting person's own account address: the only recipient a test has."""
    address = (await contact_emails([ctx.user_id])).get(ctx.user_id)
    if not address:
        raise NotFound("address")
    return address


async def send_test(
    ctx: AuthContext,
    key: str,
    *,
    sample_contact_id: UUID | None,
    idempotency_key: str,
) -> SentTest:
    registration = await check_test_send(ctx, key)
    if ctx.tenant.actor_kind != "human" or ctx.client:
        raise Forbidden("email_template.test_send", "role")  # a person, of the firm
    content = await _content(ctx, key, None)
    check_content(content, registration)
    values = await sample_values(ctx, registration, sample_contact_id)
    text_findings = lint_template(content, registration)
    if text_findings:
        raise TemplateLintFailed(text_findings)
    value_findings = lint_values(values)
    if value_findings:
        raise TemplateLintFailed(
            [LintFinding(f.code, f"var:{f.variable}") for f in value_findings]
        )
    rendered = _render(registration, content, values, 600)
    to = await own_address(ctx)
    subject = f"{TEST_PREFIX}{rendered.subject}"
    message_id = message_id_for_test(ctx.tenant_id, key, ctx.user_id, idempotency_key)
    async with tenant_session(ctx.tenant) as session:
        firm_id = await template_store.firm_template_id(session, key)
        published = await template_store.resolve(session, ctx.tenant_id, key)
    target = firm_id or (published.template_id if published is not None else None)
    if target is None:  # pragma: no cover -- `_content` found a draft or a version
        raise TemplateInvalid
    async with uow(ctx.tenant) as tx:
        await _under_cap(tx, ctx)
        tx.record(
            "email_template.test_sent",
            target=Target("email_template", target),
            after=Ref(message_id=message_id),
        )
    sent = await send_email(
        tenant_id=ctx.tenant_id,
        message_id=message_id,
        to=to,
        subject=subject,
        body=rendered.text,
        sender_name=await firm_name(ctx.tenant_id),
    )
    if not sent:
        _log.info("email_template.test_not_delivered", message_id=message_id)
    return SentTest(message_id, to, subject)
