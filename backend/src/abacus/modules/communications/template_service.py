"""POR-20's firm email templates: list, read, draft save and discard, publish (R-01-T19; C16 v1.1;
R-01 Story 7.1, 7.3).

- Every call authorises first (`email_template.read`, `.edit`, `.publish` on the firm; the agent
  and system are denied at the matrix, publish needs a fresh second factor), then writes check
  `portal.settings_editor` (404 off), then the key: only a registered firm-editable key exists
  for the firm (404 otherwise).
- A draft carries `expected_version`: 0 when there is none, else the draft's `draft_version`; any
  other value is 409 `stale_version`. The first save creates the firm's override row.
- Publish takes the draft, runs the text lint (422 `template_lint_failed`, identifier-only
  facts), and writes version n+1 insert-only in the same unit of work that deletes the draft. A
  draft based on a version that is no longer the one in use (someone published or imported
  since) is 409 `stale_version`, and so is a concurrent publish. v3 stays readable after v4.
- Audited `email_template.draft_saved`, `.draft_discarded`, `.published` on the firm-level target
  `email_template` (the firm's override row); outbox `email_template.published {key, version}`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID

from sqlalchemy.exc import DBAPIError

from abacus.kernel._flags import PORTAL_SETTINGS_EDITOR
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.communications import template_keys, template_store
from abacus.modules.communications.events import EmailTemplatePublished
from abacus.modules.communications.lint import LintFinding, lint_template
from abacus.modules.communications.render import TemplateContent, content_variables
from abacus.modules.communications.template_registry import (
    EmailTemplateRegistration,
    registered_templates,
    registration_of,
)
from abacus.modules.communications.template_store import StoredDraft, StoredVersion
from abacus.modules.communications.templates import TemplateInvalid
from abacus.modules.identity.api import AuthContext, Resource, authorise

_SERIALIZATION: Final = "40001"
_MAX_FINDING_FACTS: Final = 20
Source = str  # editor | import | handoff_seed

# The six designed keys register on import; this keeps the import from looking unused.
DESIGNED_KEYS: Final = tuple(r.key for r in template_keys.DESIGNED)


class TemplateDraftStale(DomainConflict):
    """The draft or the published version moved since the caller read it."""

    code = "stale_version"


class TemplateLintFailed(DomainInvalid):
    """The draft breaks the text lint; facts name each rule and where, never the text."""

    code = "template_lint_failed"

    def __init__(self, findings: list[LintFinding]) -> None:
        facts: dict[str, object] = {"count": len(findings)}
        for n, finding in enumerate(findings[:_MAX_FINDING_FACTS]):
            facts[f"finding_{n}"] = finding.fact()
        super().__init__(self.code, facts=facts)
        self.findings = findings


@dataclass(frozen=True)
class TemplateState:
    registration: EmailTemplateRegistration
    published: StoredVersion | None  # the version in use: the firm's, else the platform's
    draft: StoredDraft | None

    @property
    def next_version(self) -> int:
        return (self.published.version if self.published is not None else 0) + 1


@dataclass(frozen=True)
class Published:
    key: str
    template_id: UUID
    version_id: UUID
    version: int
    content: TemplateContent
    content_sha256: str
    published_at: datetime | None


def _firm(ctx: AuthContext) -> Resource:
    return Resource.firm(ctx.tenant_id)


def editable(key: str) -> EmailTemplateRegistration:
    registration = registration_of(key)
    if registration is None or not registration.firm_editable:
        raise NotFound("email_template")
    return registration


async def _editor_on(ctx: AuthContext) -> None:
    if not await flag_enabled(ctx.tenant, PORTAL_SETTINGS_EDITOR):
        raise NotFound(PORTAL_SETTINGS_EDITOR.name)


def check_content(content: TemplateContent, registration: EmailTemplateRegistration) -> None:
    """What a draft must be to be saved at all (the lint findings may remain until publish)."""
    if (content.cta_label is None) != (content.cta_target is None):
        raise TemplateInvalid
    if content.cta_target is not None and content.cta_target not in registration.cta_targets:
        raise TemplateInvalid
    if len({b.id for b in content.blocks}) != len(content.blocks):
        raise TemplateInvalid
    if not content.subject.strip() or "\n" in content.subject or "\n" in content.preheader:
        raise TemplateInvalid
    content_variables(content)  # a stray brace is refused here; unknown names are lint findings


async def _state(ctx: AuthContext, registration: EmailTemplateRegistration) -> TemplateState:
    async with tenant_session(ctx.tenant) as session:
        published = await template_store.resolve(session, ctx.tenant_id, registration.key)
        if published is not None and published.content is None:
            published = None  # a P-01-T05 text version is not a block template
        firm_id = await template_store.firm_template_id(session, registration.key)
        draft = (
            None
            if firm_id is None
            else await template_store.draft_of(session, ctx.tenant_id, firm_id)
        )
    return TemplateState(registration, published, draft)


async def list_templates(ctx: AuthContext) -> list[TemplateState]:
    """POR-20's list: the designed six first, then keys other epics register."""
    await authorise(ctx, "email_template.read", _firm(ctx))
    editable_keys = [r for r in registered_templates() if r.firm_editable]
    ordered = [r for r in template_keys.DESIGNED if r in editable_keys] + [
        r for r in editable_keys if not r.designed
    ]
    return [await _state(ctx, r) for r in ordered]


