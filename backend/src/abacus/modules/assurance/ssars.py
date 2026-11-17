"""The SSARS workspace (A-08-T22; A-08 §3 F8; SPEC-657 AC-8.1 to AC-8.6; AUD-26 a to e; DEC-5401;
amber).

- **Mode** is the engagement type, read-only: review (AR-C 90), compilation (AR-C 80),
  preparation (AR-C 70). Any other type is not an SSARS work item (404).
- **Rail per mode**: review shows Inquiries · Analytics · FS · Report; compilation replaces
  Inquiries and Analytics with "Read the FS for obvious material misstatements" (a working paper
  of kind `ssars_read_fs`, signed at L1); preparation shows FS · Report (muted, "No report —
  AR-C 70") · the client's approval from C18 ("Approved by Carla Juniper (POR-08)").
- **SSARS review analytics** (`kind = ssars_review`, stage `review`) threshold at the firm's
  variance policy (`ssars_variance_pct` **and** `ssars_variance_amount`, firm settings; unset
  reads 10% and $50,000) through the same analytics service; a person records expectations.
- **Inquiry program**: the firm's methodology program's steps become one T-02 `ssars_inquiry`
  questionnaire per recipient (the same questions in each); a person publishes it (every question
  sent) and sends templated reminders they edited (DV-4). A question counts as answered when any
  recipient answered it ("Answered 11 · Open 3").
- **Preparation**: the legend "No assurance is provided." and no report (409
  `no_report_for_preparation`, also on AUD-23's report draft).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Annotated, ClassVar, Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import DomainEvent, Ref, Target, uow
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    SettingKey,
    authorise,
    register_firm_setting,
    stored_value,
)

Mode = Literal["review", "compilation", "preparation"]
Standard = Literal["AR-C 90", "AR-C 80", "AR-C 70"]
RailKey = Literal["inquiries", "analytics", "read_fs", "fs", "report", "approval"]

STANDARD: Final[dict[str, Standard]] = {
    "review": "AR-C 90",
    "compilation": "AR-C 80",
    "preparation": "AR-C 70",
}
LEGEND: Final = "No assurance is provided."
READ_FS_CODE: Final = "RFS-1"
READ_FS_KIND: Final = "ssars_read_fs"
READ_FS_TITLE: Final = "Read the FS for obvious material misstatements"
# The firm's variance policy (AUD-26a): both legs; unset reads 10% and $50,000 (DEC-5401).
PCT_SETTING: Final = SettingKey("defaults", "ssars_variance_pct", "int", max_length=3)
AMOUNT_SETTING: Final = SettingKey("defaults", "ssars_variance_amount", "int", max_length=12)
DEFAULT_PCT: Final = Decimal("10")
DEFAULT_AMOUNT: Final = Decimal("50000")


class NoReportForPreparation(DomainConflict):
    """AR-C 70: no report for a preparation work item (AC-8.6)."""

    code = "no_report_for_preparation"


class NotSsars(DomainInvalid):
    code = "not_ssars_work_item"


class InquiryProgramEmpty(DomainInvalid):
    """The methodology program has no steps to ask."""

    code = "inquiry_program_empty"


class InquiriesAlreadyPublished(DomainConflict):
    code = "inquiries_already_published"


class NoInquiryProgram(DomainConflict):
    code = "inquiry_program_missing"


class SsarsInquiriesPublished(DomainEvent):
    event_type: ClassVar[str] = "ssars.inquiries_published"

    program_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    work_item_id: Annotated[UUID, classified("internal")]


@dataclass(frozen=True)
class RailRow:
    key: RailKey
    label: str
    state: str


@dataclass(frozen=True)
class InquirySummary:
    answered: int
    open: int
    questionnaire_id: UUID | None


@dataclass(frozen=True)
class Workspace:
    mode: Mode
    standard: Standard
    rail: tuple[RailRow, ...]
    analytics_set_id: UUID | None
    inquiries: InquirySummary | None
    legend: str | None
    report_available: bool
    approval_label: str | None


@dataclass(frozen=True)
class InquiryProgram:
    questionnaire_id: UUID
    questions: int
    published: bool


def register() -> None:
    register_firm_setting(PCT_SETTING)
    register_firm_setting(AMOUNT_SETTING)


def _person(ctx: AuthContext, action: str) -> None:
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(action, "role")


async def mode_of(tenant: TenantContext, engagement_id: UUID) -> Mode | None:
    from abacus.modules.engagements.api import engagement_type_of

    found = await engagement_type_of(tenant, engagement_id)
    return cast(Mode, found) if found in STANDARD else None


async def require_report_allowed(tenant: TenantContext, engagement_id: UUID) -> None:
    """AC-8.6: a preparation work item never gets a report (AUD-23 and AUD-26)."""
    if await mode_of(tenant, engagement_id) == "preparation":
        raise NoReportForPreparation(facts={"engagement": str(engagement_id)})


async def review_threshold(
    tenant: TenantContext, work_item_id: UUID
) -> tuple[object, UUID | None]:
    """The firm's variance policy as the analytics threshold (both legs; never provisional)."""
    from abacus.modules.assurance.analytics import ThresholdFacts

    pct = await stored_value(tenant, "defaults", "ssars_variance_pct")
    amount = await stored_value(tenant, "defaults", "ssars_variance_amount")
    return (
        ThresholdFacts(
            Decimal(str(pct)) if pct not in (None, "") else DEFAULT_PCT,
            Decimal(str(amount)) if amount not in (None, "") else DEFAULT_AMOUNT,
            None,
            None,
            False,
        ),
        None,
    )


