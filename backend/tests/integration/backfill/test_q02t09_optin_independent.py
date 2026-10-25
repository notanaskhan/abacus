"""Q-02-T09 (TASK-1251): independent acceptance tests for TASK-076, written from SPEC-036 §7 and
Q-02's row, against the app over HTTP and the migrated Postgres.

- AC-3: a firm admin with fresh MFA opts in, and the firm records who, when and the disclosure's
  material version; another role, or a stale MFA, is refused; opting out takes the firm's
  `opted_in` fact back within the same request. With `agents.client_data_optin` off, opting in
  answers 404 and opting out still works (DEC-367).
- AC-6: only the engagement partner excludes an engagement, the change is audited, and every
  route (the fake one too) is refused for it at the boundary.
- Stages: the app can never write an agent's stage (only the platform's command can), and the
  command refuses `live` until the agent has run in shadow (Q-02 row: the first stage is shadow).

Boundary: `create_app()` over HTTP, the migrated Postgres, the gateway's boundary in process.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import cast

import pytest
from sqlalchemy import text

from abacus.ai_gateway.boundary import DataBoundaryRefused, clear_cache, enforce_boundary
from abacus.kernel import provider_terms
from abacus.kernel.config import Route, settings
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.flags import forget_flags
from abacus.kernel.provider_terms import TermsEntry
from abacus.modules.identity.firm_settings import ai_client_data_opted_in
from abacus_tools.agent_stage import StageRefused, set_stage

from .support import Migrated, Net, Seeder

OPT_IN = "/v1/firm/ai-client-data"
TERMS = TermsEntry(
    "bedrock",
    "Amazon Web Services",
    "us-east-1",
    date.today() - timedelta(days=1),
    date.today() + timedelta(days=30),
    material="ab" * 32,  # a SHA-256 hex digest, as the register writes
)


@pytest.fixture
def terms(monkeypatch: pytest.MonkeyPatch) -> TermsEntry:
    """A register entry covering Bedrock today (the committed register may not)."""

    def covering(route: str, on: date) -> TermsEntry | None:
        return TERMS if route == "bedrock" else None

    monkeypatch.setattr(provider_terms, "covering", covering)
    return TERMS


async def _flag(seed: Seeder, tenant: uuid.UUID, on: bool) -> None:
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'agents.client_data_optin', $2, 'test-seed', 'Q-02-T09') "
        "ON CONFLICT (tenant_id, flag) DO UPDATE SET value = EXCLUDED.value",
        tenant,
        "true" if on else "false",
    )
    forget_flags()


async def test_ac3_a_firm_admin_with_fresh_mfa_opts_in_and_out(
    net: Net, seed: Seeder, terms: TermsEntry
) -> None:
    tenant = await seed.firm()
    await _flag(seed, tenant, True)
    admin = await seed.person(tenant, "firm_admin")
    manager = await seed.person(tenant)
    on = await net.call("PUT", OPT_IN, admin, body={"on": True})
    assert on.status_code == 200, on.text
    assert on.json()["current"] is True
    [row] = await seed.rows(
        "SELECT ai_client_data_at, ai_client_data_by, ai_client_data_material FROM firms "
        "WHERE tenant_id = $1",
        tenant,
    )
    assert row["ai_client_data_at"] is not None
    assert row["ai_client_data_by"] == admin.user_id
    assert row["ai_client_data_material"] == terms.material
    firm = TenantContext(tenant, "system", "q02t09")
    assert await ai_client_data_opted_in(firm) is True
    # Another role, and the admin with a stale MFA, are refused.
    assert (await net.call("PUT", OPT_IN, manager, body={"on": False})).status_code == 403
    assert (await net.call("PUT", OPT_IN, admin, body={"on": False}, mfa=False)).status_code == 403
    off = await net.call("PUT", OPT_IN, admin, body={"on": False})
    assert off.status_code == 200 and off.json()["current"] is False
    # The next call for the firm is refused at once: the fact is read again, nothing is cached.
    assert await ai_client_data_opted_in(firm) is False
    actions = {
        r["action"]
        for r in await seed.rows("SELECT action FROM audit_events WHERE tenant_id = $1", tenant)
    }
    assert {"firm.ai_client_data_on", "firm.ai_client_data_off"} <= actions


async def test_ac3_with_the_flag_off_opting_in_is_404_and_opting_out_still_works(
    net: Net, seed: Seeder, terms: TermsEntry
) -> None:
    tenant = await seed.firm()
    await _flag(seed, tenant, True)
    admin = await seed.person(tenant, "firm_admin")
    assert (await net.call("PUT", OPT_IN, admin, body={"on": True})).status_code == 200
    await _flag(seed, tenant, False)
    firm = TenantContext(tenant, "system", "q02t09")
    assert await ai_client_data_opted_in(firm) is False  # the flag off is not opted in
    assert (await net.call("GET", OPT_IN, admin)).status_code == 404
    assert (await net.call("PUT", OPT_IN, admin, body={"on": True})).status_code == 404
    assert (await net.call("PUT", OPT_IN, admin, body={"on": False})).status_code == 200
    stored = await seed.value(
        "SELECT ai_client_data_material FROM firms WHERE tenant_id = $1", tenant
    )
    assert stored is None


async def test_ac6_only_the_partner_excludes_and_every_route_is_refused(
    net: Net, seed: Seeder
) -> None:
    tenant = await seed.firm()
    owner = await seed.person(tenant, "firm_admin")
    site = await seed.site(tenant, owner.user_id, "Granite")
    partner = await seed.person(tenant)
    manager = await seed.person(tenant)
    await seed.member(site, partner, "engagement_partner")
    await seed.member(site, manager, "manager")
    path = f"/v1/engagements/{site.engagement_id}/ai-exclusion"
    body = {"excluded": True, "reason": "Client asked for no AI"}
    assert (await net.call("PUT", path, manager, body=body)).status_code == 403
    done = await net.call("PUT", path, partner, body=body)
    assert done.status_code == 200, done.text
    assert done.json()["excluded"] is True and done.json()["excluded_by"] == str(partner.user_id)
    actions = {
        r["action"]
        for r in await seed.rows("SELECT action FROM audit_events WHERE tenant_id = $1", tenant)
    }
    assert "engagement.ai_excluded" in actions
    clear_cache(tenant)
    firm = TenantContext(tenant, "system", "q02t09")
    for route in ("fake", "bedrock"):
        with pytest.raises(DataBoundaryRefused) as refused:
            await enforce_boundary(
                firm, cast(Route, route), "evidence.screen@v0", engagement_id=site.engagement_id
            )
        assert refused.value.reason == "engagement"
    back = await net.call("PUT", path, partner, body={"excluded": False})
    assert back.status_code == 200 and back.json()["excluded"] is False


async def test_stages_only_the_platform_writes_them_and_live_waits_for_shadow(
    seed: Seeder, migrated_db: Migrated, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenant = await seed.firm()
    firm = TenantContext(tenant, "system", "q02t09")
    with pytest.raises(Exception, match="permission denied"):
        async with tenant_session(firm) as session:
            await session.execute(
                text(
                    "INSERT INTO agent_stages (tenant_id, agent_id, stage, changed_by, note) "
                    "VALUES (:t, 'evidence.screener', 'live', 'app', 'not allowed')"
                ),
                {"t": tenant},
            )
    monkeypatch.setenv("ABACUS_MIGRATIONS_DATABASE_URL", migrated_db.owner_url)
    settings.cache_clear()  # the command reads its database from settings: the test's, not dev
    with pytest.raises(StageRefused, match="shadow runs"):
        await set_stage(tenant, "evidence.screener", "live", "too early")
    await set_stage(tenant, "evidence.screener", "shadow", "first stage")
    stages = await seed.rows(
        "SELECT stage FROM agent_stages WHERE tenant_id = $1 ORDER BY created_at", tenant
    )
    assert [r["stage"] for r in stages] == ["shadow"]
