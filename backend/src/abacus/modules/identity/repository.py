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
from decimal import Decimal
from typing import Any, Final, Literal, cast, get_args
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    MetaData,
    Numeric,
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
from sqlalchemy.dialects.postgresql import ARRAY
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
    # P-07-T30 (0155): ENG-05's hours, POR-02's team card and when the person joined the team.
    Column("budget_hours", Numeric(7, 1)),
    Column("shown_on_portal", Boolean, nullable=False),
    Column("proposed_at", DateTime(timezone=True)),
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


# G-01-T12 (0167; DEC-380): the lines a firm opened to their members (`visible()`'s reach).
service_line_policies = Table(
    "service_line_policies",
    _metadata,
    Column("tenant_id", PgUUID(as_uuid=True), nullable=False),
    Column("service_line", String, nullable=False),
    Column("enabled", Boolean, nullable=False),
    Column("content_visible_to", String, nullable=False),
)
# A firm's stricter-only overrides (0081): `visible()` keeps the service-line reach out of an
# action whose `staff` cell a firm narrowed (DEC-383).
firm_policy_overrides = Table(
    "firm_policy_overrides",
    _metadata,
    Column("tenant_id", PgUUID(as_uuid=True), nullable=False),
    Column("action", String, nullable=False),
    Column("role", String, nullable=False),
    Column("decision", String, nullable=False),
)
# The person's own membership facts `visible()` reads for the service-line reach (0004, 0142).
memberships = Table(
    "memberships",
    _metadata,
    Column("tenant_id", PgUUID(as_uuid=True), nullable=False),
    Column("user_id", PgUUID(as_uuid=True), nullable=False),
    Column("kind", String, nullable=False),
    Column("status", String, nullable=False),
    Column("level", String, nullable=True),
    Column("firm_role", String, nullable=True),
    Column("offshore", Boolean, nullable=False),
    Column("service_lines", ARRAY(String), nullable=False),
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
    # G-01-T09 (0151): walls v2.
    Column("reason_code", String, nullable=False),
    Column("reason_text", String, nullable=True),
    Column("approver_user_id", PgUUID(as_uuid=True), nullable=True),
    Column("approved_by", PgUUID(as_uuid=True), nullable=True),
    Column("approved_at", DateTime(timezone=True), nullable=True),
    Column("removed_reason", String, nullable=True),
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
    # G-01-T12 (DEC-380): the lines whose content the firm opened to the line's members.
    line_reach: frozenset[str] = frozenset()


_OVERRIDES = text("SELECT action, role, decision FROM firm_policy_overrides")
_SETTINGS_ON = text("SELECT key FROM firm_setting_values WHERE value")
# Audit never opens (0167's CHECK); it is left out here as well.
_LINE_REACH = text(
    "SELECT service_line FROM service_line_policies WHERE enabled "
    "AND content_visible_to = 'service_line' AND service_line <> 'audit'"
)


async def firm_policy(tenant: TenantContext) -> FirmPolicy:
    async with tenant_session(tenant) as session:
        overrides = (await session.execute(_OVERRIDES)).all()
        settings = (await session.execute(_SETTINGS_ON)).scalars().all()
        lines = (await session.execute(_LINE_REACH)).scalars().all()
    return FirmPolicy(
        {(str(row.action), str(row.role)): str(row.decision) for row in overrides},
        frozenset(str(key) for key in settings),
        frozenset(str(line) for line in lines),
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


_OWNERS = text(
    "SELECT DISTINCT user_id FROM client_access_grants WHERE status = 'active' "
    "AND user_id IS NOT NULL AND role IN :roles "
    "AND (expires_at IS NULL OR expires_at > clock_timestamp()) AND ("
    "(scope_kind = 'client' AND scope_id = :client) "
    "OR (scope_kind = 'client_entity' AND scope_id = :entity) "
    "OR (scope_kind = 'engagement' AND scope_id = :engagement)) ORDER BY user_id"
).bindparams(bindparam("roles", expanding=True))


async def owner_holders(
    tenant: TenantContext, client_id: UUID, client_entity_id: UUID, engagement_id: UUID
) -> list[UUID]:
    """A-02-T23: the active, unexpired grants holding the matrix's `client_admin` cells (the
    Owner and the roles that act for the client, DEC-211) on the client, the entity or the
    engagement, by holder (a pending invitation has none)."""
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            _OWNERS,
            {
                "roles": list(GRANT_ROLES_OF["client_admin"]),
                "client": client_id,
                "entity": client_entity_id,
                "engagement": engagement_id,
            },
        )
    return [cast(UUID, r[0]) for r in rows.all()]


_DELEGATE_HOLDERS = text(
    "SELECT DISTINCT user_id FROM client_access_grants WHERE id IN :ids "
    "AND status = 'active' AND user_id IS NOT NULL AND role IN ('third_party', 'delegate') "
    "AND scope_kind = 'request_item' AND scope_id = :item "
    "AND (expires_at IS NULL OR expires_at > clock_timestamp())"
).bindparams(bindparam("ids", expanding=True))


async def delegate_holders(
    tenant: TenantContext, item_id: UUID, grant_ids: Sequence[UUID]
) -> frozenset[UUID]:
    """R-01-T13: of these grants, the holders of active, unexpired delegate grants on the item."""
    if not grant_ids:
        return frozenset()
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            _DELEGATE_HOLDERS, {"ids": sorted(set(grant_ids), key=str), "item": item_id}
        )
    return frozenset(cast(UUID, r[0]) for r in rows.all())


