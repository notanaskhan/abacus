"""SPEC-002 AC-5 and ADR-026: a walled person cannot read the client's engagement through the
audit explorer either. Held apart from `test_wall_bypass.py`: the explorer reads the firm's whole
trail with no engagement on its rows (SPEC-304), and SPEC-304 says nothing of walls.
"""

from __future__ import annotations

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.uow import Target, uow

from .support import FIRM_ROLES, Env


@pytest.mark.parametrize("role", FIRM_ROLES)
async def test_spec002_ac5_the_audit_explorer_shows_nothing_of_the_walled_engagement(
    env: Env, role: str
) -> None:
    for site in (env.a, env.b):
        async with uow(TenantContext(env.tenant_id, "human", str(env.admin.user_id))) as tx:
            tx.record("engagement.created", target=Target("engagement", site.engagement_id))
    who = await env.walled(role)
    response = await env.get(who, "/v1/firm/audit-events")
    if response.status_code == 403:  # this role does not read the trail at all
        assert env.leaks(response) == []
        return
    assert response.status_code == 200, response.text
    assert env.leaks(response) == []
    assert str(env.b.engagement_id) in response.text
