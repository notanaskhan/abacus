"""What the signed-in person may do here, for the UI (F-03-T30; ADR-145; chapter 03 §5.3).

`capabilities(ctx, engagement_id)` evaluates the permission matrix through
`identity.allowed_actions`, which records no authorisation check: the route answers "what could
I do", never "do it". It adds what screens need around that: role labels, flags, entitlements,
office, time zone, the MFA window, business time and, for client users, the portal shell and
scopes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal, cast
from uuid import UUID

from abacus.kernel import _flags
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import Flag, flag
from abacus.modules.identity.api import (
    MFA_RECENT,
    ROLE_LABELS,
    AuthContext,
    GrantScope,
    Resource,
    allowed_actions,
    clock_view,
    engagement_resource,
    firm_time_zone,
    member_facts,
    portal_scopes,
    role_codes,
    walled_from,
)
from abacus.modules.platform.entitlements import MODULES, Module, entitlement

FLAGS: tuple[Flag, ...] = tuple(v for v in vars(_flags).values() if isinstance(v, Flag))


@dataclass(frozen=True)
class Role:
    code: str
    label: str


@dataclass(frozen=True)
class Portal:
    shell: str
    scopes: tuple[GrantScope, ...]


NavAccess = Literal["write", "read", "none"]
# P-01-T04 (SHL-03 admin rows): each settings area's access, from the matrix. `security_center`
# reads `security.manage` (G-02-T02) and `developer_api` stays `none` until G-03 registers
# `developer.read`: an action the matrix doesn't know is never allowed.
_NAV: Final[tuple[tuple[str, str | None, str | None], ...]] = (
    ("firm_settings", "firm.manage_settings", "firm.read_settings"),
    ("users_roles", "firm.manage_users", None),
    ("audit_log", None, "audit_event.read"),
    ("security_center", "security.manage", None),
    ("developer_api", None, None),
)


def nav_access(allowed: frozenset[str]) -> dict[str, NavAccess]:
    def access(write: str | None, read: str | None) -> NavAccess:
        if write is not None and write in allowed:
            return "write"
        if read is not None and read in allowed:
            return "read"
        return "none"

    return {key: access(write, read) for key, write, read in _NAV}


@dataclass(frozen=True)
class Capabilities:
    engagement_id: UUID | None
    capabilities: tuple[str, ...]
    roles: tuple[Role, ...]
    flags: dict[str, bool | str]
    entitlements: tuple[str, ...]
    office_id: UUID | None
    tz: str
    mfa_recent_until: datetime | None
    server_now: datetime
    clock_mode: str
    portal: Portal | None
    nav: dict[str, NavAccess]


async def capabilities(ctx: AuthContext, engagement_id: UUID | None) -> Capabilities:
    """For the firm, or one engagement. A walled or unknown engagement is `NotFound` (404)."""
    resource = (
        Resource.firm(ctx.tenant_id)
        if engagement_id is None
        else await engagement_resource(ctx.tenant, engagement_id)
    )
    # INV-3: a walled engagement answers exactly as an unknown one, so its existence never leaks.
    if resource.client_id is not None and resource.client_id in await walled_from(
        ctx.tenant, ctx.user_id
    ):
        raise NotFound("engagement")
    allowed = await allowed_actions(ctx, resource)
    member = await member_facts(ctx.tenant, ctx.user_id)
    codes = await role_codes(ctx, engagement_id)
    portal: Portal | None = None
    if member is not None and member.client:
        scopes = await portal_scopes(ctx)
        portal = Portal(scopes.shell, scopes.scopes)
    view = await clock_view(ctx.tenant)
    held_modules = [
        m for m in sorted(MODULES) if await entitlement(ctx.tenant, cast(Module, m)) is not None
    ]
    return Capabilities(
        engagement_id=engagement_id,
        capabilities=tuple(sorted(allowed)),
        roles=tuple(Role(c, ROLE_LABELS.get(c, c)) for c in codes),
        flags={f.name: await flag(ctx.tenant, f) for f in FLAGS},
        entitlements=tuple(held_modules),
        office_id=member.office_id if member is not None else None,
        tz=await firm_time_zone(ctx.tenant),
        mfa_recent_until=ctx.mfa_at + MFA_RECENT if ctx.mfa_at is not None else None,
        server_now=view.server_now,
        clock_mode=view.clock_mode,
        portal=portal,
        nav=nav_access(allowed) if engagement_id is None else nav_access(frozenset()),
    )
