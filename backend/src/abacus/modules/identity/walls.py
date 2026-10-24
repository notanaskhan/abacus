"""Ethical walls v2 (G-01-T09; SPEC-002 as amended by DEC-169; ADR-026; DEC-43, DEC-73, DEC-318).

A wall shuts one person out of one client, firm-wide, the moment it is created (DEC-73), and is
enforced in `authorise` and `visible()` (404 everywhere, no count; INV-3). v2 adds why (a reason
code and text), who approves (a named partner, never the walled person), the partner's own
approval with fresh MFA (INV-5: nobody records it for them), the lift by a partner with a reason,
the preview of blockers and effects, and the `wall.created` consumer that ends the walled
person's assignments on the client. Every change is audited and tells the walled person's
sessions and caches their access changed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import func, insert, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainForbidden, DomainInvalid, NotFound
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import AuditRow, OutboxEvent, Ref, Target, uow
from abacus.modules.identity.authz import (
    Forbidden,
    Resource,
    allowed_actions,
    authorise,
    engagement_client,
)
from abacus.modules.identity.context import AuthContext
from abacus.modules.identity.events import AccessChanged, WallApproved, WallCreated, WallRemoved
from abacus.modules.identity.repository import ethical_walls, walled_clients
from abacus.modules.identity.slots import (
    client_partner,
    end_wall_assignments,
    target_events,
    wall_assignment_count,
)
from abacus.modules.identity.team import remove_walled_member

WallReason = Literal[
    "personal_relationship", "financial_interest", "relative", "prior_employment", "other"
]
REASONS: Final[tuple[WallReason, ...]] = (
    "personal_relationship",
    "financial_interest",
    "relative",
    "prior_employment",
    "other",
)
WALL_TARGET: Final = "ethical_wall"
# Who sees every wall of the firm in the register (SPEC-002's wall administrators); a partner
# who may list walls doesn't see walls on themself or on a client they are walled from.
_REGISTER_ROLES: Final = frozenset({"firm_admin", "security_admin"})
_UNIQUE_VIOLATION: Final = "23505"
_FOREIGN_KEY_VIOLATION: Final = "23503"
_log = get_logger(__name__)


class WallExists(DomainConflict):
    """The person is already walled off from this client."""

    code = "wall_exists"


class OwnWall(DomainConflict):
    """A partner can't lift a wall on themself: another partner must (ADR-026; DEC-73)."""

    code = "own_wall"


class RelationshipPartner(DomainConflict):
    """The person leads the client's relationship: reassign it first (AC8.3)."""

    code = "relationship_partner"


class AlreadyApproved(DomainConflict):
    code = "already_approved"


class ApproverNotPartner(DomainInvalid):
    """The named approver must be an active partner-level member other than the walled person."""

    code = "approver_not_partner"


class NotNamedApprover(DomainForbidden):
    """Only the partner the wall names may approve it (AC8.2; INV-5)."""

    code = "not_named_approver"


@dataclass(frozen=True)
class WallView:
    id: UUID
    user_id: UUID
    client_id: UUID
    status: str
    created_by: UUID
    created_at: datetime
    removed_by: UUID | None
    removed_at: datetime | None
    reason_code: WallReason
    reason_text: str | None
    approver_user_id: UUID | None
    approved_by: UUID | None
    approved_at: datetime | None
    removed_reason: str | None

    @property
    def approval_status(self) -> Literal["awaiting", "approved"]:
        return "approved" if self.approved_at is not None else "awaiting"


@dataclass(frozen=True)
class WallPreview:
    blockers: list[str]
    assignments_ended: int


@dataclass(frozen=True)
class WallEvent:
    event_type: str
    at: datetime
    actor_user_id: UUID | None


def _view(m: object) -> WallView:
    row = cast(dict[str, object], m)
    return WallView(
        cast(UUID, row["id"]),
        cast(UUID, row["user_id"]),
        cast(UUID, row["client_id"]),
        cast(str, row["status"]),
        cast(UUID, row["created_by"]),
        cast(datetime, row["created_at"]),
        cast(UUID | None, row["removed_by"]),
        cast(datetime | None, row["removed_at"]),
        cast(WallReason, row["reason_code"]),
        cast(str | None, row["reason_text"]),
        cast(UUID | None, row["approver_user_id"]),
        cast(UUID | None, row["approved_by"]),
        cast(datetime | None, row["approved_at"]),
        cast(str | None, row["removed_reason"]),
    )


