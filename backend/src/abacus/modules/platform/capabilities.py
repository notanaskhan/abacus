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
from typing import cast
from uuid import UUID

from abacus.kernel import _flags
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
    my_engagement_roles,
    portal_scopes,
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


async def capabilities(ctx: AuthContext, engagement_id: UUID | None) -> Capabilities:
    """For the firm, or one engagement. A walled or unknown engagement is `NotFound` (404)."""
    resource = (
        Resource.firm(ctx.tenant_id)
        if engagement_id is None
        else await engagement_resource(ctx.tenant, engagement_id)
    )
    allowed = await allowed_actions(ctx, resource)
    member = await member_facts(ctx.tenant, ctx.user_id)
    codes: set[str] = {ctx.firm_role} if ctx.firm_role else set()
    held = await my_engagement_roles(ctx.tenant, ctx.user_id)
    if engagement_id is not None:
        role = held.get(engagement_id)
        if role is not None:
            codes.add(role)
    else:
        codes |= set(held.values())
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
        roles=tuple(Role(c, ROLE_LABELS.get(c, c)) for c in sorted(codes)),
        flags={f.name: await flag(ctx.tenant, f) for f in FLAGS},
        entitlements=tuple(held_modules),
        office_id=member.office_id if member is not None else None,
        tz=await firm_time_zone(ctx.tenant),
        mfa_recent_until=ctx.mfa_at + MFA_RECENT if ctx.mfa_at is not None else None,
        server_now=view.server_now,
        clock_mode=view.clock_mode,
        portal=portal,
    )
