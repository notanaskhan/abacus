# ac-test-author: ayushkbhatia
"""P-07 Story 5.2 (ENG-05) for P-07-T30 (P-07-T32): EQR eligibility (not on the team, cooling-off
two years, competence, independence), the eligibility approval by the quality owner and never
the EP, the EP's team approval with its "changes since" footer, the portal-visibility flag, the
blocked assignment and the confirmation request, and the human-only rule (INV-1).

Read from P-07 §3.5 Story 5.2, the ENG-05 screen contract, `docs/contracts/acceptance-
independence.md` §2, §3, §5, §6, the engagements permission matrix and DEC-326/DEC-327 (which
fix the eligibility rules the epic leaves open: cooling-off is EP on an engagement of the same
client whose period ended in the two years before this one's; competence zero is
`not_assessed`, which needs the quality owner's approval before assignment; anyone with a role
on the engagement may not approve). HTTP through `create_app()` behind `engagements.v2`; the
work-item assignment through `engagements.api.assign_work_item` (no HTTP route assigns yet).
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, cast

import asyncpg
import httpx
import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainConflict
from abacus.modules.engagements.api import assign_work_item, create_work_item
from abacus.modules.identity.api import (
    RULES,
    AgentContext,
    AuthContext,
    Forbidden,
    Resource,
    authorise,
)
from abacus.modules.identity.context import (
    _ISSUER,  # pyright: ignore[reportPrivateUsage] -- a test-only agent principal
)

from .support import Net, Person, Seeder, Site

pytestmark = pytest.mark.asyncio

Json = dict[str, object]
HUMAN_ONLY: Final = ("team.approve", "eqr.approve_eligibility")


@dataclass(frozen=True)
class Fairhaven:
    """A firm with Fairhaven's engagement (FY2025): Margaret Okonkwo is its EP and also the
    firm's quality partner; Hannah is the manager; Celia Marsh is the quality owner with no role
    on it; Thomas Whitcombe was EP on Fairhaven's FY2024 engagement."""

    net: Net
    seed: Seeder
    tenant: uuid.UUID
    site: Site
    margaret: Person
    hannah: Person
    celia: Person
    thomas: Person

    @property
    def base(self) -> str:
        return f"/v1/engagements/{self.site.engagement_id}"

    async def call(
        self,
        method: str,
        path: str,
        who: Person,
        body: Mapping[str, object] | None = None,
        *,
        mfa: bool = True,
    ) -> httpx.Response:
        return await self.net.call(method, f"{self.base}{path}", who, body=body, mfa=mfa)

    async def partner(self, firm_role: str | None = None) -> Person:
        who = await self.seed.person(self.tenant, firm_role)
        await self.seed.run(
            "UPDATE memberships SET level = 'partner' WHERE tenant_id = $1 AND user_id = $2",
            self.tenant,
            who.user_id,
        )
        return who

    async def prior(self, ended: int, ep: Person) -> uuid.UUID:
        """Another engagement of Fairhaven, for the fiscal year `ended`, with `ep` as its EP."""
        engagement = cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
                "fiscal_period_start, fiscal_period_end, created_by) VALUES ($1, $2, $3, $4, "
                "make_date($5, 1, 1), make_date($5, 12, 31), $6) RETURNING id",
                self.tenant,
                self.site.client_id,
                self.site.entity_id,
                f"Fairhaven FY{ended}",
                ended,
                ep.user_id,
            ),
        )
        await self.seed.run(
            "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
            "VALUES ($1, $2, $3, 'engagement_partner')",
            self.tenant,
            engagement,
            ep.user_id,
        )
        return engagement

    async def audit(self, action: str) -> list[tuple[str, str]]:
        rows = await self.seed.rows(
            "SELECT actor_kind, actor_id FROM audit_events WHERE tenant_id = $1 AND action = $2 "
            "ORDER BY seq",
            self.tenant,
            action,
        )
        return [(str(r["actor_kind"]), str(r["actor_id"])) for r in rows]


async def _flag(seed: Seeder, tenant: uuid.UUID, name: str) -> None:
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, $2, 'true', 'test-seed', 'P-07-T32')",
        tenant,
        name,
    )


