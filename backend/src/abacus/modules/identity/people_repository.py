"""People v2's reads and writes (G-01-T05; migration 0142). Firm-level rows only (LIST_EXEMPT:
memberships, invitations and the firm's own overrides; no engagement rows), under the caller's
row-level security. Firm roles and deactivation go through the definers, which keep the firm's
last administrators; sessions are read through definers too (0101's tables are global)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import RowMapping, bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

_MEMBERS = text(
    "SELECT user_id, firm_role, status, role_template, level, job_title, office_id, "
    "service_lines, access_ends_on, offshore, version, revoked_at, revoked_reason, created_at "
    "FROM memberships WHERE kind = 'staff' ORDER BY created_at, user_id"
)
_MEMBER = text(
    "SELECT user_id, firm_role, status, role_template, level, job_title, office_id, "
    "service_lines, access_ends_on, offshore, version, revoked_at, revoked_reason, created_at "
    "FROM memberships WHERE kind = 'staff' AND user_id = :u"
)
_PENDING = text(
    "SELECT id, email, firm_role, role_template, level, office_id, team_ids, service_lines, "
    "access_ends_on, offshore, display_name, job_title, expires_at, created_at "
    "FROM staff_invitations WHERE status = 'pending' AND expires_at > :now "
    "ORDER BY created_at, id"
)


async def staff_rows(session: AsyncSession) -> Sequence[RowMapping]:
    """Every staff membership of the session's firm (active and deactivated)."""
    return (await session.execute(_MEMBERS)).mappings().all()


async def staff_row(session: AsyncSession, user_id: UUID) -> RowMapping | None:
    return (await session.execute(_MEMBER, {"u": user_id})).mappings().first()


async def pending_invitations(session: AsyncSession, now: datetime) -> Sequence[RowMapping]:
    """Live invitations at the firm's business time (a demo clock moves it)."""
    return (await session.execute(_PENDING, {"now": now})).mappings().all()


async def last_sign_ins(session: AsyncSession) -> dict[UUID, datetime]:
    rows = await session.execute(text("SELECT user_id, signed_in_at FROM staff_last_sign_ins()"))
    return {r.user_id: r.signed_in_at for r in rows}


async def sign_in_history(
    session: AsyncSession, user_id: UUID, limit: int
) -> Sequence[RowMapping]:
    result = await session.execute(
        text(
            "SELECT signed_in_at, provider, mfa FROM staff_sign_in_history(:u, :n) "
            "ORDER BY signed_in_at DESC"
        ),
        {"u": user_id, "n": limit},
    )
    return result.mappings().all()


async def active_walls_of(session: AsyncSession, user_id: UUID) -> list[UUID]:
    """The person's own active walls (ADM-02d), oldest first."""
    rows = await session.execute(
        text(
            "SELECT id FROM ethical_walls WHERE user_id = :u AND status = 'active' "
            "ORDER BY created_at, id"
        ),
        {"u": user_id},
    )
    return [r.id for r in rows]


async def assignment_count(session: AsyncSession, user_id: UUID) -> int:
    """Engagements the person is on (engagement roles stay as history after deactivation)."""
    return int(
        await session.scalar(
            text("SELECT count(*) FROM engagement_members WHERE user_id = :u"), {"u": user_id}
        )
        or 0
    )


async def update_attributes(
    session: AsyncSession, user_id: UUID, version: int, values: dict[str, object]
) -> bool:
    """One person's attributes (every one, as merged by the service) against the version read;
    False when it moved or they are no longer active."""
    result = await session.execute(
        text(
            "UPDATE memberships SET job_title = :job_title, office_id = :office_id, "
            "service_lines = :service_lines, access_ends_on = :access_ends_on, "
            "offshore = :offshore, version = version + 1 "
            "WHERE user_id = :u AND kind = 'staff' AND status = 'active' AND version = :v"
        ),
        {**values, "u": user_id, "v": version},
    )
    return bool(getattr(result, "rowcount", 0))


async def set_template(
    session: AsyncSession, user_id: UUID, template: str, level: str | None
) -> None:
    await session.execute(
        text(
            "UPDATE memberships SET role_template = :t, level = :l, version = version + 1 "
            "WHERE user_id = :u AND kind = 'staff' AND status = 'active'"
        ),
        {"u": user_id, "t": template, "l": level},
    )


async def bump_version(session: AsyncSession, user_id: UUID) -> None:
    await session.execute(
        text("UPDATE memberships SET version = version + 1 WHERE user_id = :u AND kind = 'staff'"),
        {"u": user_id},
    )


async def set_firm_role(session: AsyncSession, user_id: UUID, role: str | None) -> str:
    return str(
        await session.scalar(
            text("SELECT membership_set_firm_role(:u, :r)"), {"u": user_id, "r": role}
        )
    )