async def _engagement(ctx: AuthContext, work_item_id: UUID) -> tuple[UUID, Mode]:
    from abacus.modules.engagements.api import work_item_engagement

    engagement_id = await work_item_engagement(ctx.tenant, work_item_id)
    if engagement_id is None:
        raise NotFound("work_item")
    mode = await mode_of(ctx.tenant, engagement_id)
    if mode is None:
        raise NotFound("ssars_work_item")
    return engagement_id, mode


# --- inquiries -----------------------------------------------------------------------------------

_LATEST_PROGRAM: Final = text(
    "SELECT id, questionnaire_ids, questions, published_at FROM ssars_inquiry_programs "
    "WHERE work_item_id = :w ORDER BY created_at DESC, id DESC LIMIT 1"
)
_INSERT_PROGRAM: Final = text(
    "INSERT INTO ssars_inquiry_programs (tenant_id, engagement_id, work_item_id, "
    "methodology_program_id, questionnaire_ids, questions, created_by) VALUES (:t, :e, :w, :p, "
    ":qs, :n, :by) RETURNING id"
)
_PUBLISH: Final = text(
    "UPDATE ssars_inquiry_programs SET published_at = clock_timestamp(), published_by = :by "
    "WHERE id = :id AND published_at IS NULL RETURNING id"
)


async def _latest(tenant: TenantContext, work_item_id: UUID) -> dict[str, object] | None:
    async with tenant_session(tenant) as session:
        found = (await session.execute(_LATEST_PROGRAM, {"w": work_item_id})).mappings().first()
    return None if found is None else dict(found)


async def inquiry_summary(ctx: AuthContext, work_item_id: UUID) -> InquirySummary | None:
    """A question is answered when any recipient answered it (by position across the copies)."""
    from abacus.modules.requests.api import questionnaire

    program = await _latest(ctx.tenant, work_item_id)
    if program is None:
        return None
    ids = cast("list[UUID]", program["questionnaire_ids"])
    answered: set[int] = set()
    total = int(cast(int, program["questions"]))
    for qid in ids:
        view = await questionnaire(ctx, qid)
        for n, q in enumerate(view.questions):
            if q.answer_version is not None:
                answered.add(n)
    return InquirySummary(len(answered), total - len(answered), ids[0] if ids else None)


async def build_inquiries(
    ctx: AuthContext,
    work_item_id: UUID,
    *,
    methodology_program_id: UUID,
    recipient_contact_ids: Sequence[UUID],
) -> InquiryProgram:
    """The firm's program steps, verbatim, as one questionnaire per recipient (drafts)."""
    from abacus.modules.methodology.api import program_steps
    from abacus.modules.requests.api import create_questionnaire, draft_question

    _person(ctx, "ssars.inquiry_manage")
    engagement_id, mode = await _engagement(ctx, work_item_id)
    if mode != "review":
        raise NotSsars(facts={"mode": mode})
    steps = await program_steps(ctx, methodology_program_id)
    if not steps:
        raise InquiryProgramEmpty(facts={"program": str(methodology_program_id)})
    questionnaire_ids: list[UUID] = []
    for contact in dict.fromkeys(recipient_contact_ids):
        created = await create_questionnaire(
            ctx,
            kind="ssars_inquiry",
            work_item_id=work_item_id,
            title="Inquiries",
            addressed_to_contact_id=contact,
            due_on=None,
            engagement_id=engagement_id,
        )
        for s in steps:
            await draft_question(
                ctx,
                created.id,
                section="Inquiries",
                type_="long_text",
                client_wording=s.step.text,
                help_text=None,
                linked_request_item_id=None,
            )
        questionnaire_ids.append(created.id)
    async with uow(ctx.tenant) as tx:
        program_id = cast(
            UUID,
            await tx.session.scalar(
                _INSERT_PROGRAM,
                {
                    "t": ctx.tenant_id,
                    "e": engagement_id,
                    "w": work_item_id,
                    "p": methodology_program_id,
                    "qs": questionnaire_ids,
                    "n": len(steps),
                    "by": ctx.user_id,
                },
            ),
        )
        tx.record(
            "ssars.inquiries_built",
            target=Target("ssars_inquiry_program", program_id),
            after=Ref(n=len(steps), m=len(questionnaire_ids)),
        )
    return InquiryProgram(questionnaire_ids[0], len(steps), False)