@pytest.fixture
async def fh(net: Net, seed: Seeder) -> Fairhaven:
    tenant = await seed.firm()
    await _flag(seed, tenant, "engagements.v2")
    admin = await seed.person(tenant, "firm_admin")
    site = await seed.site(tenant, admin.user_id, "Fairhaven")
    margaret = await seed.person(tenant, "quality_partner")
    await seed.run(
        "UPDATE memberships SET level = 'partner' WHERE tenant_id = $1 AND user_id = $2",
        tenant,
        margaret.user_id,
    )
    await seed.member(site, margaret, "engagement_partner")
    hannah = await seed.person(tenant)
    await seed.member(site, hannah, "manager")
    world = Fairhaven(net, seed, tenant, site, margaret, hannah, margaret, margaret)
    celia = await world.partner("quality_partner")
    thomas = await world.partner()
    await world.prior(2024, thomas)
    return Fairhaven(net, seed, tenant, site, margaret, hannah, celia, thomas)


async def _candidates(fh: Fairhaven, who: Person | None = None) -> dict[str, Json]:
    response = await fh.call("GET", "/eqr/candidates", who or fh.hannah)
    assert response.status_code == 200, response.text
    return {cast(str, c["user_id"]): c for c in cast(list[Json], response.json())}


def _checks(candidate: Json) -> dict[str, Json]:
    return {cast(str, c["code"]): c for c in cast(list[Json], candidate["checks"])}


# ================================================================================================
# EQR eligibility rules (Story 5.2; DEC-327)
# ================================================================================================


async def test_ac5_2_thomas_was_ep_on_fairhaven_for_fy2024_so_he_is_not_eligible(
    fh: Fairhaven,
) -> None:
    candidates = await _candidates(fh)
    thomas = candidates[str(fh.thomas.user_id)]
    assert thomas["eligibility"] == "not_eligible"
    cooling = _checks(thomas)["cooling_off"]
    assert (cooling["result"], cooling["year"]) == ("fail", 2024)
    assert set(_checks(thomas)) == {
        "not_on_team",
        "cooling_off",
        "competence",
        "independence",
        "capacity",
    }
    refused = await fh.call("POST", "/eqr", fh.hannah, {"user_id": str(fh.thomas.user_id)})
    assert refused.status_code == 409, refused.text
    body = cast(Json, refused.json())
    assert body["detail"] == "eqr_not_eligible"
    assert "cooling_off" in str(body.get("facts"))
    assert (
        await fh.seed.value(
            "SELECT count(*) FROM engagement_members WHERE engagement_id = $1 AND role = "
            "'eqr_reviewer'",
            fh.site.engagement_id,
        )
        == 0
    )
    assert await fh.audit("eqr.assigned") == []


async def test_ac5_2_an_ep_more_than_two_years_before_passes_cooling_off(fh: Fairhaven) -> None:
    dana = await fh.partner()
    await fh.prior(2022, dana)
    dana_row = (await _candidates(fh))[str(dana.user_id)]
    assert _checks(dana_row)["cooling_off"]["result"] == "pass"
    assert _checks(dana_row)["not_on_team"]["result"] == "pass"


async def test_ac5_2_a_team_member_is_never_the_eqr(
    fh: Fairhaven,
) -> None:
    candidates = await _candidates(fh)
    hannah = candidates.get(str(fh.hannah.user_id))
    if hannah is not None:  # listed or not, a team member fails `not_on_team`
        assert hannah["eligibility"] == "not_eligible"
        assert _checks(hannah)["not_on_team"]["result"] == "fail"
    refused = await fh.call("POST", "/eqr", fh.margaret, {"user_id": str(fh.hannah.user_id)})
    assert refused.status_code == 409, refused.text
    assert refused.json()["detail"] == "eqr_on_team"  # contract §6: an EQR who holds a team role
    assert await fh.audit("eqr.assigned") == []


async def _eqr(fh: Fairhaven) -> Person:
    """Dana, approved by the quality owner and made the EQR."""
    dana = await fh.partner()
    approved = await fh.call(
        "POST", "/eqr/eligibility/approve", fh.celia, {"candidate_user_id": str(dana.user_id)}
    )
    assert approved.status_code in (200, 201), approved.text
    assigned = await fh.call("POST", "/eqr", fh.hannah, {"user_id": str(dana.user_id)})
    assert assigned.status_code in (200, 201), assigned.text
    return dana


