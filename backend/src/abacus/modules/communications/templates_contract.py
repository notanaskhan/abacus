"""C16 v1.1: the firm email template, sending-domain and follow-up policy routes, stubbed
(R-01-T16; SPEC-345; R-01 §4.3). Contract: `docs/contracts/email-templates.md`.

For POR-20 and ADM-10 (R-01-T25, T28), and the keys' consumers (P-06, N-02, A-02, A-08, R-02,
A-07, T-02). C16 v1 (`docs/contracts/notifications.md`) is frozen and unchanged: these are new
routes and new models beside it.

- Reads (`email_template.read`, `portal_settings.read`, `sending_domain.read`) and the onboarding
  import are never behind a flag: with the editor off the screens show the published values
  read-only. They answer 501 until their task (list and read R-01-T19; preview and import
  R-01-T23; follow-up policy R-01-T24; sending domains R-01-T27).
- Template writes (draft save and discard, test send, publish) are behind `portal.settings_editor`;
  sending-domain writes behind `communications.firm_sender_domain`. Off: 404. On: 501.

Publish and test send carry `Idempotency-Key` (a client-visible version; an email). Publish,
import and test send need a fresh second factor; test send also an onshore member, and goes only
to the acting admin. A `sample_contact_id` on preview or test send renders only what the viewer
could read themselves (`communications.api.viewer_scoped`, DEC-379), else the sample client, and
the filled values pass `lint_values` (a client-written title never carries an amount, a TIN or an
account number out). The stubs check the flag first; the implementing tasks authorise first.
A lint failure is 422 `template_lint_failed` with identifier-only findings (`{code, block_id,
variable}`), never the text or the value.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, NoReturn, cast
from uuid import UUID

from fastapi import Depends, Header, Path
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import COMMUNICATIONS_FIRM_SENDER_DOMAIN, PORTAL_SETTINGS_EDITOR
from abacus.kernel.classification import classified
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import Flag, flag_enabled
from abacus.kernel.uow.idempotency import idempotent
from abacus.modules.communications import template_service, template_store
from abacus.modules.communications.render import Block, TemplateContent
from abacus.modules.communications.template_registry import VARIABLES as TEMPLATE_VARIABLES
from abacus.modules.communications.template_registry import (
    CtaTarget,
    FollowUpMode,
    LintCode,
    TemplateAudience,
    VariableClass,
    VariableKind,
)
from abacus.modules.communications.template_service import TemplateState, person_of
from abacus.modules.communications.template_store import StoredDraft, StoredVersion
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Resource,
    allowed_actions,
    current_context,
    names_of,
)

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
TemplateKey = Annotated[str, Path(pattern=r"^[a-z][a-z0-9_]{1,49}$")]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
BlockKind = Literal["heading", "paragraph", "item_list", "note", "footer"]
TemplateGroup = Literal["designed", "registered"]
TemplateAllowedAction = Literal["edit", "test_send", "publish"]
SendingDomainStatus = Literal["pending_dns", "verified", "failed", "revoked"]
DnsRecordType = Literal["CNAME", "MX", "TXT"]
DnsRecordStatus = Literal["pending", "verified", "failed"]


class TemplatePersonOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    display_name: Annotated[str, classified("internal")]


class TemplateBlock(BaseModel):
    """One block of a template body, typed by a person or imported; never model text (P-25
    off). Variables appear as `{name}` and must be the key's whitelisted ones."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Annotated[str, Field(pattern=r"^[a-z0-9_-]{1,40}$"), classified("internal")]
    kind: Annotated[BlockKind, classified("internal")]
    text: Annotated[str, Field(max_length=2000), classified("confidential")]


class TemplateVariableOut(BaseModel):
    """A variable the key may use, with what it resolves to; never an amount, an account
    number or a TIN (R-01 §4.7)."""

    model_config = ConfigDict(frozen=True)

    name: Annotated[str, classified("public")]
    kind: Annotated[VariableKind, classified("public")]
    classification: Annotated[VariableClass, classified("public")]
    block: Annotated[bool, classified("public")]


class TemplateVersionRefOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: Annotated[int, Field(ge=1), classified("internal")]
    published_at: Annotated[datetime, classified("internal")]
    # None: the platform default (no firm member published it).
    published_by: Annotated[TemplatePersonOut | None, classified("internal")] = None


class TemplateDraftRefOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: Annotated[int, Field(ge=1), classified("internal")]  # "Draft changes · v4"
    saved_at: Annotated[datetime, classified("internal")]