_DELEGATE_GRANTS = text(
    "SELECT id, user_id, scope_id FROM client_access_grants WHERE id IN :ids "
    "AND status = 'active' AND user_id IS NOT NULL AND role IN ('third_party', 'delegate') "
    "AND scope_kind = 'request_item' "
    "AND (expires_at IS NULL OR expires_at > clock_timestamp())"
).bindparams(bindparam("ids", expanding=True))


async def delegate_grant_holders(
    tenant: TenantContext, grant_ids: Sequence[UUID]
) -> dict[UUID, tuple[UUID, UUID]]:
    """R-01-T13 (security review L2): of these grants, the active, unexpired delegate grants,
    each grant id -> (holder, the request item it is on), in one query."""
    if not grant_ids:
        return {}
    async with tenant_session(tenant) as session:
        rows = await session.execute(_DELEGATE_GRANTS, {"ids": sorted(set(grant_ids), key=str)})
    return {cast(UUID, r[0]): (cast(UUID, r[1]), cast(UUID, r[2])) for r in rows.all()}


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


@dataclass(frozen=True)
class MemberDetail:
    """A firm team row with ENG-05's extras (P-07-T30)."""

    user_id: UUID
    role: EngagementRole
    budget_hours: Decimal | None
    shown_on_portal: bool
    proposed_at: datetime | None


async def member_details_of(tenant: TenantContext, engagement_id: UUID) -> list[MemberDetail]:
    """An engagement's firm team with hours, the portal flag and when each joined, for a caller
    that authorised a read of the engagement (P-07-T30; LIST_EXEMPT)."""
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                select(
                    engagement_members.c.user_id,
                    engagement_members.c.role,
                    engagement_members.c.budget_hours,
                    engagement_members.c.shown_on_portal,
                    engagement_members.c.proposed_at,
                )
                .where(engagement_members.c.engagement_id == engagement_id)
                .where(engagement_members.c.role.in_(sorted(ENGAGEMENT_ROLES)))
                .order_by(engagement_members.c.role, engagement_members.c.user_id)
            )
        ).all()
    return [
        MemberDetail(
            cast(UUID, r.user_id),
            cast(EngagementRole, r.role),
            cast(Decimal | None, r.budget_hours),
            bool(r.shown_on_portal),
            cast(datetime | None, r.proposed_at),
        )
        for r in rows
    ]


async def roles_ever_held(tenant: TenantContext, user_id: UUID) -> list[tuple[UUID, str]]:
    """Every (engagement, role) a person has held in the firm, from the insert-only membership
    history (0155): what they are now, and what they were before any later change or removal
    (P-07-T30 security review; LIST_EXEMPT: one person's own facts, never listed to a caller)."""
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT DISTINCT engagement_id, role FROM engagement_member_events "
                    "WHERE user_id = :u"
                ),
                {"u": user_id},
            )
        ).all()
    return [(cast(UUID, r.engagement_id), str(r.role)) for r in rows]


