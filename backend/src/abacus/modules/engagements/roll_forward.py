"""Roll forward from last year's engagement (SPEC-025 AC-2; TASK-048).

A proposal is computed, never stored: last year's team (minus anyone who has left or is now walled
from the client), the template last year used at its latest version, and last year's items. An
item is *used* when it was accepted; everything else, waived and not applicable included, is
proposed unticked. Items the latest template adds (matched by area and description, ignoring case
and spacing, D6) are flagged and ticked (D5). Deterministic code, no model ("used" is a fact).

Request items belong to `requests`, which depends on this module; it plugs in reading last year's
items and copying the confirmed ones through `register_roll_forward_items` (ADR-106, D1).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Literal
from uuid import UUID

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork
from abacus.modules.engagements.models import Engagement
from abacus.modules.engagements.repository import get_engagement, list_templates, prior_candidates
from abacus.modules.engagements.service import (
    MethodologyVersionView,
    get_ref,
    pin_methodology,
    version_detail,
)
from abacus.modules.identity.api import (
    Actor,
    AuthContext,
    Resource,
    add_rolled_forward_member,
    authorise,
    available_staff,
    engagement_team,
)

ItemKind = Literal["used", "not_used", "new_in_template"]
MAX_ITEMS = 2000  # SPEC-025 §13: one prior engagement, up to 2,000 items, in one request


@dataclass(frozen=True)
class PriorItem:
    id: UUID
    description: str
    audit_area: str
    tier: str | None
    client_visible: bool
    status: str


@dataclass(frozen=True)
class TemplateSeed:
    """An item the latest template adds; `key` is its position in that version."""

    key: int
    description: str
    audit_area: str
    tier: str | None


# (who reads, last year's engagement) -> its items, read under `visible(roll_forward.read)`.
ProposedItems = Callable[[Actor, UUID], Awaitable[list[PriorItem]]]
# (the creating unit of work, who, new engagement, prior engagement, ticked prior items, ticked
# template additions) -> how many items were created. Refuses an item not on the prior engagement.
CopyItems = Callable[
    [UnitOfWork, AuthContext, UUID, UUID, Sequence[UUID], Sequence[TemplateSeed]], Awaitable[int]
]
_items: tuple[ProposedItems, CopyItems] | None = None


def register_roll_forward_items(proposed: ProposedItems, copy: CopyItems) -> None:
    global _items
    if _items is not None and _items != (proposed, copy):
        raise RuntimeError("the roll-forward item functions are already registered")
    _items = (proposed, copy)


class RollForwardUnavailable(DomainConflict):
    code = "roll_forward_unavailable"


class PriorMismatch(DomainConflict):
    """The prior engagement isn't this client entity's, or is another type."""

    code = "prior_mismatch"


class ProposalChanged(DomainConflict):
    """The template's latest version changed since the proposal: ask for it again."""

    code = "proposal_changed"


class TeamMemberUnavailable(DomainConflict):
    """Someone confirmed has since left the firm or been walled from the client."""

    code = "team_member_unavailable"


# --- The proposal ----------------------------------------------------------------------------


@dataclass(frozen=True)
class PriorChoice:
    engagement_id: UUID
    name: str
    fiscal_period_start: date
    fiscal_period_end: date


@dataclass(frozen=True)
class ProposedMember:
    user_id: UUID
    display_name: str
    role: str
    available: bool


@dataclass(frozen=True)
class ProposedTemplate:
    template_id: UUID
    template_name: str
    version_last_year: int
    latest_version_id: UUID
    latest_version: int


@dataclass(frozen=True)
class ProposedItem:
    kind: ItemKind
    description: str
    audit_area: str
    tier: str | None
    client_visible: bool
    ticked: bool
    prior_item_id: UUID | None = None
    template_key: int | None = None


@dataclass(frozen=True)
class Proposal:
    prior: PriorChoice | None
    others: list[PriorChoice]
    team: list[ProposedMember]
    template: ProposedTemplate | None
    items: list[ProposedItem]


def _key(audit_area: str, description: str) -> tuple[str, str]:
    return (" ".join(audit_area.split()).casefold(), " ".join(description.split()).casefold())


def template_seeds(latest: MethodologyVersionView) -> list[TemplateSeed]:
    names = {area.code: area.name for area in latest.areas}
    return [
        TemplateSeed(i, item.description, names.get(item.area_code, item.area_code), item.tier)
        for i, item in enumerate(latest.items)
    ]


def classify_items(
    prior: Sequence[PriorItem], seeds: Sequence[TemplateSeed]
) -> list[ProposedItem]:
    """Used (accepted) items ticked, every other prior item unticked, then the template's
    additions flagged and ticked (D5, D6)."""
    found = [
        ProposedItem(
            "used" if item.status == "accepted" else "not_used",
            item.description,
            item.audit_area,
            item.tier,
            item.client_visible,
            ticked=item.status == "accepted",
            prior_item_id=item.id,
        )
        for item in prior
    ]
    known = {_key(item.audit_area, item.description) for item in prior}
    found += [
        ProposedItem(
            "new_in_template",
            seed.description,
            seed.audit_area,
            seed.tier,
            False,
            ticked=True,
            template_key=seed.key,
        )
        for seed in seeds
        if _key(seed.audit_area, seed.description) not in known
    ]
    return found


def _choice(engagement: Engagement) -> PriorChoice:
    return PriorChoice(
        engagement.id,
        engagement.name,
        engagement.fiscal_period_start,
        engagement.fiscal_period_end,
    )


