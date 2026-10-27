"""Engagement rules (TASK-008 design §3).

Authorise before any write: the route guard can hide a response but can't undo a commit.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Final, Literal
from uuid import UUID, uuid4

from sqlalchemy import ColumnElement, Select, select
from sqlalchemy.orm import QueryableAttribute

from abacus.ai_gateway import BoundaryFactsChanged, forget_boundary_facts
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Target, UnitOfWork, uow
from abacus.modules.engagements.events import EngagementCreated, TeamChangeProposed
from abacus.modules.engagements.models import Engagement
from abacus.modules.engagements.repository import (
    client_column as _client_column,
)
from abacus.modules.engagements.repository import (
    entity_engagement_ids,
    get_engagement,
    insert_engagement,
    list_engagements,
    lock_engagement,
    open_engagement_ids,
    set_ai_exclusion,
    set_methodology_version,
)
from abacus.modules.engagements.team_errors import EqrOnTeam

if TYPE_CHECKING:
    from abacus.modules.engagements.roll_forward import RollForward
from abacus.modules.identity.api import (
    Actor,
    AuthContext,
    Candidate,
    ContactView,
    Forbidden,
    Resource,
    StaffRole,
    TeamMember,
    add_creator_as_partner,
    add_member,
    add_self_joined_admin,
    authorise,
    candidates,
    change_role,
    contacts,
    create_invitation,
    engagement_team,
    hidden_clients,
    remove_client,
    remove_member,
    resend_invitation,
    revoke_invitation,
    set_member_hours,
    team_standing,
)
from abacus.modules.methodology.api import (
    EngagementType,
    MethodologyVersionView,
    version_in,
)
from abacus.modules.organisations.api import (
    ClientChoice,
    ClientNames,
    FirmName,
    client_names,
    client_with_entity,
    create_client,
    find_clients,
    firm_names,
)

ClientRole = Literal["client_admin", "client_contributor"]
# F-03-T12 (migration 0069): the 14 engagement types, defined by methodology since K-01-T02.


class TemplateTypeMismatch(DomainConflict):
    """The template doesn't serve this engagement's type (SPEC-024 AC-6)."""

    code = "template_type_mismatch"


@dataclass(frozen=True)
class EngagementRef:
    """Enough to authorise an action on an engagement. `archived` comes from the row
    (AUTHZ-003)."""

    tenant_id: UUID
    id: UUID
    archived: bool
    client_entity_id: UUID
    # The client, for ethical walls (SPEC-002): carried on the resource, so `authorise` needn't
    # look it up.
    client_id: UUID
    # The pinned methodology version (SPEC-008), None until applied.
    methodology_version_id: UUID | None = None

    def resource(self) -> Resource:
        return Resource.engagement(
            self.tenant_id, self.id, archived=self.archived, client_id=self.client_id
        )


@dataclass(frozen=True)
class NewEngagement:
    name: str
    client_name: str
    client_entity_name: str
    fiscal_period_start: date
    fiscal_period_end: date
    type: EngagementType = "fs_audit"
    # SPEC-025 AC-1: an existing client (and entity, or a new entity under it); else a new client.
    client_id: UUID | None = None
    client_entity_id: UUID | None = None
    # A new client whose name matches an existing one needs this (`PossibleDuplicate`).
    confirm_new: bool = False
    # SPEC-025 AC-2 (TASK-048): created from a confirmed roll-forward proposal.
    roll_forward: RollForward | None = None


@dataclass(frozen=True)
class EngagementView:
    """What routes may see of an engagement: plain data, never the ORM row (ADR-012)."""

    id: UUID
    name: str
    type: str
    status: str
    client_name: str
    client_entity_name: str
    fiscal_period_start: date
    fiscal_period_end: date
    created_at: datetime
    client_id: UUID  # SPEC-303 (TASK-304)
    client_entity_id: UUID
    service_line: str  # F-03-T12


def _view(engagement: Engagement, names: ClientNames) -> EngagementView:
    return EngagementView(
        id=engagement.id,
        name=engagement.name,
        type=engagement.type,
        status=engagement.status,
        client_name=names.client_name,
        client_entity_name=names.client_entity_name,
        fiscal_period_start=engagement.fiscal_period_start,
        fiscal_period_end=engagement.fiscal_period_end,
        created_at=engagement.created_at,
        client_id=names.client_id,
        client_entity_id=engagement.client_entity_id,
        service_line=engagement.service_line,
    )


@dataclass(frozen=True)
class EngagementMetadata:
    engagement: EngagementView
    team: list[TeamMember]


def _ref(engagement: Engagement) -> EngagementRef:
    return EngagementRef(
        engagement.tenant_id,
        engagement.id,
        engagement.status == "archived",
        engagement.client_entity_id,
        engagement.client_id,
        engagement.methodology_version_id,
    )


async def get_ref(ctx: Actor, engagement_id: UUID) -> EngagementRef:
    """Raises `NotFound` when the engagement doesn't exist in the active tenant."""
    async with tenant_session(ctx.tenant) as session:
        engagement = await get_engagement(session, engagement_id)
    if engagement is None:
        raise NotFound("engagement")
    return _ref(engagement)


