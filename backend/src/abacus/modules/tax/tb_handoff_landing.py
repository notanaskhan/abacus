"""The tax side of a TB hand-off (T-06-T39; TASK-8830; SPEC-702 F6, AC-27 to AC-31; C12; TXP-13 d,
the TXP-02 banner, AUD-38 c; ADR-004, ADR-007; DEC-5832). Amber.

- **Landing** (`on_tb_handoff_created`, the `tb_handoff.created` subscriber): once per hand-off and
  per outbox event (`tax_handoff_landings` is unique on both; a replay finds the row and does
  nothing). One unit of work records the return's TB source as the handed-off Final snapshot, by
  id (never copied, P-40), the draft tax-line mapping seeded from the person's choices (each
  account's code and where it came from: last year, a suggestion, or blank for the tax team), and
  the issues raised from the tax items the person toggled on. Nothing is written to the source
  engagement.
- **Issues** are raised as the person who handed off (`member_context`), on the return, one per
  toggled item, in the landing's unit of work (so a replay cannot raise a second). A person who
  is not on the return's team cannot raise an issue there (`issue.create`, the system may not
  either): the item is counted in `items_not_raised` and TXP-13 d says so, rather than the issue
  appearing under someone else's name.
- **Reads** (`landing`, `handoff_out`, `mappings`): the TXP-13 d and TXP-02 banner model ("From
  FY2026 audit · Final TB · handed off Nov 9"), the source link only when the viewer may open the
  source engagement (absent, never disabled), the superseded warning, and the O4 table.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import OutboxEvent, Scope, Target, uow

if TYPE_CHECKING:
    from abacus.modules.identity.api import AuthContext

TARGET: Final = "tax_return"
LANDING: Final = "tax_handoff_landing"
SOURCE_WORDS: Final = {
    "audit_release": "audit",
    "review_release": "review",
    "close_lock": "December close",
}
ITEM_TITLES: Final = {
    "passed_adjustment": (
        "Passed audit adjustment {ref} ({amount}) handed off: consider it for the M-1"
    ),
    "book_tax_expense": "Book income tax expense ({amount}) handed off: reconcile it on the M-1",
}
Source = Literal["tb_mapper", "firm_mapping", "person", "blank"]
_TRAVEL_SOURCE: Final[dict[str, Source]] = {
    "prior_year": "firm_mapping",
    "suggested": "tb_mapper",
    "blank": "blank",
}

_FOUND: Final = text("SELECT id FROM tax_handoff_landings WHERE handoff_id = :h OR event_id = :e")
_INSERT: Final = text(
    "INSERT INTO tax_handoff_landings (tenant_id, return_id, handoff_id, event_id, version_no, "
    "source_snapshot_id, draft_mapping, issue_ids, items_not_raised) VALUES (:t, :r, :h, :e, :v, "
    ":s, CAST(:m AS jsonb), CAST(:i AS uuid[]), :n) RETURNING id"
)
_LANDED: Final = text(
    "SELECT handoff_id, version_no, source_snapshot_id, draft_mapping, issue_ids, "
    "items_not_raised, landed_at FROM tax_handoff_landings WHERE return_id = :r "
    "ORDER BY version_no DESC LIMIT 1"
)


def _amount(value: Decimal) -> str:
    return f"{value:,.0f}"


def item_title(item_kind: str, source_ref: dict[str, str], amount: Decimal) -> str:
    """A fixed sentence per item kind (code's words, never a model's)."""
    template = ITEM_TITLES.get(item_kind, "Tax item handed off ({amount}): review it")
    return template.format(ref=source_ref.get("ref", ""), amount=_amount(abs(amount)))


def draft_mapping(choices: list[object]) -> list[dict[str, object]]:
    """The draft tax-line mapping seeded from the person's choices: code and source per account.
    A draft: nothing maps until the tax team adopts it on the return."""
    out: list[dict[str, object]] = []
    for choice in choices:
        c = cast(Any, choice)  # Any: ledger's TaxLineChoice, read by attribute
        out.append(
            {
                "account_no": c.account_no,
                "tax_line_code": c.tax_line_code,
                "source": c.travel,
                "suggestion_id": (None if c.suggestion_id is None else str(c.suggestion_id)),
            }
        )
    return out


async def on_tb_handoff_created(event: OutboxEvent) -> None:
    """The landing (module docstring). Idempotent on the hand-off and on `event_id`."""
    from abacus.modules.identity.api import Forbidden, member_context
    from abacus.modules.ledger.api import tb_handoff
    from abacus.modules.review.api import create_issue_in

    raw = event.payload.get("tb_handoff_id")
    if raw is None:
        return
    handoff_id = UUID(str(raw))
    system = TenantContext(event.tenant_id, "system", "tax:tb-handoff")
    async with tenant_session(system) as session:
        if (await session.execute(_FOUND, {"h": handoff_id, "e": event.event_id})).first():
            return  # a replay: the landing is already recorded
    found = await tb_handoff.handoff_of(system, handoff_id)
    if found is None:
        return
    choices = await tb_handoff.choices_of(system, handoff_id)
    items = [i for i in await tb_handoff.tax_items_of(system, handoff_id) if i.create_issue]
    person = await member_context(event.tenant_id, found.handed_off_by)
    from abacus.modules.engagements.api import work_item_engagement

    target_engagement = await work_item_engagement(system, found.target_work_item_id)
    issue_ids: list[UUID] = []
    not_raised = 0
    async with uow(system) as tx:
        for item in items:
            if person is None:
                not_raised += 1
                continue
            try:
                issue_ids.append(
                    await create_issue_in(
                        tx,
                        person,
                        record_type=TARGET,
                        record_id=found.target_work_item_id,
                        kind="action_required",
                        priority="medium",
                        title=item_title(item.item_kind, dict(item.source_ref), item.amount),
                        work_item_id=found.target_work_item_id,
                    )
                )
            except (Forbidden, NotFound):  # not on the return's team: counted, never re-owned
                not_raised += 1
        landing_id = (
            await tx.session.execute(
                _INSERT,
                {
                    "t": event.tenant_id,
                    "r": found.target_work_item_id,
                    "h": handoff_id,
                    "e": event.event_id,
                    "v": found.version_no,
                    "s": found.source_snapshot_id,
                    "m": json.dumps(draft_mapping(list(choices))),
                    "i": [str(i) for i in issue_ids],
                    "n": not_raised,
                },
            )
        ).scalar_one()
        tx.record(
            "tb_handoff.received",
            target=Target(LANDING, UUID(str(landing_id))),
            scope=Scope(engagement_id=target_engagement, work_item_id=found.target_work_item_id),
        )


SUBSCRIPTIONS: Final = {"tb_handoff.created": on_tb_handoff_created}


# --- reads ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Landing:
    handoff_id: UUID
    source_kind: str
    source_work_item_id: UUID
    source_engagement_id: UUID
    source_label: str
    handed_off_at: datetime
    handed_off_by: str | None
    source_link_allowed: bool
    superseded: bool
    book_income: dict[str, str]
    issues_created: int
    items_not_raised: int
    accounts_to_map: int


def source_label(kind: str, period_end_year: int | None) -> str:
    """ "FY2026 audit", "FY2026 review", "FY2026 December close" (TXP-13 d, TXP-02)."""
    words = SOURCE_WORDS.get(kind, "engagement")
    return f"FY{period_end_year} {words}" if period_end_year is not None else words.capitalize()


async def _allowed(ctx: AuthContext, action: str, engagement_id: UUID) -> bool:
    """`action` on the engagement, as a person: False only on Forbidden (a wall or no
    membership); any other error propagates, never read as a denial."""
    from abacus.modules.identity.api import Forbidden, authorise, engagement_resource

    try:
        await authorise(ctx, action, await engagement_resource(ctx.tenant, engagement_id))
    except Forbidden:
        return False
    return True


async def landing(ctx: object, return_id: UUID) -> Landing | None:
    """The return's newest hand-off as the tax side shows it (the route authorised the read)."""
    from abacus.modules.engagements.api import work_item_period
    from abacus.modules.identity.api import AuthContext, display_names
    from abacus.modules.ledger.api import tb_handoff

    if not isinstance(ctx, AuthContext):
        raise NotFound(TARGET)
    found = await tb_handoff.latest_for_target(ctx.tenant, return_id)
    if found is None:
        return None
    async with tenant_session(ctx.tenant) as session:
        landed = (await session.execute(_LANDED, {"r": return_id})).first()
    _start, end = await work_item_period(ctx.tenant, found.source_work_item_id)
    names = await display_names([found.handed_off_by])
    counts = found.counts
    return Landing(
        handoff_id=found.id,
        source_kind=found.source_kind,
        source_work_item_id=found.source_work_item_id,
        source_engagement_id=found.source_engagement_id,
        source_label=source_label(found.source_kind, None if end is None else end.year),
        handed_off_at=found.handed_off_at,
        handed_off_by=names.get(found.handed_off_by),
        source_link_allowed=await _allowed(
            ctx, "engagement.read_metadata", found.source_engagement_id
        ),
        superseded=found.superseded,
        book_income=dict(found.book_income),
        issues_created=0 if landed is None else len(landed.issue_ids or []),
        items_not_raised=0 if landed is None else int(landed.items_not_raised),
        accounts_to_map=int(counts.get("suggested", 0)) + int(counts.get("blank", 0)),
    )


