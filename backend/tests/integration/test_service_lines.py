"""G-01-T12 against Postgres (G-01 AC10.1 to AC10.4; DEC-380): service-line policies with Audit
locked, the service-line reader in `authorise` and `visible()`, and `access.changed` when a
line's reach opens or narrows.

Kevin Osei (staff, Tax line) holds no role on a tax engagement. While Tax is "Engagement team
only" he can't read it; once the firm opens Tax to the line he reads it (never writes), and the
list agrees; narrowing Tax again ends it on his next request. Audit never opens; an attest
client's engagement, a wall, an offshore membership and a firm admin's role all keep the reach
out. Another firm's policy changes nothing here.

Expectations come from G-01 section 3.10 and OQ-1's recommendation (DEC-380)."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import cast

import asyncpg
import pytest
from sqlalchemy import select

import abacus.modules.engagements.api  # registers the engagement lookups (line, client, attest)
import abacus.modules.organisations.api
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine, tenant_session
from abacus.kernel.errors import NotFound
from abacus.modules.engagements.models import Engagement
from abacus.modules.identity import service_lines
from abacus.modules.identity.api import AuthContext, Forbidden, Resource, authorise, visible
from abacus.modules.identity.service_lines import (
    AuditLocked,
    ServiceLineLeadInvalid,
    StalePolicy,
)

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

assert abacus.modules.engagements.api
assert abacus.modules.organisations.api


@pytest.fixture(autouse=True)
async def engines(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


def _ctx(
    tenant: uuid.UUID,
    user: uuid.UUID,
    firm_role: str | None,
    *,
    fresh: bool = True,
    kind: str = "human",
) -> AuthContext:
    return AuthContext(
        tenant=TenantContext(tenant, kind, str(user)),  # pyright: ignore[reportArgumentType] -- an actor-kind code
        user_id=user,
        membership_id=uuid.uuid4(),
        firm_role=firm_role,  # pyright: ignore[reportArgumentType] -- a seeded firm role code
        mfa_at=datetime.now(UTC) - timedelta(minutes=1 if fresh else 60),
    )


class Firm:
    def __init__(self, seed: Seeder, tenant: uuid.UUID) -> None:
        self.seed = seed
        self.tenant = tenant

    async def person(
        self,
        *,
        firm_role: str | None = None,
        level: str = "staff",
        lines: list[str] | None = None,
        offshore: bool = False,
    ) -> AuthContext:
        user = cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
                "VALUES ('https://probe.test', $1, $2, 'Probe person') RETURNING id",
                uuid.uuid4().hex,
                f"{uuid.uuid4().hex[:10]}@example.test",
            ),
        )
        await self.seed.run(
            "INSERT INTO memberships (tenant_id, user_id, firm_role, status, level, "
            "service_lines, offshore) VALUES ($1, $2, $3, 'active', $4, $5, $6)",
            self.tenant,
            user,
            firm_role,
            level,
            lines or [],
            offshore,
        )
        return _ctx(self.tenant, user, firm_role)

    async def client(self) -> uuid.UUID:
        return cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO clients (tenant_id, name) VALUES ($1, $2) RETURNING id",
                self.tenant,
                f"Client {uuid.uuid4().hex[:6]}",
            ),
        )

    async def engagement(
        self, client: uuid.UUID, kind: str, by: uuid.UUID, status: str = "active"
    ) -> uuid.UUID:
        entity = await self.seed.value(
            "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, $3) "
            "RETURNING id",
            self.tenant,
            client,
            f"Entity {uuid.uuid4().hex[:6]}",
        )
        engagement = cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, type, "
                "status, fiscal_period_start, fiscal_period_end, created_by) VALUES "
                "($1, $2, $3, $4, $5, $6, '2025-01-01', '2025-12-31', $7) RETURNING id",
                self.tenant,
                client,
                entity,
                f"Engagement {uuid.uuid4().hex[:6]}",
                kind,
                status,
                by,
            ),
        )
        await self.seed.open(self.tenant, engagement)
        return engagement

    async def access_changed(self) -> list[uuid.UUID]:
        rows = await self.seed.rows(
            "SELECT payload FROM outbox WHERE tenant_id = $1 AND event_type = 'access.changed' "
            "ORDER BY occurred_at, id",
            self.tenant,
        )
        payloads = [
            json.loads(r["payload"]) if isinstance(r["payload"], str) else r["payload"]
            for r in rows
        ]
        return [uuid.UUID(str(p["user_id"])) for p in payloads]

    async def audit(self, action: str) -> list[dict[str, object]]:
        rows = await self.seed.rows(
            "SELECT actor_kind, actor_id, target_type, target_id::text AS target_id, "
            "after_ref::text AS after_ref FROM audit_events WHERE tenant_id = $1 AND action = $2 "
            "ORDER BY seq",
            self.tenant,
            action,
        )
        return [dict(r) for r in rows]


@pytest.fixture
async def firm(seed: Seeder) -> Firm:
    tenant = await seed.firm()
    return Firm(seed, tenant)


async def _open(grace: AuthContext, line: str, version: int, *, to: str = "service_line") -> int:
    policy = await service_lines.set_policy(
        grace,
        line,  # pyright: ignore[reportArgumentType] -- a service-line code
        version=version,
        enabled=True,
        lead_user_id=None,
        content_visible_to=to,  # pyright: ignore[reportArgumentType] -- a visibility code
        cross_line_access="handoffs_only",
    )
    return policy.version


async def _reads(ctx: AuthContext, action: str, engagement: uuid.UUID) -> bool:
    try:
        await authorise(
            ctx, action, Resource.engagement(ctx.tenant_id, engagement, archived=False)
        )
    except Forbidden:
        return False
    return True


async def _listed(ctx: AuthContext, action: str) -> set[uuid.UUID]:
    async with tenant_session(ctx.tenant) as session:
        rows = await session.execute(
            select(Engagement.id).where(visible(ctx, action, Engagement.id))
        )
        return set(rows.scalars())


# --- AC10.1: the policies -----------------------------------------------------------------------


async def test_ac10_1_a_firm_without_rows_reads_four_lines_team_only(firm: Firm) -> None:
    grace = await firm.person(firm_role="firm_admin", level="admin")
    found = await service_lines.policies(grace)
    assert [
        (p.service_line, p.content_visible_to, p.cross_line_access, p.version) for p in found
    ] == [
        ("audit", "engagement_team_only", "handoffs_only", 0),
        ("tax", "engagement_team_only", "handoffs_only", 0),
        ("cas", "engagement_team_only", "handoffs_only", 0),
        ("advisory", "engagement_team_only", "handoffs_only", 0),
    ]
    assert all(p.enabled for p in found)


async def test_ac10_1_audit_can_never_be_widened_by_the_api_or_the_database(firm: Firm) -> None:
    grace = await firm.person(firm_role="firm_admin", level="admin")
    with pytest.raises(AuditLocked):
        await _open(grace, "audit", 0)
    # Narrowing (or restating) Audit is fine.
    assert await _open(grace, "audit", 0, to="engagement_team_only") == 1
    with pytest.raises(asyncpg.CheckViolationError):
        # As Grace herself, so the actor trigger passes and only the Audit CHECK can refuse.
        await firm.seed.as_actor(
            firm.tenant,
            ("human", str(grace.user_id)),
            "UPDATE service_line_policies SET content_visible_to = 'service_line' "
            "WHERE tenant_id = $1 AND service_line = 'audit'",
            firm.tenant,
        )
    [audit, *_] = await service_lines.policies(grace)
    assert audit.content_visible_to == "engagement_team_only"


async def test_ac10_1_a_stale_version_answers_409_and_the_change_is_audited(firm: Firm) -> None:
    grace = await firm.person(firm_role="firm_admin", level="admin")
    assert await _open(grace, "tax", 0) == 1
    with pytest.raises(StalePolicy):
        await _open(grace, "tax", 0, to="engagement_team_only")
    assert await _open(grace, "tax", 1, to="engagement_team_only") == 2
    rows = await firm.audit("service_line_policy.updated")
    assert len(rows) == 2
    assert {r["actor_id"] for r in rows} == {str(grace.user_id)}
    assert all("service_line" not in str(r["after_ref"]) for r in rows)  # codes, never words


async def test_ac10_1_the_lead_must_be_the_firms_active_staff(firm: Firm, seed: Seeder) -> None:
    grace = await firm.person(firm_role="firm_admin", level="admin")
    other = Firm(seed, await seed.firm())
    stranger = await other.person(lines=["tax"])
    with pytest.raises(ServiceLineLeadInvalid):
        await service_lines.set_policy(
            grace,
            "tax",
            version=0,
            enabled=True,
            lead_user_id=stranger.user_id,
            content_visible_to="service_line",
            cross_line_access="handoffs_only",
        )
    lead = await firm.person(level="partner", lines=["tax"])
    saved = await service_lines.set_policy(
        grace,
        "tax",
        version=0,
        enabled=True,
        lead_user_id=lead.user_id,
        content_visible_to="service_line",
        cross_line_access="by_request",
    )
    assert (saved.lead_user_id, saved.cross_line_access) == (lead.user_id, "by_request")


async def test_ac10_1_who_reads_and_who_changes_the_policies(firm: Firm) -> None:
    grace = await firm.person(firm_role="firm_admin", level="admin")
    felix = await firm.person(firm_role="security_admin", level="admin")
    daniel = await firm.person(level="partner", lines=["tax"])
    kevin = await firm.person(lines=["tax"])
    assert len(await service_lines.policies(daniel)) == 4  # partners read settings
    with pytest.raises(NotFound):
        await service_lines.policies(kevin)  # ADR-024: nothing to see
    with pytest.raises(Forbidden):
        await _open(kevin, "tax", 0)
    # ADR-183 condition 4 (Ayush, 2026-10-26): a security admin, metadata-only, never opens a
    # line's content to others.
    with pytest.raises(Forbidden):
        await _open(felix, "tax", 0)
    stale = _ctx(firm.tenant, grace.user_id, "firm_admin", fresh=False)
    with pytest.raises(Forbidden):
        await _open(stale, "tax", 0)  # fresh MFA
    agent_like = _ctx(firm.tenant, grace.user_id, "firm_admin", kind="agent")
    with pytest.raises(Forbidden):
        await _open(agent_like, "tax", 0)  # INV-1: a live person only
    assert await _open(daniel, "tax", 0) == 1  # partners manage them (ADR-183 condition 4)
    assert await _open(grace, "tax", 1, to="engagement_team_only") == 2  # and firm admins


# --- AC10.2, AC10.3: the reach -------------------------------------------------------------------


async def test_ac10_2_opening_and_narrowing_tax_applies_on_the_next_request(firm: Firm) -> None:
    grace = await firm.person(firm_role="firm_admin", level="admin")
    kevin = await firm.person(lines=["tax"])
    cas_only = await firm.person(lines=["cas"])
    client = await firm.client()
    tax = await firm.engagement(client, "tax_compliance", grace.user_id)
    assert not await _reads(kevin, "engagement.read", tax)
    assert tax not in await _listed(kevin, "engagement.read")

    version = await _open(grace, "tax", 0)
    assert await _reads(kevin, "engagement.read", tax)
    assert await _reads(kevin, "evidence.read", tax)  # content, read-only
    assert tax in await _listed(kevin, "engagement.read")
    assert tax in await _listed(kevin, "evidence.read")
    assert not await _reads(cas_only, "engagement.read", tax)
    assert tax not in await _listed(cas_only, "engagement.read")
    assert (await firm.access_changed()).count(kevin.user_id) == 1

    await _open(grace, "tax", version, to="engagement_team_only")
    assert not await _reads(kevin, "engagement.read", tax)
    assert tax not in await _listed(kevin, "engagement.read")
    assert (await firm.access_changed()).count(kevin.user_id) == 2
    assert cas_only.user_id not in await firm.access_changed()


async def test_ac10_3_the_reach_never_grants_a_write(firm: Firm) -> None:
    grace = await firm.person(firm_role="firm_admin", level="admin")
    kevin = await firm.person(lines=["tax"])
    tax = await firm.engagement(await firm.client(), "tax_compliance", grace.user_id)
    await _open(grace, "tax", 0)
    assert await _reads(kevin, "engagement.read", tax)
    for write in ("comment.create", "evidence.upload", "follow_up.draft", "follow_up.send"):
        assert not await _reads(kevin, write, tax), write


async def test_ac10_3_audit_attest_clients_walls_offshore_and_admins_stay_out(
    firm: Firm,
) -> None:
    grace = await firm.person(firm_role="firm_admin", level="admin")
    kevin = await firm.person(lines=["tax", "audit"])
    offshore = await firm.person(lines=["tax"], offshore=True)
    admin_in_tax = await firm.person(firm_role="firm_admin", level="admin", lines=["tax"])
    plain = await firm.client()
    tax = await firm.engagement(plain, "tax_compliance", grace.user_id)
    audit = await firm.engagement(await firm.client(), "fs_audit", grace.user_id)
    attest_client = await firm.client()
    await firm.engagement(attest_client, "fs_audit", grace.user_id)
    # The derived flag (DEC-128), set here as its trigger would for an accepted audit.
    await firm.seed.run("UPDATE clients SET is_attest_client = true WHERE id = $1", attest_client)
    attest_tax = await firm.engagement(attest_client, "tax_compliance", grace.user_id)
    walled_client = await firm.client()
    walled_tax = await firm.engagement(walled_client, "tax_compliance", grace.user_id)
    await firm.seed.run(
        "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
        "VALUES ($1, $2, $3, $4)",
        firm.tenant,
        kevin.user_id,
        walled_client,
        grace.user_id,
    )
    await _open(grace, "tax", 0)
    await _open(grace, "audit", 0, to="engagement_team_only")
    assert await _reads(kevin, "engagement.read", tax)
    assert not await _reads(kevin, "engagement.read", audit)
    assert not await _reads(kevin, "engagement.read", attest_tax)
    assert not await _reads(kevin, "engagement.read", walled_tax)
    assert (await _listed(kevin, "engagement.read")) == {tax}
    assert not await _reads(offshore, "engagement.read", tax)
    assert tax not in await _listed(offshore, "evidence.read")
    assert not await _reads(admin_in_tax, "evidence.read", tax)  # metadata only (ADR-024)
    assert tax not in await _listed(admin_in_tax, "evidence.read")


async def test_ac10_3_a_disabled_line_does_not_reach(firm: Firm) -> None:
    grace = await firm.person(firm_role="firm_admin", level="admin")
    kevin = await firm.person(lines=["cas"])
    cas = await firm.engagement(await firm.client(), "cas_monthly_close", grace.user_id)
    await service_lines.set_policy(
        grace,
        "cas",
        version=0,
        enabled=False,
        lead_user_id=None,
        content_visible_to="service_line",
        cross_line_access="handoffs_only",
    )
    assert not await _reads(kevin, "engagement.read", cas)
    assert cas not in await _listed(kevin, "engagement.read")


async def test_another_firms_policy_reaches_nothing_here(firm: Firm, seed: Seeder) -> None:
    grace = await firm.person(firm_role="firm_admin", level="admin")
    kevin = await firm.person(lines=["tax"])
    tax = await firm.engagement(await firm.client(), "tax_compliance", grace.user_id)
    other = Firm(seed, await seed.firm())
    their_admin = await other.person(firm_role="firm_admin", level="admin")
    await _open(their_admin, "tax", 0)
    assert not await _reads(kevin, "engagement.read", tax)
    assert tax not in await _listed(kevin, "engagement.read")
    assert [p.version for p in await service_lines.policies(grace)] == [0, 0, 0, 0]
    # Their reader can't reach this firm's engagement either (tenancy first).
    theirs = await other.person(lines=["tax"])
    assert not await _reads(_ctx(other.tenant, theirs.user_id, None), "engagement.read", tax)


# --- security review fix round (DEC-383) --


async def _member(firm: Firm, engagement: uuid.UUID, who: AuthContext, role: str) -> None:
    await firm.seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES ($1, $2, $3, $4)",
        firm.tenant,
        engagement,
        who.user_id,
        role,
    )


@pytest.mark.parametrize("role", ["client_service", "specialist", "eqr_reviewer"])
async def test_m1_a_team_role_the_read_isnt_granted_to_keeps_the_line_out(
    firm: Firm, role: str
) -> None:
    """ADR-183 rule 6: a team role decides, so Pat's role on E (which the read doesn't grant)
    is not topped up by her open line, in `authorise` and in lists alike."""
    grace = await firm.person(firm_role="firm_admin", level="admin")
    pat = await firm.person(lines=["tax"])
    tax = await firm.engagement(await firm.client(), "tax_compliance", grace.user_id)
    other = await firm.engagement(await firm.client(), "tax_compliance", grace.user_id)
    await _member(firm, tax, pat, role)
    await _open(grace, "tax", 0)
    # DEC-427 (ED-106): an EQR reviewer's role grants evidence.read, so the role decides "allow".
    granted = {"evidence.read"} if role == "eqr_reviewer" else set[str]()
    for action in granted:
        assert await _reads(pat, action, tax), action
    for action in ("engagement.read", "evidence.read", "run_content.read"):
        if action in granted:
            continue
        assert not await _reads(pat, action, tax), action
        assert tax not in await _listed(pat, action), action
        # The line still reaches the tax engagement she holds no role on.
        assert await _reads(pat, action, other), action
        assert other in await _listed(pat, action), action


async def test_m2_the_reach_grants_nothing_at_firm_level(firm: Firm) -> None:
    """The reach is per engagement row only: a line-only member gets no firm-level read, so the
    client search and the firm's knowledge stay as they were before the line opened."""
    from abacus.modules.engagements.service import search_clients

    grace = await firm.person(firm_role="firm_admin", level="admin")
    kevin = await firm.person(lines=["tax"])
    await firm.engagement(await firm.client(), "tax_compliance", grace.user_id)
    actions = ("client.read", "knowledge.read", "retention_policy.read", "engagement.read")

    async def firm_reads() -> list[str]:
        allowed: list[str] = []
        for action in actions:
            try:
                await authorise(kevin, action, Resource.firm(firm.tenant))
            except Forbidden:
                continue
            allowed.append(action)
        return allowed

    before = await firm_reads()
    with pytest.raises(Forbidden):
        await search_clients(kevin, "Client")
    await _open(grace, "tax", 0)
    assert await firm_reads() == before == []
    with pytest.raises(Forbidden):
        await search_clients(kevin, "Client")


