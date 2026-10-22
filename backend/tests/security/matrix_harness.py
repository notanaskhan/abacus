"""The outcome of `authorise` for one (action, human role), with every layer but the matrix's
satisfied: tenancy, no walls, the role held, independence confirmed, fresh MFA, a reason, no
firm overrides or settings, and no facts registered for the matrix conditions (which therefore
deny, fail closed). Used by the generated `test_permission_matrix_generated.py` (Q-02-T13)."""

from __future__ import annotations

import uuid
from dataclasses import fields
from datetime import UTC, datetime, timedelta
from typing import Literal, cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.identity import authz
from abacus.modules.identity.api import AuthContext, Forbidden, Resource, authorise
from abacus.modules.identity.authz.conditions import LOOKUPS
from abacus.modules.identity.repository import FirmPolicy, FirmRole

FIRM_ROLES = frozenset({"firm_admin", "practice_leader", "quality_partner", "security_admin"})
REASON = "documented in the working paper"
Outcome = Literal["allow", "deny"]


def arrange(monkeypatch: pytest.MonkeyPatch, role: str) -> tuple[AuthContext, Resource]:
    async def none(*_: object) -> frozenset[uuid.UUID]:
        return frozenset()

    async def held(*_: object) -> str | None:
        return None if role in FIRM_ROLES else role

    async def confirmed(*_: object) -> bool:
        return True

    async def policy(*_: object) -> FirmPolicy:
        return FirmPolicy({}, frozenset())

    monkeypatch.setattr(authz, "walled_clients", none)
    monkeypatch.setattr(authz, "engagement_role", held)
    monkeypatch.setattr(authz, "engagement_roles_in_firm", none)
    monkeypatch.setattr(authz, "firm_policy", policy)
    monkeypatch.setattr(authz, "_independence", (None, confirmed))
    for field in fields(LOOKUPS):
        monkeypatch.setattr(LOOKUPS, field.name, None)
    user = uuid.uuid4()
    ctx = AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)),
        user,
        uuid.uuid4(),
        cast(FirmRole | None, role if role in FIRM_ROLES else None),
        datetime.now(UTC) - timedelta(minutes=1),
    )
    if role in FIRM_ROLES:
        return ctx, Resource.firm(ctx.tenant_id)
    return ctx, Resource.engagement(ctx.tenant_id, uuid.uuid4(), archived=False)


async def outcome(monkeypatch: pytest.MonkeyPatch, action: str, role: str) -> Outcome:
    ctx, resource = arrange(monkeypatch, role)
    try:
        await authorise(ctx, action, resource, reason=REASON)
    except Forbidden:
        return "deny"
    return "allow"
