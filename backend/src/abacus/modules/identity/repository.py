"""Identity data access. PROTECTED. TASK-007 design §2-3.

Two kinds of read:
- Before a tenant is chosen (sign-in): `abacus_identity`, which bypasses row-level security but
  reads only users and the membership and firm columns sign-in needs. Only this file uses it
  (UOW-002).
- Within a tenant: `tenant_session`, like everything else.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast, get_args
from uuid import UUID

from sqlalchemy import (
    Column,
    DateTime,
    MetaData,
    Select,
    String,
    Table,
    bindparam,
    func,
    insert,
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import TenantContext, identity_engine, tenant_session

FirmRole = Literal["firm_admin", "practice_leader", "quality_partner"]
EngagementRole = Literal["engagement_partner", "manager", "senior", "staff", "reviewer"]
# SPEC-015: client users' roles on an engagement (client memberships only, a database trigger).
ClientRole = Literal["client_admin", "client_contributor"]
ENGAGEMENT_ROLES: frozenset[str] = frozenset(get_args(EngagementRole))
CLIENT_ROLES: frozenset[str] = frozenset(get_args(ClientRole))

_metadata = MetaData()
# For `visible()` subqueries; the table is created by migration 0004.
engagement_members = Table(
    "engagement_members",
    _metadata,
    Column("tenant_id", PgUUID(as_uuid=True), nullable=False),
    Column("engagement_id", PgUUID(as_uuid=True), nullable=False),
    Column("user_id", PgUUID(as_uuid=True), nullable=False),
    Column("role", String, nullable=False),
)
# Ethical walls (migration 0012; SPEC-002): `authorise` and `visible()` read active ones.
ethical_walls = Table(
    "ethical_walls",
    _metadata,
    Column("id", PgUUID(as_uuid=True), primary_key=True),
    Column("tenant_id", PgUUID(as_uuid=True), nullable=False),
    Column("user_id", PgUUID(as_uuid=True), nullable=False),
    Column("client_id", PgUUID(as_uuid=True), nullable=False),
    Column("status", String, nullable=False),
    Column("created_by", PgUUID(as_uuid=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("removed_by", PgUUID(as_uuid=True), nullable=True),
    Column("removed_at", DateTime(timezone=True), nullable=True),
)


@dataclass(frozen=True)
class UserRecord:
    id: UUID
    email: str
    display_name: str


@dataclass(frozen=True)
class MembershipRecord:
    tenant_id: UUID
    membership_id: UUID
    firm_role: FirmRole | None
    firm_name: str
    kind: str = "staff"  # SPEC-015: staff | client


_USER = text(
    "SELECT id, email, display_name FROM users "
    "WHERE idp_issuer = :issuer AND idp_subject = :subject"
)
_ACTIVE_MEMBERSHIPS = text(
    "SELECT m.tenant_id, m.id, m.firm_role, f.name, m.kind FROM memberships m "
    "JOIN firms f ON f.tenant_id = m.tenant_id "
    "WHERE m.user_id = :user AND m.status = 'active' ORDER BY f.name, m.tenant_id"
)


async def find_user(issuer: str, subject: str) -> UserRecord | None:
    async with identity_engine().connect() as conn:
        row = (await conn.execute(_USER, {"issuer": issuer, "subject": subject})).first()
    if row is None:
        return None
    return UserRecord(cast(UUID, row.id), str(row.email), str(row.display_name))


async def active_memberships(user_id: UUID) -> list[MembershipRecord]:
    """Read fresh on every request, never cached: revocation applies to the next request (AC-3)."""
    async with identity_engine().connect() as conn:
        rows = (await conn.execute(_ACTIVE_MEMBERSHIPS, {"user": user_id})).all()
    return [
        MembershipRecord(
            cast(UUID, row.tenant_id),
            cast(UUID, row.id),
            cast(FirmRole | None, row.firm_role),
            str(row.name),
            str(row.kind),
        )
        for row in rows
    ]


async def engagement_role(
    tenant: TenantContext, user_id: UUID, engagement_id: UUID
) -> EngagementRole | ClientRole | None:
    async with tenant_session(tenant) as session:
        role = (
            await session.execute(
                select(engagement_members.c.role).where(
                    engagement_members.c.engagement_id == engagement_id,
                    engagement_members.c.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
    return cast(EngagementRole | ClientRole | None, role)


async def engagement_roles_in_firm(
    tenant: TenantContext, user_id: UUID, active: Select[UUID]
) -> frozenset[str]:
    """The distinct roles the user holds on the firm's active engagements (SPEC-014)."""
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            select(engagement_members.c.role)
            .where(
                engagement_members.c.user_id == user_id,
                engagement_members.c.engagement_id.in_(active.scalar_subquery()),
            )
            .distinct()
        )
        return frozenset(str(role) for role in rows.scalars().all())