class EmailTemplateRowOut(BaseModel):
    """A POR-20 list row: "Published · v3", "Draft changes · v4", "Used by" links."""

    model_config = ConfigDict(frozen=True)

    key: Annotated[str, classified("internal")]
    name: Annotated[str, classified("public")]
    group: Annotated[TemplateGroup, classified("internal")]
    audience: Annotated[list[TemplateAudience], classified("internal")]
    used_by_label: Annotated[str, classified("public")]
    used_by_screen: Annotated[str | None, classified("internal")] = None
    published: Annotated[TemplateVersionRefOut | None, classified("internal")] = None
    draft: Annotated[TemplateDraftRefOut | None, classified("internal")] = None


class EmailTemplateListOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[EmailTemplateRowOut], Field(max_length=100), classified("internal")]


class EmailTemplateVersionOut(BaseModel):
    """A published version: insert-only, never edited (R-01 Story 7.3)."""

    model_config = ConfigDict(frozen=True)

    version: Annotated[int, Field(ge=1), classified("internal")]
    subject: Annotated[str, classified("confidential")]
    preheader: Annotated[str, classified("confidential")]
    blocks: Annotated[list[TemplateBlock], classified("confidential")]
    cta_label: Annotated[str | None, classified("confidential")]
    cta_target: Annotated[CtaTarget | None, classified("internal")]
    content_sha256: Annotated[Sha256, classified("internal")]
    published_at: Annotated[datetime, classified("internal")]
    # None: the platform default (no firm member published it).
    published_by: Annotated[TemplatePersonOut | None, classified("internal")] = None


class EmailTemplateDraftOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    expected_version: Annotated[int, Field(ge=0), classified("internal")]
    base_version: Annotated[int | None, classified("internal")]
    subject: Annotated[str, classified("confidential")]
    preheader: Annotated[str, classified("confidential")]
    blocks: Annotated[list[TemplateBlock], classified("confidential")]
    cta_label: Annotated[str | None, classified("confidential")]
    cta_target: Annotated[CtaTarget | None, classified("internal")]
    saved_at: Annotated[datetime, classified("internal")]
    saved_by: Annotated[TemplatePersonOut, classified("internal")]


class EmailTemplateOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Annotated[str, classified("internal")]
    name: Annotated[str, classified("public")]
    audience: Annotated[list[TemplateAudience], classified("internal")]
    firm_editable: Annotated[bool, classified("internal")]
    variables: Annotated[list[TemplateVariableOut], classified("public")]
    published: Annotated[EmailTemplateVersionOut | None, classified("confidential")] = None
    draft: Annotated[EmailTemplateDraftOut | None, classified("confidential")] = None
    allowed_actions: Annotated[list[TemplateAllowedAction], classified("internal")] = []


class EmailTemplateDraftIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    subject: Annotated[str, Field(min_length=1, max_length=200), classified("confidential")]
    preheader: Annotated[str, Field(max_length=200), classified("confidential")] = ""
    blocks: Annotated[list[TemplateBlock], Field(max_length=40), classified("confidential")]
    cta_label: Annotated[
        str | None, Field(default=None, max_length=60), classified("confidential")
    ]
    cta_target: Annotated[CtaTarget | None, classified("internal")] = None
    expected_version: Annotated[int, Field(ge=0), classified("internal")]


class LintFindingOut(BaseModel):
    """One lint finding: what and where, never the text (identifier-only facts)."""

    model_config = ConfigDict(frozen=True)

    code: Annotated[LintCode, classified("internal")]
    block_id: Annotated[str | None, classified("internal")] = None
    variable: Annotated[str | None, classified("internal")] = None  # unregistered_variable


class EmailPreviewIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: Annotated[Literal["draft", "published"], classified("internal")] = "draft"
    width: Annotated[Literal[600, 390], classified("internal")] = 600
    sample_contact_id: Annotated[UUID | None, classified("internal")] = None


class EmailPreviewOut(BaseModel):
    """Deterministic: the same version and values give byte-identical HTML and text."""

    model_config = ConfigDict(frozen=True)

    subject: Annotated[str, classified("confidential")]
    html: Annotated[str, classified("confidential")]
    text: Annotated[str, classified("confidential")]
    from_display: Annotated[str, classified("public")]
    from_address: Annotated[str, classified("internal")]
    reply_to: Annotated[str | None, classified("internal")] = None
    findings: Annotated[list[LintFindingOut], classified("internal")] = []


class EmailTestSendIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sample_contact_id: Annotated[UUID | None, classified("internal")] = None


class EmailTestSendOut(BaseModel):
    """Sent to the acting admin only, subject prefixed "[Test]" (synthetic tenants: the sink)."""

    model_config = ConfigDict(frozen=True)

    message_id: Annotated[UUID, classified("internal")]
    sent_to: Annotated[str, classified("confidential")]  # the admin's own address
    subject: Annotated[str, classified("confidential")]


class EmailTemplateBundleEntryIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{1,49}$"), classified("internal")]
    subject: Annotated[str, Field(min_length=1, max_length=200), classified("confidential")]
    preheader: Annotated[str, Field(max_length=200), classified("confidential")] = ""
    blocks: Annotated[list[TemplateBlock], Field(max_length=40), classified("confidential")]
    cta_label: Annotated[
        str | None, Field(default=None, max_length=60), classified("confidential")
    ]
    cta_target: Annotated[CtaTarget | None, classified("internal")] = None
    publish: Annotated[bool, classified("internal")] = False


class FirmEmailTemplateImportIn(BaseModel):
    """A counsel-approved onboarding bundle (F-09-T115 pattern). Distinct from C16 v1's staff
    `EmailTemplateImportIn`, which stays frozen."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    bundle: Annotated[
        list[EmailTemplateBundleEntryIn],
        Field(min_length=1, max_length=50),
        classified("confidential"),
    ]
    dry_run: Annotated[bool, classified("internal")] = True


class TemplateImportResultOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Annotated[str, classified("internal")]
    change: Annotated[Literal["add", "update", "unchanged", "refused"], classified("internal")]
    findings: Annotated[list[LintFindingOut], classified("internal")] = []


class FirmEmailTemplateImportOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    dry_run: Annotated[bool, classified("internal")]
    results: Annotated[list[TemplateImportResultOut], classified("internal")]


# --- sending domains (ADM-10 d) ------------------------------------------------------------------


class DnsRecordOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Annotated[DnsRecordType, classified("public")]
    name: Annotated[str, classified("public")]
    value: Annotated[str, classified("public")]
    status: Annotated[DnsRecordStatus, classified("internal")]


class SendingDomainOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    domain: Annotated[str, classified("internal")]
    from_local_part: Annotated[str, classified("internal")]
    mail_from_domain: Annotated[str, classified("internal")]
    status: Annotated[SendingDomainStatus, classified("internal")]
    records: Annotated[list[DnsRecordOut], classified("public")]
    failure_reason: Annotated[str | None, classified("internal")] = None
    requested_at: Annotated[datetime, classified("internal")]
    verified_at: Annotated[datetime | None, classified("internal")] = None
    last_checked_at: Annotated[datetime | None, classified("internal")] = None


class SendingDomainListOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[SendingDomainOut], Field(max_length=10), classified("internal")]


class SendingDomainIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    domain: Annotated[
        str,
        Field(pattern=r"^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$", max_length=253),
        classified("internal"),
    ]
    from_local_part: Annotated[
        str, Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,63}$"), classified("internal")
    ] = "clients"


# --- the follow-up policy (DEC-74) ---------------------------------------------------------------


class FollowUpPolicyFields(BaseModel):
    """The firm's one follow-up policy (R-01 §4.2 `follow_up_policies`), shared by POR-20's
    Reminder schedule and ADM-10's Reminders; P-06's per-binder override wins over it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cadence_days: Annotated[int, Field(ge=1, le=30), classified("internal")] = 7
    max_reminders: Annotated[int, Field(ge=1, le=4), classified("internal")] = 4
    send_local_time: Annotated[
        str, Field(pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$"), classified("internal")
    ] = "09:00"
    weekdays_only: Annotated[bool, classified("internal")] = True
    stop_on_binder_done: Annotated[bool, classified("internal")] = True
    notify_preparer_after_max: Annotated[bool, classified("internal")] = True
    cc_assigned_preparer: Annotated[bool, classified("internal")] = False
    # `send_on_schedule` sends only while `follow_ups.scheduled_send` is on for the firm.
    mode: Annotated[FollowUpMode, classified("internal")] = "draft_for_person"


class NextSendOut(BaseModel):
    """The next reminder for one recipient: the same pure function the scheduler uses
    (`next_send_at`: cadence, weekday shift, the recipient's time zone)."""

    model_config = ConfigDict(frozen=True)

    sample_contact_id: Annotated[UUID | None, classified("internal")]  # None: the sample client
    last_sent_at: Annotated[datetime | None, classified("internal")]
    next_send_at: Annotated[datetime, classified("internal")]
    shifted_from: Annotated[date | None, classified("internal")] = None  # Sat Sep 19 → Mon


class FollowUpPolicyOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    policy: Annotated[FollowUpPolicyFields, classified("internal")]
    version: Annotated[int, Field(ge=0), classified("internal")]
    next_send: Annotated[NextSendOut | None, classified("internal")] = None


async def _stub(ctx: AuthContext, flag: Flag | None = None) -> NoReturn:
    if flag is not None and not await flag_enabled(ctx.tenant, flag):
        raise NotFound(flag.name)
    raise NotImplementedYet


templates_router = AbacusRouter(prefix="/v1/firm/email-templates", tags=["email templates"])
domains_router = AbacusRouter(prefix="/v1/firm/sending-domains", tags=["email templates"])
policy_router = AbacusRouter(prefix="/v1/firm/follow-up-policy", tags=["email templates"])


# --- R-01-T19: list, read, draft and publish -----------------------------------------------------


async def _people(ids: set[UUID]) -> dict[UUID, TemplatePersonOut]:
    names = await names_of(sorted(ids))
    return {i: TemplatePersonOut(user_id=i, display_name=names.get(i, "")) for i in ids}


def _publishers(states: list[TemplateState]) -> set[UUID]:
    found: set[UUID] = set()
    for state in states:
        if state.published is not None:
            person = person_of(state.published.published_by)
            if person is not None:
                found.add(person)
        if state.draft is not None:
            found.add(state.draft.updated_by)
    return found


def _block_out(content: TemplateContent) -> list[TemplateBlock]:
    return [TemplateBlock(id=b.id, kind=b.kind, text=b.text) for b in content.blocks]


def _content_in(body: EmailTemplateDraftIn) -> TemplateContent:
    return TemplateContent(
        subject=body.subject,
        preheader=body.preheader,
        blocks=tuple(Block(b.id, b.kind, b.text) for b in body.blocks),
        cta_label=body.cta_label,
        cta_target=body.cta_target,
    )


def _published_by(
    version: StoredVersion, people: dict[UUID, TemplatePersonOut]
) -> TemplatePersonOut | None:
    person = person_of(version.published_by)
    return people.get(person) if person is not None else None


def _row(state: TemplateState, people: dict[UUID, TemplatePersonOut]) -> EmailTemplateRowOut:
    r = state.registration
    published = state.published
    return EmailTemplateRowOut(
        key=r.key,
        name=r.name,
        group="designed" if r.designed else "registered",
        audience=list(r.audience),
        used_by_label=r.used_by_label,
        used_by_screen=r.used_by[0] if r.used_by else None,
        published=None
        if published is None
        else TemplateVersionRefOut(
            version=published.version,
            published_at=published.published_at,
            published_by=_published_by(published, people),
        ),
        draft=None
        if state.draft is None
        else TemplateDraftRefOut(version=state.next_version, saved_at=state.draft.updated_at),
    )


def _version_out(
    version: StoredVersion, people: dict[UUID, TemplatePersonOut]
) -> EmailTemplateVersionOut | None:
    content = version.content
    if content is None:
        return None
    return EmailTemplateVersionOut(
        version=version.version,
        subject=content.subject,
        preheader=content.preheader,
        blocks=_block_out(content),
        cta_label=content.cta_label,
        cta_target=cast(CtaTarget | None, content.cta_target),
        content_sha256=version.content_sha256,
        published_at=version.published_at,
        published_by=_published_by(version, people),
    )


def _draft_out(
    state: TemplateState, draft: StoredDraft, people: dict[UUID, TemplatePersonOut]
) -> EmailTemplateDraftOut:
    published = state.published
    based_on_current = published is not None and draft.base_version_id == published.version_id
    content = draft.content
    return EmailTemplateDraftOut(
        expected_version=draft.draft_version,
        base_version=published.version if based_on_current and published is not None else None,
        subject=content.subject,
        preheader=content.preheader,
        blocks=_block_out(content),
        cta_label=content.cta_label,
        cta_target=cast(CtaTarget | None, content.cta_target),
        saved_at=draft.updated_at,
        saved_by=people.get(draft.updated_by)
        or TemplatePersonOut(user_id=draft.updated_by, display_name=""),
    )


async def _template_out(ctx: AuthContext, state: TemplateState) -> EmailTemplateOut:
    people = await _people(_publishers([state]))
    r = state.registration
    actions = await allowed_actions(
        ctx,
        Resource.firm(ctx.tenant_id),
        ("email_template.edit", "email_template.test_send", "email_template.publish"),
    )
    if not await flag_enabled(ctx.tenant, PORTAL_SETTINGS_EDITOR):
        actions = frozenset[str]()  # off: the screens show the published values read-only
    allowed: list[TemplateAllowedAction] = [
        a for a in ("edit", "test_send", "publish") if f"email_template.{a}" in actions
    ]
    if state.draft is None and "publish" in allowed:
        allowed.remove("publish")  # nothing to publish
    return EmailTemplateOut(
        key=r.key,
        name=r.name,
        audience=list(r.audience),
        firm_editable=r.firm_editable,
        variables=[
            TemplateVariableOut(
                name=v.name, kind=v.kind, classification=v.classification, block=v.block
            )
            for v in (TEMPLATE_VARIABLES[name] for name in r.variables)
        ],
        published=None if state.published is None else _version_out(state.published, people),
        draft=None if state.draft is None else _draft_out(state, state.draft, people),
        allowed_actions=allowed,
    )


@templates_router.get("", action="email_template.read", response_model=EmailTemplateListOut)
async def list_email_templates_route(ctx: Ctx) -> EmailTemplateListOut:
    """POR-20 list, ADM-10 rows (R-01-T19): the designed six first, registered keys after."""
    states = await template_service.list_templates(ctx)
    people = await _people(_publishers(states))
    return EmailTemplateListOut(items=[_row(state, people) for state in states])


@templates_router.post(
    "/import",
    action="email_template.import",
    response_model=FirmEmailTemplateImportOut,
    status_code=200,
    errors=(501,),
)
async def import_email_templates_route(
    body: FirmEmailTemplateImportIn, ctx: Ctx
) -> FirmEmailTemplateImportOut:
    """Onboarding (R-01-T23): the dry run lints every key and reports changes; applying creates
    drafts or published versions as database rows. Audited `email_template.imported` (dry runs
    are not)."""
    await _stub(ctx)


@templates_router.get("/{key}", action="email_template.read", response_model=EmailTemplateOut)
async def get_email_template_route(key: TemplateKey, ctx: Ctx) -> EmailTemplateOut:
    """The editor: published version, draft, whitelisted variables (R-01-T19). 404 for a key
    that is not registered firm-editable."""
    return await _template_out(ctx, await template_service.template_state(ctx, key))


@templates_router.put(
    "/{key}/draft",
    action="email_template.edit",
    response_model=EmailTemplateDraftOut,
    errors=(409,),
)
async def save_email_template_draft_route(
    key: TemplateKey, body: EmailTemplateDraftIn, ctx: Ctx
) -> EmailTemplateDraftOut:
    """POR-20 b (R-01-T19): 409 `stale_version` on an old `expected_version`; 422
    `template_invalid` for a call to action the key does not register, a repeated block id or a
    stray brace. Audited `email_template.draft_saved`."""
    await template_service.save_draft(ctx, key, _content_in(body), body.expected_version)
    state = await template_service.template_state(ctx, key)
    if state.draft is None:  # pragma: no cover -- saved above
        raise NotFound("email_template_draft")
    people = await _people(_publishers([state]))
    return _draft_out(state, state.draft, people)


@templates_router.delete(
    "/{key}/draft", action="email_template.edit", response_model=EmailTemplateOut
)
async def discard_email_template_draft_route(key: TemplateKey, ctx: Ctx) -> EmailTemplateOut:
    """Discard the draft (R-01-T19); 404 when there is none. Audited
    `email_template.draft_discarded`."""
    return await _template_out(ctx, await template_service.discard_draft(ctx, key))


@templates_router.post(
    "/{key}/preview",
    action="email_template.read",
    response_model=EmailPreviewOut,
    errors=(501,),
)
async def preview_email_template_route(
    key: TemplateKey, body: EmailPreviewIn, ctx: Ctx
) -> EmailPreviewOut:
    """POR-20 a, c, d (R-01-T23): deterministic HTML and text plus lint findings on the text and
    the filled values; the sample contact's items only as far as the viewer may read them
    (DEC-379); creates nothing."""
    await _stub(ctx)


@templates_router.post(
    "/{key}/test-send",
    action="email_template.test_send",
    response_model=EmailTestSendOut,
    status_code=202,
    errors=(501,),
)
async def test_send_email_template_route(
    key: TemplateKey, body: EmailTestSendIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> EmailTestSendOut:
    """POR-20 j, k (R-01-T23): to the acting admin only, fresh MFA, onshore; the sample
    contact's items as far as the viewer may read them (DEC-379); 422 `template_lint_failed`.
    Audited `email_template.test_sent`."""
    await _stub(ctx, PORTAL_SETTINGS_EDITOR)


@templates_router.post(
    "/{key}/publish",
    action="email_template.publish",
    response_model=EmailTemplateVersionOut,
    status_code=201,
    errors=(409,),
)
async def publish_email_template_route(
    key: TemplateKey, ctx: Ctx, idempotency_key: IdempotencyKey
) -> EmailTemplateVersionOut:
    """POR-20 l (R-01-T19): version n+1, insert-only, retires n; 409 `stale_version` when the
    draft moved or there is none, 422 `template_lint_failed` (facts `count` and `finding_<n>`
    = `code:where`, never the text). Audited `email_template.published`; outbox
    `email_template.published {key, version}`. A retry with the same key answers the stored
    version, after authorising again."""
    await template_service.check_publish(ctx, key)

    async def run() -> tuple[int, dict[str, object]]:
        published = await template_service.publish(ctx, key)
        # The stored answer holds identifiers only (P-36): the text is read back on a replay.
        return 201, {"version": published.version}

    stored = await idempotent(
        ctx.tenant,
        route="email_templates.publish",
        key=idempotency_key,
        body={"key": key},
        run=run,
    )
    version = int(cast(int, stored.body["version"]))
    async with tenant_session(ctx.tenant) as session:
        found = await template_store.version_at(session, ctx.tenant_id, key, version)
    out = None if found is None else _version_out(found, await _people(_publishers_of(found)))
    if out is None:  # pragma: no cover -- written above, insert-only
        raise NotFound("email_template_version")
    return out


def _publishers_of(version: StoredVersion) -> set[UUID]:
    person = person_of(version.published_by)
    return set() if person is None else {person}


@domains_router.get(
    "", action="sending_domain.read", response_model=SendingDomainListOut, errors=(501,)
)
async def list_sending_domains_route(ctx: Ctx) -> SendingDomainListOut:
    """ADM-10 d (R-01-T27): the firm's sender domain and its DNS records."""
    await _stub(ctx)


@domains_router.post(
    "",
    action="sending_domain.manage",
    response_model=SendingDomainOut,
    status_code=201,
    errors=(409, 501),
)
async def create_sending_domain_route(
    body: SendingDomainIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> SendingDomainOut:
    """An SES identity with Easy DKIM and a custom MAIL FROM; `pending_dns` (R-01-T27); 409
    `sending_domain_exists` while one is pending or verified. Audited `sending_domain.created`."""
    await _stub(ctx, COMMUNICATIONS_FIRM_SENDER_DOMAIN)


@domains_router.post(
    "/{domain_id}/check",
    action="sending_domain.manage",
    response_model=SendingDomainOut,
    errors=(501,),
)
async def check_sending_domain_route(domain_id: UUID, ctx: Ctx) -> SendingDomainOut:
    """Check the identity now (R-01-T27); the workflow checks every 15 minutes for 72 hours."""
    await _stub(ctx, COMMUNICATIONS_FIRM_SENDER_DOMAIN)


@domains_router.delete(
    "/{domain_id}",
    action="sending_domain.manage",
    response_model=SendingDomainOut,
    errors=(501,),
)
async def revoke_sending_domain_route(domain_id: UUID, ctx: Ctx) -> SendingDomainOut:
    """Revoke (R-01-T27): client mail returns to the neutral sender. Audited
    `sending_domain.revoked`."""
    await _stub(ctx, COMMUNICATIONS_FIRM_SENDER_DOMAIN)


@policy_router.get(
    "", action="portal_settings.read", response_model=FollowUpPolicyOut, errors=(501,)
)
async def get_follow_up_policy_route(
    ctx: Ctx, sample_contact_id: UUID | None = None
) -> FollowUpPolicyOut:
    """The policy and the next send for a sample recipient (R-01-T24): Mon Sep 14 + 7 days is
    Mon Sep 21; + 5 days is Sat Sep 19, shifted to Mon Sep 21."""
    await _stub(ctx)