def _human(ctx: AuthContext, action: str) -> None:
    """INV-1 behind the matrix: only a signed-in person of the firm administers walls."""
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(action, "role")


def _sqlstate(exc: IntegrityError) -> str | None:
    state = getattr(exc.orig, "sqlstate", None)
    return state if isinstance(state, str) else None


async def _get(session: AsyncSession, wall_id: UUID) -> WallView | None:
    row = (
        (await session.execute(select(ethical_walls).where(ethical_walls.c.id == wall_id)))
        .mappings()
        .one_or_none()
    )
    return _view(dict(row)) if row is not None else None


async def _hidden(ctx: AuthContext, walls: list[WallView]) -> set[UUID]:
    """Walls a reader outside the register roles must not learn of: on themself, or on a client
    they are walled from (the audit explorer's rule, `audit_hidden_walls`)."""
    if ctx.firm_role in _REGISTER_ROLES:
        return set()
    walled = await walled_clients(ctx.tenant, ctx.user_id)
    return {w.id for w in walls if w.user_id == ctx.user_id or w.client_id in walled}


async def _partner(session: AsyncSession, user_id: UUID) -> bool:
    found = await session.scalar(
        text(
            "SELECT 1 FROM memberships WHERE user_id = :u AND kind = 'staff' "
            "AND status = 'active' AND level = 'partner'"
        ),
        {"u": user_id},
    )
    return found is not None


async def _staff(session: AsyncSession, user_id: UUID) -> bool:
    found = await session.scalar(
        text(
            "SELECT 1 FROM memberships WHERE user_id = :u AND kind = 'staff' AND status = 'active'"
        ),
        {"u": user_id},
    )
    return found is not None


async def _engagements_on(
    session: AsyncSession, tenant: TenantContext, user_id: UUID, client_id: UUID
) -> list[UUID]:
    """The person's staff engagement memberships on the client's engagements."""
    rows = await session.execute(
        text(
            "SELECT engagement_id FROM engagement_members WHERE user_id = :u AND role IN "
            "('engagement_partner', 'manager', 'senior', 'staff', 'reviewer') "
            "ORDER BY engagement_id"
        ),
        {"u": user_id},
    )
    return [e for e in rows.scalars() if await engagement_client(tenant, e) == client_id]


# --- create, preview -----------------------------------------------------------------------------


async def _client_partner_or_404(ctx: AuthContext, client_id: UUID) -> UUID | None:
    partner = await client_partner(ctx.tenant, client_id)
    if partner is False or partner is True:
        raise NotFound("client")
    return partner


async def preview(ctx: AuthContext, *, user_id: UUID, client_id: UUID) -> WallPreview:
    """AC8.1, AC8.3: what POST would refuse, and how many current assignments it would end. A
    client the caller can't see (walled, offshore) or doesn't exist answers 404 (DEC-43)."""
    await authorise(ctx, "wall.create", Resource.client(ctx.tenant_id, client_id))
    partner = await _client_partner_or_404(ctx, client_id)
    async with tenant_session(ctx.tenant) as session:
        if not await _staff(session, user_id):
            raise NotFound("staff_member")
        blockers: list[str] = []
        if partner == user_id:
            blockers.append("relationship_partner")
        active = await session.scalar(
            select(ethical_walls.c.id).where(
                ethical_walls.c.user_id == user_id,
                ethical_walls.c.client_id == client_id,
                ethical_walls.c.status == "active",
            )
        )
        if active is not None:
            blockers.append("wall_exists")
        memberships = len(await _engagements_on(session, ctx.tenant, user_id, client_id))
    assignments = await wall_assignment_count(ctx.tenant, user_id, client_id)
    return WallPreview(blockers, memberships + assignments)