_USER_NAMES = text("SELECT id, display_name FROM users WHERE id IN :ids").bindparams(
    bindparam("ids", expanding=True)
)


_USER_EMAILS = text("SELECT id, email FROM users WHERE id IN :ids").bindparams(
    bindparam("ids", expanding=True)
)


async def emails_of(user_ids: list[UUID]) -> dict[UUID, str]:
    """SPEC-027 (TASK-051): where a reminder goes, for users the caller already read under RLS."""
    if not user_ids:
        return {}
    async with identity_engine().connect() as conn:
        rows = (await conn.execute(_USER_EMAILS, {"ids": user_ids})).all()
    return {cast(UUID, row.id): str(row.email) for row in rows}


async def earliest_partner_of(session: AsyncSession, engagement_id: UUID) -> UUID | None:
    """The engagement's earliest-added partner whose membership is active (SPEC-027 Q1)."""
    found = await session.scalar(
        text(
            "SELECT em.user_id FROM engagement_members em JOIN memberships m "
            "ON m.tenant_id = em.tenant_id AND m.user_id = em.user_id "
            "WHERE em.engagement_id = :e AND em.role = 'engagement_partner' "
            "AND m.status = 'active' ORDER BY em.created_at, em.user_id LIMIT 1"
        ),
        {"e": engagement_id},
    )
    return cast(UUID, found) if found is not None else None


async def client_admin_ids(session: AsyncSession, engagement_id: UUID) -> list[UUID]:
    """The engagement's client admins (SPEC-027 P-4: who is reminded when no one is assigned)."""
    rows = await session.execute(
        text(
            "SELECT user_id FROM engagement_members WHERE engagement_id = :e "
            "AND role = 'client_admin' ORDER BY created_at, user_id"
        ),
        {"e": engagement_id},
    )
    return [cast(UUID, r[0]) for r in rows.all()]


async def time_zone_of(session: AsyncSession) -> str:
    return str(await session.scalar(text("SELECT time_zone FROM firms")))


async def set_time_zone(session: AsyncSession, zone: str) -> None:
    await session.execute(text("UPDATE firms SET time_zone = :z"), {"z": zone})


async def insert_engagement_member(
    session: AsyncSession,
    tenant_id: UUID,
    engagement_id: UUID,
    user_id: UUID,
    role: EngagementRole,
) -> None:
    """Inside the caller's unit of work. The FK to memberships keeps members within the firm."""
    await session.execute(
        insert(engagement_members).values(
            tenant_id=tenant_id, engagement_id=engagement_id, user_id=user_id, role=role
        )
    )


async def engagement_members_of(
    tenant: TenantContext, engagement_id: UUID
) -> list[tuple[UUID, EngagementRole]]:
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                select(engagement_members.c.user_id, engagement_members.c.role)
                .where(engagement_members.c.engagement_id == engagement_id)
                .order_by(engagement_members.c.role, engagement_members.c.user_id)
            )
        ).all()
    return [(cast(UUID, row.user_id), cast(EngagementRole, row.role)) for row in rows]