async def _team_roles(fh: Fairhaven, who: Person) -> list[object]:
    roster = await fh.call("GET", "/team", fh.hannah)
    assert roster.status_code == 200, roster.text
    return [
        m.get("role") for m in cast(list[Json], roster.json()) if m["user_id"] == str(who.user_id)
    ]


async def test_ac5_2_the_eqr_is_refused_a_team_role_change_with_409_eqr_on_team(
    fh: Fairhaven,
) -> None:
    dana = await _eqr(fh)
    changed = await fh.call("PUT", f"/team/{dana.user_id}", fh.hannah, {"role": "staff"})
    assert changed.status_code == 409, changed.text
    assert changed.json()["detail"] == "eqr_on_team"
    assert set(await _team_roles(fh, dana)) <= {"eqr_reviewer"}


async def test_ac5_2_adding_the_eqr_to_the_team_answers_409_eqr_on_team(fh: Fairhaven) -> None:
    dana = await _eqr(fh)
    on_team = await fh.call(
        "POST", "/team", fh.hannah, {"user_id": str(dana.user_id), "role": "staff"}
    )
    assert set(await _team_roles(fh, dana)) <= {"eqr_reviewer"}  # no team role either way
    assert on_team.status_code == 409, on_team.text
    assert on_team.json()["detail"] == "eqr_on_team"


async def test_ac5_2_a_declined_independence_fails_the_independence_check(fh: Fairhaven) -> None:
    dana = await fh.partner()
    await fh.seed.run(
        "INSERT INTO independence_confirmations (tenant_id, engagement_id, user_id, status, "
        "statement_version, answered_at) VALUES ($1, $2, $3, 'declined', 'v1', "
        "clock_timestamp())",
        fh.tenant,
        fh.site.engagement_id,
        dana.user_id,
    )
    dana_row = (await _candidates(fh))[str(dana.user_id)]
    assert _checks(dana_row)["independence"]["result"] == "fail"
    assert dana_row["eligibility"] == "not_eligible"


async def test_ac5_2_an_unassessed_candidate_needs_the_quality_owners_approval_first(
    fh: Fairhaven,
) -> None:
    dana = await fh.partner()
    row = (await _candidates(fh))[str(dana.user_id)]
    assert _checks(row)["competence"]["result"] == "not_assessed"  # a new firm has no history
    assert _checks(row)["capacity"]["result"] == "not_assessed"  # placeholder
    early = await fh.call("POST", "/eqr", fh.hannah, {"user_id": str(dana.user_id)})
    assert early.status_code == 409, early.text
    assert early.json()["detail"] == "eqr_approval_required"
    approved = await fh.call(
        "POST", "/eqr/eligibility/approve", fh.celia, {"candidate_user_id": str(dana.user_id)}
    )
    assert approved.status_code in (200, 201), approved.text  # the contract fixes no create code
    assigned = await fh.call("POST", "/eqr", fh.hannah, {"user_id": str(dana.user_id)})
    assert assigned.status_code in (200, 201), assigned.text  # the contract fixes no create code
    assert assigned.json()["user_id"] == str(dana.user_id)
    assert (await _candidates(fh))[str(dana.user_id)]["current"] is True
    assert await fh.audit("eqr.assigned") == [("human", str(fh.hannah.user_id))]


async def test_ac5_2_only_the_ep_and_manager_read_candidates_and_assign(fh: Fairhaven) -> None:
    staff = await fh.seed.person(fh.tenant)
    await fh.seed.member(fh.site, staff, "staff")
    for who in (staff, fh.celia):
        refused = await fh.call("GET", "/eqr/candidates", who)
        assert refused.status_code in (403, 404), refused.text
        assert "eligibility" not in refused.text
    assert (await fh.call("GET", "/eqr/candidates", fh.margaret)).status_code == 200


# ================================================================================================
# The eligibility approval: the quality owner's, never the EP's (Story 5.2; contract §6)
# ================================================================================================


