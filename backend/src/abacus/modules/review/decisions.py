"""Decision cards (P-04-T23, TASK-1402; ADR-160 clause 8; SHL-11; DEC-503 to DEC-506).

A judgement reserved to a role is a card whose options the kind's provider computed in code
(ADR-050), never a model. The agent raises a card through its task scope
(`raise_decision_card`, `decision_card.raise`); only the card's reserved role, and the person
when it names one, decides it (`decision.decide` with the `reserved_role` condition), with a
rationale, on the version they saw, with a recent second factor when the kind asks for one.

- Every write is a person's or the agent's own unit of work with its audit event. The decision is
  insert-only and human-only at the data layer (0094), and its audit action is on the human-only
  list (0212). DECISION-001 names the only files that reach `decide_card`.
- History is numbered (`decision_card_versions`, 0211): v1 proposed, then decided, then each
  reassessment. "No change" is a new version of the same card; a changed outcome raises a
  superseding card (its first row is the reassessment) and marks the old one superseded.
- Rationales and analysis requests are sealed; handing a rationale over is an access event.
- The agent's recommendation is an option tag and the suggestion it came from: never the decider.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Final, cast
from uuid import UUID, uuid4

from abacus.kernel.clock import system_now
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainForbidden, DomainInvalid, NotFound
from abacus.kernel.listing import (
    ListPage,
    capped_total,
    clamp_limit,
    decode_cursor,
    envelope,
    keyset,
    page_of,
    query_hash,
    status_counts,
)
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork, uow
from abacus.modules.engagements.api import get_ref, lock_ref
from abacus.modules.identity.api import (
    Actor,
    AgentContext,
    AuthContext,
    Forbidden,
    Resource,
    TargetFacts,
    authorise,
    member_could,
    names_of,
    team_of,
)
from abacus.modules.review.events import (
    DecisionCardRaised,
    DecisionCardSuperseded,
    DecisionDecided,
    DecisionNotifyRequested,
)
from abacus.modules.review.models import DecisionCard, DecisionCardVersion
from abacus.modules.review.repository import (
    card_list_query,
    cards_by_id,
    current_version,
    decision_of,
    get_card,
    insert_analysis_request,
    insert_card,
    insert_decision,
    insert_version,
    lock_card,
    set_card_status,
    successors_of,
    versions_of,
)
from abacus.modules.review.sealing import open_text, record_text_reads, seal_text
from abacus.modules.review.slots import (
    CardContext,
    CardFactor,
    CardOption,
    CardSubject,
    ComputedCard,
    DecisionKind,
    UnregisteredKind,
    decision_kind,
)

SUBJECT: Final = "decision_card"
RESOURCE: Final = "decision_cards"
RAISE: Final = "decision_card.raise"
DECIDE: Final = "decision.decide"
_KEY: Final = re.compile(r"[a-z][a-z0-9_]{0,39}")
_QUESTION: Final = re.compile(r"[a-z][a-z0-9_.]{0,79}")
_RATIONALE_LIMIT: Final = 4000
_ANALYSIS_LIMIT: Final = 2000
_MAX_OPTIONS: Final = 12
_CHAIN_LIMIT: Final = 50


class RationaleRequired(DomainInvalid):
    """A decision without a rationale (SHL-11 a: Decide stays disabled until one is typed)."""

    code = "rationale_required"


class RecommendationChanged(DomainConflict):
    """The card moved past the version the decider saw (reassessed or superseded)."""

    code = "recommendation_changed"


class DecisionCardState(DomainConflict):
    """The card is not in a state that takes this (decided, superseded)."""

    code = "decision_card_state"


class DecisionInvalid(DomainInvalid):
    """An option, factor, subject or provider answer the card can't take."""

    code = "decision_invalid"


class MfaRequired(DomainForbidden):
    """The kind asks for a second factor verified in the last `max_age_s` seconds: the shell
    steps up through ConfirmItsYou and retries."""

    code = "mfa_required"


# --- Views -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class OptionView:
    key: str
    label: str
    detail: str | None
    figures: dict[str, str]
    recommended: bool


@dataclass(frozen=True)
class ContextView:
    key: str
    label: str
    value: str
    citation_id: UUID | None


