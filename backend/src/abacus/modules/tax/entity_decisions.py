"""The entity return's decision kinds, notification kinds and topics (T-05-T52; TASK-7903; T-05
F10; SHL-11 g, TXP-00, TXP-10, HOME-02; ADR-050, ADR-005; DEC-4905, DEC-4906). Amber.

- **§754 (`basis_adjustment_election`; registry codes hold no digits).** A decision card reserved
  to the engagement partner (SHL-11 g). Code computes its options and facts (ADR-050), never a
  model: the year's interest transfers from the ownership periods (T-05-T41) and, when a basis
  owner has registered one (`register_section_743b_source`, T-06), the §743(b) difference for the
  transfer; until then the card names the transfer and leaves the figure to basis (DEC-4906). Three
  options, the handoff's: elect now, file without the election (decide in the analysis), recommend
  against. The run raises the card as the agent once per return, after `interim_closing_706d` finds
  a transfer in the year (`ensure_section_754_card`); only the reserved partner decides it (P-04's
  `decision.decide`, fresh MFA).
- **§706(d) convention.** The run question `convention_706d` keeps T-05-T40's options from code
  (`entity_run_plan.convention_question`); no other provider exists.
- **C16 kinds and topics.** `workbook.fix_applied` (an approved fix wrote cells) and
  `tax_memo.went_stale` (T-05-T54) notify the people the owner names and invalidate the
  engagement and work-item topics, so TXP-00's badges and TXP-01's stale banner refetch.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date
from decimal import Decimal
from typing import Annotated, ClassVar, Final
from uuid import UUID

from pydantic import Field

from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext
from abacus.kernel.uow import DomainEvent
from abacus.modules.review.api import (
    CardContext,
    CardOption,
    CardSubject,
    ComputedCard,
    DecisionKind,
)

SECTION_754: Final = "basis_adjustment_election"
QUESTION_754: Final = "basis_adjustment_election"
RESERVED: Final = "engagement_partner"

Section743bSource = Callable[[TenantContext, UUID, date], Awaitable[Decimal | None]]
_STEP_UP: list[Section743bSource] = []


def register_section_743b_source(source: Section743bSource) -> None:
    """T-06's basis owner: the §743(b) difference for a return's transfer on a date, or None."""
    _STEP_UP[:] = [source]


def _money(amount: Decimal) -> str:
    return f"{amount:,.0f}"


def _day(d: date) -> str:
    return f"{d.month}/{d.day}/{d.year}"


def card_for(transfers: list[date], step_up: Decimal | None, year: int) -> ComputedCard:
    """The card's options and context from code's facts."""
    on = _day(transfers[0]) if transfers else None
    figure = {} if step_up is None else {"step_up": format(step_up, "f")}
    adjustment = (
        f"a {_money(step_up)} §743(b) adjustment"
        if step_up is not None
        else "the §743(b) adjustment"
    )
    options = (
        CardOption(
            "elect_now",
            "Recommend electing now",
            figure,
            f"Attach the §754 election statement to the TY{year} Form 1065 filed with the return "
            f"(Reg. §1.754-1(b)); the partnership then records {adjustment} for the transferee, "
            "allocated to partnership property under §755.",
        ),
        CardOption(
            "file_without",
            "File without the election; decide in the cost segregation & §754 analysis",
            {},
            "Basis shows the difference as an explained outside/inside difference, with no "
            "§743(b) adjustment. A late election stays available under Reg. §301.9100-2 within "
            "12 months of the extended due date.",
        ),
        CardOption(
            "against",
            "Recommend against the election",
            {},
            "No §743(b) step-up for the transferee; no ongoing basis-adjustment tracking.",
        ),
    )
    context = [CardContext("due", "Due", "With the return (Reg. §1.754-1(b))")]
    if on is not None:
        context.insert(0, CardContext("transfer", "Transfer", on))
    context.append(
        CardContext(
            "difference",
            "§743(b) difference",
            _money(step_up) if step_up is not None else "Computed with partner basis",
        )
    )
    return ComputedCard(options=options, context=tuple(context))


async def year_transfers(tenant: TenantContext, return_id: UUID) -> tuple[list[date], int]:
    from abacus.modules.tax.allocation_structure import ownership_of
    from abacus.modules.tax.overview import tax_year_of

    year = await tax_year_of(tenant, return_id)
    _, transfers = await ownership_of(tenant, return_id)
    return sorted(t for t in transfers if t.year == year), year


async def section_754_options(tenant: TenantContext, subject: CardSubject) -> ComputedCard:
    """The kind's provider (P-04 calls it when the card is raised or reassessed)."""
    if subject.work_item_id is None:
        return card_for([], None, 0)
    transfers, year = await year_transfers(tenant, subject.work_item_id)
    step_up = (
        await _STEP_UP[0](tenant, subject.work_item_id, transfers[0])
        if _STEP_UP and transfers
        else None
    )
    return card_for(transfers, step_up, year)