async def display_names(user_ids: list[UUID]) -> dict[UUID, str]:
    """Names for users already known to belong to the tenant (IDs read under RLS by the caller)."""
    if not user_ids:
        return {}
    async with identity_engine().connect() as conn:
        rows = (await conn.execute(_USER_NAMES, {"ids": user_ids})).all()
    return {cast(UUID, row.id): str(row.display_name) for row in rows}


@dataclass(frozen=True)
class WallRecord:
    id: UUID
    user_id: UUID
    client_id: UUID
    status: str
    created_by: UUID
    created_at: datetime
    removed_by: UUID | None
    removed_at: datetime | None


def _wall(m: RowMapping) -> WallRecord:
    return WallRecord(
        id=cast(UUID, m["id"]),
        user_id=cast(UUID, m["user_id"]),
        client_id=cast(UUID, m["client_id"]),
        status=cast(str, m["status"]),
        created_by=cast(UUID, m["created_by"]),
        created_at=cast(datetime, m["created_at"]),
        removed_by=cast(UUID | None, m["removed_by"]),
        removed_at=cast(datetime | None, m["removed_at"]),
    )


async def walled_clients(tenant: TenantContext, user_id: UUID) -> frozenset[UUID]:
    """The clients this person is walled off from now (active walls)."""
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            select(ethical_walls.c.client_id).where(
                ethical_walls.c.user_id == user_id, ethical_walls.c.status == "active"
            )
        )
        return frozenset(cast(UUID, client) for client in rows.scalars().all())


async def insert_wall(
    session: AsyncSession,
    *,
    wall_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    client_id: UUID,
    created_by: UUID,
) -> None:
    await session.execute(
        insert(ethical_walls).values(
            id=wall_id,
            tenant_id=tenant_id,
            user_id=user_id,
            client_id=client_id,
            created_by=created_by,
        )
    )


async def remove_wall(session: AsyncSession, wall_id: UUID, removed_by: UUID) -> WallRecord | None:
    """Mark an active wall removed; None if there is no active wall with this id."""
    row = (
        (
            await session.execute(
                update(ethical_walls)
                .where(ethical_walls.c.id == wall_id, ethical_walls.c.status == "active")
                .values(status="removed", removed_by=removed_by, removed_at=func.clock_timestamp())
                .returning(*ethical_walls.c)
            )
        )
        .mappings()
        .one_or_none()
    )
    return _wall(row) if row is not None else None


async def get_wall(session: AsyncSession, wall_id: UUID) -> WallRecord | None:
    row = (
        (await session.execute(select(ethical_walls).where(ethical_walls.c.id == wall_id)))
        .mappings()
        .one_or_none()
    )
    return _wall(row) if row is not None else None


async def all_walls(tenant: TenantContext) -> Sequence[WallRecord]:
    """Every wall of the firm, newest first (firm-level: the caller authorised `wall.list`)."""
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            select(ethical_walls).order_by(ethical_walls.c.created_at.desc(), ethical_walls.c.id)
        )
        return [_wall(row) for row in rows.mappings().all()]


# --- Support sessions (SPEC-012) ---------------------------------------------------------------


async def firm_exists(session: AsyncSession) -> bool:
    """The active tenant's firm row is visible (row-level security)."""
    return bool(await session.scalar(text("SELECT EXISTS (SELECT 1 FROM firms)")))


async def insert_support_session(session: AsyncSession, values: dict[str, object]) -> None:
    await session.execute(
        text(
            "INSERT INTO support_sessions (id, tenant_id, staff_id, staff_subject, reason, scope, "
            "duration_minutes, emergency) VALUES (:id, :tenant_id, :staff_id, :staff_subject, "
            ":reason, :scope, :duration_minutes, :emergency)"
        ),
        values,
    )