@dataclass(frozen=True)
class FactorView:
    key: str
    label: str
    applicable: bool
    checked: bool


@dataclass(frozen=True)
class DecisionView:
    id: UUID
    option_key: str
    factors: list[str]
    rationale: str
    seen_card_version: int
    decided_by: UUID
    decided_by_name: str
    decided_at: datetime


@dataclass(frozen=True)
class VersionView:
    version_no: int
    event: str
    actor_kind: str
    actor_user_id: UUID | None
    actor_initials: str | None
    at: datetime
    option_key: str | None
    changed: bool | None
    figures: dict[str, str]


@dataclass(frozen=True)
class CardItem:
    id: UUID
    engagement_id: UUID
    work_item_id: UUID | None
    kind: str
    version_no: int
    status: str
    reserved_role: str
    reserved_user_id: UUID | None
    reserved_user_name: str | None
    requested_at: datetime
    blocking_count: int
    superseded_by_version: int | None
    allowed_actions: list[str]


@dataclass(frozen=True)
class CardDetail:
    card: CardItem
    question: str
    context: list[ContextView]
    options: list[OptionView]
    factors: list[FactorView]
    citation_ids: list[UUID]
    recommendation: tuple[UUID, str] | None
    blocking_refs: list[tuple[str, UUID]]
    decision: DecisionView | None
    history: list[VersionView]


@dataclass(frozen=True)
class AnalysisRequestView:
    id: UUID
    card_id: UUID
    requested_by: UUID
    requested_at: datetime


@dataclass(frozen=True)
class NotifyView:
    card_id: UUID
    notified_user_id: UUID
    notified_at: datetime


# --- Helpers -----------------------------------------------------------------------------------


def _live_human(ctx: Actor) -> bool:
    """A decision is a person's own act (INV-1): never an agent, the platform, a client principal
    or a break-glass support session."""
    return (
        isinstance(ctx, AuthContext)
        and not ctx.client
        and ctx.tenant.actor_kind == "human"
        and not ctx.is_support
    )


def _human(ctx: Actor, action: str) -> AuthContext:
    if not _live_human(ctx):
        raise Forbidden(action, "role")
    return cast(AuthContext, ctx)


def _initials(name: str) -> str | None:
    found = "".join(w[0].upper() for w in name.split() if w[:1].isalpha())[:4]
    return found or None


def _resource(base: Resource, card: DecisionCard) -> Resource:
    """The card's engagement with its work item and reserved role and person, for the
    `reserved_role` condition (P-04-T15)."""
    return replace(
        base,
        work_item_id=card.work_item_id,
        target=TargetFacts(
            reserved_role=card.reserved_role, reserved_user_id=card.reserved_user_id
        ),
    )


async def _may(ctx: AuthContext, action: str, resource: Resource) -> bool:
    try:
        await authorise(ctx, action, resource)
    except Forbidden:
        return False
    return True


def _options_json(computed: ComputedCard, recommended: str | None) -> list[dict[str, object]]:
    return [
        {
            "key": o.key,
            "label": o.label,
            "detail": o.detail,
            "figures": dict(o.figures),
            "recommended": o.key == recommended,
        }
        for o in computed.options
    ]


def _context_json(computed: ComputedCard) -> list[dict[str, object]]:
    return [
        {
            "key": c.key,
            "label": c.label,
            "value": c.value,
            "citation_id": str(c.citation_id) if c.citation_id else None,
        }
        for c in computed.context
    ]


def _factors_json(computed: ComputedCard) -> list[dict[str, object]]:
    return [{"key": f.key, "label": f.label, "applicable": f.applicable} for f in computed.factors]


def _checked(computed: ComputedCard, recommended: str | None) -> ComputedCard:
    """The provider's answer, refused unless it is well-formed (fail closed)."""
    keys = [o.key for o in computed.options]
    if not keys or len(keys) > _MAX_OPTIONS or len(set(keys)) != len(keys):
        raise DecisionInvalid(facts={"field": "options"})
    if not all(_KEY.fullmatch(k) for k in keys):
        raise DecisionInvalid(facts={"field": "options"})
    for option in computed.options:
        if not all(
            isinstance(v, str) for v in cast(Mapping[str, object], option.figures).values()
        ):
            raise DecisionInvalid(facts={"field": "figures"})
    factor_keys = [f.key for f in computed.factors]
    if len(set(factor_keys)) != len(factor_keys) or not all(
        _KEY.fullmatch(k) for k in factor_keys
    ):
        raise DecisionInvalid(facts={"field": "factors"})
    if recommended is not None and recommended not in keys:
        raise DecisionInvalid(facts={"field": "recommended_option_key"})
    return computed


