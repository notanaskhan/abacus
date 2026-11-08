"""AUD-27: estimates, related parties and parties in interest (A-05-T53; A-05 F11; AU-C 540, 550;
ERISA §3(14)).

- **Estimates.** Each estimate's components foot to its balance (the TB line it names, 1450 for
  Granite Peak's inventory reserve), its rollforward rolls, its retrospective differences and their
  percentages, the auditor's range and the bias indicator are all code's (`compute/ebp/estimates`,
  ADR-050). Recording the method evaluates it; **Request partner conclusion…** raises a C3 decision
  card of kind `estimate_conclusion` reserved to the engagement partner, and the row reads
  "Evaluated · pending EP" until it is decided. No one but the EP decides it (P-04's `decide`).
- **Related parties.** From the client's list, the uploaded masters and the minutes; a person may
  screen one out only with a reason (the row records who and when); an agent's search proposes
  candidates and concludes nothing (A-05-T56).
- **Parties in interest.** ERISA §3(14) relationships, exemptions and reporting; the prohibited-
  transaction card reads `v_prohibited_transactions`, a view over the late remittance, so a
  corrected figure there is the figure here (no copy).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated, ClassVar, Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import DomainEvent, Ref, Scope, Target, uow
from abacus.modules.assurance.compute.ebp import estimates as engine
from abacus.modules.engagements.api import get_ref, work_item_engagement
from abacus.modules.identity.api import AuthContext, authorise
from abacus.modules.review.api import (
    CardContext,
    CardOption,
    CardSubject,
    ComputedCard,
    DecisionKind,
    raise_decision_card,
    register_decision_kind,
)

CONCLUSION_KIND: Final = "estimate_conclusion"
_CONCLUSION_OPTIONS: Final = (
    ("reasonable", "Reasonable in the context of the financial statements"),
    ("misstatement", "Not reasonable: the difference is a misstatement"),
)


class EstimateNotEvaluated(DomainConflict):
    code = "estimate_not_evaluated"


class ConclusionAlreadyRequested(DomainConflict):
    code = "conclusion_already_requested"


class StaleEstimate(DomainConflict):
    code = "stale_version"


class ScreenOutReasonRequired(DomainInvalid):
    code = "screen_out_reason_required"


class EstimateConclusionRequested(DomainEvent):
    event_type: ClassVar[str] = "estimate.conclusion_requested"

    engagement_id: Annotated[UUID, classified("internal")]
    work_item_id: Annotated[UUID, classified("internal")]
    estimate_id: Annotated[UUID, classified("internal")]
    decision_card_id: Annotated[UUID, classified("internal")]


@dataclass(frozen=True)
class EstimateView:
    id: UUID
    name: str
    account_ref: str | None
    balance: Decimal | None
    status: str
    pending_ep: bool
    footing: engine.Footing | None
    rollforward: engine.Rollforward | None
    retrospectives: tuple[engine.Retrospective, ...]
    range: engine.RangeCheck | None
    bias: engine.BiasIndicator
    version: int


async def _engagement(ctx: AuthContext, work_item_id: UUID, action: str) -> UUID:
    engagement_id = await work_item_engagement(ctx.tenant, work_item_id)
    if engagement_id is None:
        raise NotFound("work_item")
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, action, ref.resource())
    return engagement_id


def _d(value: object) -> Decimal:
    return Decimal(str(value))


def compute(
    balance: Decimal | None,
    components: Sequence[Decimal],
    rollforward: dict[str, object] | None,
    retrospective: Sequence[dict[str, object]] | None,
    range_low: Decimal | None,
    range_high: Decimal | None,
) -> tuple[
    engine.Footing | None,
    engine.Rollforward | None,
    tuple[engine.Retrospective, ...],
    engine.RangeCheck | None,
    engine.BiasIndicator,
]:
    """Every figure AUD-27a shows for one estimate, from its stored inputs."""
    footing = engine.foot(components, balance) if balance is not None and components else None
    rolled = (
        engine.rollforward(
            _d(rollforward["opening"]), _d(rollforward["usage"]), _d(rollforward["additions"]),
            balance,
        )
        if rollforward and balance is not None
        else None
    )  # fmt: skip
    retros = tuple(
        engine.retrospective(str(r["label"]), _d(r["prior_estimate"]), _d(r["outcome"]))
        for r in retrospective or ()
    )
    checked = (
        engine.range_check(range_low, range_high, balance)
        if range_low is not None and range_high is not None and balance is not None
        else None
    )
    return footing, rolled, retros, checked, engine.bias(retros)


_ESTIMATES = text(
    """
    SELECT e.id, e.name, e.account_ref, e.balance, e.status, e.decision_card_id, e.rollforward,
           e.retrospective, e.range_low, e.range_high, e.version,
           COALESCE(array_agg(c.amount ORDER BY c.position) FILTER (WHERE c.id IS NOT NULL),
                    '{}') AS components
      FROM accounting_estimates e
      LEFT JOIN estimate_components c ON c.estimate_id = e.id
     WHERE e.work_item_id = :w
     GROUP BY e.id
     ORDER BY e.name
    """
)


async def estimates(ctx: AuthContext, work_item_id: UUID) -> list[EstimateView]:
    await _engagement(ctx, work_item_id, "estimate.read")
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(_ESTIMATES, {"w": work_item_id})).mappings().all()
    out: list[EstimateView] = []
    for row in rows:
        footing, rolled, retros, checked, indicator = compute(
            row["balance"],
            [Decimal(a) for a in row["components"]],
            cast(dict[str, object] | None, row["rollforward"]),
            cast(list[dict[str, object]] | None, row["retrospective"]),
            row["range_low"],
            row["range_high"],
        )
        out.append(
            EstimateView(
                id=row["id"],
                name=row["name"],
                account_ref=row["account_ref"],
                balance=row["balance"],
                status=row["status"],
                pending_ep=row["status"] == "evaluated" and row["decision_card_id"] is not None,
                footing=footing,
                rollforward=rolled,
                retrospectives=retros,
                range=checked,
                bias=indicator,
                version=row["version"],
            )
        )
    return out


_METHOD = text(
    """
    UPDATE accounting_estimates
       SET method = CAST(:method AS jsonb), status = 'evaluated', version = version + 1,
           updated_at = clock_timestamp()
     WHERE id = :id AND work_item_id = :w AND version = :seen AND status <> 'exception'
    RETURNING version
    """
)


async def set_method(
    ctx: AuthContext, work_item_id: UUID, estimate_id: UUID, method: str, seen_version: int
) -> int:
    """Recording management's method (and the evaluation behind it) evaluates the estimate."""
    engagement_id = await _engagement(ctx, work_item_id, "estimate.evaluate")
    async with uow(ctx.tenant) as tx:
        version = (
            await tx.session.execute(
                _METHOD,
                {
                    "method": json.dumps({"text": method}),
                    "id": estimate_id,
                    "w": work_item_id,
                    "seen": seen_version,
                },
            )
        ).scalar_one_or_none()
        if version is None:
            raise StaleEstimate
        tx.record(
            "estimate.evaluated",
            target=Target("accounting_estimate", estimate_id),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )
    return int(version)