async def set_member_columns(
    session: AsyncSession, engagement_id: UUID, user_id: UUID, values: dict[str, object]
) -> bool:
    """Set `budget_hours` or `shown_on_portal` on a firm team row; False if there is no such
    row. Only those two columns are the app's to update (0155)."""
    if not values or set(values) - {"budget_hours", "shown_on_portal"}:
        raise ValueError("only budget_hours and shown_on_portal are updatable")
    found = await session.execute(
        update(engagement_members)
        .where(engagement_members.c.engagement_id == engagement_id)
        .where(engagement_members.c.user_id == user_id)
        .where(engagement_members.c.role.in_(sorted(ENGAGEMENT_ROLES)))
        .values(**values)
        .returning(engagement_members.c.user_id)
    )
    return found.scalar_one_or_none() is not None


async def display_names(user_ids: list[UUID]) -> dict[UUID, str]:
    """Names for users already known to belong to the tenant (IDs read under RLS by the caller)."""
    if not user_ids:
        return {}
    async with identity_engine().connect() as conn:
        rows = (await conn.execute(_USER_NAMES, {"ids": user_ids})).all()
    return {cast(UUID, row.id): str(row.display_name) for row in rows}


async def walled_clients(tenant: TenantContext, user_id: UUID) -> frozenset[UUID]:
    """The clients this person is walled off from now (active walls)."""
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            select(ethical_walls.c.client_id).where(
                ethical_walls.c.user_id == user_id, ethical_walls.c.status == "active"
            )
        )
        return frozenset(cast(UUID, client) for client in rows.scalars().all())


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