def _stored(card: DecisionCard) -> ComputedCard:
    """The card as computed when it was raised, for the provider's reassessment."""
    return ComputedCard(
        options=tuple(
            CardOption(
                key=str(o["key"]),
                label=str(o["label"]),
                figures=cast(dict[str, str], o.get("figures") or {}),
                detail=cast(str | None, o.get("detail")),
            )
            for o in card.options
        ),
        context=tuple(
            CardContext(
                key=str(c["key"]),
                label=str(c["label"]),
                value=str(c["value"]),
                citation_id=UUID(str(c["citation_id"])) if c.get("citation_id") else None,
            )
            for c in card.context
        ),
        factors=tuple(
            CardFactor(str(f["key"]), str(f["label"]), bool(f.get("applicable", True)))
            for f in card.factors
        ),
    )


def _recommended(card: DecisionCard) -> str | None:
    return next((str(o["key"]) for o in card.options if o.get("recommended")), None)


async def _role_holders(tenant_id: UUID, card: DecisionCard) -> list[UUID]:
    """Whom a new card waits on: its named person, else the engagement's holders of the role."""
    if card.reserved_user_id is not None:
        return [card.reserved_user_id]
    return sorted(
        {
            u
            for u, role in await team_of(tenant_id, card.engagement_id)
            if role == card.reserved_role
        }
    )


def _kind_or_none(code: str) -> DecisionKind | None:
    try:
        return decision_kind(code)
    except UnregisteredKind:
        return None


# --- Raise (the agent, through its task scope) -------------------------------------------------


async def raise_decision_card(
    ctx: Actor,
    *,
    engagement_id: UUID,
    kind: str,
    question_key: str,
    work_item_id: UUID | None = None,
    reserved_user_id: UUID | None = None,
    recommended_option_key: str | None = None,
    recommendation_suggestion_id: UUID | None = None,
) -> UUID:
    """`review.api.raise_decision_card`: a card on `engagement_id` with options computed by the
    kind's provider. The agent raises it through `task_scope` (`decision_card.raise`); its
    recommendation is a tag on one option, never a decision. With no person named, a role held
    by exactly one person on the engagement names them."""
    found = decision_kind(kind)  # unregistered: 422 unregistered_kind (fail closed)
    if not _QUESTION.fullmatch(question_key):
        raise DecisionInvalid(facts={"field": "question_key"})
    if isinstance(ctx, AgentContext) and ctx.engagement_id != engagement_id:
        raise Forbidden(RAISE, "relationship")
    ref = await get_ref(ctx, engagement_id)
    resource = replace(ref.resource(), work_item_id=work_item_id)
    await authorise(ctx, RAISE, resource)
    computed = _checked(
        await found.options(ctx.tenant, CardSubject(engagement_id, work_item_id, question_key)),
        recommended_option_key,
    )
    holders = sorted(
        {
            u
            for u, role in await team_of(ctx.tenant_id, engagement_id)
            if role == found.reserved_role
        }
    )
    person = reserved_user_id
    if person is None and len(holders) == 1:
        person = holders[0]
    if person is not None and not await member_could(
        ctx.tenant_id,
        person,
        DECIDE,
        replace(
            resource,
            target=TargetFacts(reserved_role=found.reserved_role, reserved_user_id=person),
        ),
        waive_fresh_mfa=True,
    ):
        raise DecisionInvalid(facts={"field": "reserved_user_id"})
    async with uow(ctx.tenant) as tx:
        await lock_ref(tx, engagement_id)
        card_id = await _insert_card(
            tx,
            ctx,
            engagement_id=engagement_id,
            work_item_id=work_item_id,
            kind=found,
            question_key=question_key,
            version_no=1,
            reserved_user_id=person,
            computed=computed,
            recommended=recommended_option_key,
            recommendation_suggestion_id=recommendation_suggestion_id,
            supersedes_id=None,
        )
        await insert_version(
            tx.session,
            tenant_id=ctx.tenant_id,
            card_id=card_id,
            version_no=1,
            event="proposed",
            actor_user_id=ctx.user_id if isinstance(ctx, AuthContext) else None,
        )
        tx.emit(
            DecisionCardRaised(
                card_id=card_id,
                engagement_id=engagement_id,
                kind=found.code,
                version_no=1,
                recipient_user_ids=[person] if person is not None else holders,
            )
        )
    return card_id


