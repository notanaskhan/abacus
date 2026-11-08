"""EBP-07's Schedule H line 4i as a C11 document (A-05-T58 remainder; A-05-T54; DEC-2828).

The `ebp_supplemental_schedule` kind is composed by code, never from a firm template: its rows are
`compute.ebp.form5500.schedule_4i`'s (the trust report's current holdings, the participant loans
and the plan's parties in interest), in the code-only `financial_statements` layout. So the body
holds the plan, the schedule's title and date, one table and the two footnotes, and never a
citation, a source or agent text.

- **Owner.** The current Form 5500 draft: the schedule is reported with the draft it ties to, and
  a new draft starts its own document. A re-render of the same draft is a new version.
- **Draft mark.** Every render here is a draft (C11 draws the DRAFT watermark); a final render
  needs an approval, and this kind answers none (the schedule goes out with the statements).
- **Deterministic.** The same facts compose the same blocks, so the snapshot, content hash and
  bytes repeat (DEC-44, ADR-152).
- **People only.** `ebp_schedule.render` is an engagement partner's, manager's or senior's; the
  agent and the system are denied by the matrix, and the request is a person's.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainInvalid, NotFound
from abacus.kernel.uow import uow
from abacus.modules.assurance import ebp_form5500
from abacus.modules.assurance.compute.ebp import form5500 as engine
from abacus.modules.engagements.api import (
    engagement_hold_facts,
    engagement_label,
    work_item_engagement,
)
from abacus.modules.identity.api import AuthContext

KIND: Final = "ebp_supplemental_schedule"
OWNER: Final = "ebp_form5500_draft"
ACTION: Final = "ebp_schedule.render"
RECORD_TYPE: Final = "derived_rendering"
TITLE_4I: Final = "Schedule H, line 4i — Schedule of Assets (Held at End of Year)"
COLUMNS_4I: Final = (
    "(a)",
    "(b) Identity of issue",
    "(c) Description",
    "(d) Cost",
    "(e) Current value",
)
FOOTNOTES_4I: Final = (
    "* Party in interest",
    "** Cost omitted for participant-directed investments",
)
TOTAL: Final = "Total"
OMITTED: Final = "**"

_DRAFT_OF = text(
    "SELECT work_item_id FROM ebp_form5500_drafts WHERE id = :d AND status <> 'superseded'"
)
_CURRENT = text(
    "SELECT id FROM ebp_form5500_drafts "
    "WHERE work_item_id = :w AND status <> 'superseded' ORDER BY created_at DESC LIMIT 1"
)


class NoScheduleTitle(DomainInvalid):
    """A plan with no period end: the schedule's date is never guessed."""

    code = "schedule_period_unknown"


def amount(value: Decimal) -> str:
    """Thousands separated, no cents when whole (the handoff's 6,120,450), a negative in
    parentheses."""
    text_ = f"{abs(value):,.0f}" if value == value.to_integral_value() else f"{abs(value):,.2f}"
    return f"({text_})" if value < 0 else text_


def _long(day: date) -> str:
    return f"{day:%B} {day.day}, {day.year}"


def _paragraph(words: str) -> dict[str, object]:
    return {"type": "paragraph", "runs": [{"type": "text", "text": words}]}


def compose_4i(plan_name: str, period_end: date, schedule: engine.Schedule4i) -> list[object]:
    """The document's DocBlocks from the schedule (pure)."""
    rows: list[list[str]] = [
        [
            r.mark,
            r.identity,
            r.description,
            OMITTED if r.cost_omitted else ("" if r.cost is None else amount(r.cost)),
            amount(r.current_value),
        ]
        for r in schedule.rows
    ]
    rows.append(["", TOTAL, "", "", amount(schedule.total)])
    return [
        {"type": "heading", "level": 1, "text": plan_name},
        {"type": "heading", "level": 2, "text": TITLE_4I},
        _paragraph(_long(period_end)),
        {"type": "table", "columns": list(COLUMNS_4I), "rows": rows},
        *(_paragraph(f) for f in FOOTNOTES_4I),
    ]


async def _heading(tenant: TenantContext, work_item_id: UUID) -> tuple[str, date]:
    engagement_id = await work_item_engagement(tenant, work_item_id)
    label = None if engagement_id is None else await engagement_label(tenant, engagement_id)
    if label is None or label.fiscal_period_end is None:
        raise NoScheduleTitle(facts={"work_item_id": str(work_item_id)})
    return label.client_entity_name or label.client_name, label.fiscal_period_end


async def _body(tenant: TenantContext, owner: object, _scope: object) -> Sequence[object]:
    from abacus.modules.reporting.api import OwnerRef

    if not isinstance(owner, OwnerRef) or owner.type != OWNER:
        return []
    async with tenant_session(tenant) as session:
        work_item_id = await session.scalar(_DRAFT_OF, {"d": owner.id})
    if work_item_id is None:
        raise NotFound("form5500_draft")
    plan_name, period_end = await _heading(tenant, work_item_id)
    schedule = await ebp_form5500.schedule_4i_facts(tenant, work_item_id)
    return compose_4i(plan_name, period_end, schedule)


async def _no_values(_owner: object, _scope: object) -> Mapping[str, str]:
    return {}


async def _no_approval(_ref: object) -> tuple[UUID, str] | None:
    return None  # the schedule is reported with the statements; it has no approval of its own


def ensure_kind() -> None:
    """Register the kind with C11 once per process (and again after a test resets)."""
    from abacus.modules.reporting import api as c11

    try:
        c11.document_kind(KIND)
    except c11.UnknownDocumentKind:
        c11.register_document_kind(
            c11.DocumentKind(
                kind=KIND,
                layout="financial_statements",
                variables_provider=_no_values,
                approval_provider=_no_approval,
                retention_record_type=RECORD_TYPE,
                formats=("pdf",),
                body_provider=_body,
            )
        )


async def render_4i(ctx: AuthContext, work_item_id: UUID) -> UUID:
    """A person's DRAFT render of the current draft's 4i schedule; answers the generated
    document's id. 404 when no Form 5500 draft has arrived."""
    from abacus.modules.reporting import api as c11

    engagement_id = await ebp_form5500.authorise_on(ctx, work_item_id, ACTION)
    if ctx.tenant.actor_kind != "human":
        raise DomainInvalid  # the matrix denies the agent and the system; never a run's request
    async with tenant_session(ctx.tenant) as session:
        draft_id = await session.scalar(_CURRENT, {"w": work_item_id})
    if draft_id is None:
        raise NotFound("form5500_draft")
    facts = await engagement_hold_facts(ctx.tenant, engagement_id)
    if facts is None:
        raise NotFound("engagement")
    await _heading(ctx.tenant, work_item_id)  # refuse before queueing when the date is unknown
    ensure_kind()
    async with uow(ctx.tenant) as tx:
        ticket = await c11.render(
            tx,
            c11.RenderRequest(
                kind=KIND,
                owner_ref=c11.OwnerRef(OWNER, draft_id),
                scope=c11.RenderScope(
                    client_id=facts.client_id,
                    engagement_id=engagement_id,
                    work_item_id=work_item_id,
                ),
                template_version_id=None,
                requested_by=c11.Requester("human", user_id=ctx.user_id),
                formats=("pdf",),
            ),
        )
    return ticket.generated_document_id