async def engagement_resource_of(tenant: TenantContext, engagement_id: UUID) -> Resource:
    """The engagement as an authorisation resource (F-03-T30), or `NotFound`."""
    async with tenant_session(tenant) as session:
        engagement = await get_engagement(session, engagement_id)
    if engagement is None:
        raise NotFound("engagement")
    return _ref(engagement).resource()


async def lock_ref(tx: UnitOfWork, engagement_id: UUID) -> EngagementRef:
    """For writes: resolve and share-lock the engagement inside the caller's unit of work, then
    authorise against it there, so the check and the write see the same row. `NotFound` (404)
    when it isn't in the active tenant."""
    engagement = await lock_engagement(tx.session, engagement_id)
    if engagement is None:
        raise NotFound("engagement")
    return _ref(engagement)


class PossibleDuplicate(DomainConflict):
    """A client with this name (normalised) already exists: pick it, or confirm a new one."""

    code = "possible_duplicate"


async def create_engagement(ctx: AuthContext, new: NewEngagement) -> EngagementMetadata:
    from abacus.modules.engagements.roll_forward import (  # roll_forward imports this module
        apply_roll_forward,
        check_prior,
    )

    await authorise(ctx, "engagement.create", Resource.firm(ctx.tenant_id))
    engagement_id = uuid4()
    roll = new.roll_forward
    if roll is not None:
        if new.client_id is None or new.client_entity_id is None:
            raise DomainInvalid("a roll-forward is for an existing client entity")
        await check_prior(ctx, roll, new.client_entity_id, new.type)
    if new.client_id is not None and await hidden_clients(
        ctx.tenant, ctx.user_id, [new.client_id]
    ):
        # Refused before anything is written; `authorise` below is the authoritative check.
        raise Forbidden("engagement.create", "wall")
    if new.client_id is None and not new.confirm_new:
        found = await find_clients(ctx.tenant, new.client_name, exact=True)
        walled = await hidden_clients(ctx.tenant, ctx.user_id, [c.id for c in found])
        matches = [c for c in found if c.id not in walled]
        if matches:
            raise PossibleDuplicate(new.client_name)
    async with uow(ctx.tenant) as tx:
        if new.client_id is not None:
            client = await client_with_entity(
                tx, ctx.tenant_id, new.client_id, new.client_entity_id, new.client_entity_name
            )
        else:
            client = await create_client(
                tx, ctx.tenant_id, new.client_name, new.client_entity_name
            )
        await insert_engagement(
            tx.session,
            engagement_id=engagement_id,
            tenant_id=ctx.tenant_id,
            client_id=client.client_id,
            client_entity_id=client.client_entity_id,
            name=new.name,
            fiscal_period_start=new.fiscal_period_start,
            fiscal_period_end=new.fiscal_period_end,
            created_by=ctx.user_id,
            type=new.type,
            prior_engagement_id=roll.prior_engagement_id if roll is not None else None,
        )
        if new.client_id is not None:
            # SPEC-025 AC-1: an existing client. The engagement just written is checked against
            # the creator's walls (ADR-026); a walled creator is refused and nothing is kept.
            ref = await lock_ref(tx, engagement_id)
            await authorise(ctx, "engagement.create", ref.resource())
        tx.record("engagement.created", target=Target("engagement", engagement_id))
        await add_creator_as_partner(tx, ctx, engagement_id, client.client_id)
        if roll is not None:
            await apply_roll_forward(tx, ctx, engagement_id, client.client_id, roll)
        tx.emit(EngagementCreated(engagement_id=engagement_id))
    return await _metadata(ctx, engagement_id)