async def _insert_card(
    tx: UnitOfWork,
    ctx: Actor,
    *,
    engagement_id: UUID,
    work_item_id: UUID | None,
    kind: DecisionKind,
    question_key: str,
    version_no: int,
    reserved_user_id: UUID | None,
    computed: ComputedCard,
    recommended: str | None,
    recommendation_suggestion_id: UUID | None,
    supersedes_id: UUID | None,
) -> UUID:
    card_id = await insert_card(
        tx.session,
        tenant_id=ctx.tenant_id,
        engagement_id=engagement_id,
        work_item_id=work_item_id,
        kind=kind.code,
        version_no=version_no,
        question_key=question_key,
        reserved_role=kind.reserved_role,
        reserved_user_id=reserved_user_id,
        options=_options_json(computed, recommended),
        context=_context_json(computed),
        factors=_factors_json(computed),
        recommendation_suggestion_id=recommendation_suggestion_id,
        blocking_refs=[{"type": t, "id": str(i)} for t, i in computed.blocking_refs],
        supersedes_id=supersedes_id,
        raised_by_kind=ctx.tenant.actor_kind,
        raised_by_id=ctx.tenant.actor_id,
        run_id=ctx.agent_run_id if isinstance(ctx, AgentContext) else None,
    )
    tx.record(
        "decision_card.raised",
        target=Target(SUBJECT, card_id),
        after=Ref(version=version_no),
        scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
    )
    return card_id


# --- Reads -------------------------------------------------------------------------------------


async def _readable(ctx: AuthContext, card_id: UUID) -> tuple[DecisionCard, Resource]:
    async with tenant_session(ctx.tenant) as session:
        card = await get_card(session, card_id)
    if card is None:
        raise NotFound(SUBJECT)
    ref = await get_ref(ctx, card.engagement_id)
    resource = _resource(ref.resource(), card)
    await authorise(ctx, "decision.read", resource)  # a wall answers 404
    return card, resource


async def _allowed(ctx: AuthContext, card: DecisionCard, resource: Resource) -> list[str]:
    if not _live_human(ctx) or card.status == "superseded":
        return []
    out: list[str] = []
    if card.status == "awaiting_role" and await _may(ctx, DECIDE, resource):
        out.append(DECIDE)
    if await _may(ctx, "decision.request_analysis", resource):
        out.append("decision.request_analysis")
    if (
        card.status == "awaiting_role"
        and card.reserved_user_id is not None
        and card.reserved_user_id != ctx.user_id
        and await _may(ctx, "decision.notify", resource)
    ):
        out.append("decision.notify")
    kind = _kind_or_none(card.kind)
    if (
        kind is not None
        and kind.reassess is not None
        and await _may(ctx, "decision.reassess", resource)
    ):
        out.append("decision.reassess")
    return out


async def _chain(session_tenant: TenantContext, card: DecisionCard) -> list[DecisionCard]:
    """The card and every card it supersedes, oldest first (bounded)."""
    chain = [card]
    async with tenant_session(session_tenant) as session:
        while chain[0].supersedes_id is not None and len(chain) < _CHAIN_LIMIT:
            found = await cards_by_id(session, [chain[0].supersedes_id])
            if not found or found[0].engagement_id != card.engagement_id:
                break
            chain.insert(0, found[0])
    return chain


async def _successor_versions(tenant: TenantContext, card_ids: Sequence[UUID]) -> dict[UUID, int]:
    async with tenant_session(tenant) as session:
        later = await successors_of(session, card_ids)
    return {c.supersedes_id: c.version_no for c in later if c.supersedes_id is not None}