async def publish_inquiries(ctx: AuthContext, work_item_id: UUID) -> InquiryProgram:
    """A person publishes: every drafted question of every copy is sent (POR-05)."""
    from abacus.modules.requests.api import questionnaire, send_question

    _person(ctx, "ssars.inquiry_manage")
    engagement_id, _ = await _engagement(ctx, work_item_id)
    program = await _latest(ctx.tenant, work_item_id)
    if program is None:
        raise NoInquiryProgram(facts={"work_item": str(work_item_id)})
    if program["published_at"] is not None:
        raise InquiriesAlreadyPublished(facts={"work_item": str(work_item_id)})
    ids = cast("list[UUID]", program["questionnaire_ids"])
    for qid in ids:
        for q in (await questionnaire(ctx, qid)).questions:
            if q.sent_at is None:
                await send_question(ctx, q.id)
    async with uow(ctx.tenant) as tx:
        done = await tx.session.scalar(_PUBLISH, {"id": program["id"], "by": ctx.user_id})
        if done is None:
            raise InquiriesAlreadyPublished(facts={"work_item": str(work_item_id)})
        tx.record(
            "ssars.inquiries_published",
            target=Target("ssars_inquiry_program", cast(UUID, program["id"])),
            after=Ref(n=int(cast(int, program["questions"]))),
        )
        tx.emit(
            SsarsInquiriesPublished(
                program_id=cast(UUID, program["id"]),
                engagement_id=engagement_id,
                work_item_id=work_item_id,
            )
        )
    return InquiryProgram(ids[0], int(cast(int, program["questions"])), True)


async def remind(
    ctx: AuthContext, work_item_id: UUID, *, template_key: str, text_: str
) -> tuple[UUID, datetime]:
    """DV-4: a reminder a person worded from the firm template, sent to each recipient's copy as
    one more question on it ("Send reminder…")."""
    from abacus.kernel.clock import system_now
    from abacus.modules.requests.api import draft_question, send_question

    _person(ctx, "client_question.send")
    await _engagement(ctx, work_item_id)
    program = await _latest(ctx.tenant, work_item_id)
    if program is None or program["published_at"] is None:
        raise NoInquiryProgram(facts={"work_item": str(work_item_id)})
    ids = cast("list[UUID]", program["questionnaire_ids"])
    for qid in ids:
        drafted = await draft_question(
            ctx,
            qid,
            section="Reminders",
            type_="long_text",
            client_wording=text_.strip(),
            help_text=None,
            linked_request_item_id=None,
        )
        await send_question(ctx, drafted.id)
    async with uow(ctx.tenant) as tx:
        tx.record(
            "ssars.reminder_sent",
            target=Target("ssars_inquiry_program", cast(UUID, program["id"])),
            after=Ref(n=len(ids)),
        )
    del template_key  # recorded by the questionnaire's own history; the wording is the person's
    return ids[0], system_now()


# --- the workspace -------------------------------------------------------------------------------


async def _read_fs_state(ctx: AuthContext, engagement_id: UUID) -> str:
    from abacus.modules.workpapers.api import workpapers_for

    papers = await workpapers_for(ctx, engagement_id)
    found = next((p for p in papers if p.code == READ_FS_CODE), None)
    return "not_started" if found is None else str(found.status)


async def _fs_state(ctx: AuthContext, work_item_id: UUID) -> str:
    """S48 rest: the FS row reads the statements package's own state (reporting owns it)."""
    from abacus.modules.reporting.api import statements_package_state

    return await statements_package_state(ctx.tenant, work_item_id)


async def open_read_fs(ctx: AuthContext, work_item_id: UUID) -> UUID:
    """AUD-26c: the compilation's "Read the FS" procedure as a working paper (L1 sign-off)."""
    from abacus.modules.workpapers.api import create_workpaper, workpapers_for

    _person(ctx, "workpaper.edit")
    engagement_id, mode = await _engagement(ctx, work_item_id)
    if mode != "compilation":
        raise NotSsars(facts={"mode": mode})
    existing = next(
        (p for p in await workpapers_for(ctx, engagement_id) if p.code == READ_FS_CODE), None
    )
    if existing is not None:
        return existing.id
    return await create_workpaper(
        ctx, engagement_id, READ_FS_CODE, READ_FS_TITLE, None, kind=READ_FS_KIND
    )