async def get_support_session(
    session: AsyncSession, session_id: UUID, *, lock: bool = False
) -> RowMapping | None:
    select_one = text(
        "SELECT id, staff_id, staff_subject, reason, scope, duration_minutes, emergency, status, "
        "approved_by_kind, approved_by, starts_at, expires_at, ended_at, acknowledged_at, "
        "created_at, (status = 'active' AND expires_at > clock_timestamp()) AS live "
        "FROM support_sessions WHERE id = :id"
    )
    locked = text(
        "SELECT id, staff_id, staff_subject, reason, scope, duration_minutes, emergency, status, "
        "approved_by_kind, approved_by, starts_at, expires_at, ended_at, acknowledged_at, "
        "created_at, (status = 'active' AND expires_at > clock_timestamp()) AS live "
        "FROM support_sessions WHERE id = :id FOR UPDATE"
    )
    result = await session.execute(locked if lock else select_one, {"id": session_id})
    return result.mappings().first()


async def list_support_sessions(session: AsyncSession) -> Sequence[RowMapping]:
    listed = text(
        "SELECT id, staff_id, staff_subject, reason, scope, duration_minutes, emergency, status, "
        "approved_by_kind, approved_by, starts_at, expires_at, ended_at, acknowledged_at, "
        "created_at, (status = 'active' AND expires_at > clock_timestamp()) AS live "
        "FROM support_sessions ORDER BY created_at DESC, id"
    )
    return (await session.execute(listed)).mappings().all()


async def activate_support_session(
    session: AsyncSession, session_id: UUID, by_kind: str, by: UUID
) -> None:
    await session.execute(
        text(
            "UPDATE support_sessions SET status = 'active', approved_by_kind = :kind, "
            "approved_by = :by, starts_at = clock_timestamp(), "
            "expires_at = clock_timestamp() + make_interval(mins => duration_minutes) "
            "WHERE id = :id AND status = 'requested'"
        ),
        {"id": session_id, "kind": by_kind, "by": by},
    )


async def close_support_session(session: AsyncSession, session_id: UUID, status: str) -> None:
    await session.execute(
        text(
            "UPDATE support_sessions SET status = :status, ended_at = clock_timestamp() "
            "WHERE id = :id AND status IN ('requested', 'active')"
        ),
        {"id": session_id, "status": status},
    )


async def acknowledge_support_session(session: AsyncSession, session_id: UUID) -> None:
    await session.execute(
        text(
            "UPDATE support_sessions SET acknowledged_at = clock_timestamp() "
            "WHERE id = :id AND acknowledged_at IS NULL"
        ),
        {"id": session_id},
    )


async def active_firm_admins(tenant: TenantContext) -> list[UUID]:
    """The firm's active firm admins (SPEC-013 recipients), read under the tenant."""
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            text(
                "SELECT user_id FROM memberships WHERE firm_role = 'firm_admin' "
                "AND status = 'active' ORDER BY user_id"
            )
        )
        return [cast(UUID, row.user_id) for row in rows.all()]


# --- Client invitations (SPEC-015) -------------------------------------------------------------


async def insert_invitation(session: AsyncSession, values: dict[str, object]) -> None:
    await session.execute(
        text(
            "INSERT INTO client_invitations (id, tenant_id, engagement_id, email, role, "
            "invited_by, expires_at) VALUES (:id, :tenant_id, :engagement_id, :email, :role, "
            ":invited_by, clock_timestamp() + make_interval(days => :days))"
        ),
        values,
    )


async def invitations_today(session: AsyncSession, engagement_id: UUID) -> int:
    count = await session.scalar(
        text(
            "SELECT count(*) FROM client_invitations WHERE engagement_id = :e "
            "AND created_at > clock_timestamp() - interval '1 day'"
        ),
        {"e": engagement_id},
    )
    return int(count or 0)


