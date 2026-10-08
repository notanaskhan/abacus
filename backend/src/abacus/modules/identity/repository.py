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
ENGAGEMENT_ROLES: frozenset[str] = frozenset(get_args(EngagementRole))

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


_USER = text(
    "SELECT id, email, display_name FROM users "
    "WHERE idp_issuer = :issuer AND idp_subject = :subject"
)
_ACTIVE_MEMBERSHIPS = text(
    "SELECT m.tenant_id, m.id, m.firm_role, f.name FROM memberships m "
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
        )
        for row in rows
    ]


async def engagement_role(
    tenant: TenantContext, user_id: UUID, engagement_id: UUID
) -> EngagementRole | None:
    async with tenant_session(tenant) as session:
        role = (
            await session.execute(
                select(engagement_members.c.role).where(
                    engagement_members.c.engagement_id == engagement_id,
                    engagement_members.c.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
    return cast(EngagementRole | None, role)


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
