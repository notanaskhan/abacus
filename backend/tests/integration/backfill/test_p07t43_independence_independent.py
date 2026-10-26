# ac-test-author: ayushkbhatia
"""SPEC-332 AC-17 to AC-22, AC-27 and AC-28 for P-07-T41 (P-07-T43): each member confirms or
declines their own independence (the note sealed), reminders sent by a person, the engagement
partner's conclusion with fresh MFA and its preconditions (INV-1), NAS rows with the EP's
evaluation and the SKE designee on an attest client, rotation derived from the prior-engagement
chain, insert-only breaches, and the G2 provider. "Margaret Okonkwo concludes only after all five
confirm, NAS is evaluated and conflicts are cleared, and G2 then reports met."

Read from SPEC-332 §5 Stories 5 to 9, P-07 §3.5 Story 5.1, §4.2 M7, §4.3 and §4.7, the CLI-08
screen contract, `docs/contracts/acceptance-independence.md`, the engagements matrix,
`error-codes.yaml` and the human-only register. HTTP through `create_app()` behind
`engagements.v2` and `engagements.acceptance_v2` on Brightwater Hale's Northwind PY2025 EBP audit
(an attest client) with five members, four confirmed; the live-human layer through
`engagements.api`, the database layer as raw SQL, the call-site layer through `banned_patterns`.

Spec gaps followed here (TASK-1323): the conclusion's blockers are identifier facts, one count per
reason code (`member_not_confirmed`, `member_declined`, `conflict_not_cleared`,
`ske_designee_missing`, `nas_not_evaluated`), since facts are flat (ADR-139); a person with no
role on the engagement is refused confirming at the matrix (403 or 404), so `not_self` cannot
arise through the route, which has no user id; the SKE designee is an `engagement_contacts` row
(DEC-63) with no designation route yet, so it is seeded; NAS rows are the client's engagements
outside the attest family; rotation's review threshold is the platform default of seven years
until firm settings hold integers. The `independence_conclusion_due` notification is P-07-T47's.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Final, cast

import asyncpg
import httpx
import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.db.session import ActorKind
from abacus.modules.identity.api import RULES, AuthContext, Forbidden
from abacus_tools.quality import banned_patterns

from .support import Net, Person, Seeder, Site

pytestmark = pytest.mark.asyncio

Json = dict[str, object]
STATEMENTS: Final = ["no_financial_interest", "no_family_in_key_position", "not_a_participant"]


@dataclass
class Northwind:
    """Northwind Robotics 401(k) Plan, PY2025 EBP audit: Margaret Okonkwo (EP, partner), Hannah
    Leclerc (manager), Thomas Whitcombe (senior), Mia Dorsey (staff) confirmed; Ana Cruz (staff)
    pending; Grace Holloway firm admin with no role; Rita Vance a quality partner."""

    net: Net
    seed: Seeder
    tenant: uuid.UUID
    site: Site
    grace: Person
    margaret: Person
    hannah: Person
    thomas: Person
    mia: Person
    ana: Person
    rita: Person
    tax_engagement: uuid.UUID

    @property
    def eid(self) -> uuid.UUID:
        return self.site.engagement_id

    @property
    def ind(self) -> str:
        return f"/v1/engagements/{self.eid}/independence"

    async def call(
        self,
        method: str,
        path: str,
        who: Person,
        body: Mapping[str, object] | None = None,
        *,
        mfa: bool = True,
    ) -> httpx.Response:
        return await self.net.http.request(
            method, path, json=body, headers=self.net.headers(who, mfa=mfa)
        )

    async def summary(self, who: Person | None = None) -> Json:
        return _json(await self.call("GET", self.ind, who or self.margaret))

    async def confirm(self, who: Person) -> httpx.Response:
        return await self.call(
            "POST",
            f"{self.ind}/confirm",
            who,
            {"statement_version": "northwind_2025_v1", "statement_codes": STATEMENTS},
        )

    async def conclude(
        self,
        option: str = "independent",
        *,
        who: Person | None = None,
        mfa: bool = True,
        **kw: object,
    ) -> httpx.Response:
        return await self.call(
            "POST", f"{self.ind}/conclude", who or self.margaret, {"option": option, **kw}, mfa=mfa
        )

    async def designate_ske(self) -> uuid.UUID:
        contact = cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO contacts (tenant_id, client_id, display_name, contact_kind) "
                "VALUES ($1, $2, 'Dana Kowalski', 'client_person') RETURNING id",
                self.tenant,
                self.site.client_id,
            ),
        )
        await self.seed.run(
            "INSERT INTO engagement_contacts (tenant_id, engagement_id, contact_id, designation, "
            "designated_by) VALUES ($1, $2, $3, 'ske_designee', $4)",
            self.tenant,
            self.eid,
            contact,
            self.margaret.user_id,
        )
        return contact

    async def evaluate_nas(self, who: Person | None = None, status: str = "concluded") -> Json:
        return _json(
            await self.call(
                "PUT",
                f"{self.ind}/nas/tax_compliance",
                who or self.margaret,
                {
                    "provided": True,
                    "status": status,
                    "evaluation": "Permitted: management takes responsibility for the returns.",
                },
            )
        )

    async def gate(self, gate: str) -> Json:
        gates = cast(
            list[Json],
            _json(await self.call("GET", f"/v1/engagements/{self.eid}/gates", self.margaret)),
        )
        return next(g for g in gates if g["gate"] == gate)

    async def audit(self, action: str) -> list[tuple[str, str]]:
        rows = await self.seed.rows(
            "SELECT actor_kind, actor_id FROM audit_events WHERE tenant_id = $1 AND action = $2 "
            "ORDER BY seq",
            self.tenant,
            action,
        )
        return [(str(r["actor_kind"]), str(r["actor_id"])) for r in rows]


def _json(response: httpx.Response, status: int = 200) -> Json:
    assert response.status_code == status, response.text
    return cast(Json, response.json())


def _refusal(response: httpx.Response, status: int, detail: str) -> Json:
    assert response.status_code == status, response.text
    body = cast(Json, response.json())
    assert body["detail"] == detail, body
    return cast(Json, body.get("facts") or {})


def _members(summary: Json) -> dict[str, Json]:
    return {cast(str, m["user_id"]): m for m in cast(list[Json], summary["members"])}


def _reasons(summary: Json) -> set[str]:
    return {cast(str, b["reason_code"]) for b in cast(list[Json], summary["blockers"])}


async def _level(seed: Seeder, tenant: uuid.UUID, who: Person, level: str) -> None:
    await seed.run(
        "UPDATE memberships SET level = $3 WHERE tenant_id = $1 AND user_id = $2",
        tenant,
        who.user_id,
        level,
    )


async def _join(seed: Seeder, site: Site, who: Person, role: str, *, confirmed: bool) -> None:
    await seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES ($1, $2, $3, $4)",
        site.tenant_id,
        site.engagement_id,
        who.user_id,
        role,
    )
    if confirmed:
        await seed.run(
            "INSERT INTO independence_confirmations (tenant_id, engagement_id, user_id, status, "
            "statement_version, answered_at) VALUES ($1, $2, $3, 'confirmed', 'v1', "
            "clock_timestamp())",
            site.tenant_id,
            site.engagement_id,
            who.user_id,
        )
    else:
        await seed.run(
            "INSERT INTO independence_confirmations (tenant_id, engagement_id, user_id) "
            "VALUES ($1, $2, $3)",
            site.tenant_id,
            site.engagement_id,
            who.user_id,
        )


async def _world(net: Net, *, attest: bool = True) -> Northwind:
    seed = net.seed
    tenant = await seed.firm()
    for flag in ("engagements.v2", "engagements.acceptance_v2"):
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'P-07-T43')",
            tenant,
            flag,
        )
    grace = await seed.person(tenant, "firm_admin")
    rita = await seed.person(tenant, "quality_partner")
    margaret = await seed.person(tenant)
    await _level(seed, tenant, margaret, "partner")
    hannah = await seed.person(tenant)
    await _level(seed, tenant, hannah, "manager")
    thomas = await seed.person(tenant)
    await _level(seed, tenant, thomas, "senior")
    mia = await seed.person(tenant)
    await _level(seed, tenant, mia, "staff")
    ana = await seed.person(tenant)
    await _level(seed, tenant, ana, "staff")
    site = await seed.site(tenant, grace.user_id, "Northwind", opened=False)
    if attest:
        await seed.attest(tenant, site.engagement_id)
    await _join(seed, site, margaret, "engagement_partner", confirmed=True)
    await _join(seed, site, hannah, "manager", confirmed=True)
    await _join(seed, site, thomas, "senior", confirmed=True)
    await _join(seed, site, mia, "staff", confirmed=True)
    await _join(seed, site, ana, "staff", confirmed=False)
    # The firm also prepares the plan's Form 5500: a nonattest service to the attest client.
    tax = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, type, status, "
            "fiscal_period_start, fiscal_period_end, created_by) VALUES ($1, $2, $3, "
            "'Northwind 5500 PY2025', 'tax_compliance', 'active', '2025-01-01', '2025-12-31', $4) "
            "RETURNING id",
            tenant,
            site.client_id,
            site.entity_id,
            grace.user_id,
        ),
    )
    return Northwind(net, seed, tenant, site, grace, margaret, hannah, thomas, mia, ana, rita, tax)


@pytest.fixture
async def nw(net: Net) -> Northwind:
    return await _world(net)


async def _ready(nw: Northwind) -> None:
    """Every precondition met: Ana confirmed, the SKE designee named, NAS evaluated."""
    _json(await nw.confirm(nw.ana))
    await nw.designate_ske()
    await nw.evaluate_nas()


# ================================================================================================
# Story 5: confirmation (AC-17) and the summary
# ================================================================================================


async def test_ac17_four_of_five_then_ana_confirms_only_her_own(nw: Northwind) -> None:
    before = await nw.summary(nw.hannah)
    assert before["attest_client"] is True
    assert (before["confirmed"], before["total"]) == (4, 5)
    assert _members(before)[str(nw.ana.user_id)]["confirmation"] == "requested"
    assert "member_not_confirmed" in _reasons(before)
    pending = [
        b
        for b in cast(list[Json], before["blockers"])
        if b["reason_code"] == "member_not_confirmed"
    ]
    assert [b["ref_id"] for b in pending] == [str(nw.ana.user_id)]

    confirmed = _json(await nw.confirm(nw.ana))
    assert confirmed["user_id"] == str(nw.ana.user_id)
    assert confirmed["confirmation"] == "confirmed"
    assert confirmed["answered_at"] is not None
    after = await nw.summary(nw.ana)
    assert (after["confirmed"], after["total"]) == (5, 5)
    ana = _members(after)[str(nw.ana.user_id)]
    assert ana["statement_version"] == "northwind_2025_v1"
    assert "member_not_confirmed" not in _reasons(after)
    assert await nw.audit("independence.confirmed") == [("human", str(nw.ana.user_id))]
    # Nobody else's row moved.
    others = await nw.seed.rows(
        "SELECT user_id, status FROM independence_confirmations WHERE engagement_id = $1 "
        "AND user_id <> $2",
        nw.eid,
        nw.ana.user_id,
    )
    assert {str(r["status"]) for r in others} == {"confirmed"}


async def test_ac17_the_three_statements_are_required(nw: Northwind) -> None:
    refused = await nw.call(
        "POST",
        f"{nw.ind}/confirm",
        nw.ana,
        {"statement_version": "northwind_2025_v1", "statement_codes": STATEMENTS[:2]},
    )
    assert refused.status_code == 422, refused.text
    assert _members(await nw.summary())[str(nw.ana.user_id)]["confirmation"] == "requested"


async def test_ac17_someone_without_a_role_here_cannot_confirm(nw: Northwind) -> None:
    for who in (nw.grace, nw.rita):
        refused = await nw.confirm(who)
        assert refused.status_code in (403, 404), (who, refused.text)
    assert await nw.audit("independence.confirmed") == []
    assert (await nw.summary())["confirmed"] == 4


async def test_ac17_a_decline_needs_a_note_sealed_and_keeps_the_member_blocked(
    nw: Northwind,
) -> None:
    note = "My spouse holds Northwind Robotics stock through a brokerage account."
    empty = await nw.call("POST", f"{nw.ind}/decline", nw.ana, {"note": ""})
    assert empty.status_code == 422, empty.text
    declined = _json(await nw.call("POST", f"{nw.ind}/decline", nw.ana, {"note": note}))
    assert declined["confirmation"] == "declined"
    assert await nw.audit("independence.declined") == [("human", str(nw.ana.user_id))]
    summary = await nw.summary()
    assert "member_declined" in _reasons(summary)
    assert summary["confirmed"] == 4
    # The engagement partner reads the note; a colleague does not.
    assert _members(summary)[str(nw.ana.user_id)]["decline_note"] == note
    assert _members(await nw.summary(nw.mia))[str(nw.ana.user_id)]["decline_note"] is None
    # Sealed at rest: the plain words are nowhere in the row.
    row = await nw.seed.rows(
        "SELECT * FROM independence_confirmations WHERE engagement_id = $1 AND user_id = $2",
        nw.eid,
        nw.ana.user_id,
    )
    assert note not in repr(dict(row[0]))
    # Still not cleared: the conclusion lists her.
    facts = _refusal(await nw.conclude(), 409, "independence_preconditions_unmet")
    assert "member_declined" in facts


async def test_ac17_a_reminder_is_sent_by_the_person_clicking_and_counted(nw: Northwind) -> None:
    sent = _json(
        await nw.call(
            "POST", f"{nw.ind}/reminders", nw.hannah, {"user_ids": [str(nw.ana.user_id)]}
        )
    )
    assert sent["reminded_user_ids"] == [str(nw.ana.user_id)]
    assert await nw.audit("independence.reminded") == [("human", str(nw.hannah.user_id))]
    ana = _members(await nw.summary())[str(nw.ana.user_id)]
    assert ana["reminder_count"] == 1
    # Only someone still to answer is reminded.
    refused = await nw.call(
        "POST", f"{nw.ind}/reminders", nw.hannah, {"user_ids": [str(nw.mia.user_id)]}
    )
    assert refused.status_code == 422, refused.text


# ================================================================================================
# Story 5: the conclusion (AC-18, AC-19)
# ================================================================================================


async def test_ac19_the_conclusion_names_every_missing_precondition(nw: Northwind) -> None:
    facts = _refusal(await nw.conclude(), 409, "independence_preconditions_unmet")
    assert {"member_not_confirmed", "ske_designee_missing", "nas_not_evaluated"} <= set(facts)
    assert await nw.audit("independence.concluded") == []
    assert (await nw.summary())["conclusion"] is None
    assert (await nw.gate("G2"))["met"] is False


async def test_ac19_a_conflict_hit_not_cleared_blocks_the_conclusion(nw: Northwind) -> None:
    await _ready(nw)
    await nw.seed.run(
        "INSERT INTO clients (tenant_id, name) VALUES ($1, $2)",
        nw.tenant,
        f"Harborline Capital {nw.site.marker}",
    )
    check = _json(
        await nw.call(
            "POST",
            "/v1/conflict-checks",
            nw.hannah,
            {
                "subject": {"kind": "client", "id": str(nw.site.client_id)},
                "names": [f"Harborline Capital {nw.site.marker}"],
            },
        ),
        201,
    )
    hits = [r for r in cast(list[Json], check["results"]) if r["assessment"] == "pending"]
    assert hits
    facts = _refusal(await nw.conclude(), 409, "independence_preconditions_unmet")
    assert set(facts) == {"conflict_not_cleared"}
    assert "conflict_not_cleared" in _reasons(await nw.summary())
    for hit in hits:
        _json(
            await nw.call(
                "POST",
                f"/v1/conflict-checks/{check['id']}/results/{hit['id']}/clear",
                nw.hannah,
                {"assessment": "not_adverse", "reason": "A lender to the sponsor, not adverse."},
            )
        )
    _json(await nw.conclude(), 201)


async def test_ac18_margaret_concludes_independent_and_g2_reports_met(nw: Northwind) -> None:
    await _ready(nw)
    assert (await nw.gate("G2"))["met"] is False
    concluded = _json(await nw.conclude(), 201)
    assert concluded["option"] == "independent"
    assert concluded["concluded_by"] == str(nw.margaret.user_id)
    assert concluded["supersedes_id"] is None
    summary = await nw.summary()
    assert cast(Json, summary["conclusion"])["id"] == concluded["id"]
    assert await nw.audit("independence.concluded") == [("human", str(nw.margaret.user_id))]
    assert (await nw.gate("G2"))["met"] is True
    outbox = await nw.seed.value(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 "
        "AND event_type = 'independence.concluded'",
        nw.tenant,
    )
    assert outbox == 1


async def test_ac18_safeguards_are_required_and_not_independent_leaves_g2_unmet(
    nw: Northwind,
) -> None:
    await _ready(nw)
    refused = await nw.conclude("independent_with_safeguards")
    assert refused.status_code == 422, refused.text
    first = _json(await nw.conclude("not_independent"), 201)
    assert (await nw.gate("G2"))["met"] is False
    second = _json(
        await nw.conclude(
            "independent_with_safeguards",
            safeguards="Ana Cruz moved off the plan's investments testing.",
        ),
        201,
    )
    assert second["supersedes_id"] == first["id"]
    assert second["safeguards"] == "Ana Cruz moved off the plan's investments testing."
    assert (await nw.gate("G2"))["met"] is True
    # Insert-only: the first row never changes.
    with pytest.raises(asyncpg.PostgresError):
        await nw.seed.run(
            "UPDATE independence_conclusions SET option = 'independent' WHERE id = $1",
            uuid.UUID(cast(str, first["id"])),
        )


async def test_ac18_only_margaret_with_fresh_mfa_concludes(nw: Northwind) -> None:
    await _ready(nw)
    for who in (nw.hannah, nw.thomas, nw.ana, nw.grace, nw.rita):
        refused = await nw.conclude(who=who)
        assert refused.status_code in (403, 404), (who, refused.text)
    stale = await nw.conclude(mfa=False)
    assert stale.status_code == 403, stale.text
    assert await nw.audit("independence.concluded") == []
    allowed = cast(list[str], (await nw.summary(nw.hannah))["allowed_actions"])
    assert "independence.conclude" not in allowed
    assert "independence.conclude" in cast(list[str], (await nw.summary())["allowed_actions"])


# ================================================================================================
# INV-1 at every layer (AC-20)
# ================================================================================================


async def test_ac20_the_matrix_denies_the_agent_and_system_confirming_or_concluding() -> None:
    for action in ("independence.confirm", "independence.conclude"):
        rule = RULES[action]
        assert rule.decisions.get("agent") == "deny", action
        assert rule.decisions.get("system") == "deny", action
    conclude = RULES["independence.conclude"]
    assert {r for r, d in conclude.decisions.items() if d != "deny"} == {"engagement_partner"}


async def test_ac20_an_agent_or_system_context_is_refused_by_the_service(nw: Northwind) -> None:
    from abacus.modules.engagements import api as engagements_api

    # Looked up by name so this suite type-checks before T41 adds them.
    names = ("conclude_independence", "confirm_independence")
    conclude, confirm = (
        cast(Callable[..., Awaitable[object]], getattr(engagements_api, name)) for name in names
    )
    await _ready(nw)
    fresh = datetime.now(UTC) - timedelta(minutes=1)
    for kind in ("agent", "system"):
        for who in (nw.margaret, nw.ana):
            ctx = AuthContext(
                TenantContext(nw.tenant, cast(ActorKind, kind), str(who.user_id)),
                who.user_id,
                uuid.uuid4(),
                None,
                fresh,
            )
            with pytest.raises(Forbidden):
                await conclude(ctx, nw.eid, option="independent", safeguards=None)
            with pytest.raises(Forbidden):
                await confirm(
                    ctx,
                    nw.eid,
                    statement_version="northwind_2025_v1",
                    statement_codes=STATEMENTS,
                    interests_note=None,
                )
    assert (await nw.summary())["conclusion"] is None


async def test_ac20_the_database_refuses_a_conclusion_written_by_a_non_human(
    nw: Northwind,
) -> None:
    for kind in ("agent", "system", "policy"):
        with pytest.raises(asyncpg.CheckViolationError):
            await nw.seed.run(
                "INSERT INTO independence_conclusions (tenant_id, engagement_id, option, "
                "concluded_by, mfa_verified_at, actor_kind) "
                "VALUES ($1, $2, 'independent', $3, now(), $4)",
                nw.tenant,
                nw.eid,
                nw.margaret.user_id,
                kind,
            )
    register = (
        Path(__file__).resolve().parents[4] / "docs/architecture/human-only-actions.yaml"
    ).read_text(encoding="utf-8")
    assert "action: independence.concluded" in register
    assert "action: independence.confirmed" in register


async def test_ac20_only_the_independence_module_may_call_the_conclusion(
    tmp_path: Path,
) -> None:
    rel = "src/abacus/modules/requests/sneaky.py"

    def found(text: str) -> list[str]:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return [v.rule_id for v in banned_patterns.scan(tmp_path) if v.path == rel]

    assert found("VALUE = 1\n") == []
    assert found("from abacus.modules.engagements.api import conclude_independence\n") != []


# ================================================================================================
# Story 6: NAS and the SKE designee (AC-21, AC-22)
# ================================================================================================


async def test_ac21_the_tax_service_is_a_nas_row_the_engagement_partner_decides(
    nw: Northwind,
) -> None:
    nas = _json(await nw.call("GET", f"{nw.ind}/nas", nw.hannah))
    assert nas["attest_client"] is True
    rows = {cast(str, r["service_code"]): r for r in cast(list[Json], nas["rows"])}
    assert rows["tax_compliance"]["status"] == "pending"
    contact = await nw.designate_ske()
    # Hannah prepares the row; the decision is Margaret's.
    prepared = await nw.evaluate_nas(nw.hannah, status="pending")
    assert prepared["status"] == "pending"
    refused = await nw.call(
        "PUT",
        f"{nw.ind}/nas/tax_compliance",
        nw.hannah,
        {"provided": True, "status": "concluded", "evaluation": "Permitted."},
    )
    assert refused.status_code == 403, refused.text
    decided = await nw.evaluate_nas()
    assert decided["status"] == "concluded"
    assert decided["evaluated_by"] == str(nw.margaret.user_id)
    after = _json(await nw.call("GET", f"{nw.ind}/nas", nw.mia))
    assert after["ske_designee_contact_id"] == str(contact)
    assert [r["status"] for r in cast(list[Json], after["rows"])] == ["concluded"]
    assert [a for a, _ in await nw.audit("nas.evaluated")] == ["human", "human"]
    with pytest.raises(asyncpg.PostgresError):
        await nw.seed.run("DELETE FROM nas_evaluation_events WHERE tenant_id = $1", nw.tenant)
    # Staff cannot evaluate at all.
    staff = await nw.call(
        "PUT",
        f"{nw.ind}/nas/tax_compliance",
        nw.mia,
        {"provided": True, "status": "pending"},
    )
    assert staff.status_code == 403, staff.text


async def test_ac22_without_an_ske_designee_nas_and_the_conclusion_are_refused(
    nw: Northwind,
) -> None:
    _json(await nw.confirm(nw.ana))
    facts = _refusal(
        await nw.call(
            "PUT",
            f"{nw.ind}/nas/tax_compliance",
            nw.margaret,
            {"provided": True, "status": "concluded", "evaluation": "Permitted."},
        ),
        409,
        "independence_preconditions_unmet",
    )
    assert "ske_designee_missing" in facts
    facts = _refusal(await nw.conclude(), 409, "independence_preconditions_unmet")
    assert "ske_designee_missing" in facts
    assert "ske_designee_missing" in _reasons(await nw.summary())


async def test_ac22_a_non_attest_client_needs_no_ske_designee_or_nas(net: Net) -> None:
    nw = await _world(net, attest=False)
    summary = await nw.summary()
    assert summary["attest_client"] is False
    assert {"ske_designee_missing", "nas_not_evaluated"}.isdisjoint(_reasons(summary))
    nas = _json(await nw.call("GET", f"{nw.ind}/nas", nw.margaret))
    assert (nas["attest_client"], nas["rows"]) == (False, [])
    _json(await nw.confirm(nw.ana))
    _json(await nw.conclude(), 201)


# ================================================================================================
# Story 8: rotation (AC-27)
# ================================================================================================


async def test_ac27_years_served_derive_from_the_prior_engagement_chain(nw: Northwind) -> None:
    # Margaret led the six prior years' audits too; Hannah joined for the last two.
    child = nw.eid
    for back in range(1, 7):
        year = 2025 - back
        prior = cast(
            uuid.UUID,
            await nw.seed.value(
                "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, type, "
                "status, fiscal_period_start, fiscal_period_end, created_by) VALUES ($1, $2, $3, "
                "$4, 'ebp_audit', 'archived', $5, $6, $7) RETURNING id",
                nw.tenant,
                nw.site.client_id,
                nw.site.entity_id,
                f"Northwind PY{year}",
                date(year, 1, 1),
                date(year, 12, 31),
                nw.grace.user_id,
            ),
        )
        await nw.seed.run(
            "UPDATE engagements SET prior_engagement_id = $2 WHERE id = $1", child, prior
        )
        await nw.seed.run(
            "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
            "VALUES ($1, $2, $3, 'engagement_partner')",
            nw.tenant,
            prior,
            nw.margaret.user_id,
        )
        if back <= 1:
            await nw.seed.run(
                "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
                "VALUES ($1, $2, $3, 'manager')",
                nw.tenant,
                prior,
                nw.hannah.user_id,
            )
        child = prior
    rotation = _json(await nw.call("GET", f"{nw.ind}/rotation", nw.hannah))
    assert rotation["review_years"] == 7
    rows = {cast(str, r["user_id"]): r for r in cast(list[Json], rotation["rows"])}
    assert rows[str(nw.margaret.user_id)]["years_served"] == 7
    assert rows[str(nw.margaret.user_id)]["familiarity_flag"] is True
    assert rows[str(nw.hannah.user_id)]["years_served"] == 2
    assert rows[str(nw.hannah.user_id)]["familiarity_flag"] is False
    assert rows[str(nw.ana.user_id)]["years_served"] == 1


# ================================================================================================
# Story 9: breaches (AC-28)
# ================================================================================================


async def test_ac28_the_banner_stays_until_three_events_and_the_log_is_insert_only(
    nw: Northwind,
) -> None:
    await _ready(nw)
    _json(await nw.conclude(), 201)
    breach = _json(
        await nw.call(
            "POST",
            f"{nw.ind}/breaches",
            nw.hannah,
            {
                "description": "Mia Dorsey bought sponsor shares on Sep 2.",
                "user_id": str(nw.mia.user_id),
            },
        ),
        201,
    )
    assert breach["resolved"] is False
    assert [e["kind"] for e in cast(list[Json], breach["events"])] == ["logged"]
    assert "breach_open" in _reasons(await nw.summary())
    assert (await nw.gate("G2"))["met"] is False
    path = f"{nw.ind}/breaches/{breach['id']}/events"
    for who, kind in ((nw.margaret, "evaluated"), (nw.rita, "tcwg_communicated")):
        step = _json(await nw.call("POST", path, who, {"kind": kind, "note": "Recorded."}), 201)
        assert step["resolved"] is False
    staff = await nw.call("POST", path, nw.mia, {"kind": "remediated"})
    assert staff.status_code == 403, staff.text
    done = _json(await nw.call("POST", path, nw.hannah, {"kind": "remediated"}), 201)
    assert done["resolved"] is True
    assert "breach_open" not in _reasons(await nw.summary())
    assert await nw.audit("independence_breach.logged") == [("human", str(nw.hannah.user_id))]
    assert len(await nw.audit("independence_breach.updated")) == 3
    for delete in (
        "DELETE FROM independence_breaches WHERE tenant_id = $1",
        "DELETE FROM independence_breach_events WHERE tenant_id = $1",
    ):
        with pytest.raises(asyncpg.PostgresError):
            await nw.seed.run(delete, nw.tenant)


# ================================================================================================
# Walls (INV-3), tenancy and the flag
# ================================================================================================


async def test_inv3_a_walled_member_and_another_firm_get_404(nw: Northwind, net: Net) -> None:
    _json(
        await nw.call(
            "POST",
            "/v1/walls",
            nw.grace,
            {"user_id": str(nw.mia.user_id), "client_id": str(nw.site.client_id)},
        ),
        201,
    )
    assert (await nw.call("GET", nw.ind, nw.mia)).status_code == 404
    other = await net.seed.firm()
    stranger = await net.seed.person(other, "firm_admin")
    assert (await net.call("GET", nw.ind, stranger)).status_code == 404