async def get_invitation(
    session: AsyncSession, invitation_id: UUID, *, lock: bool = False
) -> RowMapping | None:
    plain = text(
        "SELECT id, engagement_id, email, role, invited_by, status, expires_at, created_at, "
        "(status = 'pending' AND expires_at > clock_timestamp()) AS live "
        "FROM client_invitations WHERE id = :id"
    )
    locked = text(
        "SELECT id, engagement_id, email, role, invited_by, status, expires_at, created_at, "
        "(status = 'pending' AND expires_at > clock_timestamp()) AS live "
        "FROM client_invitations WHERE id = :id FOR UPDATE"
    )
    result = await session.execute(locked if lock else plain, {"id": invitation_id})
    return result.mappings().first()


async def pending_invitation_for(
    session: AsyncSession, engagement_id: UUID, email: str
) -> UUID | None:
    return await session.scalar(
        text(
            "SELECT id FROM client_invitations WHERE engagement_id = :e "
            "AND lower(email) = lower(:email) AND status = 'pending' FOR UPDATE"
        ),
        {"e": engagement_id, "email": email},
    )


async def set_invitation_status(
    session: AsyncSession, invitation_id: UUID, status: str, accepted_by: UUID | None = None
) -> None:
    await session.execute(
        text(
            "UPDATE client_invitations SET status = :status, accepted_by = :by, "
            "accepted_at = CASE WHEN :status = 'accepted' THEN clock_timestamp() END "
            "WHERE id = :id"
        ),
        {"id": invitation_id, "status": status, "by": accepted_by},
    )


async def extend_invitation(session: AsyncSession, invitation_id: UUID, days: int) -> None:
    await session.execute(
        text(
            "UPDATE client_invitations SET expires_at = clock_timestamp() + "
            "make_interval(days => :days) WHERE id = :id AND status = 'pending'"
        ),
        {"id": invitation_id, "days": days},
    )


async def set_token_hash(session: AsyncSession, invitation_id: UUID, digest: str | None) -> None:
    await session.execute(
        text("SELECT invitation_token_set(:id, :hash)"), {"id": invitation_id, "hash": digest}
    )


async def find_token(session: AsyncSession, digest: str, identity: str) -> RowMapping | None:
    result = await session.execute(
        text("SELECT (invitation_token_find(:hash, :identity)).*"),
        {"hash": digest, "identity": identity},
    )
    return result.mappings().first()


async def provision_client_user(
    session: AsyncSession, issuer: str, subject: str, email: str, display_name: str
) -> UUID:
    found = await session.scalar(
        text("SELECT provision_client_user(:issuer, :subject, :email, :name)"),
        {"issuer": issuer, "subject": subject, "email": email, "name": display_name},
    )
    return cast(UUID, found)


async def membership_kind(session: AsyncSession, user_id: UUID) -> str | None:
    return await session.scalar(
        text("SELECT kind FROM memberships WHERE user_id = :u"), {"u": user_id}
    )


async def add_client_membership(session: AsyncSession, user_id: UUID) -> None:
    await session.execute(text("SELECT add_client_membership(:u)"), {"u": user_id})


async def remove_client_member(session: AsyncSession, engagement_id: UUID, user_id: UUID) -> bool:
    removed = await session.scalar(
        text("SELECT remove_client_member(:e, :u)"), {"e": engagement_id, "u": user_id}
    )
    return bool(removed)


async def client_contacts(session: AsyncSession, engagement_id: UUID) -> Sequence[RowMapping]:
    """The engagement's client members (with their names) and pending invitations."""
    result = await session.execute(
        text(
            "SELECT 'member' AS kind, em.user_id AS id, em.role, NULL::text AS email, "
            "NULL::timestamptz AS expires_at FROM engagement_members em "
            "WHERE em.engagement_id = :e AND em.role IN ('client_admin', 'client_contributor') "
            "UNION ALL SELECT 'invitation', ci.id, ci.role, ci.email, ci.expires_at "
            "FROM client_invitations ci WHERE ci.engagement_id = :e AND ci.status = 'pending' "
            "AND ci.expires_at > clock_timestamp() ORDER BY 1, 3, 2"
        ),
        {"e": engagement_id},
    )
    return result.mappings().all()