_FOR_CARD = text(
    "SELECT status, decision_card_id FROM accounting_estimates "
    "WHERE id = :id AND work_item_id = :w"
)
_LINK_CARD = text(
    "UPDATE accounting_estimates SET decision_card_id = :card, version = version + 1, "
    "updated_at = clock_timestamp() WHERE id = :id AND decision_card_id IS NULL RETURNING id"
)


async def request_conclusion(ctx: AuthContext, work_item_id: UUID, estimate_id: UUID) -> UUID:
    """Request partner conclusion… (AU-C 540): the EP's card; anyone else's decide is 403."""
    engagement_id = await _engagement(ctx, work_item_id, "estimate.request_conclusion")
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_FOR_CARD, {"id": estimate_id, "w": work_item_id})).first()
    if row is None:
        raise NotFound("accounting_estimate")
    if row.status != "evaluated":
        raise EstimateNotEvaluated
    if row.decision_card_id is not None:
        raise ConclusionAlreadyRequested
    card_id = await raise_decision_card(
        ctx,
        engagement_id=engagement_id,
        kind=CONCLUSION_KIND,
        question_key=question_key(estimate_id),
        work_item_id=work_item_id,
    )
    async with uow(ctx.tenant) as tx:
        if (
            await tx.session.execute(_LINK_CARD, {"card": card_id, "id": estimate_id})
        ).first() is None:
            raise ConclusionAlreadyRequested
        tx.record(
            "estimate.conclusion_requested",
            target=Target("accounting_estimate", estimate_id),
            after=Ref(card=card_id),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )
        tx.emit(
            EstimateConclusionRequested(
                engagement_id=engagement_id,
                work_item_id=work_item_id,
                estimate_id=estimate_id,
                decision_card_id=card_id,
            )
        )
    return card_id


_QUESTION_PREFIX: Final = "estimate.conclusion."


def question_key(estimate_id: UUID) -> str:
    """A card names its estimate in its question key (C3 keys are `[a-z0-9_.]`)."""
    return f"{_QUESTION_PREFIX}{estimate_id.hex}"


def estimate_of(key: str) -> UUID | None:
    if not key.startswith(_QUESTION_PREFIX):
        return None
    try:
        return UUID(hex=key.removeprefix(_QUESTION_PREFIX))
    except ValueError:
        return None


_CARD_FACTS = text(
    "SELECT name, balance, range_low, range_high FROM accounting_estimates WHERE id = :id"
)


async def _conclusion_card(tenant: TenantContext, subject: CardSubject) -> ComputedCard:
    """The options with the figures they rest on (balance, range); fixed copy, code figures."""
    estimate_id = estimate_of(subject.question_key)
    if estimate_id is None:
        raise NotFound("accounting_estimate")
    async with tenant_session(tenant) as session:
        row = (await session.execute(_CARD_FACTS, {"id": estimate_id})).first()
    if row is None:
        raise NotFound("accounting_estimate")
    figures = {
        "estimate_id": str(estimate_id),
        "balance": str(row.balance) if row.balance is not None else "",
        "range_low": str(row.range_low) if row.range_low is not None else "",
        "range_high": str(row.range_high) if row.range_high is not None else "",
    }
    return ComputedCard(
        options=tuple(CardOption(k, label, figures) for k, label in _CONCLUSION_OPTIONS),
        context=(CardContext("estimate", "Estimate", str(row.name)),),
    )


