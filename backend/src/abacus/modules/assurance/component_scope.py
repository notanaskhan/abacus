"""Component scope (A-09-T21; A-09 §3 F6; SPEC-658; POR-23; DEC-63, DEC-35; DEC-5314; red).

A component auditor's grant (`component_auditor` on scope kind `component`, to a named contact)
reaches exactly one component's room:

- **The resolver** gives a component scope its client and engagement but a work item no other
  resource carries (the component's own id), so `scope_only` on any engagement-wide resource
  never passes for it: the consolidation, the group audit's papers and every other component
  answer 404 (INV-3, INV-4).
- **The room guard** (`require_room`): the person's active component grants name the component,
  or 404.
- **The message rule** (`foreign_figures`): a message to a component auditor that names a figure
  of another component (in whole cents, as written) is refused; its own component's figures and
  small counts pass. Code, never a model (ADR-065).

Revocation is the grant's own status (archive or expiry sets it; `active_grants` reads only
active, unexpired grants).
"""

from __future__ import annotations

import re
from collections.abc import Collection
from decimal import Decimal, InvalidOperation
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.modules.identity.api import AuthContext, ScopeFacts, portal_scopes

ROLE: Final = "component_auditor"
KIND: Final = "component"
SMALL_CENTS: Final = 100 * 100
_AMOUNT: Final = re.compile(r"(?<![\w.])\$?\s?(\d{1,3}(?:,\d{3})+|\d+)(\.\d{1,2})?\b")
_FACTS: Final = text("SELECT engagement_id FROM components WHERE id = :c")


async def component_scope(tenant: TenantContext, component_id: UUID) -> ScopeFacts | None:
    async with tenant_session(tenant) as session:
        engagement = await session.scalar(_FACTS, {"c": component_id})
    if engagement is None:
        return None
    from abacus.modules.engagements.api import client_of

    client = await client_of(tenant, engagement)
    if client is None:
        return None
    # The component's own id as the work item: nothing but the room's own routes matches it.
    return ScopeFacts(client_id=client, engagement_id=None, work_item_id=component_id)


async def component_ids(ctx: AuthContext) -> frozenset[UUID]:
    """The components the person's active component-auditor grants name."""
    if not ctx.client:
        return frozenset()
    scopes = await portal_scopes(ctx)
    return frozenset(s.scope_id for s in scopes.scopes if s.role == ROLE and s.scope_kind == KIND)


async def require_room(ctx: AuthContext, component_id: UUID) -> UUID:
    if component_id not in await component_ids(ctx):
        raise NotFound("component_room")
    return component_id


def _cents(match: re.Match[str]) -> int | None:
    try:
        whole = Decimal(match.group(1).replace(",", ""))
        frac = Decimal(match.group(2)) if match.group(2) else Decimal(0)
    except InvalidOperation:
        return None
    return int((whole + frac) * 100)


def foreign_figures(text_in: str, own: Collection[int], others: Collection[int]) -> list[int]:
    """The figures (in cents) the text names that belong to another component and not to this
    one; under 100.00 they are counts or days and pass."""
    found: list[int] = []
    for match in _AMOUNT.finditer(text_in):
        cents = _cents(match)
        if cents is None or cents < SMALL_CENTS or cents in own:
            continue
        if cents in others:
            found.append(cents)
    return sorted(set(found))