async def test_ac5_2_margaret_cannot_approve_eligibility_on_her_own_engagement(
    fh: Fairhaven,
) -> None:
    dana = await fh.partner()
    refused = await fh.call(
        "POST", "/eqr/eligibility/approve", fh.margaret, {"candidate_user_id": str(dana.user_id)}
    )
    assert refused.status_code == 409, refused.text
    assert refused.json()["detail"] == "eqr_approver_is_ep"
    assert await fh.audit("eqr.eligibility_approved") == []
    approved = await fh.call(
        "POST", "/eqr/eligibility/approve", fh.celia, {"candidate_user_id": str(dana.user_id)}
    )
    assert approved.status_code in (200, 201), approved.text  # the contract fixes no create code
    body = cast(Json, approved.json())
    assert (body["approved_by"], body["candidate_user_id"]) == (
        str(fh.celia.user_id),
        str(dana.user_id),
    )
    assert body["result"] in ("eligible", "not_eligible")
    assert await fh.audit("eqr.eligibility_approved") == [("human", str(fh.celia.user_id))]


async def test_ac5_2_nobody_with_a_role_on_the_engagement_and_no_non_quality_owner_approves(
    fh: Fairhaven,
) -> None:
    dana = await fh.partner()
    body = {"candidate_user_id": str(dana.user_id)}
    # Hannah, the manager, holds no quality_partner role: the matrix refuses her.
    refused = await fh.call("POST", "/eqr/eligibility/approve", fh.hannah, body)
    assert refused.status_code == 403, refused.text
    # A quality partner who is on the team is refused as on the engagement.
    qp_on_team = await fh.partner("quality_partner")
    await fh.seed.member(fh.site, qp_on_team, "reviewer")
    on_it = await fh.call("POST", "/eqr/eligibility/approve", qp_on_team, body)
    assert on_it.status_code == 409, on_it.text
    assert on_it.json()["detail"] == "eqr_approver_on_engagement"
    # The candidate never approves themself.
    self_qp = await fh.partner("quality_partner")
    own = await fh.call(
        "POST", "/eqr/eligibility/approve", self_qp, {"candidate_user_id": str(self_qp.user_id)}
    )
    assert own.status_code == 422, own.text
    assert await fh.audit("eqr.eligibility_approved") == []


# ================================================================================================
# Team approval and the "changes since" footer (Story 5.2)
# ================================================================================================


def _hash(members: list[tuple[uuid.UUID, str]]) -> str:
    """DEC-327: the sha256 of the sorted `user_id:role` lines."""
    lines = sorted(f"{user}:{role}" for user, role in members)
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


async def _approval(fh: Fairhaven) -> Json:
    response = await fh.call("GET", "/team/approval", fh.hannah)
    assert response.status_code == 200, response.text
    return cast(Json, response.json())


async def test_ac5_2_the_ep_approves_the_team_and_a_later_addition_shows_as_changes_since(
    fh: Fairhaven,
) -> None:
    before = await _approval(fh)
    assert before["approved_by"] is None
    current = cast(str, before["member_set_hash"])
    assert len(current) == 64
    # Only the EP approves, with fresh MFA.
    manager = await fh.call("POST", "/team/approve", fh.hannah, {"member_set_hash": current})
    assert manager.status_code == 403, manager.text
    stale_mfa = await fh.call(
        "POST", "/team/approve", fh.margaret, {"member_set_hash": current}, mfa=False
    )
    assert stale_mfa.status_code == 403, stale_mfa.text
    approved = await fh.call("POST", "/team/approve", fh.margaret, {"member_set_hash": current})
    assert approved.status_code in (200, 201), approved.text  # the contract fixes no create code
    footer = await _approval(fh)
    assert (footer["approved_by"], footer["changed"], footer["added_since"]) == (
        str(fh.margaret.user_id),
        False,
        [],
    )
    assert footer["approved_at"] is not None and footer["approved_by_name"]
    assert await fh.audit("team.approved") == [("human", str(fh.margaret.user_id))]

    kira = await fh.seed.person(fh.tenant)
    added = await fh.call(
        "POST", "/team", fh.hannah, {"user_id": str(kira.user_id), "role": "staff"}
    )
    assert added.status_code in (200, 201), added.text
    changed = await _approval(fh)
    assert changed["changed"] is True
    assert changed["added_since"] == [str(kira.user_id)]
    assert changed["approved_by"] == str(fh.margaret.user_id)  # "until Margaret approves again"
    assert changed["member_set_hash"] != current
    # Approving the set read before Kira joined is stale.
    stale = await fh.call("POST", "/team/approve", fh.margaret, {"member_set_hash": current})
    assert stale.status_code == 409, stale.text
    assert stale.json()["detail"] == "stale_version"
    again = await fh.call(
        "POST", "/team/approve", fh.margaret, {"member_set_hash": changed["member_set_hash"]}
    )
    assert again.status_code in (200, 201), again.text  # the contract fixes no create code
    after = await _approval(fh)
    assert (after["changed"], after["added_since"]) == (False, [])