async def _item(
    ctx: AuthContext,
    card: DecisionCard,
    resource: Resource | None,
    names: Mapping[UUID, str],
    current: int,
    superseded_by: int | None,
) -> CardItem:
    return CardItem(
        id=card.id,
        engagement_id=card.engagement_id,
        work_item_id=card.work_item_id,
        kind=card.kind,
        version_no=current,
        status=card.status,
        reserved_role=card.reserved_role,
        reserved_user_id=card.reserved_user_id,
        reserved_user_name=names.get(card.reserved_user_id) if card.reserved_user_id else None,
        requested_at=card.created_at,
        blocking_count=len(card.blocking_refs),
        superseded_by_version=superseded_by,
        allowed_actions=await _allowed(ctx, card, resource) if resource is not None else [],
    )


def _current(rows: Sequence[DecisionCardVersion], card: DecisionCard) -> int:
    mine = [r.version_no for r in rows if r.card_id == card.id]
    return max(mine) if mine else card.version_no


async def list_cards(
    ctx: AuthContext,
    *,
    engagement_id: UUID | None,
    state: str | None,
    cursor: str | None,
    limit: int | None,
) -> ListPage[CardItem]:
    """`GET /v1/decision-cards`: cards on engagements the caller may read them in, oldest first;
    `counts` per status without the state filter. No question, option or rationale."""
    size = clamp_limit(limit)
    query = query_hash(engagement_id=engagement_id, state=state)
    after = (
        decode_cursor(cursor, tenant_id=ctx.tenant_id, resource=RESOURCE, query=query)
        if cursor
        else None
    )
    base, sort, id_column = card_list_query(ctx, engagement_id=engagement_id)
    stmt = base.where(DecisionCard.status == state) if state is not None else base
    async with tenant_session(ctx.tenant) as session:
        counts = await status_counts(session, base, DecisionCard.status.expression)
        total = await capped_total(session, stmt)
        fetched = (
            (
                await session.execute(
                    keyset(stmt, sort=sort, id_column=id_column, after=after, limit=size)
                )
            )
            .scalars()
            .all()
        )
        rows, position = page_of(
            fetched, limit=size, key=lambda r: r.created_at, id_of=lambda r: r.id
        )
        history = await versions_of(session, [r.id for r in rows])
    names = await names_of(sorted({r.reserved_user_id for r in rows if r.reserved_user_id}))
    later = await _successor_versions(ctx.tenant, [r.id for r in rows])
    resources: dict[UUID, Resource] = {}
    for engagement in sorted({r.engagement_id for r in rows}):
        resources[engagement] = (await get_ref(ctx, engagement)).resource()
    items = [
        await _item(
            ctx,
            r,
            _resource(resources[r.engagement_id], r),
            names,
            _current(history, r),
            later.get(r.id),
        )
        for r in rows
    ]
    return envelope(
        items,
        next_position=position,
        tenant_id=ctx.tenant_id,
        resource=RESOURCE,
        query=query,
        total=total,
        counts=counts,
    )