async def deactivate(
    session: AsyncSession,
    user_id: UUID,
    reason: str,
    on_behalf_of: UUID | None,
    *,
    end_sessions: bool,
) -> str:
    return str(
        await session.scalar(
            text("SELECT membership_deactivate(:u, :r, :b, :end)"),
            {"u": user_id, "r": reason, "b": on_behalf_of, "end": end_sessions},
        )
    )


async def reconcile_template(session: AsyncSession, user_id: UUID) -> None:
    """After a firm-role change: a stored template that implies another firm role is cleared, so
    the person reads the template their new firm role and level imply (`firm_admin` and
    `it_security` imply a firm role; the others imply none)."""
    await session.execute(
        text(
            "UPDATE memberships SET role_template = NULL WHERE user_id = :u AND kind = 'staff' "
            "AND role_template IS NOT NULL AND (CASE role_template "
            "WHEN 'firm_admin' THEN 'firm_admin' WHEN 'it_security' THEN 'security_admin' END) "
            "IS DISTINCT FROM (CASE WHEN firm_role IN ('firm_admin', 'security_admin') "
            "THEN firm_role END)"
        ),
        {"u": user_id},
    )


async def pending_invitations_of(
    session: AsyncSession, user_id: UUID, email: str | None
) -> list[UUID]:
    """Pending invitations the person sent, or (with their email) sent to them; locked."""
    result = await session.execute(
        text(
            "SELECT id FROM staff_invitations WHERE status = 'pending' AND (invited_by = :u "
            "OR (CAST(:e AS text) IS NOT NULL AND lower(email) = lower(CAST(:e AS text)))) "
            "ORDER BY created_at, id FOR UPDATE"
        ),
        {"u": user_id, "e": email},
    )
    return [r.id for r in result]


async def lock_firm(session: AsyncSession) -> bool:
    """Serialise seat checks on the firm's row; whether the firm is synthetic."""
    return bool(await session.scalar(text("SELECT synthetic FROM firms FOR UPDATE")))


async def seats_held(session: AsyncSession, now: datetime, but_email: str | None = None) -> int:
    """Active staff plus live invitations (a pending invitation holds a seat, AC3.4), less a
    live one for `but_email` (an invitation about to be replaced)."""
    return int(
        await session.scalar(
            text(
                "SELECT (SELECT count(*) FROM memberships WHERE kind = 'staff' "
                "AND status = 'active') + (SELECT count(*) FROM staff_invitations "
                "WHERE status = 'pending' AND expires_at > :now "
                "AND (CAST(:e AS text) IS NULL OR lower(email) <> lower(CAST(:e AS text))))"
            ),
            {"now": now, "e": but_email},
        )
        or 0
    )


async def stored_seats(session: AsyncSession) -> int | None:
    value = await session.scalar(
        text("SELECT value FROM firm_settings WHERE section = 'plan' AND key = 'seats'")
    )
    return value if isinstance(value, int) and not isinstance(value, bool) else None


async def inviter_may_invite(session: AsyncSession, user_id: UUID) -> bool:
    """The inviter is still an active firm administrator here."""
    return bool(
        await session.scalar(
            text(
                "SELECT EXISTS (SELECT 1 FROM memberships WHERE user_id = :u AND kind = 'staff' "
                "AND status = 'active' AND firm_role = 'firm_admin')"
            ),
            {"u": user_id},
        )
    )


async def insert_invitation(session: AsyncSession, values: dict[str, object]) -> None:
    await session.execute(
        text(
            "INSERT INTO staff_invitations (id, tenant_id, email, firm_role, invited_by, "
            "expires_at, role_template, level, office_id, team_ids, service_lines, "
            "access_ends_on, offshore, display_name, job_title) VALUES (:id, :tenant_id, :email, "
            ":firm_role, :invited_by, :expires_at, :role_template, :level, :office_id, "
            ":team_ids, :service_lines, :access_ends_on, :offshore, :display_name, :job_title)"
        ),
        values,
    )


async def invitation_terms(session: AsyncSession, invitation_id: UUID) -> RowMapping | None:
    """What an accepted invitation gives the membership (AC3.4)."""
    result = await session.execute(
        text(
            "SELECT role_template, level, office_id, team_ids, service_lines, access_ends_on, "
            "offshore, job_title FROM staff_invitations WHERE id = :id"
        ),
        {"id": invitation_id},
    )
    return result.mappings().first()


_DENIED = text(
    "SELECT action, role FROM firm_policy_overrides WHERE decision = 'deny' AND action IN :actions"
).bindparams(bindparam("actions", expanding=True))


async def denied_overrides(session: AsyncSession, actions: list[str]) -> set[tuple[str, str]]:
    """The firm's stricter-only `deny` overrides on these actions, as (action, role)."""
    if not actions:
        return set()
    return {(r.action, r.role) for r in await session.execute(_DENIED, {"actions": actions})}


def as_date(value: object) -> date | None:
    return value if isinstance(value, date) else None