async def self_join(ctx: AuthContext, engagement_id: UUID) -> EngagementMetadata:
    """ADR-024: a firm admin joins an engagement to see its content (as reviewer); the team is
    notified (SPEC-013 AC-8). Walls apply through `authorise`."""
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "engagement.self_join", ref.resource())
        await add_self_joined_admin(tx, ctx, engagement_id, ref.client_id)
    return await _metadata(ctx, engagement_id)


async def engagement_metadata(ctx: AuthContext, engagement_id: UUID) -> EngagementMetadata:
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "engagement.read_metadata", ref.resource())
    return await _metadata(ctx, engagement_id)


async def _metadata(ctx: AuthContext, engagement_id: UUID) -> EngagementMetadata:
    async with tenant_session(ctx.tenant) as session:
        engagement = await get_engagement(session, engagement_id)
        if engagement is None:
            raise NotFound("engagement")
        names = await client_names(session, [engagement.client_entity_id])
        view = _view(engagement, names[engagement.client_entity_id])
    team = await engagement_team(ctx, engagement_id)
    return EngagementMetadata(view, team)


async def engagements_for(ctx: AuthContext) -> Sequence[EngagementView]:
    async with tenant_session(ctx.tenant) as session:
        engagements = await list_engagements(session, ctx)
        names = await client_names(session, [e.client_entity_id for e in engagements])
        return [_view(e, names[e.client_entity_id]) for e in engagements]


def client_subquery(
    engagement_id: ColumnElement[UUID] | QueryableAttribute[UUID],
) -> ColumnElement[UUID]:
    """The engagement's client, as a subquery per row (for walls in `visible()`)."""
    return _client_column(engagement_id)


def clients_of_engagements(
    admits: Callable[[ColumnElement[UUID] | QueryableAttribute[UUID]], ColumnElement[bool]],
) -> Select[UUID]:
    """The clients of the engagements `admits` lets through (the `client` scope kind, ADR-145)."""
    return select(Engagement.client_id).where(admits(Engagement.id))


def engagements_of_scope(kind: str, scope_ids: Select[tuple[UUID]]) -> Select[UUID]:
    """The engagements of the clients (`client`) or client entities (`client_entity`) a subquery
    names: what a client-wide grant covers (DEC-129, DEC-211)."""
    column = Engagement.client_entity_id if kind == "client_entity" else Engagement.client_id
    return select(Engagement.id).where(column.in_(scope_ids))


async def client_of(tenant: TenantContext, engagement_id: UUID) -> UUID | None:
    """The engagement's client, or None outside the tenant (for walls in `authorise`)."""
    async with tenant_session(tenant) as session:
        engagement = await get_engagement(session, engagement_id)
    return engagement.client_id if engagement is not None else None


# SPEC-027 (TASK-050; ADR-106): the platform's rule-based retrieval, registered by connections
# (a leaf: nothing imports it) so the engagement agent can start it and record why it did or
# didn't run. Unregistered, nothing is retrieved ("unavailable").
AutoRetrieve = Callable[[UUID, UUID, UUID | None], Awaitable[str]]
_auto_retrieve: AutoRetrieve | None = None


def register_auto_retrieval(run: AutoRetrieve) -> None:
    global _auto_retrieve
    if _auto_retrieve is not None and _auto_retrieve is not run:
        raise RuntimeError("automatic retrieval is already registered")
    _auto_retrieve = run


async def run_auto_retrieval(tenant_id: UUID, engagement_id: UUID, only: UUID | None) -> str:
    if _auto_retrieve is None:
        return "unavailable"
    return await _auto_retrieve(tenant_id, engagement_id, only)


async def open_engagements(tenant: TenantContext) -> list[UUID]:
    """SPEC-027 (TASK-050): the firm's non-archived engagements (the agents to resume)."""
    async with tenant_session(tenant) as session:
        return list(await open_engagement_ids(session))