def register_estimate_conclusion_kind() -> None:
    register_decision_kind(
        DecisionKind(
            code=CONCLUSION_KIND,
            reserved_role="engagement_partner",
            options=_conclusion_card,
            # The question names its estimate (`estimate.conclusion.<id>`); the card's context
            # carries the estimate's name.
        )
    )


# --- related parties -----------------------------------------------------------------------------

_PARTIES = text(
    "SELECT id, display_ref, source, relationship, status, screened_out_reason, finding_id "
    "FROM related_parties WHERE work_item_id = :w ORDER BY display_ref NULLS LAST, id"
)
_ADD_PARTY = text(
    """
    INSERT INTO related_parties (tenant_id, engagement_id, work_item_id, display_ref, source,
                                 relationship, created_by_kind)
    VALUES (:t, :e, :w, :name, :source, :relationship, 'human')
    RETURNING id
    """
)
_SCREEN_OUT = text(
    """
    UPDATE related_parties
       SET status = 'screened_out', screened_out_reason = :reason, screened_out_by = :by,
           screened_out_at = clock_timestamp(), version = version + 1,
           updated_at = clock_timestamp()
     WHERE id = :id AND work_item_id = :w AND status = 'unevaluated'
    RETURNING id
    """
)


@dataclass(frozen=True)
class PartyView:
    id: UUID
    name: str | None
    source: str
    relationship: str | None
    status: str
    screened_out_reason: str | None
    finding_id: UUID | None


async def related_parties(ctx: AuthContext, work_item_id: UUID) -> list[PartyView]:
    await _engagement(ctx, work_item_id, "related_party.read")
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(_PARTIES, {"w": work_item_id})).all()
    return [PartyView(*row) for row in rows]


async def add_related_party(
    ctx: AuthContext,
    work_item_id: UUID,
    name: str,
    *,
    source: str = "manual",
    relationship: str | None = None,
) -> UUID:
    if source not in ("client_list", "manual"):
        raise DomainInvalid  # agent candidates arrive through the mode (A-05-T56)
    engagement_id = await _engagement(ctx, work_item_id, "related_party.manage")
    async with uow(ctx.tenant) as tx:
        party_id = (
            await tx.session.execute(
                _ADD_PARTY,
                {
                    "t": ctx.tenant_id,
                    "e": engagement_id,
                    "w": work_item_id,
                    "name": name[:300],
                    "source": source,
                    "relationship": relationship,
                },
            )
        ).scalar_one()
        tx.record(
            "related_party.added",
            target=Target("related_party", party_id),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )
    return cast(UUID, party_id)


async def screen_out(ctx: AuthContext, work_item_id: UUID, party_id: UUID, reason: str) -> None:
    """A person screens a candidate out, with a reason (AU-C 550); the row keeps who and when."""
    if not reason.strip():
        raise ScreenOutReasonRequired
    engagement_id = await _engagement(ctx, work_item_id, "related_party.screen_out")
    async with uow(ctx.tenant) as tx:
        found = (
            await tx.session.execute(
                _SCREEN_OUT,
                {"reason": reason[:1000], "by": ctx.user_id, "id": party_id, "w": work_item_id},
            )
        ).first()
        if found is None:
            raise NotFound("related_party")
        tx.record(
            "related_party.screened_out",
            target=Target("related_party", party_id),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )


# --- parties in interest -------------------------------------------------------------------------

_PII = text(
    "SELECT id, name, erisa_relationship, exemption, reporting FROM parties_in_interest "
    "WHERE work_item_id = :w ORDER BY name"
)
_PROHIBITED = text(
    "SELECT late_remittance_id, principal, deposited_on, business_days_late, lost_earnings, "
    "correction_status, form_5330_status FROM v_prohibited_transactions WHERE work_item_id = :w "
    "ORDER BY due_on"
)


@dataclass(frozen=True)
class ProhibitedTransaction:
    """Read from the late remittance (EBP-04): reported on line 4a, never copied."""

    late_remittance_id: UUID
    principal: Decimal | None
    deposited_on: object
    business_days_late: int | None
    lost_earnings: Decimal | None
    correction_status: str | None
    form_5330_status: str | None


async def parties_in_interest(
    ctx: AuthContext, work_item_id: UUID
) -> tuple[list[tuple[UUID, str, str, str | None, str | None]], list[ProhibitedTransaction]]:
    await _engagement(ctx, work_item_id, "ebp.read")
    async with tenant_session(ctx.tenant) as session:
        parties = [tuple(r) for r in (await session.execute(_PII, {"w": work_item_id})).all()]
        prohibited = [
            ProhibitedTransaction(*r)
            for r in (await session.execute(_PROHIBITED, {"w": work_item_id})).all()
        ]
    return cast(list[tuple[UUID, str, str, str | None, str | None]], parties), prohibited