# --- Engagement team (SPEC-017) ----------------------------------------------------------------


async def team_candidate_ids(
    session: AsyncSession, engagement_id: UUID, client_id: UUID
) -> list[UUID]:
    """Active staff of the firm, not on the team, not walled from the engagement's client."""
    rows = await session.execute(
        text(
            "SELECT m.user_id FROM memberships m WHERE m.kind = 'staff' AND m.status = 'active' "
            "AND NOT EXISTS (SELECT 1 FROM engagement_members em WHERE em.engagement_id = :e "
            "AND em.user_id = m.user_id) AND NOT EXISTS (SELECT 1 FROM ethical_walls w "
            "WHERE w.user_id = m.user_id AND w.client_id = :c AND w.status = 'active') "
            "ORDER BY m.user_id"
        ),
        {"e": engagement_id, "c": client_id},
    )
    return [cast(UUID, row[0]) for row in rows.all()]


async def set_team_role(
    session: AsyncSession, engagement_id: UUID, user_id: UUID, role: str
) -> str:
    found = await session.scalar(
        text("SELECT team_member_set_role(:e, :u, :r)"),
        {"e": engagement_id, "u": user_id, "r": role},
    )
    return str(found)


async def remove_team_member_row(session: AsyncSession, engagement_id: UUID, user_id: UUID) -> str:
    found = await session.scalar(
        text("SELECT team_member_remove(:e, :u)"), {"e": engagement_id, "u": user_id}
    )
    return str(found)


async def active_staff_ids(session: AsyncSession) -> list[UUID]:
    """The firm's active staff members (SPEC-019 Q4: the wall picker); never client users."""
    rows = await session.execute(
        text(
            "SELECT user_id FROM memberships WHERE kind = 'staff' AND status = 'active' "
            "ORDER BY user_id"
        )
    )
    return [cast(UUID, row[0]) for row in rows.all()]


# --- Self-serve sign-up (SPEC-024; TASK-040) ---------------------------------------------------


async def firm_signup(
    session: AsyncSession,
    *,
    code_hash: str,
    identity_hash: str,
    address_hash: str,
    issuer: str,
    subject: str,
    email: str,
    display_name: str,
    firm_name: str,
) -> tuple[str, UUID | None]:
    """The reviewed `firm_signup` definer function: (outcome, new tenant or None)."""
    # One call returns one (outcome, tenant_id) record.
    row = (
        await session.execute(
            text(
                "SELECT firm_signup("
                ":code, :identity, :address, :issuer, :subject, :email, :name, :firm) AS result"
            ),
            {
                "code": code_hash,
                "identity": identity_hash,
                "address": address_hash,
                "issuer": issuer,
                "subject": subject,
                "email": email,
                "name": display_name,
                "firm": firm_name,
            },
        )
    ).one()
    outcome, tenant_id = cast(tuple[str, UUID | None], tuple(row.result))
    return outcome, tenant_id


# --- Staff invitations, firm roles and revocation (SPEC-024 AC-3, AC-4; TASK-041) --------------

_USER_CONTACTS = text("SELECT id, display_name, email FROM users WHERE id IN :ids").bindparams(
    bindparam("ids", expanding=True)
)


async def user_contacts(user_ids: list[UUID]) -> dict[UUID, tuple[str, str]]:
    """Names and emails for users the caller already read under RLS (the staff list)."""
    if not user_ids:
        return {}
    async with identity_engine().connect() as conn:
        rows = (await conn.execute(_USER_CONTACTS, {"ids": user_ids})).all()
    return {cast(UUID, r.id): (str(r.display_name), str(r.email)) for r in rows}


