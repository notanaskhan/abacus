"""Service-line policies: who reads a line's content (G-01-T12; G-01 §3.10; DEC-380).

Each of the four lines has one policy per firm: whether the firm offers it, its lead, whether its
content is visible to the engagement team only or to the line's members (read-only; DEC-380,
enforced in `authz` as the `service_line_reader`), and how cross-line work is handled. A line
without a row reads as offered, "Engagement team only" and "Hand-offs only", so no firm is
widened by default. Audit can never be widened (422 `audit_locked`, and 0167's CHECK).

Reading is `firm.read_settings` (a 404 for anyone else, ADR-024); a change is
`service_line_policy.manage` (firm admin or partner, never a security admin: ADR-183 condition
4; fresh MFA), a live person's only (INV-1),
against the line's version (409 `stale_version`). It is audited with codes only, published as
`service_line_policy.changed`, and when the line's reach opens or narrows every active member
holding the line is told their access changed (their next request applies it: AC10.2).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import RowMapping, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.authz import Forbidden, Resource, authorise
from abacus.modules.identity.context import AuthContext
from abacus.modules.identity.events import AccessChanged, ServiceLinePolicyChanged

ServiceLine = Literal["audit", "tax", "cas", "advisory"]
ContentVisibility = Literal["engagement_team_only", "service_line"]
CrossLineAccess = Literal["handoffs_only", "by_request"]

LINES: Final[tuple[ServiceLine, ...]] = ("audit", "tax", "cas", "advisory")
VISIBILITIES: Final[tuple[ContentVisibility, ...]] = ("engagement_team_only", "service_line")
CROSS_LINE: Final[tuple[CrossLineAccess, ...]] = ("handoffs_only", "by_request")
_TARGET: Final = "service_line_policy"
_FOREIGN_KEY_VIOLATION: Final = "23503"


class AuditLocked(DomainInvalid):
    """Audit content is visible to the engagement team only; it can never be widened."""

    code = "audit_locked"


class ServiceLineLeadInvalid(DomainInvalid):
    """The lead must be an active staff member of the firm."""

    code = "service_line_lead_invalid"


# The policy changed since it was read: read it again. No docstring: the error catalogue keeps
# the shared `stale_version` summary.
class StalePolicy(DomainConflict):
    code = "stale_version"


@dataclass(frozen=True)
class Policy:
    service_line: ServiceLine
    enabled: bool
    lead_user_id: UUID | None
    content_visible_to: ContentVisibility
    cross_line_access: CrossLineAccess
    version: int  # 0: no row yet (the defaults)


def _default(line: ServiceLine) -> Policy:
    return Policy(line, True, None, "engagement_team_only", "handoffs_only", 0)


_ROWS = text(
    "SELECT service_line, enabled, lead_user_id, content_visible_to, cross_line_access, version "
    "FROM service_line_policies"
)


def _policy(m: RowMapping) -> Policy:
    return Policy(
        cast(ServiceLine, m["service_line"]),
        bool(m["enabled"]),
        cast(UUID | None, m["lead_user_id"]),
        cast(ContentVisibility, m["content_visible_to"]),
        cast(CrossLineAccess, m["cross_line_access"]),
        cast(int, m["version"]),
    )


async def _read_or_404(ctx: AuthContext) -> None:
    try:
        await authorise(ctx, "firm.read_settings", Resource.firm(ctx.tenant_id))
    except Forbidden:
        raise NotFound("service_line_policy") from None


async def policies(ctx: AuthContext) -> list[Policy]:
    """The four lines in their fixed order, a line without a row at its defaults (AC10.1)."""
    await _read_or_404(ctx)
    async with tenant_session(ctx.tenant) as session:
        stored = {
            p.service_line: p
            for p in map(_policy, (await session.execute(_ROWS)).mappings().all())
        }
    return [stored.get(line, _default(line)) for line in LINES]


def _human(ctx: AuthContext) -> None:
    """INV-1 behind the matrix: only a signed-in person changes who reads a line."""
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden("service_line_policy.manage", "role")


async def set_policy(
    ctx: AuthContext,
    line: ServiceLine,
    *,
    version: int,
    enabled: bool,
    lead_user_id: UUID | None,
    content_visible_to: ContentVisibility,
    cross_line_access: CrossLineAccess,
) -> Policy:
    """AC10.1, AC10.2: one line's policy against its version (0 for a line never saved)."""
    await authorise(ctx, "service_line_policy.manage", Resource.firm(ctx.tenant_id))
    _human(ctx)
    if line == "audit" and content_visible_to != "engagement_team_only":
        raise AuditLocked(facts={"service_line": line})
    async with uow(ctx.tenant) as tx:
        current = (
            (
                await tx.session.execute(
                    text(
                        "SELECT service_line, enabled, lead_user_id, content_visible_to, "
                        "cross_line_access, version FROM service_line_policies "
                        "WHERE service_line = :line FOR UPDATE"
                    ),
                    {"line": line},
                )
            )
            .mappings()
            .first()
        )
        before = _policy(current) if current is not None else _default(line)
        if before.version != version:
            raise StalePolicy(facts={"version": before.version})
        if lead_user_id is not None and not await _active_staff(tx.session, lead_user_id):
            raise ServiceLineLeadInvalid(facts={"field": "lead_user_id"})
        values = {
            "tenant": ctx.tenant_id,
            "line": line,
            "enabled": enabled,
            "lead": lead_user_id,
            "visible": content_visible_to,
            "cross": cross_line_access,
            "by": ctx.user_id,
        }
        try:
            if current is None:
                await tx.session.execute(
                    text(
                        "INSERT INTO service_line_policies (tenant_id, service_line, enabled, "
                        "lead_user_id, content_visible_to, cross_line_access, updated_by) "
                        "VALUES (:tenant, :line, :enabled, :lead, :visible, :cross, :by)"
                    ),
                    values,
                )
            else:
                await tx.session.execute(
                    text(
                        "UPDATE service_line_policies SET enabled = :enabled, "
                        "lead_user_id = :lead, content_visible_to = :visible, "
                        "cross_line_access = :cross, version = version + 1, updated_by = :by, "
                        "updated_at = abacus_now() WHERE service_line = :line"
                    ),
                    values,
                )
        except IntegrityError as exc:
            if getattr(exc.orig, "sqlstate", None) == _FOREIGN_KEY_VIOLATION:
                raise ServiceLineLeadInvalid(facts={"field": "lead_user_id"}) from None
            raise
        after = Policy(
            line,
            enabled,
            lead_user_id,
            content_visible_to,
            cross_line_access,
            before.version + 1,
        )
        tx.record(
            "service_line_policy.updated",
            target=Target(_TARGET, LINES.index(line) + 1),
            after=Ref(
                version=after.version,
                enabled=int(enabled),
                content_visible_to=VISIBILITIES.index(content_visible_to) + 1,
                cross_line_access=CROSS_LINE.index(cross_line_access) + 1,
            ),
        )
        tx.emit(ServiceLinePolicyChanged(service_line=line, version=after.version))
        if _opens(before) != _opens(after):
            for user_id in await _holding(tx.session, line):
                tx.emit(AccessChanged(user_id=user_id))
    return after


def _opens(policy: Policy) -> bool:
    """Whether the line's content reaches its members (the reach `authz` applies)."""
    return (
        policy.service_line != "audit"
        and policy.enabled
        and policy.content_visible_to == "service_line"
    )


async def _active_staff(session: AsyncSession, user_id: UUID) -> bool:
    found = await session.scalar(
        text(
            "SELECT 1 FROM memberships WHERE user_id = :u AND kind = 'staff' AND status = 'active'"
        ),
        {"u": user_id},
    )
    return found is not None


async def _holding(session: AsyncSession, line: ServiceLine) -> list[UUID]:
    rows = await session.execute(
        text(
            "SELECT user_id FROM memberships WHERE kind = 'staff' AND status = 'active' "
            "AND :line = ANY(service_lines) ORDER BY user_id"
        ),
        {"line": line},
    )
    return list(rows.scalars())