async def all_engagement_ids(tenant: TenantContext) -> list[UUID]:
    """Q-02-T47: every engagement of the firm, archived ones included, oldest first, ids only. The
    firm export's candidates; the caller authorises each one as its acting person before reading
    anything of it."""
    async with tenant_session(tenant) as session:
        found = await session.execute(
            select(Engagement.id).order_by(Engagement.created_at, Engagement.id)
        )
        return list(found.scalars().all())


async def is_archived(tenant: TenantContext, engagement_id: UUID) -> bool | None:
    """SPEC-027 (TASK-050): whether the engagement is archived, or None outside the tenant (the
    engagement agent ends with it)."""
    async with tenant_session(tenant) as session:
        engagement = await get_engagement(session, engagement_id)
    return engagement.status == "archived" if engagement is not None else None


async def engagements_of_entity(tenant: TenantContext, client_entity_id: UUID) -> list[UUID]:
    """A-02-T16 (POR-16): the entity's engagements, newest first, as the candidates an
    entity-scoped action authorises on, one by one (`connection.read` and the others are
    authorised on an engagement, never firm-wide: DEC-316)."""
    async with tenant_session(tenant) as session:
        return list(await entity_engagement_ids(session, client_entity_id))


async def entity_of(tenant: TenantContext, engagement_id: UUID) -> UUID | None:
    """The engagement's client entity, or None outside the tenant (SPEC-022: whose connection
    serves it, for the platform's automatic retrievals)."""
    async with tenant_session(tenant) as session:
        engagement = await get_engagement(session, engagement_id)
    return engagement.client_entity_id if engagement is not None else None


# --- Methodology (SPEC-008; the templates are the methodology module's since K-01-T02) ---------


class MethodologyAlreadyApplied(DomainConflict):
    """An engagement is pinned to one methodology version, once (SPEC-008 Q4)."""

    code = "methodology_already_applied"


async def pin_methodology(
    tx: UnitOfWork, engagement_id: UUID, version_id: UUID
) -> MethodologyVersionView:
    """Inside the caller's unit of work, after `lock_ref` and its `authorise`: pin the version
    (`MethodologyAlreadyApplied` if one is pinned) and return its rows."""
    detail = await version_in(tx.session, version_id)
    engagement = await lock_engagement(tx.session, engagement_id)
    if engagement is not None and engagement.type not in detail.summary.engagement_types:
        raise TemplateTypeMismatch(engagement.type)
    if not await set_methodology_version(tx.session, engagement_id, version_id):
        raise MethodologyAlreadyApplied(str(engagement_id))
    return detail


def active_engagements() -> Select[UUID]:
    """The firm's non-archived engagements, as a subquery for identity (SPEC-014)."""
    return select(Engagement.id).where(Engagement.status != "archived")


# --- Client contacts (SPEC-015) ----------------------------------------------------------------


async def invite_client(
    ctx: AuthContext, engagement_id: UUID, email: str, role: ClientRole
) -> UUID:
    await gate_client_data(ctx, engagement_id, "client_contact.invite")
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        if ref.archived:
            # ED-008 (SPEC-015 AC-3): someone who may see the engagement's contacts hears that it
            # is archived (409); anyone else is refused as before, so nothing leaks.
            from abacus.modules.engagements.record import EngagementArchived  # record imports us

            await authorise(ctx, "client_contact.read", ref.resource())
            raise EngagementArchived
        await authorise(ctx, "client_contact.invite", ref.resource())
        return await create_invitation(tx, ctx, engagement_id, email, role)


async def client_contacts_of(ctx: AuthContext, engagement_id: UUID) -> list[ContactView]:
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "client_contact.read", ref.resource())
    return await contacts(ctx, engagement_id)


async def revoke_client_invitation(
    ctx: AuthContext, engagement_id: UUID, invitation_id: UUID
) -> None:
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "client_contact.invite", ref.resource())
        await revoke_invitation(tx, ctx, engagement_id, invitation_id)


async def resend_client_invitation(
    ctx: AuthContext, engagement_id: UUID, invitation_id: UUID
) -> None:
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "client_contact.invite", ref.resource())
        await resend_invitation(tx, ctx, engagement_id, invitation_id)