async def test_ac5_2_the_member_set_hash_is_the_sorted_user_and_role_lines(fh: Fairhaven) -> None:
    footer = await _approval(fh)
    assert footer["member_set_hash"] == _hash(
        [(fh.margaret.user_id, "engagement_partner"), (fh.hannah.user_id, "manager")]
    )


# ================================================================================================
# Portal visibility (ENG-05 "Shown on portal")
# ================================================================================================


async def test_ac5_2_the_partner_or_manager_sets_shown_on_portal_and_staff_cannot(
    fh: Fairhaven,
) -> None:
    staff = await fh.seed.person(fh.tenant)
    await fh.seed.member(fh.site, staff, "staff")
    path = f"/team/{fh.hannah.user_id}/portal-visibility"
    refused = await fh.call("PUT", path, staff, {"shown_on_portal": True})
    assert refused.status_code == 403, refused.text
    shown = await fh.call("PUT", path, fh.hannah, {"shown_on_portal": True})
    assert shown.status_code == 200, shown.text
    assert shown.json() == {"user_id": str(fh.hannah.user_id), "shown_on_portal": True}
    roster = {
        m["user_id"]: m
        for m in cast(list[Json], (await fh.call("GET", "/team", fh.hannah)).json())
    }
    assert roster[str(fh.hannah.user_id)]["shown_on_portal"] is True
    assert roster[str(fh.margaret.user_id)]["shown_on_portal"] is False  # default off
    assert await fh.audit("team.portal_visibility_changed") == [("human", str(fh.hannah.user_id))]


# ================================================================================================
# Blocked assignment and the confirmation request (Story 5.2; ENG-05 b)
# ================================================================================================


def _ctx(who: Person) -> AuthContext:
    return AuthContext(
        TenantContext(who.tenant_id, "human", str(who.user_id)),
        who.user_id,
        uuid.uuid4(),
        None,
        datetime.now(UTC),
    )


async def _work_item(fh: Fairhaven) -> uuid.UUID:
    found = await fh.seed.value(
        "SELECT id FROM work_items WHERE engagement_id = $1 LIMIT 1", fh.site.engagement_id
    )
    if found is None:
        found = await create_work_item(
            _ctx(fh.margaret), fh.site.engagement_id, "advisory_project", name="ENG-05 work"
        )
    return cast(uuid.UUID, found)


