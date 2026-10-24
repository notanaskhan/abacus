"""Identity data access. PROTECTED. TASK-007 design §2-3.

Two kinds of read:
- Before a tenant is chosen (sign-in): `abacus_identity`, which bypasses row-level security but
  reads only users and the membership and firm columns sign-in needs. Only this file uses it
  (UOW-002).
- Within a tenant: `tenant_session`, like everything else.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, Literal, cast, get_args
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    MetaData,
    Select,
    String,
    Table,
    bindparam,
    func,
    insert,
    literal,
    or_,
    select,
    text,
    union,
    update,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.engine import Row, RowMapping
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import TenantContext, identity_engine, tenant_session

# F-03-T23: security_admin (IT and security; no client content, chapter 03 §4.2).
FirmRole = Literal["firm_admin", "practice_leader", "quality_partner", "security_admin"]
# F-03-T23: eqr_reviewer, specialist and client_service join the engagement roles (§4.2).
EngagementRole = Literal[
    "engagement_partner",
    "manager",
    "senior",
    "staff",
    "reviewer",
    "eqr_reviewer",
    "specialist",
    "client_service",
]
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


def engagement_team_query() -> Select[UUID, UUID, str]:
    """Every engagement's team, `(engagement_id, user_id, role)`, as a subquery for the client
    record's derived Manager and Preparer (P-07-T09; DEC-62, DEC-138)."""
    team = engagement_members.c
    return cast(Select[UUID, UUID, str], select(team.engagement_id, team.user_id, team.role))


