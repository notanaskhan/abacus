"""Filing deadlines v1 stub (FD-1; T-08-T04; SPEC-710 AC-9 to AC-20;
`docs/contracts/filing-deadlines.md`). Screen HOME-03, the HOME-01 pane source, I-02 Today, I-04
HOME-04 and R-03. Answers F-07-T21's deadlines request.

Every route answers, in order: a client principal 403 (AC-18: portal principals never read a
deadline); the `practice.filing_deadlines` flag off 404; a human-only route refuses an agent, the
platform or a support session 403 (INV-1); then 501 until its build task (T-08-T10, T21, T44).

Classification (ADR-031): rows carry metadata only, never TRI or amounts (AC-2.6): client names
and owners are `confidential`; dates, rule text, ids, codes and counts are `internal`. Risk tiers
and days left are computed on read in the firm's zone and never stored (AC-9).

The provider protocol (`platform.register_filing_deadline_source`, T-08-T07) is documented in
`docs/contracts/filing-deadlines.md`; sources answer `(ctx, window) -> [FilingDeadlineFact]`.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import PRACTICE_FILING_DEADLINES
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.modules.identity.api import AbacusRouter, AuthContext, Forbidden, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)]
Internal = classified("internal")
Confidential = classified("confidential")
Count = Annotated[int, Field(ge=0), Internal]

View = Literal["month", "week", "list"]
Risk = Literal["overdue", "due_7", "due_30", "later", "done"]
SourceKind = Literal[
    "tax_return",
    "extension",
    "estimate_batch",
    "fiduciary_statement",
    "election_window",
    "notice_response",
    "envelope",
    "close",
    "assurance_report",
    "form_5500",
    "consent",
]
ServiceLine = Literal["audit", "tax", "cas", "advisory"]
ExportFormat = Literal["xlsx", "ics"]


def _cfg() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


class FilingDeadlineOwnerOut(BaseModel):
    model_config = _cfg()

    user_id: Annotated[UUID, Internal]
    initials: Annotated[str, Field(max_length=4), Confidential]


class FilingDeadlineItemOut(BaseModel):
    """One chip or list row (HOME-03 a, b, c, f)."""

    model_config = _cfg()

    filing_deadline_id: Annotated[UUID, Internal]
    source_kind: Annotated[SourceKind, Internal]
    client_id: Annotated[UUID | None, Internal] = None
    client_name: Annotated[str, Field(max_length=200), Confidential]
    filing_label: Annotated[str, Field(max_length=80), Internal]
    due_on: Annotated[date, Internal]
    original_due_on: Annotated[date, Internal]
    postponed_from: Annotated[date | None, Internal] = None
    extension_form: Annotated[str | None, Field(max_length=20), Internal] = None
    rule_text: Annotated[str | None, Field(max_length=200), Internal] = None
    stage_code: Annotated[str, Field(max_length=40), Internal]
    stage_label: Annotated[str, Field(max_length=80), Internal]
    risk: Annotated[Risk, Internal]
    days_left: Annotated[int, Internal]
    risk_label: Annotated[str, Field(max_length=60), Internal]
    owners: Annotated[list[FilingDeadlineOwnerOut], Internal]
    signer: Annotated[FilingDeadlineOwnerOut | None, Confidential] = None
    work_item_id: Annotated[UUID | None, Internal] = None
    href: Annotated[str | None, Field(max_length=200), Internal] = None


class FilingDeadlineDayOut(BaseModel):
    """A grid cell: three chips and "+n more" (AC-10: Sep 15 holds 12)."""

    model_config = _cfg()

    on: Annotated[date, Internal]
    total: Count
    shown: Annotated[list[UUID], Internal]
    holiday: Annotated[str | None, Field(max_length=80), Internal] = None


class FilingDeadlineCalendarOut(BaseModel):
    model_config = _cfg()

    view: Annotated[View, Internal]
    window_from: Annotated[date, Internal]
    window_to: Annotated[date, Internal]
    today: Annotated[date, Internal]
    firm_zone: Annotated[str, Field(max_length=40), Internal]
    items: Annotated[list[FilingDeadlineItemOut], Internal]
    days: Annotated[list[FilingDeadlineDayOut], Internal] = []
    remaining: Count
    next_cursor: Annotated[str | None, Internal] = None


class FilingDeadlineDetailOut(BaseModel):
    """The rule popover (AC-11): the rule text and the reference-set versions come from the row."""

    model_config = _cfg()

    item: Annotated[FilingDeadlineItemOut, Internal]
    original_due_on: Annotated[date, Internal]
    extended_due_on: Annotated[date | None, Internal] = None
    extension_filed_on: Annotated[date | None, Internal] = None
    postponement_notice_id: Annotated[UUID | None, Internal] = None
    internal_target_on: Annotated[date | None, Internal] = None
    reference_set_version_ids: Annotated[list[UUID], Internal]
    computed_at: Annotated[datetime, Internal]


class FilingDeadlinePostponementIn(BaseModel):
    """DF-10 client relief (T-08-T44): a person applies a published notice to one client."""

    model_config = _cfg()

    client_id: Annotated[UUID, Internal]
    notice_id: Annotated[UUID, Internal]
    reference_set_version_id: Annotated[UUID, Internal]


class FilingDeadlinePostponementOut(BaseModel):
    model_config = _cfg()

    application_id: Annotated[UUID, Internal]
    client_id: Annotated[UUID, Internal]
    moved: Count
    applied_at: Annotated[datetime, Internal]


# --- routes (each 501, one action) -------------------------------------------------------------

filing_deadlines_router = AbacusRouter(prefix="/v1", tags=["practice"])


async def _on(ctx: AuthContext, action: str = "filing_deadline.read") -> None:
    if ctx.client:
        raise Forbidden(action, "role")
    if not await flag_enabled(ctx.tenant, PRACTICE_FILING_DEADLINES):
        raise NotFound(PRACTICE_FILING_DEADLINES.name)


async def _human(ctx: AuthContext, action: str) -> None:
    await _on(ctx, action)
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(action, "role")


_RISK_LABEL: dict[str, str] = {
    "overdue": "Overdue", "due_7": "Due within 7 days", "due_30": "Due within 30 days",
    "later": "Later", "done": "Done",
}  # fmt: skip


async def _items(ctx: AuthContext, found: list[object]) -> list[FilingDeadlineItemOut]:
    from abacus.modules.identity.api import names_of
    from abacus.modules.organisations.api import firm_names
    from abacus.modules.practice.compute import deadlines as calc
    from abacus.modules.practice.deadlines_service import Row, firm_today

    rows = [cast(Row, r) for r in found]
    today = await firm_today(ctx)
    clients = {n.client_id: n.name for n in await firm_names(ctx.tenant) if n.id == n.client_id}
    people = {u for r in rows for u in (*r.owner_user_ids, r.signer_user_id) if u is not None}
    names = await names_of(sorted(people, key=str)) if people else {}

    def who(u: UUID) -> FilingDeadlineOwnerOut:
        name = names.get(u, "")
        return FilingDeadlineOwnerOut(
            user_id=u, initials=("".join(p[0] for p in name.split()[:2]).upper() or "?")[:4]
        )

    out: list[FilingDeadlineItemOut] = []
    for r in rows:
        tier = calc.risk(r.deadline(), today)
        out.append(
            FilingDeadlineItemOut(
                filing_deadline_id=r.deadline_id,
                source_kind=cast(SourceKind, r.source_kind),
                client_id=r.client_id,
                client_name=(clients.get(r.client_id, "") if r.client_id else "")[:200],
                filing_label=r.filing_label,
                due_on=r.due_on,
                original_due_on=r.original_due_on,
                postponed_from=r.postponed_from,
                extension_form=r.extension_form,
                stage_code=r.stage_code,
                stage_label=r.stage_code.replace("_", " ").capitalize()[:80],
                risk=tier,
                days_left=calc.days_left(r.deadline(), today),
                risk_label=_RISK_LABEL[tier],
                owners=[who(u) for u in r.owner_user_ids],
                signer=None if r.signer_user_id is None else who(r.signer_user_id),
                work_item_id=r.work_item_id,
            )
        )
    return out


@filing_deadlines_router.get(
    "/filing-deadlines",
    action="filing_deadline.read",
    response_model=FilingDeadlineCalendarOut,
    errors=(501,),
)
async def filing_deadlines_route(
    ctx: Ctx,
    window_from: Annotated[date, Query(alias="from")],
    window_to: Annotated[date, Query(alias="to")],
    view: View = "month",
    office_id: UUID | None = None,
    service: ServiceLine | None = None,
    person_id: UUID | None = None,
    risk: Risk | None = None,
    cursor: str | None = None,
) -> FilingDeadlineCalendarOut:
    """Walled clients contribute no row, day count or "+n more" (AC-14)."""
    await _on(ctx)
    from abacus.modules.practice.deadlines_service import firm_today, rows

    found = await rows(
        ctx, window_from, window_to, office=office_id, service=service, person=person_id
    )
    items = [i for i in await _items(ctx, list(found)) if risk is None or i.risk == risk]
    days: list[FilingDeadlineDayOut] = []
    if view == "month":
        by_day: dict[date, list[FilingDeadlineItemOut]] = {}
        for i in items:
            by_day.setdefault(i.due_on, []).append(i)
        days = [
            FilingDeadlineDayOut(on=d, total=len(v), shown=[i.filing_deadline_id for i in v[:3]])
            for d, v in sorted(by_day.items())
        ]
    return FilingDeadlineCalendarOut(
        view=view,
        window_from=window_from,
        window_to=window_to,
        today=await firm_today(ctx),
        firm_zone="America/Chicago",
        items=items,
        days=days,
        remaining=sum(max(d.total - len(d.shown), 0) for d in days),
    )


@filing_deadlines_router.get(
    "/filing-deadlines/export",
    action="export.create",
    response_model=bytes,
    errors=(501,),
)
async def filing_deadlines_export_route(
    ctx: Ctx,
    fmt: Annotated[ExportFormat, Query(alias="format")],
    window_from: Annotated[date, Query(alias="from")],
    window_to: Annotated[date, Query(alias="to")],
) -> bytes:
    """A one-off xlsx or RFC 5545 ics with fresh MFA; no TIN, no amount, no feed (AC-16)."""
    await _human(ctx, "export.create")
    from abacus.modules.practice.deadlines_service import export_deadlines

    return await export_deadlines(ctx, fmt, window_from, window_to)


@filing_deadlines_router.get(
    "/filing-deadlines/{filing_deadline_id}",
    action="filing_deadline.read",
    response_model=FilingDeadlineDetailOut,
    errors=(501,),
)
async def filing_deadline_route(filing_deadline_id: UUID, ctx: Ctx) -> FilingDeadlineDetailOut:
    await _on(ctx)
    from abacus.modules.practice.deadlines_service import detail

    r = await detail(ctx, filing_deadline_id)
    item = (await _items(ctx, [r]))[0]
    return FilingDeadlineDetailOut(
        item=item,
        original_due_on=r.original_due_on,
        extended_due_on=r.extended_due_on,
        internal_target_on=None,
        reference_set_version_ids=list(r.reference_set_version_ids),
        computed_at=r.computed_at,
    )


@filing_deadlines_router.post(
    "/postponement-applications",
    action="filing_deadline.apply_postponement",
    response_model=FilingDeadlinePostponementOut,
    status_code=201,
    errors=(409, 501),
)
async def postponement_application_route(
    body: FilingDeadlinePostponementIn, ctx: Ctx, key: IdempotencyKey
) -> FilingDeadlinePostponementOut:
    """Human-only with fresh MFA (OQ-17); only that client's dates move."""
    await _human(ctx, "filing_deadline.apply_postponement")
    raise NotImplementedYet