async def authorise_read(ctx: object, handoff_id: UUID) -> object:
    """`tb_handoff.read`: the source engagement's members, or the target return's team."""
    from abacus.modules.engagements.api import work_item_engagement
    from abacus.modules.identity.api import AuthContext
    from abacus.modules.ledger.api import tb_handoff

    if not isinstance(ctx, AuthContext):
        raise NotFound("tb_handoff")
    found = await tb_handoff.handoff_of(ctx.tenant, handoff_id)
    if found is None:
        raise NotFound("tb_handoff")
    target_engagement = await work_item_engagement(ctx.tenant, found.target_work_item_id)
    for engagement_id in (found.source_engagement_id, target_engagement):
        if engagement_id is not None and await _allowed(ctx, "tb_handoff.read", engagement_id):
            return found
    raise NotFound("tb_handoff")  # neither side: the hand-off is absent, never forbidden


async def issue_count(tenant: TenantContext, handoff_id: UUID) -> int:
    async with tenant_session(tenant) as session:
        found = (
            await session.execute(
                text("SELECT issue_ids FROM tax_handoff_landings WHERE handoff_id = :h"),
                {"h": handoff_id},
            )
        ).first()
    return 0 if found is None else len(found.issue_ids or [])


def mapping_source(travel: str) -> Source:
    return _TRAVEL_SOURCE.get(travel, "blank")


__all__ = [
    "ITEM_TITLES",
    "SUBSCRIPTIONS",
    "Landing",
    "authorise_read",
    "draft_mapping",
    "issue_count",
    "item_title",
    "landing",
    "mapping_source",
    "on_tb_handoff_created",
    "source_label",
]