async def staff_memberships(session: AsyncSession) -> Sequence[RowMapping]:
    """The session's firm's staff memberships, for a caller that authorised `firm.manage_users`
    (LIST_EXEMPT: firm-level, no engagement rows)."""
    result = await session.execute(
        text(
            "SELECT user_id, firm_role, status FROM memberships WHERE kind = 'staff' "
            "ORDER BY status, created_at, user_id"
        )
    )
    return result.mappings().all()


async def pending_staff_invitations(session: AsyncSession) -> Sequence[RowMapping]:
    """The session's firm's live staff invitations (LIST_EXEMPT, as `staff_memberships`)."""
    result = await session.execute(
        text(
            "SELECT id, email, firm_role, expires_at, created_at FROM staff_invitations "
            "WHERE status = 'pending' AND expires_at > clock_timestamp() ORDER BY created_at, id"
        )
    )
    return result.mappings().all()


async def insert_staff_invitation(session: AsyncSession, values: dict[str, object]) -> None:
    await session.execute(
        text(
            "INSERT INTO staff_invitations (id, tenant_id, email, firm_role, invited_by, "
            "expires_at) VALUES (:id, :tenant_id, :email, :firm_role, :invited_by, "
            "clock_timestamp() + make_interval(days => :days))"
        ),
        values,
    )


async def pending_staff_invitation_for(session: AsyncSession, email: str) -> UUID | None:
    return await session.scalar(
        text(
            "SELECT id FROM staff_invitations WHERE lower(email) = lower(:email) "
            "AND status = 'pending' FOR UPDATE"
        ),
        {"email": email},
    )


async def get_staff_invitation(
    session: AsyncSession, invitation_id: UUID, *, lock: bool = False
) -> RowMapping | None:
    plain = text(
        "SELECT id, email, firm_role, invited_by, status, expires_at, "
        "(status = 'pending' AND expires_at > clock_timestamp()) AS live "
        "FROM staff_invitations WHERE id = :id"
    )
    locked = text(
        "SELECT id, email, firm_role, invited_by, status, expires_at, "
        "(status = 'pending' AND expires_at > clock_timestamp()) AS live "
        "FROM staff_invitations WHERE id = :id FOR UPDATE"
    )
    result = await session.execute(locked if lock else plain, {"id": invitation_id})
    return result.mappings().first()


async def set_staff_invitation_status(
    session: AsyncSession, invitation_id: UUID, status: str, accepted_by: UUID | None = None
) -> None:
    await session.execute(
        text(
            "UPDATE staff_invitations SET status = :status, accepted_by = :by, "
            "accepted_at = CASE WHEN :status = 'accepted' THEN clock_timestamp() END "
            "WHERE id = :id"
        ),
        {"id": invitation_id, "status": status, "by": accepted_by},
    )


async def extend_staff_invitation(session: AsyncSession, invitation_id: UUID, days: int) -> None:
    await session.execute(
        text(
            "UPDATE staff_invitations SET expires_at = clock_timestamp() + "
            "make_interval(days => :days) WHERE id = :id AND status = 'pending'"
        ),
        {"id": invitation_id, "days": days},
    )


async def set_staff_token_hash(
    session: AsyncSession, invitation_id: UUID, digest: str | None
) -> None:
    await session.execute(
        text("SELECT staff_invitation_token_set(:id, :hash)"),
        {"id": invitation_id, "hash": digest},
    )


async def find_staff_token(session: AsyncSession, digest: str, identity: str) -> RowMapping | None:
    result = await session.execute(
        text("SELECT (staff_invitation_token_find(:hash, :identity)).*"),
        {"hash": digest, "identity": identity},
    )
    return result.mappings().first()


async def add_staff_membership(session: AsyncSession, user_id: UUID, role: str | None) -> str:
    return str(
        await session.scalar(
            text("SELECT add_staff_membership(:u, :r)"), {"u": user_id, "r": role}
        )
    )