async def _approval_label(ctx: AuthContext, engagement_id: UUID) -> str | None:
    """POR-08 via C18: the client's approval of the FS package, by name."""
    from abacus.modules.engagements.api import ApprovalKindNotRegistered, client_approval_provider

    try:
        provider = client_approval_provider("fs_package")
    except ApprovalKindNotRegistered:
        return None
    items = await provider.items(ctx.tenant, engagement_id)
    approved = [i for i in items if i.state == "approved" and i.decided_by]
    if not approved:
        return None
    latest = max(approved, key=lambda i: i.decided_at or datetime.min)
    return f"Approved by {latest.decided_by} (POR-08)"


async def workspace(ctx: AuthContext, work_item_id: UUID) -> Workspace:
    """`GET /v1/work-items/{wid}/ssars` (the route authorised `ssars.read`)."""
    engagement_id, mode = await _engagement(ctx, work_item_id)
    await authorise(ctx, "ssars.read", await _resource(ctx, engagement_id))
    analytics_set_id: UUID | None = None
    inquiries: InquirySummary | None = None
    rail: list[RailRow] = []
    if mode == "review":
        inquiries = await inquiry_summary(ctx, work_item_id)
        async with tenant_session(ctx.tenant) as session:
            current = (
                await session.execute(
                    text(
                        "SELECT id, status FROM analytics_sets WHERE work_item_id = :w AND "
                        "kind = 'ssars_review' AND status IN ('computing', 'current') "
                        "ORDER BY version_no DESC LIMIT 1"
                    ),
                    {"w": work_item_id},
                )
            ).first()
        analytics_set_id = current.id if current else None
        state = (
            "not_started"
            if inquiries is None
            else ("answered" if inquiries.open == 0 else "requested")
        )
        rail += [
            RailRow("inquiries", "Inquiries", state),
            RailRow("analytics", "Analytics", str(current.status) if current else "not_started"),
        ]
    if mode == "compilation":
        rail.append(RailRow("read_fs", READ_FS_TITLE, await _read_fs_state(ctx, engagement_id)))
    rail.append(RailRow("fs", "FS", await _fs_state(ctx, work_item_id)))
    if mode == "preparation":
        rail.append(RailRow("report", "No report — AR-C 70", "not_applicable"))
        approval = await _approval_label(ctx, engagement_id)
        rail.append(
            RailRow("approval", approval or "Approval", "approved" if approval else "requested")
        )
    else:
        label = (
            "Compilation report (AR-C 80)" if mode == "compilation" else "Review report (AR-C 90)"
        )
        rail.append(RailRow("report", label, "not_started"))
        approval = None
    return Workspace(
        mode=mode,
        standard=STANDARD[mode],
        rail=tuple(rail),
        analytics_set_id=analytics_set_id,
        inquiries=inquiries,
        legend=LEGEND if mode == "preparation" else None,
        report_available=mode != "preparation",
        approval_label=approval,
    )


async def _resource(ctx: AuthContext, engagement_id: UUID) -> Resource:
    from abacus.modules.engagements.api import get_ref

    return (await get_ref(ctx, engagement_id)).resource()


# --- expectations --------------------------------------------------------------------------------

_INSERT_EXPECTATION: Final = text(
    "INSERT INTO analytics_expectations (tenant_id, set_id, line_position, low, high, pct_low, "
    "pct_high, basis, citation_ids, set_by) VALUES (:t, :set, :pos, :low, :high, :pl, :ph, "
    ":basis, :cites, :by)"
)


async def put_expectation(
    ctx: AuthContext,
    set_id: UUID,
    position: int,
    *,
    low_pct: Decimal | None,
    high_pct: Decimal | None,
    basis: str,
    citation_ids: Sequence[UUID],
) -> object:
    """AR-C 90's expectation for a line (a range and its basis); a new row each time."""
    from abacus.modules.assurance import analytics

    _person(ctx, "analytics.configure")
    row = await analytics._current(ctx, set_id, "analytics.configure")  # pyright: ignore[reportPrivateUsage] -- the module's own check
    view = await analytics.set_view(ctx, set_id, authorised=True)
    line = next((x for x in view.lines if x.position == position), None)
    if line is None or line.derived:
        raise NotFound("analytics_line")
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            _INSERT_EXPECTATION,
            {
                "t": ctx.tenant_id,
                "set": set_id,
                "pos": position,
                "low": None,
                "high": None,
                "pl": low_pct,
                "ph": high_pct,
                "basis": basis.strip(),
                "cites": list(citation_ids),
                "by": ctx.user_id,
            },
        )
        tx.record(
            "analytics.expectation_set",
            target=Target(analytics.TARGET, set_id),
            after=Ref(position=position),
        )
    del row
    found = await analytics.set_view(ctx, set_id, authorised=True)
    return next(x for x in found.lines if x.position == position)