async def remove_client_contact(ctx: AuthContext, engagement_id: UUID, user_id: UUID) -> None:
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "client_contact.remove", ref.resource())
        await remove_client(tx, ctx, engagement_id, user_id)


# --- Engagement team (SPEC-017) -----------------------------------------------------------------


async def team_of_engagement(ctx: AuthContext, engagement_id: UUID) -> list[TeamMember]:
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "engagement.read_metadata", ref.resource())
    return await engagement_team(ctx, engagement_id)


async def team_candidates(ctx: AuthContext, engagement_id: UUID) -> list[Candidate]:
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "engagement.member_add", ref.resource())
    return await candidates(ctx.tenant, engagement_id, ref.client_id)


class _Keep:
    """`change_team_role`'s "leave the hours as they are"."""


KEEP_HOURS: Final = _Keep()


async def add_to_team(
    ctx: AuthContext,
    engagement_id: UUID,
    user_id: UUID,
    role: StaffRole,
    budget_hours: Decimal | None = None,
) -> None:
    """The EQR takes no team role (409 `eqr_on_team`, DEC-327; ED-053)."""
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "engagement.member_add", ref.resource())
        if await team_standing(ctx.tenant, engagement_id, user_id) == "eqr":
            raise EqrOnTeam(facts={"user_id": str(user_id)})
        await add_member(tx, ctx, engagement_id, ref.client_id, user_id, role)
        if budget_hours is not None:  # P-07-T30: ENG-05's hours
            await set_member_hours(tx, engagement_id, user_id, budget_hours)
        # P-07-T47: a changed team waits for the engagement partner's approval (ENG-05).
        tx.emit(
            TeamChangeProposed(engagement_id=engagement_id, user_id=user_id, by_user=ctx.user_id)
        )


async def change_team_role(
    ctx: AuthContext,
    engagement_id: UUID,
    user_id: UUID,
    role: StaffRole | None,
    budget_hours: Decimal | _Keep | None = KEEP_HOURS,
) -> None:
    """A role change, an hours change, or both. The EQR is never given a team role (409
    `eqr_on_team`, P-07-T30): replace them through `POST …/eqr` instead."""
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "engagement.member_add", ref.resource())
        if await team_standing(ctx.tenant, engagement_id, user_id) == "eqr":
            raise EqrOnTeam(facts={"user_id": str(user_id)})
        if role is not None:
            await change_role(tx, ctx, engagement_id, user_id, role)
            tx.emit(
                TeamChangeProposed(
                    engagement_id=engagement_id, user_id=user_id, by_user=ctx.user_id
                )
            )
        if not isinstance(budget_hours, _Keep):
            await set_member_hours(tx, engagement_id, user_id, budget_hours)


async def remove_from_team(ctx: AuthContext, engagement_id: UUID, user_id: UUID) -> None:
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "engagement.member_remove", ref.resource())
        await remove_member(tx, ctx, engagement_id, user_id)


async def firm_clients(ctx: AuthContext) -> list[FirmName]:
    """SPEC-019 Q4: the firm's clients (entities left out), for the wall picker, minus any the
    person is walled from (G-01-T09 review: partners hold `wall.create` now; DEC-43). Offshore
    hides no client (TASK-1207, DEC-319)."""
    await authorise(ctx, "wall.create", Resource.firm(ctx.tenant_id))
    names = [n for n in await firm_names(ctx.tenant) if n.id == n.client_id]
    hidden = await hidden_clients(ctx.tenant, ctx.user_id, [n.client_id for n in names])
    return sorted((n for n in names if n.client_id not in hidden), key=lambda n: n.name.casefold())


# --- Clients you already have (SPEC-025 AC-1; TASK-043) ----------------------------------------


async def search_clients(ctx: AuthContext, text_: str) -> list[ClientChoice]:
    """The firm's clients matching a name, minus any the person is walled off from (offshore
    hides none: TASK-1207, DEC-319)."""
    await authorise(ctx, "client.read", Resource.firm(ctx.tenant_id))
    found = await find_clients(ctx.tenant, text_)
    hidden = await hidden_clients(ctx.tenant, ctx.user_id, [c.id for c in found])
    return [c for c in found if c.id not in hidden]


@dataclass(frozen=True)
class EngagementLabel:
    name: str
    client_name: str
    fiscal_year: int


