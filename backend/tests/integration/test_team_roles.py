"""ENG-05 team and roles against Postgres (P-07-T30; SPEC-332; P-07 §3.5 Story 5.2; DEC-327):
"Thomas Whitcombe is ineligible as Fairhaven's EQR for cooling-off and Margaret Okonkwo cannot
approve EQR eligibility on Margaret's own engagement." Also: the EQR is never on the team; the
EP's team approval and the changes-since facts; hours and the portal flag; confirmation
requests; the insert-only rows refuse an agent and any change at the database."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal

import asyncpg
import pytest

import abacus.modules.evidence.api as _evidence  # registers the member-removed handler
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.errors import DomainInvalid, NotFound
from abacus.modules.engagements import team as team_model
from abacus.modules.engagements.service import add_to_team, change_team_role
from abacus.modules.engagements.team_errors import (
    EqrApprovalRequired,
    EqrApproverIsEp,
    EqrApproverOnEngagement,
    EqrNotEligible,
    EqrOnTeam,
    TeamChanged,
)
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.identity.repository import FirmRole

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
assert _evidence


class _Firm:
    def __init__(self, seed: Seeder) -> None:
        self.seed = seed
        self.tenant = uuid.uuid4()
        self.firm_roles: dict[uuid.UUID, FirmRole | None] = {}

    async def user(self, name: str, firm_role: FirmRole | None = None) -> uuid.UUID:
        user = uuid.UUID(
            str(
                await self.seed.value(
                    "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
                    "VALUES ('https://probe.test', $1, $2, $3) RETURNING id",
                    uuid.uuid4().hex,
                    f"{uuid.uuid4().hex}@example.test",
                    name,
                )
            )
        )
        await self.seed.run(
            "INSERT INTO memberships (tenant_id, user_id, firm_role, status) "
            "VALUES ($1, $2, $3, 'active')",
            self.tenant,
            user,
            firm_role,
        )
        self.firm_roles[user] = firm_role
        return user

    async def make(self) -> _Firm:
        await self.seed.run(
            "INSERT INTO firms (tenant_id, name) VALUES ($1, 'Brightwater Hale')", self.tenant
        )
        # Margaret is the engagement partner and also holds the firm's quality role, so only
        # the EP rule (not the matrix) can refuse her the eligibility approval.
        self.margaret = await self.user("Margaret Okonkwo", "quality_partner")
        self.thomas = await self.user("Thomas Whitcombe")
        self.celia = await self.user("Celia Marsh", "quality_partner")
        self.quinn = await self.user("Quinn Avery", "quality_partner")
        self.rosa = await self.user("Rosa Lindqvist", "quality_partner")
        self.hannah = await self.user("Hannah Leclerc")
        self.kira = await self.user("Kira Ross")
        self.client = await self.seed.value(
            "INSERT INTO clients (tenant_id, name) VALUES ($1, 'Fairhaven') RETURNING id",
            self.tenant,
        )
        self.entity = await self.seed.value(
            "INSERT INTO client_entities (tenant_id, client_id, name) "
            "VALUES ($1, $2, 'Fairhaven Plan') RETURNING id",
            self.tenant,
            self.client,
        )
        self.py2024 = await self.engagement(2024, self.thomas)
        self.py2025 = await self.engagement(2025, self.margaret)
        await self.member(self.py2025, self.hannah, "manager")
        return self

    async def engagement(self, year: int, partner: uuid.UUID) -> uuid.UUID:
        engagement = uuid.UUID(
            str(
                await self.seed.value(
                    "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
                    "fiscal_period_start, fiscal_period_end, created_by, type) "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7, 'ebp_audit') RETURNING id",
                    self.tenant,
                    self.client,
                    self.entity,
                    f"PY{year} EBP Audit",
                    datetime(year, 1, 1).date(),
                    datetime(year, 12, 31).date(),
                    partner,
                )
            )
        )
        await self.member(engagement, partner, "engagement_partner")
        return engagement

    async def member(self, engagement: uuid.UUID, user: uuid.UUID, role: str) -> None:
        await self.seed.run(
            "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
            "VALUES ($1, $2, $3, $4)",
            self.tenant,
            engagement,
            user,
            role,
        )

    def ctx(self, user: uuid.UUID, *, client: bool = False, mfa: bool = True) -> AuthContext:
        tenant = TenantContext(self.tenant, "human", str(user))
        at = datetime.now(UTC) if mfa else None
        role = self.firm_roles[user]
        return AuthContext(tenant, user, uuid.uuid4(), role, at, client=client)

    async def cleared(self, candidate: uuid.UUID) -> None:
        """Rosa, a quality owner with no role on PY2025, approves the candidate's eligibility
        (their competence has no history here, so assignment needs it)."""
        await team_model.approve_eqr_eligibility(self.ctx(self.rosa), self.py2025, candidate)

    async def approve(self, user: uuid.UUID) -> team_model.TeamApproval:
        seen = await team_model.team_approval(self.ctx(user), self.py2025)
        return await team_model.approve_team(self.ctx(user), self.py2025, seen.member_set_hash)

    async def count(self, sql: str, *args: object) -> int:
        return int(str(await self.seed.value(sql, *args)))

    async def audited(self, action: str) -> int:
        return await self.count(
            "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND action = $2",
            self.tenant,
            action,
        )

    async def role_of(self, engagement: uuid.UUID, user: uuid.UUID) -> str | None:
        found = await self.seed.value(
            "SELECT role FROM engagement_members WHERE engagement_id = $1 AND user_id = $2",
            engagement,
            user,
        )
        return None if found is None else str(found)


@pytest.fixture
async def firm(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[_Firm]:
    # Fresh pools on this test's event loop; display names come through the identity engine.
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield await _Firm(Seeder(migrated_db.superuser_dsn)).make()
    await dispose_engine()
    settings.cache_clear()


def _check(candidate: team_model.Candidate, code: str) -> team_model.Check:
    return next(c for c in candidate.checks if c.code == code)


async def test_ac_thomas_whitcombe_is_not_eligible_as_fairhavens_eqr_for_cooling_off(
    firm: _Firm,
) -> None:
    found = {
        c.user_id: c for c in await team_model.eqr_candidates(firm.ctx(firm.hannah), firm.py2025)
    }
    thomas = found[firm.thomas]
    assert thomas.eligibility == "not_eligible"
    assert _check(thomas, "cooling_off") == team_model.Check("cooling_off", "fail", year=2024)
    assert _check(thomas, "competence").count == 1  # EP on the PY2024 audit
    celia = found[firm.celia]
    assert celia.eligibility == "eligible"
    assert [c.result for c in celia.checks] == [
        "pass",
        "pass",
        "not_assessed",
        "pending",
        "not_assessed",
    ]
    assert firm.margaret not in found and firm.hannah not in found  # on the engagement already
    with pytest.raises(EqrNotEligible) as refused:
        await team_model.assign_eqr(firm.ctx(firm.hannah), firm.py2025, firm.thomas)
    assert refused.value.facts == {"cooling_off": "fail"}
    assert await firm.role_of(firm.py2025, firm.thomas) is None
    with pytest.raises(EqrApprovalRequired):  # competence not assessed: the quality owner first
        await team_model.assign_eqr(firm.ctx(firm.hannah), firm.py2025, firm.celia)
    await firm.cleared(firm.celia)
    await team_model.assign_eqr(firm.ctx(firm.hannah), firm.py2025, firm.celia)
    assert await firm.role_of(firm.py2025, firm.celia) == "eqr_reviewer"
    assert await firm.audited("eqr.assigned") == 1
    assert (
        await firm.count(
            "SELECT count(*) FROM independence_confirmations WHERE engagement_id = $1 "
            "AND user_id = $2 AND status = 'requested'",
            firm.py2025,
            firm.celia,
        )
        == 1
    )


async def test_ac_margaret_okonkwo_cannot_approve_eqr_eligibility_on_her_own_engagement(
    firm: _Firm,
) -> None:
    with pytest.raises(EqrApproverIsEp):
        await team_model.approve_eqr_eligibility(firm.ctx(firm.margaret), firm.py2025, firm.celia)
    with pytest.raises(DomainInvalid):  # never the candidate themself
        await team_model.approve_eqr_eligibility(firm.ctx(firm.celia), firm.py2025, firm.celia)
    with pytest.raises(Forbidden):  # the manager holds no quality role
        await team_model.approve_eqr_eligibility(firm.ctx(firm.hannah), firm.py2025, firm.celia)
    assert (
        await firm.count(
            "SELECT count(*) FROM eqr_eligibility_approvals WHERE tenant_id = $1", firm.tenant
        )
        == 0
    )
    approval = await team_model.approve_eqr_eligibility(
        firm.ctx(firm.quinn), firm.py2025, firm.celia
    )
    assert approval.result == "eligible" and approval.approved_by == firm.quinn
    refused = await team_model.approve_eqr_eligibility(
        firm.ctx(firm.quinn), firm.py2025, firm.thomas
    )
    assert refused.result == "not_eligible"  # recorded as not eligible, never assigned
    rows = await firm.seed.rows(
        "SELECT result, actor_kind, checks FROM eqr_eligibility_approvals WHERE tenant_id = $1 "
        "ORDER BY approved_at",
        firm.tenant,
    )
    assert [(r["result"], r["actor_kind"]) for r in rows] == [
        ("eligible", "human"),
        ("not_eligible", "human"),
    ]
    assert await firm.audited("eqr.eligibility_approved") == 2


async def test_the_eqr_is_never_on_the_team(firm: _Firm) -> None:
    with pytest.raises(EqrOnTeam):  # the manager holds a team role
        await team_model.assign_eqr(firm.ctx(firm.margaret), firm.py2025, firm.hannah)
    await firm.cleared(firm.celia)
    await team_model.assign_eqr(firm.ctx(firm.margaret), firm.py2025, firm.celia)
    with pytest.raises(EqrOnTeam):  # and the EQR takes no team role
        await change_team_role(firm.ctx(firm.margaret), firm.py2025, firm.celia, "senior")
    # Replacing the EQR: Celia leaves the engagement, Quinn joins as EQR.
    await firm.cleared(firm.quinn)
    await team_model.assign_eqr(firm.ctx(firm.margaret), firm.py2025, firm.quinn)
    assert await firm.role_of(firm.py2025, firm.celia) is None
    assert await firm.role_of(firm.py2025, firm.quinn) == "eqr_reviewer"
    roster = await team_model.team_of(firm.ctx(firm.hannah), firm.py2025)
    assert {(m.user_id, m.role) for m in roster} >= {(firm.quinn, "eqr_reviewer")}


async def test_team_approval_and_the_changes_since_footer(firm: _Firm) -> None:
    before = await team_model.team_approval(firm.ctx(firm.hannah), firm.py2025)
    assert before.approved_by is None and not before.changed
    with pytest.raises(Forbidden):  # the manager does not approve the team
        await firm.approve(firm.hannah)
    approved = await firm.approve(firm.margaret)
    assert approved.approved_by == firm.margaret
    assert approved.approved_by_name == "Margaret Okonkwo"
    assert not approved.changed and approved.added_since == []
    await firm.cleared(firm.celia)
    await team_model.assign_eqr(firm.ctx(firm.margaret), firm.py2025, firm.celia)
    unchanged = await team_model.team_approval(firm.ctx(firm.hannah), firm.py2025)
    assert not unchanged.changed  # the EQR is not on the team
    await add_to_team(firm.ctx(firm.hannah), firm.py2025, firm.kira, "staff", Decimal("24.0"))
    after = await team_model.team_approval(firm.ctx(firm.hannah), firm.py2025)
    assert after.changed and after.added_since == [firm.kira]
    again = await firm.approve(firm.margaret)
    assert not again.changed and again.added_since == []
    assert await firm.audited("team.approved") == 2


async def test_hours_specialists_and_the_portal_flag(firm: _Firm) -> None:
    await add_to_team(firm.ctx(firm.margaret), firm.py2025, firm.kira, "specialist")
    await change_team_role(firm.ctx(firm.hannah), firm.py2025, firm.kira, None, Decimal("172.0"))
    await team_model.set_portal_visibility(firm.ctx(firm.hannah), firm.py2025, firm.hannah, True)
    roster = {m.user_id: m for m in await team_model.team_of(firm.ctx(firm.hannah), firm.py2025)}
    kira = roster[firm.kira]
    assert (kira.role, kira.budget_hours, kira.independence) == (
        "specialist",
        Decimal("172.0"),
        "requested",
    )
    assert kira.proposed_at is not None
    assert roster[firm.hannah].shown_on_portal and not kira.shown_on_portal
    assert await firm.audited("engagement_member.hours_changed") == 1
    assert await firm.audited("team.portal_visibility_changed") == 1
    with pytest.raises(Forbidden):  # the portal flag is the leads'
        await team_model.set_portal_visibility(firm.ctx(firm.kira), firm.py2025, firm.kira, True)


async def test_confirmation_requests_go_to_open_confirmations_only(firm: _Firm) -> None:
    await add_to_team(firm.ctx(firm.hannah), firm.py2025, firm.kira, "staff")
    sent = await team_model.remind_independence(firm.ctx(firm.hannah), firm.py2025, [firm.kira])
    assert sent == [firm.kira]
    assert await firm.audited("independence.reminded") == 1
    assert (
        await firm.count(
            "SELECT count(*) FROM outbox WHERE tenant_id = $1 "
            "AND event_type = 'independence.requested'",
            firm.tenant,
        )
        == 2  # on joining, and the reminder
    )
    with pytest.raises(DomainInvalid):  # Margaret was never asked (seeded directly)
        await team_model.remind_independence(firm.ctx(firm.hannah), firm.py2025, [firm.margaret])
    with pytest.raises(Forbidden):  # a staff member cannot send them
        await team_model.remind_independence(firm.ctx(firm.kira), firm.py2025, [firm.kira])


async def test_the_approval_rows_refuse_an_agent_and_any_change(firm: _Firm) -> None:
    approval = await firm.approve(firm.margaret)
    insert = (
        "INSERT INTO team_approvals (tenant_id, engagement_id, approved_by, member_set_hash) "
        "VALUES ($1, $2, $3, $4)"
    )
    with pytest.raises(asyncpg.CheckViolationError):
        await firm.seed.as_actor(
            firm.tenant,
            ("agent", "engagement_agent"),
            insert,
            firm.tenant,
            firm.py2025,
            firm.margaret,
            "0" * 64,
        )
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await firm.seed.run("UPDATE team_approvals SET approved_by = approved_by")
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await firm.seed.run("DELETE FROM eqr_eligibility_approvals")
    assert approval.approved_at is not None


# --- Security review (DEC-327) --------------------------------------------------------------


async def test_review_a_client_principal_never_reads_the_internal_roster(firm: _Firm) -> None:
    for read in (team_model.team_of, team_model.team_approval):
        with pytest.raises(Forbidden):
            await read(firm.ctx(firm.hannah, client=True), firm.py2025)


async def test_review_cooling_off_survives_thomas_leaving_fy2024(firm: _Firm) -> None:
    """Thomas removes himself from the PY2024 engagement (as any later edit could): the
    membership history still shows he was its partner, so he stays ineligible."""
    await firm.member(firm.py2024, firm.hannah, "engagement_partner")
    await firm.seed.run(
        "DELETE FROM engagement_members WHERE engagement_id = $1 AND user_id = $2",
        firm.py2024,
        firm.thomas,
    )
    assert await firm.role_of(firm.py2024, firm.thomas) is None
    found = {
        c.user_id: c for c in await team_model.eqr_candidates(firm.ctx(firm.hannah), firm.py2025)
    }
    assert _check(found[firm.thomas], "cooling_off") == team_model.Check(
        "cooling_off", "fail", year=2024
    )
    with pytest.raises(EqrNotEligible):
        await team_model.assign_eqr(firm.ctx(firm.hannah), firm.py2025, firm.thomas)
    events = await firm.seed.rows(
        "SELECT event, role FROM engagement_member_events WHERE engagement_id = $1 "
        "AND user_id = $2 ORDER BY id",
        firm.py2024,
        firm.thomas,
    )
    assert [(r["event"], r["role"]) for r in events] == [
        ("added", "engagement_partner"),
        ("removed", "engagement_partner"),
    ]
    with pytest.raises(asyncpg.InsufficientPrivilegeError):  # the history is never edited
        await firm.seed.run("DELETE FROM engagement_member_events")


async def test_review_no_one_with_a_role_on_the_engagement_approves_eligibility(
    firm: _Firm,
) -> None:
    await firm.member(firm.py2025, firm.quinn, "specialist")
    with pytest.raises(EqrApproverOnEngagement):
        await team_model.approve_eqr_eligibility(firm.ctx(firm.quinn), firm.py2025, firm.celia)
    await firm.cleared(firm.celia)
    await team_model.assign_eqr(firm.ctx(firm.margaret), firm.py2025, firm.celia)
    with pytest.raises(EqrApproverOnEngagement):  # the current EQR neither
        await team_model.approve_eqr_eligibility(firm.ctx(firm.celia), firm.py2025, firm.rosa)
    assert await firm.audited("eqr.eligibility_approved") == 1


async def test_review_a_walled_candidate_is_404_before_any_check(firm: _Firm) -> None:
    await firm.seed.run(
        "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
        "VALUES ($1, $2, $3, $4)",
        firm.tenant,
        firm.thomas,
        firm.client,
        firm.margaret,
    )
    with pytest.raises(NotFound):  # never 409 eqr_not_eligible with facts about him
        await team_model.assign_eqr(firm.ctx(firm.margaret), firm.py2025, firm.thomas)


async def test_review_the_partner_approves_exactly_the_team_they_saw(firm: _Firm) -> None:
    seen = await team_model.team_approval(firm.ctx(firm.margaret), firm.py2025)
    await add_to_team(firm.ctx(firm.hannah), firm.py2025, firm.kira, "staff")
    with pytest.raises(TeamChanged):
        await team_model.approve_team(firm.ctx(firm.margaret), firm.py2025, seen.member_set_hash)
    assert (
        await firm.count("SELECT count(*) FROM team_approvals WHERE tenant_id = $1", firm.tenant)
        == 0
    )
    with pytest.raises(Forbidden):  # fresh MFA (`mfa_recent`)
        await team_model.approve_team(
            firm.ctx(firm.margaret, mfa=False),
            firm.py2025,
            (await team_model.team_approval(firm.ctx(firm.margaret), firm.py2025)).member_set_hash,
        )
    approved = await firm.approve(firm.margaret)
    assert approved.approved_by == firm.margaret and not approved.changed