async def test_ac5_2_kira_views_the_attest_engagement_but_is_not_assigned_until_she_confirms(
    fh: Fairhaven,
) -> None:
    await fh.seed.attest(fh.tenant, fh.site.engagement_id)
    kira = await fh.seed.person(fh.tenant)
    added = await fh.call(
        "POST", "/team", fh.hannah, {"user_id": str(kira.user_id), "role": "staff"}
    )
    assert added.status_code in (200, 201), added.text
    roster = {
        m["user_id"]: m
        for m in cast(list[Json], (await fh.call("GET", "/team", fh.hannah)).json())
    }
    assert roster[str(kira.user_id)]["independence"] == "requested"
    opened = await fh.net.call("GET", fh.base, kira)
    assert opened.status_code == 200, opened.text  # she can view the engagement (DEC-39)
    work_item = await _work_item(fh)
    with pytest.raises(DomainConflict) as refused:
        await assign_work_item(_ctx(fh.hannah), work_item, kira.user_id, "preparer")
    assert refused.value.facts == {"gate": "G2", "user_id": str(kira.user_id)}
    # "Send confirmation request": a reminder to Kira, by the person clicking.
    sent = await fh.call(
        "POST", "/independence/reminders", fh.hannah, {"user_ids": [str(kira.user_id)]}
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["reminded_user_ids"] == [str(kira.user_id)]
    assert await fh.audit("independence.reminded") == [("human", str(fh.hannah.user_id))]
    # Margaret has confirmed: no reminder is open for her.
    closed = await fh.call(
        "POST", "/independence/reminders", fh.hannah, {"user_ids": [str(fh.margaret.user_id)]}
    )
    assert closed.status_code == 422, closed.text
    await fh.seed.run(
        "UPDATE independence_confirmations SET status = 'confirmed', answered_at = now(), "
        "statement_version = 'v1' WHERE engagement_id = $1 AND user_id = $2",
        fh.site.engagement_id,
        kira.user_id,
    )
    await assign_work_item(_ctx(fh.hannah), work_item, kira.user_id, "preparer")
    assert (
        await fh.seed.value(
            "SELECT count(*) FROM work_item_assignments WHERE work_item_id = $1 AND user_id = $2",
            work_item,
            kira.user_id,
        )
        == 1
    )


async def test_ac5_2_on_a_non_attest_engagement_the_new_member_is_assigned_at_once(
    fh: Fairhaven,
) -> None:
    await fh.seed.run(
        "UPDATE engagements SET type = 'cas_monthly_close' WHERE id = $1", fh.site.engagement_id
    )
    kira = await fh.seed.person(fh.tenant)
    added = await fh.call(
        "POST", "/team", fh.hannah, {"user_id": str(kira.user_id), "role": "staff"}
    )
    assert added.status_code in (200, 201), added.text
    await assign_work_item(_ctx(fh.hannah), await _work_item(fh), kira.user_id, "preparer")
    # Confirmation is still requested (SPEC-332 AC-14).
    roster = {
        m["user_id"]: m
        for m in cast(list[Json], (await fh.call("GET", "/team", fh.hannah)).json())
    }
    assert roster[str(kira.user_id)]["independence"] == "requested"


# ================================================================================================
# INV-1: team approval and the eligibility approval are a live person's
# ================================================================================================


async def test_inv1_agent_and_system_are_refused_the_team_and_eligibility_approvals(
    fh: Fairhaven,
) -> None:
    for action in (*HUMAN_ONLY, "eqr.assign", "independence.remind"):
        decisions = RULES[action].decisions
        for principal in ("agent", "system"):
            assert decisions.get(principal, "deny") == "deny", (action, decisions)
        assert not {
            r
            for r, d in decisions.items()
            if r.startswith("client_") and r != "client_service" and d != "deny"
        }
    person = AuthContext(
        TenantContext(fh.tenant, "human", str(fh.margaret.user_id)),
        fh.margaret.user_id,
        uuid.uuid4(),
        "quality_partner",
        datetime.now(UTC) - timedelta(minutes=1),
    )
    run = uuid.uuid4()
    agent = AgentContext(
        tenant=TenantContext(fh.tenant, "agent", f"agent:probe:{run}", fh.margaret.user_id),
        agent_id="probe",
        agent_run_id=run,
        engagement_id=fh.site.engagement_id,
        task_scope=frozenset(HUMAN_ONLY),
        initiator=person,
        issued_by=_ISSUER,
    )
    target = Resource.engagement(fh.tenant, fh.site.engagement_id, archived=False)
    await authorise(person, "eqr.approve_eligibility", target)  # Margaret herself may (matrix)
    for action in HUMAN_ONLY:
        with pytest.raises(Forbidden):
            await authorise(agent, action, target)


async def test_inv1_the_approval_rows_refuse_a_non_human_actor_in_the_database(
    fh: Fairhaven,
) -> None:
    with pytest.raises(asyncpg.CheckViolationError):
        await fh.seed.run(
            "INSERT INTO team_approvals (tenant_id, engagement_id, approved_by, "
            "member_set_hash, actor_kind) VALUES ($1, $2, $3, $4, 'agent')",
            fh.tenant,
            fh.site.engagement_id,
            fh.margaret.user_id,
            "0" * 64,
        )
    with pytest.raises(asyncpg.CheckViolationError):
        await fh.seed.run(
            "INSERT INTO eqr_eligibility_approvals (tenant_id, engagement_id, "
            "candidate_user_id, checks, result, approved_by, actor_kind) "
            "VALUES ($1, $2, $3, '[]'::jsonb, 'eligible', $4, 'system')",
            fh.tenant,
            fh.site.engagement_id,
            fh.thomas.user_id,
            fh.celia.user_id,
        )