async def set_firm_role(session: AsyncSession, user_id: UUID, role: str | None) -> str:
    return str(
        await session.scalar(
            text("SELECT membership_set_firm_role(:u, :r)"), {"u": user_id, "r": role}
        )
    )


async def revoke_membership(session: AsyncSession, user_id: UUID) -> str:
    return str(await session.scalar(text("SELECT membership_revoke(:u)"), {"u": user_id}))


# --- Firm settings: autonomy and onboarding (SPEC-024 AC-5, AC-7; TASK-042) -------------------

_FIRM_SETTINGS = text(
    "SELECT autonomy_level, autonomy_set_at, budget_reviewed_at, walls_none_needed_at, "
    "sso_skipped_at, onboarding_dismissed_at FROM firms"
)


async def firm_settings(session: AsyncSession) -> RowMapping | None:
    """The session's firm's settings (row-level security leaves one row)."""
    return (await session.execute(_FIRM_SETTINGS)).mappings().first()


async def set_autonomy_level(session: AsyncSession, level: int) -> None:
    await session.execute(
        text("UPDATE firms SET autonomy_level = :level, autonomy_set_at = clock_timestamp()"),
        {"level": level},
    )


_ACKNOWLEDGE = {
    "budget": text("UPDATE firms SET budget_reviewed_at = clock_timestamp()"),
    "walls": text("UPDATE firms SET walls_none_needed_at = clock_timestamp()"),
    "sso": text("UPDATE firms SET sso_skipped_at = clock_timestamp()"),
    "dismiss": text("UPDATE firms SET onboarding_dismissed_at = clock_timestamp()"),
}


async def acknowledge_onboarding(session: AsyncSession, step: str) -> None:
    await session.execute(_ACKNOWLEDGE[step])


async def onboarding_counts(session: AsyncSession) -> RowMapping:
    """Counts for the checklist, in the session's firm."""
    return (
        (
            await session.execute(
                text(
                    "SELECT "
                    "(SELECT count(*) FROM memberships WHERE kind = 'staff' AND status = 'active')"
                    " AS staff, "
                    "(SELECT count(*) FROM staff_invitations WHERE status = 'pending' "
                    "AND expires_at > clock_timestamp()) AS invitations, "
                    "(SELECT count(*) FROM ethical_walls WHERE status = 'active') AS walls"
                )
            )
        )
        .mappings()
        .one()
    )


async def firm_name_of(tenant_id: UUID) -> str | None:
    """The firm's name, read through the identity role (SPEC-025: invitations)."""
    async with identity_engine().connect() as conn:
        found = await conn.scalar(
            text("SELECT name FROM firms WHERE tenant_id = :t"), {"t": tenant_id}
        )
    return str(found) if found is not None else None


async def firm_is_synthetic(session: AsyncSession) -> bool:
    """SPEC-026: whether the session's firm is synthetic (set only by seeding and evaluations)."""
    return bool(await session.scalar(text("SELECT synthetic FROM firms")))


async def agents_paused_since(session: AsyncSession) -> datetime | None:
    """SPEC-027: when the session's firm paused every engagement agent, or None."""
    found = await session.scalar(text("SELECT agents_paused_at FROM firms"))
    return cast(datetime, found) if found is not None else None


async def set_agents_paused(session: AsyncSession, by: UUID | None) -> None:
    await session.execute(
        text(
            "UPDATE firms SET agents_paused_at = CASE WHEN CAST(:by AS uuid) IS NULL THEN NULL "
            "ELSE now() END, agents_paused_by = CAST(:by AS uuid)"
        ),
        {"by": by},
    )


async def letter_required(session: AsyncSession) -> bool:
    """Whether the session's firm requires the engagement letter before client data."""
    return bool(await session.scalar(text("SELECT require_letter FROM firms")))


async def set_letter_required(session: AsyncSession, required: bool) -> None:
    await session.execute(text("UPDATE firms SET require_letter = :r"), {"r": required})