async def card_detail(ctx: AuthContext, card_id: UUID) -> CardDetail:
    """SHL-11 a to h: the card, its numbered history across the cards it supersedes, and the
    caller's allowed actions. A decided card's rationale read is an access event."""
    card, resource = await _readable(ctx, card_id)
    chain = await _chain(ctx.tenant, card)
    async with tenant_session(ctx.tenant) as session:
        history = list(await versions_of(session, [c.id for c in chain]))
        decision = await decision_of(session, card.id)
    later = await _successor_versions(ctx.tenant, [card.id])
    people = {r.actor_user_id for r in history if r.actor_user_id is not None}
    if card.reserved_user_id is not None:
        people.add(card.reserved_user_id)
    if decision is not None:
        people.add(decision.decided_by)
    names = await names_of(sorted(people))
    decided: DecisionView | None = None
    if decision is not None:
        await record_text_reads(
            ctx.tenant,
            SUBJECT,
            [card.id],
            engagement_id=card.engagement_id,
            client_id=resource.client_id,
            work_item_id=card.work_item_id,
        )
        decided = DecisionView(
            id=decision.id,
            option_key=decision.option_key,
            factors=[str(f) for f in decision.factors],
            rationale=await open_text(
                ctx.tenant, decision.rationale_sealed, "decision", decision.id, "rationale"
            ),
            seen_card_version=decision.seen_card_version,
            decided_by=decision.decided_by,
            decided_by_name=names.get(decision.decided_by, "Former member"),
            decided_at=decision.created_at,
        )
    kind = _kind_or_none(card.kind)
    recommended = _recommended(card)
    chosen = set(decided.factors) if decided else set[str]()
    context = [
        ContextView(
            str(c["key"]),
            str(c["label"]),
            str(c["value"]),
            UUID(str(c["citation_id"])) if c.get("citation_id") else None,
        )
        for c in card.context
    ]
    return CardDetail(
        card=await _item(ctx, card, resource, names, _current(history, card), later.get(card.id)),
        question=(kind.questions.get(card.question_key, "") if kind else ""),
        context=context,
        options=[
            OptionView(
                key=str(o["key"]),
                label=str(o["label"]),
                detail=cast(str | None, o.get("detail")),
                figures=cast(dict[str, str], o.get("figures") or {}),
                recommended=bool(o.get("recommended")),
            )
            for o in card.options
        ],
        factors=[
            FactorView(
                str(f["key"]),
                str(f["label"]),
                bool(f.get("applicable", True)),
                str(f["key"]) in chosen,
            )
            for f in card.factors
        ],
        citation_ids=[c.citation_id for c in context if c.citation_id is not None],
        recommendation=(
            (card.recommendation_suggestion_id, recommended)
            if card.recommendation_suggestion_id is not None and recommended is not None
            else None
        ),
        blocking_refs=[(str(b["type"]), UUID(str(b["id"]))) for b in card.blocking_refs],
        decision=decided,
        history=[
            VersionView(
                version_no=r.version_no,
                event=r.event,
                actor_kind=r.actor_kind
                if r.actor_kind in ("human", "agent", "system")
                else "system",
                actor_user_id=r.actor_user_id,
                actor_initials=_initials(names.get(r.actor_user_id, ""))
                if r.actor_user_id
                else None,
                at=r.created_at,
                option_key=r.option_key,
                changed=r.changed,
                figures=dict(r.figures),
            )
            for r in sorted(history, key=lambda r: (r.version_no, r.created_at))
        ],
    )


# --- Decide ------------------------------------------------------------------------------------


def _fresh(ctx: AuthContext, kind: DecisionKind) -> None:
    """ADR-160 clause 8: the kind declares whether deciding needs a recent second factor."""
    limit = kind.mfa_max_age_s
    if limit is None:
        return
    if ctx.mfa_at is None or system_now() - ctx.mfa_at > timedelta(seconds=limit):
        raise MfaRequired(facts={"max_age_s": limit})


