"""Identity data access. PROTECTED. TASK-007 design §2-3.

Two kinds of read:
- Before a tenant is chosen (sign-in): `abacus_identity`, which bypasses row-level security but
  reads only users and the membership and firm columns sign-in needs. Only this file uses it
  (UOW-002).
- Within a tenant: `tenant_session`, like everything else.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast, get_args
from uuid import UUID

from sqlalchemy import Column, MetaData, String, Table, bindparam, insert, select, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
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