async def create_wall(
    ctx: AuthContext,
    *,
    user_id: UUID,
    client_id: UUID,
    reason_code: WallReason = "other",
    reason_text: str | None = None,
    approver_user_id: UUID | None = None,
) -> WallView:
    """Active at once (DEC-73), from the person's next request, everywhere on the client.
    409 `relationship_partner`, `wall_exists`; 422 `approver_not_partner`. Firm admin or partner,
    fresh MFA."""
    await authorise(ctx, "wall.create", Resource.client(ctx.tenant_id, client_id))
    _human(ctx, "wall.create")
    partner = await _client_partner_or_404(ctx, client_id)
    if partner == user_id:
        raise RelationshipPartner(facts={"client_id": str(client_id)})
    wall_id = uuid4()
    try:
        async with uow(ctx.tenant) as tx:
            if approver_user_id is not None and (
                approver_user_id == user_id or not await _partner(tx.session, approver_user_id)
            ):
                raise ApproverNotPartner(facts={"field": "approver_user_id"})
            await tx.session.execute(
                insert(ethical_walls).values(
                    id=wall_id,
                    tenant_id=ctx.tenant_id,
                    user_id=user_id,
                    client_id=client_id,
                    created_by=ctx.user_id,
                    reason_code=reason_code,
                    reason_text=reason_text,
                    approver_user_id=approver_user_id,
                )
            )
            refs: dict[str, UUID | int] = {
                "user_id": user_id,
                "client_id": client_id,
                "reason": REASONS.index(reason_code) + 1,
            }
            if approver_user_id is not None:
                refs["approver_user_id"] = approver_user_id
            tx.record("wall.created", target=Target(WALL_TARGET, wall_id), after=Ref(**refs))
            tx.emit(
                WallCreated(
                    wall_id=wall_id,
                    user_id=user_id,
                    client_id=client_id,
                    created_by=ctx.user_id,
                    approver_user_id=approver_user_id,
                )
            )
            tx.emit(AccessChanged(user_id=user_id))
            wall = await _get(tx.session, wall_id)
    except IntegrityError as exc:
        state = _sqlstate(exc)
        if state == _UNIQUE_VIOLATION:
            raise WallExists from None
        if state == _FOREIGN_KEY_VIOLATION:
            raise NotFound("member or client") from None  # not in this firm
        raise
    if wall is None:  # just written in this tenant
        raise RuntimeError("ethical wall vanished after insert")
    return wall


# --- approve, lift -------------------------------------------------------------------------------


async def _visible_wall(ctx: AuthContext, session: AsyncSession, wall_id: UUID) -> WallView:
    wall = await _get(session, wall_id)
    if wall is None or wall.id in await _hidden(ctx, [wall]):
        raise NotFound("ethical wall")
    return wall


async def approve_wall(ctx: AuthContext, wall_id: UUID) -> WallView:
    """AC8.2: the named partner's own approval, once, with fresh MFA; it changes no access."""
    await authorise(ctx, "wall.approve", Resource.firm(ctx.tenant_id))
    _human(ctx, "wall.approve")
    async with uow(ctx.tenant) as tx:
        wall = await _visible_wall(ctx, tx.session, wall_id)
        if wall.status != "active":
            raise NotFound("ethical wall")
        if wall.approver_user_id != ctx.user_id:
            raise NotNamedApprover
        if wall.approved_at is not None:
            raise AlreadyApproved
        done = await tx.session.execute(
            update(ethical_walls)
            .where(
                ethical_walls.c.id == wall_id,
                ethical_walls.c.status == "active",
                ethical_walls.c.approved_at.is_(None),
            )
            .values(approved_by=ctx.user_id, approved_at=func.clock_timestamp())
            .returning(ethical_walls.c.id)
        )
        if done.scalar_one_or_none() is None:
            raise AlreadyApproved
        tx.record(
            "wall.approved",
            target=Target(WALL_TARGET, wall_id),
            after=Ref(user_id=wall.user_id, client_id=wall.client_id),
        )
        tx.emit(WallApproved(wall_id=wall_id, created_by=wall.created_by, approved_by=ctx.user_id))
        approved = await _get(tx.session, wall_id)
    if approved is None:
        raise NotFound("ethical wall")
    return approved