async def ensure_section_754_card(
    agent: object, engagement_id: UUID, return_id: UUID
) -> UUID | None:
    """Once per return: raise the §754 card as the run's agent when the year has a transfer and no
    §754 card awaits or was decided (a refused raise leaves the run step's result unchanged)."""
    from abacus.modules.identity.api import AgentContext
    from abacus.modules.review.api import awaiting_cards, decided_cards, raise_decision_card

    if not isinstance(agent, AgentContext):
        return None
    transfers, _ = await year_transfers(agent.tenant, return_id)
    if not transfers:
        return None
    if await awaiting_cards(agent.tenant, return_id, [SECTION_754]):
        return None
    if any(
        c.kind == SECTION_754 for c in await decided_cards(agent.tenant, engagement_id, RESERVED)
    ):
        return None
    try:
        return await raise_decision_card(
            agent,
            engagement_id=engagement_id,
            kind=SECTION_754,
            question_key=QUESTION_754,
            work_item_id=return_id,
        )
    except Exception:
        return None


# --- C16 and topics -----------------------------------------------------------------------------


class WorkbookFixApplied(DomainEvent):
    """An approved fix wrote cells on a return's workbook (T-05-T50)."""

    event_type: ClassVar[str] = "workbook.fix_applied"

    work_item_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    cells: Annotated[int, classified("internal")]
    by_user: Annotated[UUID | None, classified("internal")] = None
    recipient_user_ids: Annotated[list[UUID], classified("internal")] = Field(
        default_factory=list[UUID]
    )


class TaxMemoWentStale(DomainEvent):
    """A figure the memo cites changed after it was adopted or approved (T-05-T54)."""

    event_type: ClassVar[str] = "tax_memo.went_stale"

    work_item_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    memo_id: Annotated[UUID, classified("internal")]
    by_user: Annotated[UUID | None, classified("internal")] = None
    recipient_user_ids: Annotated[list[UUID], classified("internal")] = Field(
        default_factory=list[UUID]
    )


TOPIC_EVENTS: Final = (
    (WorkbookFixApplied.event_type, "work_item_id"),
    (TaxMemoWentStale.event_type, "memo_id"),
)


def register() -> None:
    """At the tax api's import: the §754 kind and the badge and stale-banner topics."""
    from abacus.kernel import realtime
    from abacus.modules.review.api import register_decision_kind

    register_decision_kind(
        DecisionKind(
            code=SECTION_754,
            reserved_role=RESERVED,
            options=section_754_options,
            questions={QUESTION_754: "Recommend a §754 election for the transfer?"},
        )
    )
    for event, ref in TOPIC_EVENTS:
        if realtime.invalidation_of(event) is None:  # never replace another module's entry
            realtime.register_invalidation(
                event,
                realtime.Invalidation(
                    event.split(".")[0],
                    ref,
                    (("engagement", "engagement_id"), ("work_item", "work_item_id")),
                ),
            )


__all__ = [
    "QUESTION_754",
    "SECTION_754",
    "TOPIC_EVENTS",
    "TaxMemoWentStale",
    "WorkbookFixApplied",
    "card_for",
    "ensure_section_754_card",
    "register",
    "register_section_743b_source",
    "section_754_options",
    "year_transfers",
]