async def test_l1_a_firms_staff_override_keeps_the_line_out_of_lists_too(firm: Firm) -> None:
    grace = await firm.person(firm_role="firm_admin", level="admin")
    kevin = await firm.person(lines=["tax"])
    tax = await firm.engagement(await firm.client(), "tax_compliance", grace.user_id)
    await _open(grace, "tax", 0)
    assert tax in await _listed(kevin, "evidence.read")
    await firm.seed.run(
        "INSERT INTO firm_policy_overrides (tenant_id, action, role, decision, reason, set_by) "
        "VALUES ($1, 'evidence.read', 'staff', 'deny', 'stricter', $2)",
        firm.tenant,
        grace.user_id,
    )
    assert not await _reads(kevin, "evidence.read", tax)
    assert tax not in await _listed(kevin, "evidence.read")
    assert tax in await _listed(kevin, "engagement.read")  # only the overridden action narrows


async def test_l2_an_agent_run_never_inherits_the_initiators_line(firm: Firm) -> None:
    from abacus.modules.identity import context
    from abacus.modules.identity.api import AgentContext

    grace = await firm.person(firm_role="firm_admin", level="admin")
    kevin = await firm.person(lines=["tax"])
    tax = await firm.engagement(await firm.client(), "tax_compliance", grace.user_id)
    await _open(grace, "tax", 0)
    assert await _reads(kevin, "evidence.read", tax)
    run_id = uuid.uuid4()
    agent = AgentContext(
        tenant=TenantContext(firm.tenant, "agent", f"agent:evidence.screener:{run_id}"),
        agent_id="evidence.screener",
        agent_run_id=run_id,
        engagement_id=tax,
        task_scope=frozenset({"screening.run", "evidence.read"}),
        initiator=kevin,
        issued_by=context._ISSUER,  # pyright: ignore[reportPrivateUsage] -- an agent run's context
    )
    for action in ("screening.run", "evidence.read"):
        with pytest.raises(Forbidden):
            await authorise(agent, action, Resource.engagement(firm.tenant, tax, archived=False))
    async with tenant_session(agent.tenant) as session:
        rows = await session.execute(
            select(Engagement.id).where(visible(agent, "evidence.read", Engagement.id))
        )
        assert tax not in set(rows.scalars())


async def test_l4_a_policy_row_is_a_live_persons_own(firm: Firm) -> None:
    grace = await firm.person(firm_role="firm_admin", level="admin")
    other = await firm.person(firm_role="firm_admin", level="admin")
    for actor, by in (
        (("agent", f"agent:x:{uuid.uuid4()}"), grace.user_id),
        (("human", str(other.user_id)), grace.user_id),
    ):
        with pytest.raises(asyncpg.PostgresError):
            await firm.seed.as_actor(
                firm.tenant,
                actor,
                "INSERT INTO service_line_policies (tenant_id, service_line, content_visible_to, "
                "updated_by) VALUES ($1, 'tax', 'service_line', $2)",
                firm.tenant,
                by,
            )
    assert await _open(grace, "tax", 0) == 1  # the service's own write is the person's