async def active_quality_partners(tenant: TenantContext) -> list[UUID]:
    """P-07-T47 (security review M3): the firm's active quality owners, who approve an EQR's
    eligibility (`eqr.approve_eligibility`), under the tenant."""
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            text(
                "SELECT user_id FROM memberships WHERE firm_role = 'quality_partner' "
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
            "invited_by, expires_at, kind, contact_id, grant_template, terms_version, terms_url, "
            "grant_ids) "
            "VALUES (:id, :tenant_id, :engagement_id, :email, :role, :invited_by, "
            "clock_timestamp() + make_interval(days => :days), :kind, :contact_id, "
            "CAST(:grant_template AS jsonb), :terms_version, :terms_url, "
            "CAST(:grant_ids AS uuid[]))"
        ),
        {
            "kind": "firm_invite",
            "contact_id": None,
            "grant_template": None,
            "terms_version": None,
            "terms_url": None,
            "grant_ids": None,
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
        "kind, contact_id, grant_template, terms_version, terms_url, grant_ids, used_at, "
        "(status = 'pending' AND expires_at > clock_timestamp()) AS live "
        "FROM client_invitations WHERE id = :id"
    )
    locked = text(
        "SELECT id, engagement_id, email, role, invited_by, status, expires_at, created_at, "
        "kind, contact_id, grant_template, terms_version, terms_url, grant_ids, used_at, "
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
            "accepted_at = clock_timestamp(), used_at = clock_timestamp(), "
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


async def count_invitation_renewal(
    session: AsyncSession, invitation_id: UUID, most: int
) -> int | None:
    """P-08-T21 (AC-14): one more recipient renewal of an expired pending invitation, below
    `most`; the new count, or None when it may not be renewed."""
    return await session.scalar(
        text(
            "UPDATE client_invitations SET renewal_count = renewal_count + 1 "
            "WHERE id = :id AND status = 'pending' AND expires_at <= clock_timestamp() "
            "AND renewal_count < :most RETURNING renewal_count"
        ),
        {"id": invitation_id, "most": most},
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
    session: AsyncSession, engagement_id: UUID, client_id: UUID, *, offshore_consented: bool
) -> list[UUID]:
    """Active staff of the firm, not on the team, not walled from the engagement's client, and
    not offshore unless an offshore-disclosure consent covers the client (`offshore_consented`,
    from `offshore.offshore_consented`; DEC-52, TASK-1207 review)."""
    rows = await session.execute(
        text(
            "SELECT m.user_id FROM memberships m WHERE m.kind = 'staff' AND m.status = 'active' "
            "AND (:offshore_ok OR NOT m.offshore) "
            "AND NOT EXISTS (SELECT 1 FROM engagement_members em WHERE em.engagement_id = :e "
            "AND em.user_id = m.user_id) AND NOT EXISTS (SELECT 1 FROM ethical_walls w "
            "WHERE w.user_id = m.user_id AND w.client_id = :c AND w.status = 'active') "
            "ORDER BY m.user_id"
        ),
        {"e": engagement_id, "c": client_id, "offshore_ok": offshore_consented},
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


async def firm_tenant_ids() -> list[UUID]:
    """G-01-T13 (DEC-381): every firm's id, for the hourly access-end job, which then works
    inside each firm's own session. Through the identity role, which already reads
    `firms.tenant_id` (no other column, and no new grant); identifiers only (LIST-001 does not
    apply: a platform job, no person's list)."""
    async with identity_engine().connect() as conn:
        result = await conn.execute(text("SELECT tenant_id FROM firms ORDER BY tenant_id"))
        return [cast(UUID, r[0]) for r in result]


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


# --- Contact invitations and pending grants (P-07-T25; DEC-300) ---------------------------------


@dataclass(frozen=True)
class ContactGrantRow:
    """A grant made for a contact: pending (no person yet), active or revoked."""

    id: UUID
    user_id: UUID | None
    contact_id: UUID
    role: str
    scope_kind: str
    scope_id: UUID
    status: str
    created_at: datetime
    granted_by: UUID | None


_CONTACT_GRANTS = text(
    "SELECT id, user_id, contact_id, role, scope_kind, scope_id, status, created_at, granted_by "
    "FROM client_access_grants WHERE contact_id IN :ids ORDER BY created_at, scope_kind, scope_id"
).bindparams(bindparam("ids", expanding=True))
_GRANTS_BY_ID = text(
    "SELECT id, user_id, contact_id, role, scope_kind, scope_id, status, created_at, granted_by "
    "FROM client_access_grants WHERE id IN :ids ORDER BY created_at, scope_kind, scope_id"
).bindparams(bindparam("ids", expanding=True))
_GRANTS_BY_ID_LOCKED = text(
    "SELECT id, user_id, contact_id, role, scope_kind, scope_id, status, created_at, granted_by "
    "FROM client_access_grants WHERE id IN :ids ORDER BY created_at, scope_kind, scope_id "
    "FOR UPDATE"
).bindparams(bindparam("ids", expanding=True))
_CONTACT_INVITATIONS = text(
    "SELECT id, engagement_id, contact_id, email, status, expires_at, created_at, "
    "grant_ids, invited_by, (status = 'pending' AND expires_at > clock_timestamp()) AS live "
    "FROM client_invitations WHERE contact_id IN :ids ORDER BY created_at DESC, id"
).bindparams(bindparam("ids", expanding=True))
_CONTACT_INVITATIONS_LOCKED = text(
    "SELECT id, engagement_id, contact_id, email, status, expires_at, created_at, "
    "grant_ids, invited_by, (status = 'pending' AND expires_at > clock_timestamp()) AS live "
    "FROM client_invitations WHERE contact_id IN :ids ORDER BY created_at DESC, id FOR UPDATE"
).bindparams(bindparam("ids", expanding=True))


def _contact_grant(row: Row[Any]) -> ContactGrantRow:  # Any: a text() row's columns are untyped
    return ContactGrantRow(
        cast(UUID, row.id),
        cast(UUID | None, row.user_id),
        cast(UUID, row.contact_id),
        str(row.role),
        str(row.scope_kind),
        cast(UUID, row.scope_id),
        str(row.status),
        cast(datetime, row.created_at),
        cast(UUID | None, row.granted_by),
    )


async def contact_grants(
    session: AsyncSession, contact_ids: Sequence[UUID]
) -> list[ContactGrantRow]:
    """Every grant made for these contacts, oldest first."""
    if not contact_ids:
        return []
    rows = await session.execute(_CONTACT_GRANTS, {"ids": list(contact_ids)})
    return [_contact_grant(r) for r in rows.all()]


async def grants_by_id(
    session: AsyncSession, grant_ids: Sequence[UUID], *, lock: bool = False
) -> list[ContactGrantRow]:
    if not grant_ids:
        return []
    statement = _GRANTS_BY_ID_LOCKED if lock else _GRANTS_BY_ID
    rows = await session.execute(statement, {"ids": list(grant_ids)})
    return [_contact_grant(r) for r in rows.all()]


async def insert_pending_grant(session: AsyncSession, values: dict[str, object]) -> UUID:
    """A grant waiting for its contact's first sign-in: no person, status `pending`."""
    found = await session.scalar(
        text(
            "INSERT INTO client_access_grants (tenant_id, user_id, contact_id, role, scope_kind, "
            "scope_id, granted_by, status) VALUES (:tenant_id, NULL, :contact_id, :role, "
            ":scope_kind, :scope_id, :granted_by, 'pending') RETURNING id"
        ),
        values,
    )
    return cast(UUID, found)


async def activate_grant(session: AsyncSession, grant_id: UUID, user_id: UUID) -> bool:
    """The pending grant becomes the person's (once: `client_access_grants_bind`)."""
    row = (
        await session.execute(
            text(
                "UPDATE client_access_grants SET user_id = :user, status = 'active' "
                "WHERE id = :id AND status = 'pending' AND user_id IS NULL RETURNING id"
            ),
            {"id": grant_id, "user": user_id},
        )
    ).first()
    return row is not None


async def held_grant(
    session: AsyncSession, user_id: UUID, role: str, scope_kind: str, scope_id: UUID
) -> tuple[UUID, str] | None:
    """The person's one row for this role on this scope (unique per firm), whatever its status:
    its id and status, locked, or None."""
    row = (
        await session.execute(
            text(
                "SELECT id, status FROM client_access_grants WHERE user_id = :user "
                "AND role = :role AND scope_kind = :kind AND scope_id = :scope FOR UPDATE"
            ),
            {"user": user_id, "role": role, "kind": scope_kind, "scope": scope_id},
        )
    ).first()
    return None if row is None else (cast(UUID, row[0]), str(row[1]))


async def contact_invitations(
    session: AsyncSession, contact_ids: Sequence[UUID], *, lock: bool = False
) -> list[RowMapping]:
    """The contacts' invitations, newest first."""
    if not contact_ids:
        return []
    statement = _CONTACT_INVITATIONS_LOCKED if lock else _CONTACT_INVITATIONS
    rows = await session.execute(statement, {"ids": list(contact_ids)})
    return list(rows.mappings().all())


async def set_invitation_grants(
    session: AsyncSession, invitation_id: UUID, grant_ids: Sequence[UUID]
) -> None:
    await session.execute(
        text(
            "UPDATE client_invitations SET grant_ids = CAST(:ids AS uuid[]) "
            "WHERE id = :id AND status = 'pending'"
        ),
        {"id": invitation_id, "ids": list(grant_ids)},
    )


async def unlock_sign_in(session: AsyncSession, email: str) -> bool:
    """The firm's portal sign-in lock on this address cleared; whether there was one."""
    return bool(
        await session.scalar(text("SELECT portal_sign_in_unlock(:email)"), {"email": email})
    )


async def locked_emails(session: AsyncSession, emails: Sequence[str]) -> set[str]:
    """Which of these addresses the firm's portal has locked now (lower-cased)."""
    if not emails:
        return set()
    rows = await session.execute(
        text("SELECT * FROM portal_sign_in_locked(CAST(:emails AS text[]))"),
        {"emails": list(emails)},
    )
    return {str(r[0]) for r in rows.all()}


async def end_portal_access(
    session: AsyncSession, tenant_id: UUID, user_id: UUID
) -> list[Any]:  # Any: a text() row's columns are untyped
    """The person's portal sessions and trusted devices in the firm, ended now (0133)."""
    rows = await session.execute(
        text("SELECT * FROM portal_access_revoke(:tenant, :user)"),
        {"tenant": tenant_id, "user": user_id},
    )
    return list(rows.all())


async def insert_grant_event_of(
    session: AsyncSession, grant_id: UUID, event: str, by: UUID | None
) -> None:
    """A grant's event row in the grant's own firm (a caller that holds no tenant id)."""
    await session.execute(
        text(
            "INSERT INTO client_access_events (tenant_id, grant_id, event, by_user_id) "
            "SELECT tenant_id, id, :event, :by FROM client_access_grants WHERE id = :id"
        ),
        {"id": grant_id, "event": event, "by": by},
    )