async def template_state(ctx: AuthContext, key: str) -> TemplateState:
    await authorise(ctx, "email_template.read", _firm(ctx))
    return await _state(ctx, editable(key))


async def save_draft(
    ctx: AuthContext, key: str, content: TemplateContent, expected_version: int
) -> StoredDraft:
    await authorise(ctx, "email_template.edit", _firm(ctx))
    await _editor_on(ctx)
    registration = editable(key)
    check_content(content, registration)
    async with uow(ctx.tenant) as tx:
        template_id = await template_store.ensure_firm_template(
            tx.session, key, registration.audience
        )
        current = await template_store.draft_of(tx.session, ctx.tenant_id, template_id, lock=True)
        have = current.draft_version if current is not None else 0
        if expected_version != have:
            raise TemplateDraftStale(facts={"draft_version": have})
        if current is not None:
            base = current.base_version_id
        else:
            published = await template_store.resolve(tx.session, ctx.tenant_id, key)
            base = published.version_id if published is not None else None
        await template_store.put_draft(
            tx.session,
            ctx.tenant_id,
            template_id,
            base_version_id=base,
            draft_version=have + 1,
            content=content,
            updated_by=ctx.user_id,
        )
        tx.record(
            "email_template.draft_saved",
            target=Target("email_template", template_id),
            after=Ref(draft_version=have + 1),
        )
        saved = await template_store.draft_of(tx.session, ctx.tenant_id, template_id)
    if saved is None:  # pragma: no cover -- written above in the same unit of work
        raise TemplateDraftStale
    return saved


async def discard_draft(ctx: AuthContext, key: str) -> TemplateState:
    await authorise(ctx, "email_template.edit", _firm(ctx))
    await _editor_on(ctx)
    registration = editable(key)
    async with uow(ctx.tenant) as tx:
        template_id = await template_store.firm_template_id(tx.session, key)
        draft = (
            None
            if template_id is None
            else await template_store.draft_of(tx.session, ctx.tenant_id, template_id, lock=True)
        )
        if template_id is None or draft is None:
            raise NotFound("email_template_draft")
        await template_store.delete_draft(tx.session, template_id)
        tx.record(
            "email_template.draft_discarded",
            target=Target("email_template", template_id),
            before=Ref(draft_version=draft.draft_version),
        )
    return await _state(ctx, registration)


async def check_publish(ctx: AuthContext, key: str) -> None:
    """Authorise a publish before an idempotent replay answers (ED-026's lesson)."""
    await authorise(ctx, "email_template.publish", _firm(ctx))
    await _editor_on(ctx)
    editable(key)


async def publish(ctx: AuthContext, key: str, *, source: Source = "editor") -> Published:
    """Publish the firm's draft of `key` as version n+1 (insert-only), retiring n."""
    await check_publish(ctx, key)
    registration = editable(key)
    async with uow(ctx.tenant) as tx:
        template_id = await template_store.firm_template_id(tx.session, key)
        draft = (
            None
            if template_id is None
            else await template_store.draft_of(tx.session, ctx.tenant_id, template_id, lock=True)
        )
        if template_id is None or draft is None:
            raise TemplateDraftStale(facts={"draft_version": 0})
        current = await template_store.resolve(tx.session, ctx.tenant_id, key)
        current_id = current.version_id if current is not None else None
        if draft.base_version_id != current_id:
            raise TemplateDraftStale(facts={"draft_version": draft.draft_version})
        check_content(draft.content, registration)
        findings = lint_template(draft.content, registration)
        if findings:
            raise TemplateLintFailed(findings)
        version = (current.version if current is not None else 0) + 1
        try:
            version_id, sha = await template_store.publish_version(
                tx.session,
                ctx.tenant_id,
                key,
                template_id,
                version,
                draft.content,
                published_by=f"user:{ctx.user_id}",
                source=source,
            )
        except DBAPIError as exc:
            if getattr(exc.orig, "sqlstate", None) == _SERIALIZATION:
                raise TemplateDraftStale(facts={"draft_version": draft.draft_version}) from None
            raise
        await template_store.delete_draft(tx.session, template_id)
        tx.record(
            "email_template.published",
            target=Target("email_template", template_id),
            before=Ref(version_id=current_id) if current_id is not None else None,
            after=Ref(version_id=version_id, version=version, sha256=sha),
        )
        tx.emit(EmailTemplatePublished(key=key, version=version))
        stored = await template_store.version_at(tx.session, ctx.tenant_id, key, version)
    return Published(
        key,
        template_id,
        version_id,
        version,
        draft.content,
        sha,
        stored.published_at if stored is not None else None,
    )


def person_of(published_by: str) -> UUID | None:
    """The firm member who published a version (`user:<id>`); None for a platform default."""
    kind, _, value = published_by.partition(":")
    if kind != "user":
        return None
    try:
        return UUID(value)
    except ValueError:
        return None