async def decide_card(
    ctx: AuthContext,
    card_id: UUID,
    *,
    option_key: str,
    factors: Sequence[str],
    rationale: str | None,
    seen_version: int,
) -> CardDetail:
    """`POST /v1/decision-cards/{id}/decide` (SHL-11 a to c): a live ctx holding the card's
    reserved role (and, when it names one, that ctx) decides, with a rationale, on the version
    they saw. 403 outside the role, 403 `mfa_required` per kind, 409 `decision_card_state` once
    decided or superseded, 409 `recommendation_changed` on a stale version, 422
    `rationale_required`."""
    _human(ctx, DECIDE)
    card, _ = await _readable(ctx, card_id)
    kind = decision_kind(card.kind)
    text = (rationale or "").strip()
    decision_id = uuid4()
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, card.engagement_id)
        locked = await lock_card(tx.session, card_id)
        if locked is None or locked.engagement_id != card.engagement_id:
            raise NotFound(SUBJECT)
        await authorise(ctx, DECIDE, _resource(ref.resource(), locked))
        _fresh(ctx, kind)
        if locked.status != "awaiting_role":
            raise DecisionCardState(facts={"status": locked.status})
        current = await current_version(tx.session, locked.id) or locked.version_no
        if seen_version != current:
            raise RecommendationChanged(facts={"version_no": current})
        options = {str(o["key"]): o for o in locked.options}
        if option_key not in options:
            raise DecisionInvalid(facts={"field": "option_key"})
        known = {str(f["key"]) for f in locked.factors}
        chosen = list(dict.fromkeys(factors))
        if not set(chosen) <= known:
            raise DecisionInvalid(facts={"field": "factors"})
        if not text:
            raise RationaleRequired
        if len(text) > _RATIONALE_LIMIT:
            raise DecisionInvalid(facts={"field": "rationale"})
        await insert_decision(
            tx.session,
            id=decision_id,
            tenant_id=ctx.tenant_id,
            card_id=locked.id,
            option_key=option_key,
            rationale_sealed=await seal_text(
                ctx.tenant, text, "decision", decision_id, "rationale"
            ),
            factors=chosen,
            seen_card_version=seen_version,
            decided_by=ctx.user_id,
            mfa_at=ctx.mfa_at,
        )
        await insert_version(
            tx.session,
            tenant_id=ctx.tenant_id,
            card_id=locked.id,
            version_no=current + 1,
            event="decided",
            option_key=option_key,
            figures=cast(dict[str, str], options[option_key].get("figures") or {}),
            decision_id=decision_id,
            actor_user_id=ctx.user_id,
        )
        await set_card_status(tx.session, locked.id, "decided")
        tx.record(
            "decision.decided",
            target=Target(SUBJECT, locked.id),
            after=Ref(decision=decision_id, version=current + 1),
            scope=Scope(engagement_id=locked.engagement_id, work_item_id=locked.work_item_id),
        )
        tx.emit(
            DecisionDecided(
                card_id=locked.id,
                decision_id=decision_id,
                engagement_id=locked.engagement_id,
                kind=locked.kind,
                option_key=option_key,
                decided_by=ctx.user_id,
            )
        )
    return await card_detail(ctx, card_id)


# --- Analysis requests, notify, reassess -------------------------------------------------------


async def request_analysis(ctx: AuthContext, card_id: UUID, text: str) -> AnalysisRequestView:
    """SHL-11 b: "Request more analysis" records a sealed request for the run (P-10 delivers)."""
    _human(ctx, "decision.request_analysis")
    body = (text or "").strip()
    if not body or len(body) > _ANALYSIS_LIMIT:
        raise DecisionInvalid(facts={"field": "text"})
    card, _ = await _readable(ctx, card_id)
    request_id = uuid4()
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, card.engagement_id)
        locked = await lock_card(tx.session, card_id)
        if locked is None:
            raise NotFound(SUBJECT)
        await authorise(ctx, "decision.request_analysis", _resource(ref.resource(), locked))
        if locked.status == "superseded":
            raise DecisionCardState(facts={"status": locked.status})
        at = await insert_analysis_request(
            tx.session,
            id=request_id,
            tenant_id=ctx.tenant_id,
            card_id=locked.id,
            text_sealed=await seal_text(ctx.tenant, body, "decision_analysis", request_id, "text"),
            requested_by=ctx.user_id,
        )
        tx.record(
            "decision.analysis_requested",
            target=Target(SUBJECT, locked.id),
            after=Ref(request=request_id),
            scope=Scope(engagement_id=locked.engagement_id, work_item_id=locked.work_item_id),
        )
    return AnalysisRequestView(request_id, card_id, ctx.user_id, at)


async def notify(ctx: AuthContext, card_id: UUID) -> NotifyView:
    """SHL-11 b: "Notify <ctx>" sends the card's named ctx a mention notification."""
    _human(ctx, "decision.notify")
    card, _ = await _readable(ctx, card_id)
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, card.engagement_id)
        locked = await lock_card(tx.session, card_id)
        if locked is None:
            raise NotFound(SUBJECT)
        await authorise(ctx, "decision.notify", _resource(ref.resource(), locked))
        if locked.status != "awaiting_role" or locked.reserved_user_id is None:
            raise DecisionCardState(facts={"status": locked.status})
        tx.record(
            "decision.notified",
            target=Target(SUBJECT, locked.id),
            after=Ref(user=locked.reserved_user_id),
            scope=Scope(engagement_id=locked.engagement_id, work_item_id=locked.work_item_id),
        )
        tx.emit(
            DecisionNotifyRequested(
                card_id=locked.id,
                engagement_id=locked.engagement_id,
                by_user=ctx.user_id,
                assignee_user_id=locked.reserved_user_id,
            )
        )
        reserved = locked.reserved_user_id
    return NotifyView(card_id, reserved, system_now())