# F-03-T26 (ADR-146): client access lives in grants. An engagement-scope `owner` or
# `contributor` grant is what the matrix calls `client_admin` or `client_contributor`; the other
# grant roles have no matrix cells yet (P-08).
client_access_grants = Table(
    "client_access_grants",
    _metadata,
    Column("id", PgUUID(as_uuid=True), primary_key=True),
    Column("tenant_id", PgUUID(as_uuid=True), nullable=False),
    Column("user_id", PgUUID(as_uuid=True), nullable=False),
    Column("role", String, nullable=False),
    Column("scope_kind", String, nullable=False),
    Column("scope_id", PgUUID(as_uuid=True), nullable=False),
    Column("status", String, nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
GRANT_ROLE_OF: dict[str, str] = {"client_admin": "owner", "client_contributor": "contributor"}
MATRIX_ROLE_OF: dict[str, ClientRole] = {
    "owner": "client_admin",
    "contributor": "client_contributor",
}
# DEC-211 (DEC-129): the full-client grant roles that act for the client hold the matrix's
# `client_admin` cells, a `contributor` its `client_contributor` cells. `delegate` waits for P-09's
# matrix cells (DEC-158); the limited roles (third party, K-1 recipient and the rest) hold none.
GRANT_ROLES_OF: dict[str, tuple[str, ...]] = {
    "client_admin": ("owner", "plan_administrator", "trustee", "taxpayer", "spouse"),
    "client_contributor": ("contributor",),
}
# A client-wide grant covers its client's (or client entity's) engagements (DEC-129). The
# engagements module registers how to list them, as identity never reads its tables (ADR-008);
# unregistered, only engagement-scope grants count (fail closed).
EngagementsOfScope = Callable[[str, Select[tuple[UUID]]], Select[UUID]]
_engagements_of_scope: EngagementsOfScope | None = None


def register_engagements_of_scope(builder: EngagementsOfScope) -> None:
    """engagements registers how to list the engagements of a `client` or `client_entity` scope."""
    global _engagements_of_scope
    known = _engagements_of_scope
    if known is not None and (known.__module__, known.__qualname__) != (
        builder.__module__,
        builder.__qualname__,
    ):
        raise RuntimeError("the engagements-of-scope subquery is already registered")
    _engagements_of_scope = builder


def _granted(
    tenant_id: UUID, user_id: UUID, kind: str, roles: Sequence[str]
) -> Select[tuple[UUID]]:
    return select(client_access_grants.c.scope_id).where(
        client_access_grants.c.tenant_id == tenant_id,
        client_access_grants.c.user_id == user_id,
        client_access_grants.c.scope_kind == kind,
        client_access_grants.c.role.in_(
            sorted({grant for r in roles for grant in GRANT_ROLES_OF[r]})
        ),
        client_access_grants.c.status == "active",
        or_(
            client_access_grants.c.expires_at.is_(None),
            client_access_grants.c.expires_at > func.clock_timestamp(),
        ),
    )


def client_grant_engagements(
    tenant_id: UUID, user_id: UUID, roles: Sequence[str]
) -> Select[tuple[UUID]]:
    """The engagements where the person holds one of these client matrix roles: an active,
    unexpired grant of a matching grant role on the engagement, or on its client or client
    entity (DEC-211)."""
    found = _granted(tenant_id, user_id, "engagement", roles)
    builder = _engagements_of_scope
    if builder is None:
        return found
    wide = [builder(kind, _granted(tenant_id, user_id, kind, roles)) for kind in _CLIENT_WIDE]
    return select(union(found, *wide).subquery().c[0])


_CLIENT_WIDE: Final = ("client", "client_entity")


# F-03-T24 (migration 0081): the firm settings a firm switched on. `visible()` reads the
# stricter-only `g2_blocks_view` here (ADR-164 item 3, P-07-T24); `authorise` reads them all once
# per request through `firm_policy`.
firm_setting_values = Table(
    "firm_setting_values",
    _metadata,
    Column("tenant_id", PgUUID(as_uuid=True), nullable=False),
    Column("key", String, nullable=False),
    Column("value", Boolean, nullable=False),
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


@dataclass(frozen=True)
class MemberFacts:
    """What the matrix conditions read about a person's membership (F-03-T24)."""

    level: str | None
    offshore: bool
    service_lines: frozenset[str]
    client: bool
    office_id: UUID | None = None  # F-03-T30: `/v1/me/capabilities`


_MEMBER_FACTS = text(
    "SELECT level, offshore, service_lines, kind, office_id FROM memberships "
    "WHERE user_id = :user_id AND status = 'active'"
)


async def member_facts(tenant: TenantContext, user_id: UUID) -> MemberFacts | None:
    """The person's level, offshore flag, service lines and kind in this firm, or None."""
    async with tenant_session(tenant) as session:
        row = (await session.execute(_MEMBER_FACTS, {"user_id": user_id})).one_or_none()
    if row is None:
        return None
    return MemberFacts(
        level=cast(str | None, row.level),
        offshore=bool(row.offshore),
        service_lines=frozenset(cast(list[str], row.service_lines)),
        client=row.kind == "client",
        office_id=cast(UUID | None, row.office_id),
    )


@dataclass(frozen=True)
class FirmPolicy:
    """A firm's narrowing overrides, (action, role) -> decision, and the firm settings it has
    switched on (F-03-T24)."""

    overrides: dict[tuple[str, str], str]
    settings_on: frozenset[str]


_OVERRIDES = text("SELECT action, role, decision FROM firm_policy_overrides")
_SETTINGS_ON = text("SELECT key FROM firm_setting_values WHERE value")


async def firm_policy(tenant: TenantContext) -> FirmPolicy:
    async with tenant_session(tenant) as session:
        overrides = (await session.execute(_OVERRIDES)).all()
        settings = (await session.execute(_SETTINGS_ON)).scalars().all()
    return FirmPolicy(
        {(str(row.action), str(row.role)): str(row.decision) for row in overrides},
        frozenset(str(key) for key in settings),
    )


_INSERT_OVERRIDE = text(
    "INSERT INTO firm_policy_overrides (tenant_id, action, role, decision, reason, set_by) "
    "VALUES (:tenant_id, :action, :role, :decision, :reason, :set_by) "
    "ON CONFLICT (tenant_id, action, role) DO NOTHING RETURNING action"
)


async def insert_policy_override(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    action: str,
    role: str,
    decision: str,
    reason: str,
    set_by: UUID,
) -> bool:
    """Whether a row was written (False: the cell was already overridden)."""
    row = await session.execute(
        _INSERT_OVERRIDE,
        {
            "tenant_id": tenant_id,
            "action": action,
            "role": role,
            "decision": decision,
            "reason": reason,
            "set_by": set_by,
        },
    )
    return row.first() is not None


_UPSERT_SETTING = text(
    "INSERT INTO firm_setting_values (tenant_id, key, value, set_by) "
    "VALUES (:tenant_id, :key, :value, :set_by) "
    "ON CONFLICT (tenant_id, key) DO UPDATE SET value = EXCLUDED.value, "
    "version = firm_setting_values.version + 1, set_by = EXCLUDED.set_by, "
    "set_at = clock_timestamp() RETURNING version"
)


async def upsert_firm_setting(
    session: AsyncSession, *, tenant_id: UUID, key: str, value: bool, set_by: UUID
) -> int:
    """Set the firm's value for `key`; the row's version afterwards."""
    row = await session.execute(
        _UPSERT_SETTING, {"tenant_id": tenant_id, "key": key, "value": value, "set_by": set_by}
    )
    return int(row.scalar_one())


@dataclass(frozen=True)
class GrantRow:
    """A client access grant (F-03-T26)."""

    id: UUID
    user_id: UUID
    role: str
    scope_kind: str
    scope_id: UUID
    document_classes: tuple[str, ...] | None
    status: str


_ACTIVE_GRANTS = text(
    "SELECT id, user_id, role, scope_kind, scope_id, document_classes, status "
    "FROM client_access_grants WHERE user_id = :user_id AND status = 'active' "
    "AND (expires_at IS NULL OR expires_at > clock_timestamp()) "
    "ORDER BY scope_kind, scope_id, role"
)
_GRANT = text(
    "SELECT id, user_id, role, scope_kind, scope_id, document_classes, status "
    "FROM client_access_grants WHERE id = :id"
)


def _grant(row: Row[Any]) -> GrantRow:  # Any: a text() row's columns are untyped
    classes = cast(list[str] | None, row.document_classes)
    return GrantRow(
        cast(UUID, row.id),
        cast(UUID, row.user_id),
        str(row.role),
        str(row.scope_kind),
        cast(UUID, row.scope_id),
        None if classes is None else tuple(classes),
        str(row.status),
    )


async def active_grants(tenant: TenantContext, user_id: UUID) -> list[GrantRow]:
    """The person's active, unexpired client access grants in this firm."""
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_ACTIVE_GRANTS, {"user_id": user_id})).all()
    return [_grant(row) for row in rows]


async def get_grant(session: AsyncSession, grant_id: UUID) -> GrantRow | None:
    row = (await session.execute(_GRANT, {"id": grant_id})).first()
    return None if row is None else _grant(row)


_INSERT_GRANT = text(
    "INSERT INTO client_access_grants (tenant_id, user_id, contact_id, role, scope_kind, "
    "scope_id, document_classes, granted_by, expires_at) "
    "VALUES (:tenant_id, :user_id, :contact_id, :role, :scope_kind, :scope_id, "
    ":document_classes, :granted_by, :expires_at) "
    "ON CONFLICT (tenant_id, user_id, role, scope_kind, scope_id) DO NOTHING RETURNING id"
)


async def insert_grant(session: AsyncSession, values: dict[str, object]) -> UUID | None:
    """The new grant's id, or None when the person already holds that role on that scope."""
    row = (await session.execute(_INSERT_GRANT, values)).first()
    return None if row is None else cast(UUID, row.id)


_SET_GRANT_STATUS = text(
    "UPDATE client_access_grants SET status = :status "
    "WHERE id = :id AND status <> :status RETURNING id"
)


async def set_grant_status(session: AsyncSession, grant_id: UUID, status: str) -> bool:
    row = (await session.execute(_SET_GRANT_STATUS, {"id": grant_id, "status": status})).first()
    return row is not None


_GRANT_EVENT = text(
    "INSERT INTO client_access_events (tenant_id, grant_id, event, by_user_id) "
    "VALUES (:tenant_id, :grant_id, :event, :by_user_id)"
)


async def insert_grant_event(
    session: AsyncSession, *, tenant_id: UUID, grant_id: UUID, event: str, by: UUID | None
) -> None:
    await session.execute(
        _GRANT_EVENT,
        {"tenant_id": tenant_id, "grant_id": grant_id, "event": event, "by_user_id": by},
    )


async def engagement_role(
    tenant: TenantContext, user_id: UUID, engagement_id: UUID
) -> EngagementRole | ClientRole | None:
    """The person's role on the engagement: a staff row, or (F-03-T26) a client grant on it or
    (DEC-211) on its client or client entity, the client admin roles before contributor."""
    async with tenant_session(tenant) as session:
        role = (
            await session.execute(
                select(engagement_members.c.role).where(
                    engagement_members.c.engagement_id == engagement_id,
                    engagement_members.c.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        if role is not None:
            return cast(EngagementRole, role)
        # The stronger client role first (owner before contributor, DEC-211).
        for matrix_role in ("client_admin", "client_contributor"):
            covers = select(literal(True)).where(
                literal(engagement_id).in_(
                    client_grant_engagements(tenant.tenant_id, user_id, [matrix_role])
                )
            )
            if (await session.execute(covers)).scalar_one_or_none():
                return matrix_role
    return None


async def my_engagement_roles(tenant: TenantContext, user_id: UUID) -> dict[UUID, EngagementRole]:
    """TASK-102: the person's own firm roles on engagements in the tenant (their own rows)."""
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                select(engagement_members.c.engagement_id, engagement_members.c.role)
                .where(engagement_members.c.user_id == user_id)
                .where(engagement_members.c.role.in_(sorted(ENGAGEMENT_ROLES)))
            )
        ).all()
    return {cast(UUID, r.engagement_id): cast(EngagementRole, r.role) for r in rows}


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
    """The engagement's client admins (SPEC-027 P-4: who is reminded when no one is assigned):
    its active owner grants (F-03-T26)."""
    rows = await session.execute(
        text(
            "SELECT user_id FROM client_access_grants WHERE scope_kind = 'engagement' "
            "AND scope_id = :e AND role = 'owner' AND status = 'active' "
            "AND (expires_at IS NULL OR expires_at > clock_timestamp()) "
            "ORDER BY created_at, user_id"
        ),
        {"e": engagement_id},
    )
    return [cast(UUID, r[0]) for r in rows.all()]


async def grant_contact_ids(session: AsyncSession, user_id: UUID) -> list[UUID]:
    """The contacts the person's grants name (P-08-T17: the MFA floor's designations), in the
    caller's tenant session. Revoked or expired grants count too: a designation stays a reason
    for the second step whatever became of the grant."""
    rows = await session.execute(
        text(
            "SELECT DISTINCT contact_id FROM client_access_grants "
            "WHERE user_id = :u AND contact_id IS NOT NULL"
        ),
        {"u": user_id},
    )
    return [cast(UUID, r[0]) for r in rows.all()]


async def contact_user_ids(session: AsyncSession, contact_id: UUID) -> list[UUID]:
    """The people whose grants name the contact (P-08-T17: who a new designation affects)."""
    rows = await session.execute(
        text(
            "SELECT DISTINCT user_id FROM client_access_grants WHERE contact_id = :c "
            "ORDER BY user_id"
        ),
        {"c": contact_id},
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
                # the firm team only: client users share the table (TASK-090)
                .where(engagement_members.c.role.in_(sorted(ENGAGEMENT_ROLES)))
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


async def active_security_admins(tenant: TenantContext) -> list[UUID]:
    """Q-02-T33: the firm's active security admins (the Qualified Individual), under the tenant."""
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            text(
                "SELECT user_id FROM memberships WHERE firm_role = 'security_admin' "
                "AND status = 'active' ORDER BY user_id"
            )
        )
        return [cast(UUID, row.user_id) for row in rows.all()]


async def active_partner_members(tenant: TenantContext) -> list[UUID]:
    """Q-02-T33: the firm's active partner-level staff (the derived `firm_partner`, DEC-132)."""
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            text(
                "SELECT user_id FROM memberships WHERE level = 'partner' AND kind = 'staff' "
                "AND status = 'active' ORDER BY user_id"
            )
        )
        return [cast(UUID, row.user_id) for row in rows.all()]


# --- Client invitations (SPEC-015) -------------------------------------------------------------


async def insert_invitation(session: AsyncSession, values: dict[str, object]) -> None:
    await session.execute(
        text(
            "INSERT INTO client_invitations (id, tenant_id, engagement_id, email, role, "
            "invited_by, expires_at, kind, contact_id, grant_template, terms_version, terms_url) "
            "VALUES (:id, :tenant_id, :engagement_id, :email, :role, :invited_by, "
            "clock_timestamp() + make_interval(days => :days), :kind, :contact_id, "
            "CAST(:grant_template AS jsonb), :terms_version, :terms_url)"
        ),
        {
            "kind": "firm_invite",
            "contact_id": None,
            "grant_template": None,
            "terms_version": None,
            "terms_url": None,
        }
        | values,
    )


async def invitation_engagements(
    session: AsyncSession, invitation_ids: Sequence[UUID]
) -> dict[UUID, UUID]:
    """Invitation id -> its engagement, for the audit explorer (its reader is authorised)."""
    statement = text(
        "SELECT id, engagement_id FROM client_invitations WHERE id IN :ids"
    ).bindparams(bindparam("ids", expanding=True))
    rows = await session.execute(statement, {"ids": list(invitation_ids)})
    return {cast(UUID, found): cast(UUID, owned) for found, owned in rows}


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
        "kind, contact_id, grant_template, terms_version, terms_url, "
        "(status = 'pending' AND expires_at > clock_timestamp()) AS live "
        "FROM client_invitations WHERE id = :id"
    )
    locked = text(
        "SELECT id, engagement_id, email, role, invited_by, status, expires_at, created_at, "
        "kind, contact_id, grant_template, terms_version, terms_url, "
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


async def accept_invitation_row(
    session: AsyncSession, invitation_id: UUID, user_id: UUID, terms: bool
) -> None:
    """Accepted by `user_id`, with the terms' acceptance time when the invitation carries terms
    (P-08-T18), in one statement (the table CHECKs that terms are accepted only on acceptance)."""
    await session.execute(
        text(
            "UPDATE client_invitations SET status = 'accepted', accepted_by = :by, "
            "accepted_at = clock_timestamp(), "
            "terms_accepted_at = CASE WHEN :terms THEN clock_timestamp() END "
            "WHERE id = :id AND status = 'pending'"
        ),
        {"id": invitation_id, "by": user_id, "terms": terms},
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


_ENGAGEMENT_GRANT = text(
    "INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id, "
    "granted_by) VALUES (:tenant_id, :user_id, :role, 'engagement', :engagement_id, :by) "
    "ON CONFLICT (tenant_id, user_id, role, scope_kind, scope_id) DO NOTHING RETURNING id"
)
_REACTIVATE = text(
    "UPDATE client_access_grants SET status = 'active' WHERE user_id = :user_id "
    "AND role = :role AND scope_kind = 'engagement' AND scope_id = :engagement_id "
    "AND status <> 'active' RETURNING id"
)


async def grant_engagement_role(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    engagement_id: UUID,
    user_id: UUID,
    role: ClientRole,
    by: UUID | None,
) -> UUID | None:
    """A client role on an engagement as its grant (F-03-T26): new, or reactivated after a
    removal. The grant's id when it changed, with its `client_access_events` row."""
    values = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "role": GRANT_ROLE_OF[role],
        "engagement_id": engagement_id,
        "by": by,
    }
    row = (await session.execute(_ENGAGEMENT_GRANT, values)).first()
    event = "granted"
    if row is None:
        row = (await session.execute(_REACTIVATE, values)).first()
        event = "activated"
    if row is None:
        return None
    grant_id = cast(UUID, row.id)
    await insert_grant_event(session, tenant_id=tenant_id, grant_id=grant_id, event=event, by=by)
    return grant_id


async def remove_client_member(session: AsyncSession, engagement_id: UUID, user_id: UUID) -> bool:
    removed = await session.scalar(
        text("SELECT remove_client_member(:e, :u)"), {"e": engagement_id, "u": user_id}
    )
    return bool(removed)


async def client_contacts(session: AsyncSession, engagement_id: UUID) -> Sequence[RowMapping]:
    """The engagement's client members (with their names) and pending invitations."""
    result = await session.execute(
        text(
            "SELECT 'member' AS kind, g.user_id AS id, "
            "CASE g.role WHEN 'owner' THEN 'client_admin' ELSE 'client_contributor' END AS role, "
            "NULL::text AS email, NULL::timestamptz AS expires_at FROM client_access_grants g "
            "WHERE g.scope_kind = 'engagement' AND g.scope_id = :e "
            "AND g.role IN ('owner', 'contributor') AND g.status = 'active' "
            "AND (g.expires_at IS NULL OR g.expires_at > clock_timestamp()) "
            "AND NOT (g.role = 'contributor' AND EXISTS (SELECT 1 FROM client_access_grants o "
            "WHERE o.scope_kind = 'engagement' AND o.scope_id = g.scope_id "
            "AND o.user_id = g.user_id AND o.role = 'owner' AND o.status = 'active')) "
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


_ELSEWHERE = text(
    "SELECT user_id, bool_or(status = 'active') AS active FROM memberships "
    "WHERE user_id IN :ids AND tenant_id <> :tenant GROUP BY user_id"
).bindparams(bindparam("ids", expanding=True))


async def memberships_elsewhere(tenant_id: UUID, user_ids: list[UUID]) -> dict[UUID, bool]:
    """G-01-T05 (DEC-286): which of these people belong or belonged to another firm (True: one
    still active there). Staff sessions carry no firm, so their sign-ins can't be told apart, and
    deactivation here ends a person's sessions only when no other firm holds them."""
    if not user_ids:
        return {}
    # A per-person fact for the caller's own firm members (LIST-001 does not apply: no rows of
    # another firm are returned, only whether one exists).
    async with identity_engine().connect() as conn:
        result = await conn.execute(_ELSEWHERE, {"ids": user_ids, "tenant": tenant_id})
        return {cast(UUID, r.user_id): bool(r.active) for r in result}


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


async def firm_tenancy_row(session: AsyncSession) -> RowMapping | None:
    """Q-01-T45: the session's firm's region, synthetic flag and tenant-key state (ADR-156)."""
    result = await session.execute(
        text(
            "SELECT synthetic, region, kms_key_status, kms_replica_verified_at, created_at "
            "FROM firms"
        )
    )
    return result.mappings().first()


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


async def drafted_guidance_shown(session: AsyncSession) -> bool:
    """SPEC-035 (TASK-073): whether the session's firm shows approved drafted guidance to
    clients."""
    return bool(await session.scalar(text("SELECT drafted_guidance_to_clients FROM firms")))


async def set_drafted_guidance_shown(session: AsyncSession, shown: bool) -> None:
    await session.execute(text("UPDATE firms SET drafted_guidance_to_clients = :s"), {"s": shown})


# --- AI on clients' data (SPEC-036; TASK-076) ---------------------------------------------------


@dataclass(frozen=True)
class AiClientDataRow:
    at: datetime | None
    by: UUID | None
    material: str | None


async def ai_client_data(session: AsyncSession) -> AiClientDataRow:
    """The session's firm's opt-in (who, when, which terms), or all None."""
    row = (
        await session.execute(
            text("SELECT ai_client_data_at, ai_client_data_by, ai_client_data_material FROM firms")
        )
    ).one()
    return AiClientDataRow(
        cast(datetime | None, row[0]), cast(UUID | None, row[1]), cast(str | None, row[2])
    )


async def set_ai_client_data(session: AsyncSession, by: UUID | None, material: str | None) -> None:
    await session.execute(
        text(
            "UPDATE firms SET ai_client_data_at = CASE WHEN CAST(:by AS uuid) IS NULL THEN NULL "
            "ELSE clock_timestamp() END, ai_client_data_by = CAST(:by AS uuid), "
            "ai_client_data_material = CAST(:material AS text)"
        ),
        {"by": by, "material": material},
    )


# --- F-04-T07: a synthetic firm's demo clock -------------------------------------------------

_DEMO_CLOCK = text(
    "SELECT mode, anchor_at, anchored_real_at FROM firm_demo_clocks WHERE tenant_id = :t"
)
_SET_DEMO_CLOCK = text(
    "INSERT INTO firm_demo_clocks (tenant_id, mode, anchor_at, set_by) "
    "VALUES (:t, :mode, :anchor_at, :set_by) ON CONFLICT (tenant_id) DO UPDATE SET "
    "mode = EXCLUDED.mode, anchor_at = EXCLUDED.anchor_at, "
    "anchored_real_at = clock_timestamp(), set_by = EXCLUDED.set_by, set_at = clock_timestamp()"
)
_RESET_DEMO_CLOCK = text("DELETE FROM firm_demo_clocks WHERE tenant_id = :t")


@dataclass(frozen=True)
class DemoClockRow:
    mode: str
    anchor_at: datetime
    anchored_real_at: datetime


async def demo_clock_row(session: AsyncSession, tenant_id: UUID) -> DemoClockRow | None:
    row = (await session.execute(_DEMO_CLOCK, {"t": tenant_id})).first()
    if row is None:
        return None
    return DemoClockRow(
        str(row.mode), cast(datetime, row.anchor_at), cast(datetime, row.anchored_real_at)
    )


async def set_demo_clock_row(
    session: AsyncSession, tenant_id: UUID, mode: str | None, anchor_at: datetime | None, by: str
) -> None:
    if mode is None:
        await session.execute(_RESET_DEMO_CLOCK, {"t": tenant_id})
        return
    await session.execute(
        _SET_DEMO_CLOCK, {"t": tenant_id, "mode": mode, "anchor_at": anchor_at, "set_by": by}
    )
