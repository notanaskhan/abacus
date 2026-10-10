"""Engagement rules (TASK-008 design §3).

Authorise before any write: the route guard can hide a response but can't undo a commit.
"""

from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING, Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import ColumnElement, Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import QueryableAttribute

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.engagements.events import EngagementCreated
from abacus.modules.engagements.models import Engagement, MethodologyTemplate, MethodologyVersion
from abacus.modules.engagements.repository import (
    client_column as _client_column,
)
from abacus.modules.engagements.repository import (
    get_engagement,
    get_version,
    insert_engagement,
    insert_version,
    list_engagements,
    list_templates,
    lock_engagement,
    lock_or_insert_template,
    open_engagement_ids,
    set_methodology_version,
    version_rows,
)

if TYPE_CHECKING:
    from abacus.modules.engagements.roll_forward import RollForward
from abacus.modules.engagements.workbook import (
    AccountRule,
    Area,
    TemplateItem,
    Tier,
    parse_workbook,
)
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
    remove_client,
    remove_member,
    resend_invitation,
    revoke_invitation,
    walled_from,
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
# SPEC-024 Q5: the US engagement types under AICPA standards.
EngagementType = Literal["audit", "review", "compilation", "agreed_upon_procedures"]


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
    type: EngagementType = "audit"
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
    if new.client_id is not None and new.client_id in await walled_from(ctx.tenant, ctx.user_id):
        # Refused before anything is written; `authorise` below is the authoritative check.
        raise Forbidden("engagement.create", "wall")
    if new.client_id is None and not new.confirm_new:
        walled = await walled_from(ctx.tenant, ctx.user_id)
        matches = [
            c
            for c in await find_clients(ctx.tenant, new.client_name, exact=True)
            if c.id not in walled
        ]
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
        await add_creator_as_partner(tx, ctx, engagement_id)
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
        await add_self_joined_admin(tx, ctx, engagement_id)
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


async def is_archived(tenant: TenantContext, engagement_id: UUID) -> bool | None:
    """SPEC-027 (TASK-050): whether the engagement is archived, or None outside the tenant (the
    engagement agent ends with it)."""
    async with tenant_session(tenant) as session:
        engagement = await get_engagement(session, engagement_id)
    return engagement.status == "archived" if engagement is not None else None


async def entity_of(tenant: TenantContext, engagement_id: UUID) -> UUID | None:
    """The engagement's client entity, or None outside the tenant (SPEC-022: whose connection
    serves it, for the platform's automatic retrievals)."""
    async with tenant_session(tenant) as session:
        engagement = await get_engagement(session, engagement_id)
    return engagement.client_entity_id if engagement is not None else None


# --- Methodology templates (SPEC-008) ---------------------------------------------------------


class TemplateNameInvalid(DomainInvalid):
    """A template name is 1 to 100 characters."""

    code = "template_name_invalid"


class MethodologyAlreadyApplied(DomainConflict):
    """An engagement is pinned to one methodology version, once (SPEC-008 Q4)."""

    code = "methodology_already_applied"


@dataclass(frozen=True)
class TemplateVersionSummary:
    template_id: UUID
    template_name: str
    version_id: UUID
    version: int
    created_at: datetime
    engagement_types: tuple[str, ...] = ("audit",)


@dataclass(frozen=True)
class MethodologyVersionView:
    summary: TemplateVersionSummary
    areas: tuple[Area, ...]
    items: tuple[TemplateItem, ...]
    rules: tuple[AccountRule, ...]


def _summary(template: MethodologyTemplate, version: MethodologyVersion) -> TemplateVersionSummary:
    return TemplateVersionSummary(
        template.id,
        template.name,
        version.id,
        version.version,
        version.created_at,
        tuple(template.engagement_types),
    )


async def import_template(
    ctx: AuthContext,
    name: str,
    data: bytes,
    engagement_types: Sequence[EngagementType] = ("audit",),
) -> TemplateVersionSummary:
    """Parse and store the workbook as the template's next version (AC-1 to AC-3). Raises
    `TemplateInvalid` with every problem, storing nothing."""
    await authorise(ctx, "methodology.manage", Resource.firm(ctx.tenant_id))
    name = name.strip()
    if not 1 <= len(name) <= 100:
        raise TemplateNameInvalid(name)
    methodology = parse_workbook(data)
    fingerprint = hashlib.sha256(data).hexdigest()
    async with uow(ctx.tenant) as tx:
        template_id, _ = await lock_or_insert_template(
            tx.session,
            tenant_id=ctx.tenant_id,
            name=name,
            created_by=ctx.user_id,
            engagement_types=sorted(set(engagement_types)) or ["audit"],
        )
        version_id, number = await insert_version(
            tx.session,
            tenant_id=ctx.tenant_id,
            template_id=template_id,
            fingerprint=fingerprint,
            imported_by=ctx.user_id,
            methodology=methodology,
        )
        tx.record(
            "methodology.imported",
            target=Target("methodology_version", version_id),
            after=Ref(
                template_id=template_id,
                version=number,
                source_fingerprint=fingerprint,
                areas=len(methodology.areas),
                items=len(methodology.items),
                rules=len(methodology.rules),
            ),
        )
    found = await version_detail(ctx.tenant, version_id)
    return found.summary