async def engagement_label(tenant: TenantContext, engagement_id: UUID) -> EngagementLabel | None:
    """What goes out in the firm's name about an engagement (SPEC-025 AC-8: invitations)."""
    async with tenant_session(tenant) as session:
        engagement = await get_engagement(session, engagement_id)
        if engagement is None:
            return None
        names = await client_names(session, [engagement.client_entity_id])
    found = names.get(engagement.client_entity_id)
    return EngagementLabel(
        engagement.name,
        found.client_name if found is not None else "your company",
        engagement.fiscal_period_end.year,
    )


@dataclass(frozen=True)
class CheckFacts:
    """What upload checks compare a document with (SPEC-029; TASK-055)."""

    fiscal_period_end: date
    client_entity_name: str
    methodology_version_id: UUID | None


async def check_facts(tenant: TenantContext, engagement_id: UUID) -> CheckFacts | None:
    """For a caller acting as the system on the engagement's own uploads (None outside the
    tenant)."""
    async with tenant_session(tenant) as session:
        engagement = await get_engagement(session, engagement_id)
        if engagement is None:
            return None
        names = await client_names(session, [engagement.client_entity_id])
    found = names.get(engagement.client_entity_id)
    return CheckFacts(
        engagement.fiscal_period_end,
        found.client_entity_name if found is not None else "",
        engagement.methodology_version_id,
    )


async def gate_client_data(ctx: AuthContext, engagement_id: UUID, action: str) -> None:
    """SPEC-025 AC-7: client-data actions wait until the engagement is open (audited refusal)."""
    from abacus.modules.engagements.setup import (  # setup imports this module
        EngagementNotOpen,
        require_open,
    )

    await get_ref(ctx, engagement_id)  # an unknown or another firm's engagement is 404, not 409
    try:
        await require_open(ctx.tenant, engagement_id)
    except EngagementNotOpen:
        async with uow(ctx.tenant) as tx:
            tx.record("client_data.gate_refused", target=Target("engagement", engagement_id))
        get_logger(__name__).info(
            "client_data.gate_refused", engagement_id=str(engagement_id), action=action
        )
        raise


# --- AI exclusion (SPEC-036 §4.6; TASK-076) -----------------------------------------------------


@dataclass(frozen=True)
class AiExclusion:
    excluded_at: datetime | None
    excluded_by: UUID | None
    reason: str | None


async def ai_excluded(tenant: TenantContext, engagement_id: UUID) -> bool:
    """For the gateway (SPEC-036 §4.2 `engagement`): whether AI is off for this engagement."""
    async with tenant_session(tenant) as session:
        found = await get_engagement(session, engagement_id)
    return found is not None and found.ai_excluded_at is not None


async def ai_exclusion(ctx: AuthContext, engagement_id: UUID) -> AiExclusion:
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "engagement.read_metadata", ref.resource())
    async with tenant_session(ctx.tenant) as session:
        found = await get_engagement(session, engagement_id)
    if found is None:
        raise NotFound("engagement")
    return AiExclusion(found.ai_excluded_at, found.ai_excluded_by, found.ai_excluded_reason)


async def set_ai_exclusion_of(
    ctx: AuthContext, engagement_id: UUID, excluded: bool, reason: str | None
) -> AiExclusion:
    """AC-6: the engagement partner switches AI off (with a reason) or on again. The firm's
    cached boundary facts are dropped in this request."""
    reason = (reason or "").strip() or None
    if excluded and reason is None:
        raise AiExclusionReasonRequired(str(engagement_id))
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "engagement.ai_exclude", ref.resource())
        await set_ai_exclusion(
            tx.session,
            engagement_id,
            ctx.user_id if excluded else None,
            reason if excluded else None,
        )
        tx.record(
            "engagement.ai_excluded" if excluded else "engagement.ai_included",
            target=Target("engagement", engagement_id),
        )
        tx.emit(BoundaryFactsChanged())  # Q-02-T08: the worker forgets them too
    forget_boundary_facts(ctx.tenant_id)
    return await ai_exclusion(ctx, engagement_id)


class AiExclusionReasonRequired(DomainInvalid):
    """Switching AI off for an engagement needs a reason (SPEC-036 §4.6)."""

    code = "ai_exclusion_reason_required"
