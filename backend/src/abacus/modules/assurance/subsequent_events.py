"""AUD-19 b to e: subsequent events, legal letters and going concern (A-07-T23; TASK-6207;
DEC-2807; A-07 F2; AU-C 560, 501.A86, 570).

- **Procedures** (`subsequent_event_procedures`): a manager or senior adds the firm's procedures
  and marks each performed through a date, as themself; the bring-down run (`bring_down.py`)
  records that it re-checked them through the report date, never performs one.
- **Events** (`subsequent_events`, insert-only, human-only by CHECK): a manager or senior records
  the description, Recognized or Nonrecognized, the FS effect (both sealed), the note reference and
  citations. The agent records none in A-07.
- **Legal letter** (`legal_letters`, one per work item): Not applicable with a sealed basis, or a
  request to counsel recorded against a P-06 third-party request item (SHL-14).
- **Going concern**: code computes the inputs (Granite Peak's DSCR 1.32x against the 1.25x
  covenant, the revolver's maturity) and stores them with an engine version and an inputs hash;
  the decision is the EP's `going_concern` card (C3). Nothing here records a conclusion.

The routes stay 501 until A-07-T33 turns on `audits.completion`; this is the service they call.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.crypto import seal
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.engagements.api import assurance_item, get_ref
from abacus.modules.identity.api import AuthContext, Forbidden, authorise
from abacus.modules.review.api import raise_decision_card

ENGINE_VERSION: Final = "going_concern@1"
GOING_CONCERN: Final = "going_concern"


class StaleVersion(DomainConflict):
    code = "stale_version"


class BasisRequired(DomainInvalid):
    code = "basis_required"


class EventInvalid(DomainInvalid):
    code = "subsequent_event_invalid"


def _person(ctx: AuthContext, action: str) -> None:
    """Every act here is a named person's (ADR-005); a client never reaches it."""
    if ctx.client:
        raise NotFound("subsequent_event")
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(action, "role")


async def _authorised(ctx: AuthContext, work_item_id: UUID, action: str) -> UUID:
    _person(ctx, action)
    item = await assurance_item(ctx.tenant, work_item_id)
    await authorise(ctx, action, (await get_ref(ctx, item.engagement_id)).resource())
    return item.engagement_id


# --- procedures ----------------------------------------------------------------------------------


async def add_procedure(ctx: AuthContext, work_item_id: UUID, procedure_key: str) -> UUID:
    engagement_id = await _authorised(ctx, work_item_id, "subsequent_event.update")
    async with uow(ctx.tenant) as tx:
        found = await tx.session.scalar(
            text(
                "INSERT INTO subsequent_event_procedures (tenant_id, engagement_id, work_item_id, "
                "procedure_key) VALUES (:t, :e, :wi, :k) "
                "ON CONFLICT (tenant_id, work_item_id, procedure_key) DO NOTHING RETURNING id"
            ),
            {"t": ctx.tenant_id, "e": engagement_id, "wi": work_item_id, "k": procedure_key},
        )
        if found is None:
            raise DomainConflict(facts={"procedure_key": procedure_key})
        tx.record(
            "subsequent_event.procedure_added",
            target=Target("subsequent_event_procedure", found),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )
    return found


async def perform_procedure(
    ctx: AuthContext,
    work_item_id: UUID,
    procedure_id: UUID,
    *,
    performed_through: date,
    status: Literal["open", "performed"],
    seen_version: int,
) -> int:
    engagement_id = await _authorised(ctx, work_item_id, "subsequent_event.update")
    async with uow(ctx.tenant) as tx:
        version = await tx.session.scalar(
            text(
                "UPDATE subsequent_event_procedures SET performed_through = :through, "
                "performed_by = :by, status = :status, version = version + 1, "
                "updated_at = clock_timestamp() WHERE id = :id AND work_item_id = :wi "
                "AND version = :seen RETURNING version"
            ),
            {
                "through": performed_through,
                "by": ctx.user_id if status == "performed" else None,
                "status": status,
                "id": procedure_id,
                "wi": work_item_id,
                "seen": seen_version,
            },
        )
        if version is None:
            raise StaleVersion(facts={"seen_version": seen_version})
        tx.record(
            "subsequent_event.procedure_performed",
            target=Target("subsequent_event_procedure", procedure_id),
            after=Ref(status=status, through=performed_through.isoformat()),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )
    return int(version)


# --- events --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class NewSubsequentEvent:
    description: str
    recognition: Literal["recognized", "nonrecognized"]
    fs_effect: str | None = None
    note_ref: str | None = None
    citation_ids: tuple[UUID, ...] = ()