async def methodology_templates(
    ctx: AuthContext, *, latest: bool = False
) -> list[TemplateVersionSummary]:
    await authorise(ctx, "methodology.read", Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        return [_summary(t, v) for t, v in await list_templates(session, latest=latest)]


async def methodology_version(ctx: AuthContext, version_id: UUID) -> MethodologyVersionView:
    await authorise(ctx, "methodology.read", Resource.firm(ctx.tenant_id))
    return await version_detail(ctx.tenant, version_id)


async def version_detail(tenant: TenantContext, version_id: UUID) -> MethodologyVersionView:
    """A version's rows for a caller that has authorised under its own context (`NotFound`
    outside the tenant)."""
    async with tenant_session(tenant) as session:
        return await _detail(session, version_id)


async def _detail(session: AsyncSession, version_id: UUID) -> MethodologyVersionView:
    found = await get_version(session, version_id)
    if found is None:
        raise NotFound("methodology_version")
    areas, items, rules = await version_rows(session, version_id)
    return MethodologyVersionView(
        _summary(*found),
        tuple(Area(a.code, a.name) for a in areas),
        tuple(
            TemplateItem(i.area_code, i.description, cast(Tier, i.retrievability_tier))
            for i in items
        ),
        tuple(AccountRule(r.area_code, r.account_from, r.account_to) for r in rules),
    )


async def pin_methodology(
    tx: UnitOfWork, engagement_id: UUID, version_id: UUID
) -> MethodologyVersionView:
    """Inside the caller's unit of work, after `lock_ref` and its `authorise`: pin the version
    (`MethodologyAlreadyApplied` if one is pinned) and return its rows."""
    detail = await _detail(tx.session, version_id)
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


async def add_to_team(
    ctx: AuthContext, engagement_id: UUID, user_id: UUID, role: StaffRole
) -> None:
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "engagement.member_add", ref.resource())
        await add_member(tx, ctx, engagement_id, ref.client_id, user_id, role)


async def change_team_role(
    ctx: AuthContext, engagement_id: UUID, user_id: UUID, role: StaffRole
) -> None:
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "engagement.member_add", ref.resource())
        await change_role(tx, ctx, engagement_id, user_id, role)


async def remove_from_team(ctx: AuthContext, engagement_id: UUID, user_id: UUID) -> None:
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "engagement.member_remove", ref.resource())
        await remove_member(tx, ctx, engagement_id, user_id)


async def firm_clients(ctx: AuthContext) -> list[FirmName]:
    """SPEC-019 Q4: the firm's clients (entities left out), for the wall picker."""
    await authorise(ctx, "wall.create", Resource.firm(ctx.tenant_id))
    names = await firm_names(ctx.tenant)
    return sorted((n for n in names if n.id == n.client_id), key=lambda n: n.name.casefold())


# --- Clients you already have (SPEC-025 AC-1; TASK-043) ----------------------------------------


async def search_clients(ctx: AuthContext, text_: str) -> list[ClientChoice]:
    """The firm's clients matching a name, minus any the person is walled off from."""
    await authorise(ctx, "client.read", Resource.firm(ctx.tenant_id))
    walled = await walled_from(ctx.tenant, ctx.user_id)
    return [c for c in await find_clients(ctx.tenant, text_) if c.id not in walled]


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


async def gate_client_data(ctx: AuthContext, engagement_id: UUID, action: str) -> None:
    """SPEC-025 AC-7: client-data actions wait until the engagement is open (audited refusal)."""
    from abacus.modules.engagements.setup import (  # setup imports this module
        EngagementNotOpen,
        require_open,
    )

    try:
        await require_open(ctx.tenant, engagement_id)
    except EngagementNotOpen:
        async with uow(ctx.tenant) as tx:
            tx.record("client_data.gate_refused", target=Target("engagement", engagement_id))
        get_logger(__name__).info(
            "client_data.gate_refused", engagement_id=str(engagement_id), action=action
        )
        raise
