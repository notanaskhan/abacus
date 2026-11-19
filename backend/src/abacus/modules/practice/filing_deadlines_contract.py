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
from typing import Annotated, Literal
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
    raise NotImplementedYet


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
    raise NotImplementedYet


@filing_deadlines_router.get(
    "/filing-deadlines/{filing_deadline_id}",
    action="filing_deadline.read",
    response_model=FilingDeadlineDetailOut,
    errors=(501,),
)
async def filing_deadline_route(filing_deadline_id: UUID, ctx: Ctx) -> FilingDeadlineDetailOut:
    await _on(ctx)
    raise NotImplementedYet


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