async def reassess(ctx: AuthContext, card_id: UUID) -> CardDetail:
    """SHL-11 d, h: the kind's provider recomputes in code. No change records a new version of
    the same card with the provider's figures; a changed outcome raises a superseding card (its
    first version is the reassessment) and marks this one superseded."""
    _human(ctx, "decision.reassess")
    card, _ = await _readable(ctx, card_id)
    kind = decision_kind(card.kind)
    if kind.reassess is None:
        raise UnregisteredKind
    if card.status == "superseded":
        raise DecisionCardState(facts={"status": card.status})
    async with tenant_session(ctx.tenant) as session:
        decision = await decision_of(session, card.id)
    subject = CardSubject(card.engagement_id, card.work_item_id, card.question_key)
    outcome = await kind.reassess(
        ctx.tenant, subject, decision.option_key if decision else None, _stored(card)
    )
    if not all(isinstance(v, str) for v in cast(Mapping[str, object], outcome.figures).values()):
        raise DecisionInvalid(facts={"field": "figures"})
    if outcome.changed:
        if outcome.card is None:
            raise DecisionInvalid(facts={"field": "card"})
        _checked(outcome.card, None)
    result = card_id
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, card.engagement_id)
        locked = await lock_card(tx.session, card_id)
        if locked is None:
            raise NotFound(SUBJECT)
        await authorise(ctx, "decision.reassess", _resource(ref.resource(), locked))
        if locked.status != card.status:
            raise RecommendationChanged(facts={"status": locked.status})
        current = await current_version(tx.session, locked.id) or locked.version_no
        version = current + 1
        scope = Scope(engagement_id=locked.engagement_id, work_item_id=locked.work_item_id)
        if not outcome.changed:
            await insert_version(
                tx.session,
                tenant_id=ctx.tenant_id,
                card_id=locked.id,
                version_no=version,
                event="reassessed",
                changed=False,
                figures=dict(outcome.figures),
                actor_user_id=ctx.user_id,
            )
            tx.record(
                "decision.reassessed",
                target=Target(SUBJECT, locked.id),
                after=Ref(version=version, changed=0),
                scope=scope,
            )
        else:
            result = await _insert_card(
                tx,
                ctx,
                engagement_id=locked.engagement_id,
                work_item_id=locked.work_item_id,
                kind=kind,
                question_key=locked.question_key,
                version_no=version,
                reserved_user_id=locked.reserved_user_id,
                computed=cast(ComputedCard, outcome.card),
                recommended=None,
                recommendation_suggestion_id=None,
                supersedes_id=locked.id,
            )
            await insert_version(
                tx.session,
                tenant_id=ctx.tenant_id,
                card_id=result,
                version_no=version,
                event="reassessed",
                changed=True,
                figures=dict(outcome.figures),
                actor_user_id=ctx.user_id,
            )
            await set_card_status(tx.session, locked.id, "superseded")
            tx.record(
                "decision.reassessed",
                target=Target(SUBJECT, locked.id),
                after=Ref(version=version, changed=1, card=result),
                scope=scope,
            )
            tx.record(
                "decision_card.superseded",
                target=Target(SUBJECT, locked.id),
                after=Ref(card=result, version=version),
                scope=scope,
            )
            tx.emit(
                DecisionCardSuperseded(
                    card_id=locked.id,
                    superseded_by_card_id=result,
                    engagement_id=locked.engagement_id,
                    kind=locked.kind,
                )
            )
            tx.emit(
                DecisionCardRaised(
                    card_id=result,
                    engagement_id=locked.engagement_id,
                    kind=locked.kind,
                    version_no=version,
                    recipient_user_ids=await _role_holders(ctx.tenant_id, locked),
                )
            )
    return await card_detail(ctx, result)