async def record_subsequent_event(
    ctx: AuthContext, work_item_id: UUID, new: NewSubsequentEvent
) -> UUID:
    """A manager or senior records it (the matrix); the row is human-only by CHECK."""
    if not new.description.strip():
        raise EventInvalid(facts={"field": "description"})
    if len(new.citation_ids) > 20:
        raise EventInvalid(facts={"field": "citation_ids"})
    engagement_id = await _authorised(ctx, work_item_id, "subsequent_event.create")
    async with uow(ctx.tenant) as tx:
        event_id = await tx.session.scalar(text("SELECT gen_random_uuid()"))
        description = await seal(
            ctx.tenant_id, new.description.strip().encode(), f"subsequent_event:{event_id}"
        )
        effect = (
            None
            if not new.fs_effect
            else await seal(
                ctx.tenant_id, new.fs_effect.encode(), f"subsequent_event:{event_id}:fx"
            )
        )
        await tx.session.execute(
            text(
                "INSERT INTO subsequent_events (id, tenant_id, engagement_id, work_item_id, "
                "description_sealed, recognition, fs_effect_sealed, note_ref, citation_ids, "
                "recorded_by, actor_kind, actor_id) VALUES (:id, :t, :e, :wi, :d, :r, :fx, :n, "
                ":c, :by, current_setting('app.actor_kind', true), "
                "current_setting('app.actor_id', true))"
            ),
            {
                "id": event_id,
                "t": ctx.tenant_id,
                "e": engagement_id,
                "wi": work_item_id,
                "d": description,
                "r": new.recognition,
                "fx": effect,
                "n": new.note_ref,
                "c": list(new.citation_ids),
                "by": ctx.user_id,
            },
        )
        tx.record(
            "subsequent_event.recorded",
            target=Target("subsequent_event", event_id),
            after=Ref(recognition=new.recognition),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )
    return event_id


# --- legal letter --------------------------------------------------------------------------------


async def legal_letter_not_applicable(
    ctx: AuthContext, work_item_id: UUID, *, basis: str, seen_version: int | None
) -> None:
    """AUD-19 c: Not applicable with a basis (sealed; CHECK `not_applicable = basis IS NOT
    NULL`)."""
    if not basis.strip():
        raise BasisRequired(facts={"field": "basis"})
    engagement_id = await _authorised(ctx, work_item_id, "legal_letter.update")
    async with uow(ctx.tenant) as tx:
        sealed = await seal(ctx.tenant_id, basis.strip().encode(), f"legal_letter:{work_item_id}")
        if seen_version is None:
            done = await tx.session.scalar(
                text(
                    "INSERT INTO legal_letters (tenant_id, engagement_id, work_item_id, "
                    "not_applicable, basis_sealed, status) VALUES (:t, :e, :wi, true, :b, "
                    "'not_applicable') ON CONFLICT (tenant_id, work_item_id) DO NOTHING "
                    "RETURNING id"
                ),
                {"t": ctx.tenant_id, "e": engagement_id, "wi": work_item_id, "b": sealed},
            )
        else:
            done = await tx.session.scalar(
                text(
                    "UPDATE legal_letters SET not_applicable = true, basis_sealed = :b, "
                    "status = 'not_applicable', request_item_id = NULL, "
                    "version = version + 1, updated_at = clock_timestamp() "
                    "WHERE work_item_id = :wi AND version = :seen RETURNING id"
                ),
                {"b": sealed, "wi": work_item_id, "seen": seen_version},
            )
        if done is None:
            raise StaleVersion(facts={"seen_version": seen_version})
        tx.record(
            "legal_letter.recorded",
            target=Target("legal_letter", done),
            after=Ref(status="not_applicable"),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )


async def legal_letter_requested(
    ctx: AuthContext, work_item_id: UUID, request_item_id: UUID
) -> None:
    """The legal letter is requested through a P-06 third-party request item (SHL-14), which
    the request carries; no internal terms travel with it (the request module's own rule)."""
    engagement_id = await _authorised(ctx, work_item_id, "legal_letter.request")
    async with uow(ctx.tenant) as tx:
        done = await tx.session.scalar(
            text(
                "INSERT INTO legal_letters (tenant_id, engagement_id, work_item_id, "
                "request_item_id, status) VALUES (:t, :e, :wi, :r, 'requested') "
                "ON CONFLICT (tenant_id, work_item_id) DO UPDATE SET request_item_id = :r, "
                "status = 'requested', not_applicable = false, basis_sealed = NULL, "
                "version = legal_letters.version + 1, updated_at = clock_timestamp() "
                "RETURNING id"
            ),
            {"t": ctx.tenant_id, "e": engagement_id, "wi": work_item_id, "r": request_item_id},
        )
        tx.record(
            "legal_letter.recorded",
            target=Target("legal_letter", done),
            after=Ref(status="requested", request_item=request_item_id),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )


# --- going concern -------------------------------------------------------------------------------

_TWO: Final = Decimal("0.01")


@dataclass(frozen=True)
class GoingConcernInputs:
    """A person enters the figures from the trial balance and the loan agreement; code computes
    the ratio and the headroom (ADR-050)."""

    cash_available_for_debt_service: Decimal
    debt_service: Decimal
    covenant_dscr: Decimal
    facility_matures_on: date | None = None


@dataclass(frozen=True)
class GoingConcernFacts:
    dscr: Decimal
    covenant_dscr: Decimal
    meets_covenant: bool
    headroom: Decimal
    facility_matures_on: date | None


def going_concern_facts(inputs: GoingConcernInputs) -> GoingConcernFacts:
    """Granite Peak: 1.32x against 1.25x, met, with 0.07x headroom."""
    if inputs.debt_service <= 0:
        raise DomainInvalid(facts={"field": "debt_service"})
    dscr = (inputs.cash_available_for_debt_service / inputs.debt_service).quantize(
        _TWO, ROUND_HALF_UP
    )
    covenant = inputs.covenant_dscr.quantize(_TWO, ROUND_HALF_UP)
    return GoingConcernFacts(
        dscr,
        covenant,
        dscr >= covenant,
        (dscr - covenant).quantize(_TWO),
        inputs.facility_matures_on,
    )


def _inputs_json(inputs: GoingConcernInputs, facts: GoingConcernFacts) -> str:
    return json.dumps(
        {
            "cash_available_for_debt_service": str(inputs.cash_available_for_debt_service),
            "debt_service": str(inputs.debt_service),
            "covenant_dscr": str(facts.covenant_dscr),
            "dscr": str(facts.dscr),
            "meets_covenant": facts.meets_covenant,
            "headroom": str(facts.headroom),
            "facility_matures_on": None
            if facts.facility_matures_on is None
            else facts.facility_matures_on.isoformat(),
        },
        sort_keys=True,
    )


async def request_going_concern_decision(
    ctx: AuthContext, work_item_id: UUID, inputs: GoingConcernInputs
) -> UUID:
    """Store code's inputs, then raise the EP's `going_concern` card (the options are AU-C 570's
    fixed copy; the agent may only recommend). Returns the card's id."""
    engagement_id = await _authorised(ctx, work_item_id, "going_concern.request_decision")
    facts = going_concern_facts(inputs)
    body = _inputs_json(inputs, facts)
    digest = hashlib.sha256(f"{ENGINE_VERSION}\n{body}".encode()).hexdigest()
    card_id = await raise_decision_card(
        ctx,
        engagement_id=engagement_id,
        kind=GOING_CONCERN,
        question_key=GOING_CONCERN,
        work_item_id=work_item_id,
        raised_under="going_concern.request_decision",
    )
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "INSERT INTO going_concern_evaluations (tenant_id, engagement_id, work_item_id, "
                "decision_card_id, inputs, engine_version, inputs_hash) VALUES (:t, :e, :wi, "
                ":card, CAST(:inputs AS jsonb), :engine, :hash) "
                "ON CONFLICT (tenant_id, work_item_id) DO UPDATE SET decision_card_id = :card, "
                "inputs = CAST(:inputs AS jsonb), engine_version = :engine, inputs_hash = :hash, "
                "version = going_concern_evaluations.version + 1, updated_at = clock_timestamp()"
            ),
            {
                "t": ctx.tenant_id,
                "e": engagement_id,
                "wi": work_item_id,
                "card": card_id,
                "inputs": body,
                "engine": ENGINE_VERSION,
                "hash": digest,
            },
        )
        tx.record(
            "going_concern.decision_requested",
            target=Target("work_item", work_item_id),
            after=Ref(card=card_id, inputs_hash=digest),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )
    return card_id


__all__ = [
    "ENGINE_VERSION",
    "BasisRequired",
    "EventInvalid",
    "GoingConcernFacts",
    "GoingConcernInputs",
    "NewSubsequentEvent",
    "StaleVersion",
    "add_procedure",
    "going_concern_facts",
    "legal_letter_not_applicable",
    "legal_letter_requested",
    "perform_procedure",
    "record_subsequent_event",
    "request_going_concern_decision",
]