async def remove_wall(ctx: AuthContext, wall_id: UUID, reason: str | None = None) -> WallView:
    """AC8.4: a partner lifts a wall with fresh MFA (DEC-73), never their own (409 `own_wall`);
    the record stays, marked removed, with the reason."""
    await authorise(ctx, "wall.remove", Resource.firm(ctx.tenant_id))
    _human(ctx, "wall.remove")
    async with uow(ctx.tenant) as tx:
        wall = await _get(tx.session, wall_id)
        if wall is not None and wall.status == "active" and wall.user_id == ctx.user_id:
            raise OwnWall
        if wall is None or wall.status != "active" or wall.id in await _hidden(ctx, [wall]):
            raise NotFound("ethical wall")
        row = (
            (
                await tx.session.execute(
                    update(ethical_walls)
                    .where(ethical_walls.c.id == wall_id, ethical_walls.c.status == "active")
                    .values(
                        status="removed",
                        removed_by=ctx.user_id,
                        removed_at=func.clock_timestamp(),
                        removed_reason=reason,
                    )
                    .returning(*ethical_walls.c)
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise NotFound("ethical wall")
        tx.record(
            "wall.removed",
            target=Target(WALL_TARGET, wall_id),
            before=Ref(user_id=wall.user_id, client_id=wall.client_id),
        )
        tx.emit(WallRemoved(wall_id=wall_id, user_id=wall.user_id))
        tx.emit(AccessChanged(user_id=wall.user_id))
    return _view(dict(row))


# --- read ----------------------------------------------------------------------------------------


async def list_walls(ctx: AuthContext) -> list[WallView]:
    """The firm's walls, active and removed, newest first (fresh MFA). Firm and security admins
    see the whole register; a partner, the walls they may know of."""
    await authorise(ctx, "wall.list", Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        rows = await session.execute(
            select(ethical_walls).order_by(ethical_walls.c.created_at.desc(), ethical_walls.c.id)
        )
        walls = [_view(dict(r)) for r in rows.mappings().all()]
    hidden = await _hidden(ctx, walls)
    return [w for w in walls if w.id not in hidden]


async def wall_events(
    ctx: AuthContext, wall_id: UUID, before_seq: int | None, limit: int
) -> tuple[list[WallEvent], int | None, int]:
    """AC8.6: the wall's log, newest first, from the audit trail: a page, the cursor for the
    next one and the total. A wall's log is short (created, approved, lifted)."""
    await authorise(ctx, "wall.list", Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        await _visible_wall(ctx, session, wall_id)
    rows: list[AuditRow] = await target_events(ctx.tenant, WALL_TARGET, wall_id, None, _LOG_CAP)
    after = [r for r in rows if before_seq is None or r.seq < before_seq]
    page = after[:limit]
    events = [
        WallEvent(r.action, r.occurred_at, _uuid(r.actor_id) if r.actor_kind == "human" else None)
        for r in page
    ]
    return events, (page[-1].seq if len(after) > limit else None), len(rows)


_LOG_CAP: Final = 500


def _uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except ValueError:
        return None


async def wall_actions(ctx: AuthContext, wall: WallView) -> list[str]:
    """What the reader may do with this wall now (ADM-03e): approve when they are its named
    partner and it awaits them; lift when they are a partner and it isn't their own."""
    if wall.status != "active":
        return []
    held = await allowed_actions(
        ctx, Resource.firm(ctx.tenant_id), ("wall.approve", "wall.remove")
    )
    found: list[str] = []
    if (
        "wall.approve" in held
        and wall.approver_user_id == ctx.user_id
        and wall.approved_at is None
    ):
        found.append("wall.approve")
    if "wall.remove" in held and wall.user_id != ctx.user_id:
        found.append("wall.remove")
    return found


# --- the `wall.created` consumer (AC8.5) ---------------------------------------------------------


async def end_assignments_for_wall(event: OutboxEvent) -> None:
    """End the walled person's engagement memberships and work-item assignments on the client,
    as the system on behalf of the wall's creator: one audit row each. Idempotent (a re-run finds
    nothing left), and nothing ends for a wall lifted before this runs. Access is already denied
    by `authorise` before this runs."""
    payload = event.payload
    try:
        wall_id = UUID(str(payload["wall_id"]))
        user_id = UUID(str(payload["user_id"]))
        client_id = UUID(str(payload["client_id"]))
        creator = UUID(str(payload["created_by"]))
    except (KeyError, ValueError):
        _log.warning("wall.created_malformed", event_id=event.event_id)
        return
    system = TenantContext(event.tenant_id, "system", "identity:wall_created", creator)
    try:
        async with uow(system) as tx:
            wall = await _get(tx.session, wall_id)
            if wall is None or wall.status != "active":
                raise _NothingToEnd
            ended = 0
            for engagement_id in await _engagements_on(tx.session, system, user_id, client_id):
                if await remove_walled_member(tx, engagement_id, user_id, creator):
                    ended += 1
                else:
                    _log.info("wall.membership_kept", engagement_id=engagement_id, wall_id=wall_id)
            ended += await end_wall_assignments(tx, event.tenant_id, user_id, client_id, creator)
            if not ended:
                raise _NothingToEnd  # nothing written: roll back (no audit row to record)
            tx.emit(AccessChanged(user_id=user_id))
    except _NothingToEnd:
        return


class _NothingToEnd(Exception):
    pass