async def _latest_of(
    ctx: AuthContext, version_id: UUID | None
) -> tuple[MethodologyVersionView, MethodologyVersionView] | None:
    """(the version last year used, its template's latest version), or None without one."""
    if version_id is None:
        return None
    then = await version_detail(ctx.tenant, version_id)
    async with tenant_session(ctx.tenant) as session:
        latest = [
            v.id
            for t, v in await list_templates(session, latest=True)
            if t.id == then.summary.template_id
        ]
    return then, await version_detail(ctx.tenant, latest[0]) if latest else then


async def propose(
    ctx: AuthContext,
    *,
    client_entity_id: UUID,
    type: str,
    fiscal_period_start: date,
    prior_engagement_id: UUID | None = None,
) -> Proposal:
    await authorise(ctx, "engagement.create", Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        candidates = list(
            await prior_candidates(session, ctx, client_entity_id, type, fiscal_period_start)
        )
    if not candidates:
        return Proposal(None, [], [], None, [])
    chosen = candidates[0]
    if prior_engagement_id is not None:
        matching = [c for c in candidates if c.id == prior_engagement_id]
        if not matching:
            raise NotFound("prior_engagement")
        chosen = matching[0]
    if _items is None:
        raise RollForwardUnavailable("items")
    ref = await get_ref(ctx, chosen.id)
    await authorise(ctx, "roll_forward.read", ref.resource())
    available = await available_staff(ctx.tenant, ref.client_id)
    team = [
        ProposedMember(m.user_id, m.display_name, m.role, m.user_id in available)
        for m in await engagement_team(ctx, chosen.id)
        if m.user_id != ctx.user_id
    ]
    versions = await _latest_of(ctx, chosen.methodology_version_id)
    template = None
    seeds: list[TemplateSeed] = []
    if versions is not None:
        then, latest = versions
        template = ProposedTemplate(
            then.summary.template_id,
            latest.summary.template_name,
            then.summary.version,
            latest.summary.version_id,
            latest.summary.version,
        )
        seeds = template_seeds(latest)
    prior_items = (await _items[0](ctx, chosen.id))[:MAX_ITEMS]
    return Proposal(
        _choice(chosen),
        [_choice(c) for c in candidates if c.id != chosen.id],
        team,
        template,
        classify_items(prior_items, seeds),
    )


# --- Creating from a confirmed proposal --------------------------------------------------------


@dataclass(frozen=True)
class RollForward:
    prior_engagement_id: UUID
    team: Sequence[tuple[UUID, str]]  # (person, role)
    version_id: UUID | None  # the template's latest version, as proposed; None for no template
    prior_item_ids: Sequence[UUID]
    template_keys: Sequence[int]


async def check_prior(
    ctx: AuthContext, roll: RollForward, client_entity_id: UUID | None, type: str
) -> UUID:
    """Before the unit of work: the caller may read the prior engagement, which is this entity's
    and this type. Returns its client."""
    if _items is None:
        raise RollForwardUnavailable("items")
    ref = await get_ref(ctx, roll.prior_engagement_id)
    await authorise(ctx, "roll_forward.read", ref.resource())
    async with tenant_session(ctx.tenant) as session:
        prior = await get_engagement(session, roll.prior_engagement_id)
    if prior is None:
        raise NotFound("prior_engagement")
    if prior.client_entity_id != client_entity_id or prior.type != type:
        raise PriorMismatch(str(roll.prior_engagement_id))
    return prior.client_id


async def apply_roll_forward(
    tx: UnitOfWork, ctx: AuthContext, engagement_id: UUID, client_id: UUID, roll: RollForward
) -> None:
    """Inside the creating unit of work, after the creator became partner: exactly what was
    confirmed — the team, the template's latest version, the ticked items."""
    if _items is None:
        raise RollForwardUnavailable("items")
    for user_id, role in roll.team:
        if user_id == ctx.user_id:
            continue  # the creator is already an engagement partner (D4)
        try:
            await add_rolled_forward_member(tx, ctx, engagement_id, client_id, user_id, role)  # pyright: ignore[reportArgumentType] -- validated as a staff role by the route
        except NotFound:
            raise TeamMemberUnavailable(str(user_id)) from None
    seeds: list[TemplateSeed] = []
    prior = await get_ref(ctx, roll.prior_engagement_id)
    versions = await _latest_of(ctx, prior.methodology_version_id)
    if roll.version_id is not None:
        if versions is None or versions[1].summary.version_id != roll.version_id:
            raise ProposalChanged(str(roll.version_id))
        await pin_methodology(tx, engagement_id, roll.version_id)
        wanted = set(roll.template_keys)
        prior_items = await _items[0](ctx, roll.prior_engagement_id)
        offered = {
            p.template_key
            for p in classify_items(prior_items, template_seeds(versions[1]))
            if p.template_key is not None
        }
        if not wanted <= offered:
            raise DomainInvalid("a template item that wasn't proposed")
        seeds = [s for s in template_seeds(versions[1]) if s.key in wanted]
    elif roll.template_keys:
        raise DomainInvalid("template items without the template")
    created = await _items[1](
        tx, ctx, engagement_id, roll.prior_engagement_id, roll.prior_item_ids, seeds
    )
    tx.record(
        "engagement.rolled_forward",
        target=Target("engagement", engagement_id),
        after=Ref(
            prior_engagement_id=roll.prior_engagement_id,
            items_created=created,
            team_added=len([u for u, _ in roll.team if u != ctx.user_id]),
        ),
    )
