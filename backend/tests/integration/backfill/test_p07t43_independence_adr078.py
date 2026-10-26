# ac-test-author: ayushkbhatia
"""P-07-T43, second session (ADR-078, TASK-1348): independent AC tests for P-07-T41's
independence (CLI-08), written from the contract and not from T41's code or TASK-1323's suite.

"Self-only confirmation, decline note, conclusion EP-only with MFA and preconditions (INV-1),
breach events insert-only, rotation derivation, G2 provider and attest-only scope."

Sources: `docs/contracts/acceptance-independence.md` (§1 "Independence as built", §2, §5, §6,
§7), `docs/architecture/permission-matrix/engagements.yaml` and `identity.yaml`
(`independence.annual_read`), DEC-428 and DEC-429. HTTP through `create_app()` with fake
sign-in tokens, `engagements.v2` and `engagements.acceptance_v2` on.

The cast (synthetic): Brightwater Hale's Northwind Robotics 401(k) Plan PY2025 audit, an attest
client. Margaret Okonkwo (engagement partner, partner level), Hannah Leclerc (manager), Thomas
Whitcombe (senior), Mia Dorsey and Ana Cruz (staff); Grace Holloway (firm admin, no role here);
Rita Vance (quality partner). Ana's confirmation is open; the others have confirmed.

Readings of the contract this suite takes (recorded in TASK-1348):
- "for oneself only": a body naming another person is either refused (422) or ignored; in both
  cases only the caller's row may move.
- the decline note is "read only by the person and by whoever holds `independence.conclude`
  here": the engagement partner; the manager and the other members read null.
- a missing fresh MFA factor answers 401 or 403 (the matrix's `mfa_recent`); nothing is written.
- a conclusion needs a partner-level engagement partner; a manager-level one is refused with a
  4xx and nothing written (the contract names no code).
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, cast

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.db.session import ActorKind
from abacus.modules.engagements import api as engagements_api
from abacus.modules.identity.api import AuthContext, Forbidden

from .support import Net, Person, Seeder, Site

Json = dict[str, object]
CODES: Final = ["no_financial_interest", "no_family_in_key_position", "not_a_participant"]
VERSION: Final = "northwind_2025_v1"


@dataclass
class Plan:
    net: Net
    seed: Seeder
    tenant: uuid.UUID
    site: Site
    grace: Person
    rita: Person
    margaret: Person
    hannah: Person
    thomas: Person
    mia: Person
    ana: Person

    @property
    def eid(self) -> uuid.UUID:
        return self.site.engagement_id

    @property
    def base(self) -> str:
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
        return await self.net.call(method, path, who, body=body, mfa=mfa)

    async def summary(self, who: Person) -> Json:
        return _ok(await self.call("GET", self.base, who))

    async def confirm(self, who: Person, **extra: object) -> httpx.Response:
        body: Json = {"statement_version": VERSION, "statement_codes": CODES, **extra}
        return await self.call("POST", f"{self.base}/confirm", who, body)

    async def conclude(
        self, who: Person | None = None, option: str = "independent", **kw: object
    ) -> httpx.Response:
        body: Json = {"option": option, **kw}
        return await self.call("POST", f"{self.base}/conclude", who or self.margaret, body)

    async def ske(self) -> None:
        contact = await self.seed.value(
            "INSERT INTO contacts (tenant_id, client_id, display_name, contact_kind) "
            "VALUES ($1, $2, 'Dana Kowalski', 'client_person') RETURNING id",
            self.tenant,
            self.site.client_id,
        )
        await self.seed.run(
            "INSERT INTO engagement_contacts (tenant_id, engagement_id, contact_id, designation, "
            "designated_by) VALUES ($1, $2, $3, 'ske_designee', $4)",
            self.tenant,
            self.eid,
            contact,
            self.margaret.user_id,
        )

    async def nas(self, who: Person, status: str, code: str = "tax_compliance") -> httpx.Response:
        return await self.call(
            "PUT",
            f"{self.base}/nas/{code}",
            who,
            {"provided": True, "status": status, "evaluation": "Management owns the returns."},
        )

    async def ready(self) -> None:
        assert (await self.confirm(self.ana)).status_code == 200
        await self.ske()
        assert (await self.nas(self.margaret, "concluded")).status_code == 200

    async def g2(self) -> Json:
        gates = cast(
            list[Json],
            _ok(await self.call("GET", f"/v1/engagements/{self.eid}/gates", self.margaret)),
        )
        return next(g for g in gates if g["gate"] == "G2")

    async def conclusions(self) -> int:
        return cast(
            int,
            await self.seed.value(
                "SELECT count(*) FROM independence_conclusions WHERE engagement_id = $1", self.eid
            ),
        )


def _ok(response: httpx.Response, status: int = 200) -> Json:
    assert response.status_code == status, response.text
    return cast(Json, response.json())


def _refused(response: httpx.Response, status: int, detail: str) -> Json:
    assert response.status_code == status, response.text
    body = cast(Json, response.json())
    assert body["detail"] == detail, body
    return cast(Json, body.get("facts") or {})


def _member(summary: Json, who: Person) -> Json:
    return next(
        m for m in cast(list[Json], summary["members"]) if m["user_id"] == str(who.user_id)
    )


def _blockers(summary: Json) -> list[tuple[str, str]]:
    return [
        (cast(str, b["reason_code"]), cast(str, b["ref_id"]))
        for b in cast(list[Json], summary["blockers"])
    ]


async def _level(seed: Seeder, tenant: uuid.UUID, who: Person, level: str) -> None:
    await seed.run(
        "UPDATE memberships SET level = $3 WHERE tenant_id = $1 AND user_id = $2",
        tenant,
        who.user_id,
        level,
    )


async def _seat(seed: Seeder, site: Site, who: Person, role: str, *, confirmed: bool) -> None:
    await seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES ($1, $2, $3, $4)",
        site.tenant_id,
        site.engagement_id,
        who.user_id,
        role,
    )
    await seed.run(
        "INSERT INTO independence_confirmations (tenant_id, engagement_id, user_id, status, "
        "statement_version, answered_at) VALUES ($1, $2, $3, $4, $5, $6)",
        site.tenant_id,
        site.engagement_id,
        who.user_id,
        "confirmed" if confirmed else "requested",
        "v1" if confirmed else None,
        datetime.now(UTC) if confirmed else None,
    )


async def _plan(net: Net, *, attest: bool = True) -> Plan:
    seed = net.seed
    tenant = await seed.firm()
    for flag in ("engagements.v2", "engagements.acceptance_v2"):
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'TASK-1348')",
            tenant,
            flag,
        )
    grace = await seed.person(tenant, "firm_admin")
    rita = await seed.person(tenant, "quality_partner")
    people: dict[str, Person] = {}
    for name, level in (
        ("margaret", "partner"),
        ("hannah", "manager"),
        ("thomas", "senior"),
        ("mia", "staff"),
        ("ana", "staff"),
    ):
        people[name] = await seed.person(tenant)
        await _level(seed, tenant, people[name], level)
    site = await seed.site(tenant, grace.user_id, "Northwind", opened=False)
    if attest:
        await seed.attest(tenant, site.engagement_id)
    for name, role in (
        ("margaret", "engagement_partner"),
        ("hannah", "manager"),
        ("thomas", "senior"),
        ("mia", "staff"),
        ("ana", "staff"),
    ):
        await _seat(seed, site, people[name], role, confirmed=name != "ana")
    # The firm also prepares the plan's Form 5500: a service outside the attest family.
    await seed.run(
        "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, type, status, "
        "fiscal_period_start, fiscal_period_end, created_by) VALUES ($1, $2, $3, "
        "'Northwind 5500 PY2025', 'tax_compliance', 'active', '2025-01-01', '2025-12-31', $4)",
        tenant,
        site.client_id,
        site.entity_id,
        grace.user_id,
    )
    return Plan(net, seed, tenant, site, grace, rita, **people)


@pytest.fixture
async def plan(net: Net) -> Plan:
    return await _plan(net)


# --- confirmation is the caller's own -----------------------------------------------------------


async def test_ac17_a_confirmation_naming_someone_else_moves_only_the_callers_row(
    plan: Plan,
) -> None:
    await plan.seed.run(
        "UPDATE independence_confirmations SET status = 'requested', answered_at = NULL "
        "WHERE engagement_id = $1 AND user_id = $2",
        plan.eid,
        plan.mia.user_id,
    )
    sneaky = await plan.confirm(plan.ana, user_id=str(plan.mia.user_id))
    assert sneaky.status_code in (200, 422), sneaky.text
    if sneaky.status_code == 200:
        assert sneaky.json()["user_id"] == str(plan.ana.user_id)
    after = await plan.summary(plan.margaret)
    assert _member(after, plan.mia)["confirmation"] == "requested"
    # Mia herself may still answer, and only her own answer moves her row.
    assert (await plan.confirm(plan.mia)).status_code == 200
    assert _member(await plan.summary(plan.margaret), plan.mia)["confirmation"] == "confirmed"


async def test_ac17_someone_with_no_role_here_cannot_confirm_or_decline(plan: Plan) -> None:
    for who in (plan.grace, plan.rita):
        assert (await plan.confirm(who)).status_code in (403, 404), who
        declined = await plan.call(
            "POST", f"{plan.base}/decline", who, {"note": "I hold plan assets."}
        )
        assert declined.status_code in (403, 404)
    rows = await plan.seed.rows(
        "SELECT user_id FROM independence_confirmations WHERE engagement_id = $1", plan.eid
    )
    assert {r["user_id"] for r in rows} == {
        p.user_id for p in (plan.margaret, plan.hannah, plan.thomas, plan.mia, plan.ana)
    }


@pytest.mark.parametrize(
    "codes",
    [
        [],
        CODES[:2],
        [CODES[0], CODES[0], CODES[1]],
        [*CODES, "no_loans"],
    ],
)
async def test_ac17_exactly_three_distinct_statements(plan: Plan, codes: list[str]) -> None:
    refused = await plan.call(
        "POST",
        f"{plan.base}/confirm",
        plan.ana,
        {"statement_version": VERSION, "statement_codes": codes},
    )
    assert refused.status_code == 422, refused.text
    assert _member(await plan.summary(plan.ana), plan.ana)["confirmation"] == "requested"


async def test_ac17_a_confirmation_is_audited_as_the_person_and_announced(plan: Plan) -> None:
    confirmed = _ok(await plan.confirm(plan.ana))
    assert (confirmed["user_id"], confirmed["confirmation"]) == (
        str(plan.ana.user_id),
        "confirmed",
    )
    audit = await plan.seed.rows(
        "SELECT actor_kind, actor_id FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'independence.confirmed'",
        plan.tenant,
    )
    assert [(r["actor_kind"], r["actor_id"]) for r in audit] == [("human", str(plan.ana.user_id))]
    outbox = await plan.seed.value(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 "
        "AND event_type = 'independence.confirmed'",
        plan.tenant,
    )
    assert outbox == 1


# --- the decline note: sealed, and read only as the contract says ------------------------------


async def test_ac17_the_decline_note_is_sealed_and_read_only_by_the_person_and_the_ep(
    plan: Plan,
) -> None:
    note = f"My spouse holds a participant account {uuid.uuid4().hex[:8]}"
    declined = _ok(await plan.call("POST", f"{plan.base}/decline", plan.ana, {"note": note}))
    assert declined["confirmation"] == "declined"
    # The person and the engagement partner (`independence.conclude` here) read it.
    for reader in (plan.ana, plan.margaret):
        assert _member(await plan.summary(reader), plan.ana)["decline_note"] == note, reader
    # Nobody else on the team does, nor the quality partner reading in scope.
    for reader in (plan.hannah, plan.thomas, plan.mia):
        summary = await plan.summary(reader)
        assert _member(summary, plan.ana)["decline_note"] is None, reader
        assert note not in str(summary)
    # The banner names the decline, by identifier only.
    summary = await plan.summary(plan.hannah)
    assert ("member_declined", str(plan.ana.user_id)) in _blockers(summary)
    # Sealed at rest: the words appear in no column of the row, nor in the audit trail.
    row = await plan.seed.value(
        "SELECT c::text FROM independence_confirmations c WHERE engagement_id = $1 "
        "AND user_id = $2",
        plan.eid,
        plan.ana.user_id,
    )
    assert note not in cast(str, row)
    trail = await plan.seed.rows(
        "SELECT a::text AS t FROM audit_events a WHERE tenant_id = $1", plan.tenant
    )
    assert all(note not in cast(str, r["t"]) for r in trail)


async def test_ac17_a_decline_needs_a_note(plan: Plan) -> None:
    for body in ({}, {"note": ""}):
        refused = await plan.call("POST", f"{plan.base}/decline", plan.ana, body)
        assert refused.status_code == 422, refused.text
    assert _member(await plan.summary(plan.ana), plan.ana)["confirmation"] == "requested"


# --- reminders are a person's -------------------------------------------------------------------


async def test_ac17_reminders_are_sent_by_the_ep_or_manager_and_counted(plan: Plan) -> None:
    body = {"user_ids": [str(plan.ana.user_id)]}
    for who in (plan.thomas, plan.mia):
        assert (await plan.call("POST", f"{plan.base}/reminders", who, body)).status_code in (
            403,
            404,
        )
    sent = _ok(await plan.call("POST", f"{plan.base}/reminders", plan.hannah, body))
    assert sent["reminded_user_ids"] == [str(plan.ana.user_id)]
    assert _member(await plan.summary(plan.hannah), plan.ana)["reminder_count"] == 1
    audit = await plan.seed.rows(
        "SELECT actor_kind, actor_id FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'independence.reminded'",
        plan.tenant,
    )
    assert [(r["actor_kind"], r["actor_id"]) for r in audit] == [
        ("human", str(plan.hannah.user_id))
    ]
    # A member whose confirmation is not open is not reminded.
    refused = await plan.call(
        "POST", f"{plan.base}/reminders", plan.hannah, {"user_ids": [str(plan.mia.user_id)]}
    )
    assert refused.status_code == 422, refused.text


# --- the conclusion: the EP's, partner level, fresh MFA, preconditions --------------------------


async def test_ac19_the_conclusion_counts_each_blocker_reason(plan: Plan) -> None:
    await plan.call("POST", f"{plan.base}/decline", plan.mia, {"note": "A family member."})
    facts = _refused(await plan.conclude(), 409, "independence_preconditions_unmet")
    assert facts.get("member_not_confirmed") == 1, facts  # Ana
    assert facts.get("member_declined") == 1, facts  # Mia
    assert facts.get("ske_designee_missing") == 1, facts  # an attest client with no designee
    assert cast(int, facts.get("nas_not_evaluated", 0)) >= 1, facts
    assert all(isinstance(v, int) for v in facts.values()), facts
    assert await plan.conclusions() == 0


async def test_ac18_only_the_engagement_partner_concludes(plan: Plan) -> None:
    await plan.ready()
    for who in (plan.hannah, plan.thomas, plan.grace, plan.rita):
        refused = await plan.conclude(who)
        assert refused.status_code in (403, 404), (who, refused.text)
    assert await plan.conclusions() == 0


async def test_ac18_the_conclusion_needs_a_fresh_second_factor(plan: Plan) -> None:
    await plan.ready()
    stale = await plan.call(
        "POST", f"{plan.base}/conclude", plan.margaret, {"option": "independent"}, mfa=False
    )
    assert stale.status_code in (401, 403), stale.text
    assert await plan.conclusions() == 0


async def test_ac18_an_engagement_partner_below_partner_level_cannot_conclude(
    plan: Plan,
) -> None:
    await plan.ready()
    await _level(plan.seed, plan.tenant, plan.margaret, "manager")
    refused = await plan.conclude()
    assert 400 <= refused.status_code < 500, refused.text
    assert await plan.conclusions() == 0


async def test_ac18_safeguards_go_with_independent_with_safeguards(plan: Plan) -> None:
    await plan.ready()
    refused = await plan.conclude(option="independent_with_safeguards")
    assert refused.status_code == 422, refused.text
    assert await plan.conclusions() == 0


async def test_ac18_a_conclusion_supersedes_the_newest_and_never_changes_it(plan: Plan) -> None:
    await plan.ready()
    first = _ok(await plan.conclude(), 201)
    before = await plan.seed.value(
        "SELECT c::text FROM independence_conclusions c WHERE engagement_id = $1", plan.eid
    )
    second = _ok(
        await plan.conclude(
            option="independent_with_safeguards", safeguards="A second partner reviews the 5500."
        ),
        201,
    )
    summary = await plan.summary(plan.hannah)
    conclusion = cast(Json, summary["conclusion"])
    assert conclusion["option"] == "independent_with_safeguards"
    assert conclusion["supersedes_id"] == _conclusion_id(first)
    assert _conclusion_id(second) != _conclusion_id(first)
    after = await plan.seed.value(
        "SELECT c::text FROM independence_conclusions c WHERE id = $1",
        uuid.UUID(_conclusion_id(first)),
    )
    assert after == before
    successors = await plan.seed.rows(
        "SELECT supersedes_id, count(*) AS n FROM independence_conclusions "
        "WHERE engagement_id = $1 AND supersedes_id IS NOT NULL GROUP BY supersedes_id",
        plan.eid,
    )
    assert [r["n"] for r in successors] == [1]


def _conclusion_id(answer: Json) -> str:
    """The conclusion's id, whether the route answers the conclusion or the summary."""
    if "conclusion" in answer and isinstance(answer["conclusion"], dict):
        return cast(str, cast(Json, answer["conclusion"])["id"])
    return cast(str, answer["id"])


async def _race(plan: Plan) -> list[httpx.Response]:
    await plan.ready()
    _ok(await plan.conclude(), 201)
    return list(await asyncio.gather(plan.conclude(), plan.conclude(), plan.conclude()))


async def test_ac18_concurrent_conclusions_leave_one_successor_each(plan: Plan) -> None:
    answers = await _race(plan)
    assert any(a.status_code == 201 for a in answers), [a.text for a in answers]
    successors = await plan.seed.rows(
        "SELECT supersedes_id, count(*) AS n FROM independence_conclusions "
        "WHERE engagement_id = $1 AND supersedes_id IS NOT NULL GROUP BY supersedes_id",
        plan.eid,
    )
    assert successors and all(r["n"] == 1 for r in successors), successors


async def test_ac18_a_losing_concurrent_conclusion_answers_409_never_500(plan: Plan) -> None:
    # Five rounds of three racers, so the defect shows whatever the scheduling of one round.
    answers = await _race(plan)
    for _ in range(4):
        answers += await asyncio.gather(plan.conclude(), plan.conclude(), plan.conclude())
    assert all(a.status_code in (201, 409) for a in answers), [a.text for a in answers]


async def test_ac20_an_agent_or_system_context_never_confirms_or_concludes(plan: Plan) -> None:
    await plan.ready()
    fresh = datetime.now(UTC) - timedelta(minutes=1)
    for kind in ("agent", "system"):
        ctx = AuthContext(
            TenantContext(plan.tenant, cast(ActorKind, kind), str(plan.margaret.user_id)),
            plan.margaret.user_id,
            uuid.uuid4(),
            None,
            fresh,
        )
        with pytest.raises(Forbidden):
            await engagements_api.conclude_independence(
                ctx, plan.eid, option="independent", safeguards=None
            )
        with pytest.raises(Forbidden):
            await engagements_api.confirm_independence(
                ctx,
                plan.eid,
                statement_version=VERSION,
                statement_codes=CODES,
                interests_note=None,
            )
    assert await plan.conclusions() == 0


# --- breaches: each event once, insert-only, and G2 ------------------------------------------


async def test_ac28_a_breach_keeps_g2_unmet_until_all_three_events(plan: Plan) -> None:
    await plan.ready()
    _ok(await plan.conclude(), 201)
    assert (await plan.g2())["met"] is True
    breach = _ok(
        await plan.call(
            "POST",
            f"{plan.base}/breaches",
            plan.rita,
            {
                "description": "A staff member bought plan sponsor stock.",
                "user_id": str(plan.mia.user_id),
            },
        ),
        201,
    )
    assert breach["resolved"] is False
    assert (await plan.g2())["met"] is False
    assert ("breach_open", cast(str, breach["id"])) in _blockers(await plan.summary(plan.hannah))
    events = f"{plan.base}/breaches/{breach['id']}/events"
    for kind in ("evaluated", "tcwg_communicated"):
        _ok(await plan.call("POST", events, plan.hannah, {"kind": kind}), 201)
    again = await plan.call("POST", events, plan.hannah, {"kind": "evaluated"})
    _refused(again, 409, "illegal_transition")
    assert (await plan.g2())["met"] is False
    done = _ok(await plan.call("POST", events, plan.margaret, {"kind": "remediated"}), 201)
    assert done["resolved"] is True
    assert (await plan.g2())["met"] is True


async def test_ac28_a_breach_does_not_block_the_conclusion_itself(plan: Plan) -> None:
    await plan.ready()
    _ok(
        await plan.call(
            "POST", f"{plan.base}/breaches", plan.hannah, {"description": "A loan to a trustee."}
        ),
        201,
    )
    assert (await plan.conclude()).status_code == 201
    assert (await plan.g2())["met"] is False


async def test_ac28_breach_events_are_insert_only_for_the_app(plan: Plan) -> None:
    breach = _ok(
        await plan.call(
            "POST", f"{plan.base}/breaches", plan.hannah, {"description": "A loan to a trustee."}
        ),
        201,
    )
    _ok(
        await plan.call(
            "POST",
            f"{plan.base}/breaches/{breach['id']}/events",
            plan.hannah,
            {"kind": "evaluated"},
        ),
        201,
    )
    for verb in (
        "DELETE FROM independence_breaches",
        "UPDATE independence_breaches SET tenant_id = tenant_id",
        "DELETE FROM independence_breach_events",
        "UPDATE independence_breach_events SET tenant_id = tenant_id",
    ):
        with pytest.raises(DBAPIError):
            async with tenant_session(
                TenantContext(plan.tenant, "human", str(plan.hannah.user_id))
            ) as session:
                await session.execute(text(verb))
    events = await plan.seed.value(
        "SELECT count(*) FROM independence_breach_events WHERE tenant_id = $1", plan.tenant
    )
    assert events == 1


async def test_ac28_breaches_are_managed_by_the_ep_manager_or_quality_partner(plan: Plan) -> None:
    for who in (plan.thomas, plan.mia):
        refused = await plan.call(
            "POST", f"{plan.base}/breaches", who, {"description": "A loan to a trustee."}
        )
        assert refused.status_code in (403, 404), refused.text


# --- NAS and the SKE designee: attest clients only ---------------------------------------------


async def test_ac21_the_ep_decides_a_nas_row_and_then_it_is_locked(plan: Plan) -> None:
    await plan.ske()
    nas = _ok(await plan.call("GET", f"{plan.base}/nas", plan.hannah))
    assert nas["attest_client"] is True
    assert [r["service_code"] for r in cast(list[Json], nas["rows"])] == ["tax_compliance"]
    # The manager prepares (pending) but may not decide.
    assert (await plan.nas(plan.hannah, "pending")).status_code == 200
    assert (await plan.nas(plan.hannah, "concluded")).status_code == 403
    _ok(await plan.nas(plan.margaret, "concluded"))
    _refused(await plan.nas(plan.hannah, "pending"), 409, "decision_locked")
    rows = cast(list[Json], _ok(await plan.call("GET", f"{plan.base}/nas", plan.thomas))["rows"])
    assert [(r["status"], r["evaluated_by"]) for r in rows] == [
        ("concluded", str(plan.margaret.user_id))
    ]


async def test_ac21_a_service_the_firm_does_not_provide_is_invalid(plan: Plan) -> None:
    await plan.ske()
    for code in ("bookkeeping", "ebp_audit"):  # not provided; the attest family itself
        facts = _refused(await plan.nas(plan.margaret, "concluded", code), 422, "invalid")
        assert facts.get("field") == "service_code", facts


async def test_ac22_without_an_ske_designee_nas_is_refused(plan: Plan) -> None:
    facts = _refused(
        await plan.nas(plan.margaret, "concluded"), 409, "independence_preconditions_unmet"
    )
    assert "ske_designee_missing" in facts, facts


async def test_attest_only_a_non_attest_client_has_no_nas_and_no_designee_blocker(
    net: Net,
) -> None:
    plan = await _plan(net, attest=False)
    summary = await plan.summary(plan.margaret)
    assert summary["attest_client"] is False
    reasons = {r for r, _ in _blockers(summary)}
    assert reasons <= {"member_not_confirmed"}, reasons
    nas = _ok(await plan.call("GET", f"{plan.base}/nas", plan.margaret))
    assert (nas["attest_client"], nas["rows"]) == (False, [])
    facts = _refused(await plan.nas(plan.margaret, "concluded"), 422, "invalid")
    assert facts.get("field") == "attest_client", facts
    assert (await plan.confirm(plan.ana)).status_code == 200
    assert (await plan.conclude()).status_code == 201
    assert (await plan.g2())["met"] is True


# --- G2 -----------------------------------------------------------------------------------------


async def test_ac18_g2_is_met_from_the_conclusions_time_and_not_on_not_independent(
    plan: Plan,
) -> None:
    await plan.ready()
    assert (await plan.g2())["met"] is False
    concluded = _ok(await plan.conclude(), 201)
    gate = await plan.g2()
    assert gate["met"] is True
    at = cast(
        datetime,
        await plan.seed.value(
            "SELECT concluded_at FROM independence_conclusions WHERE id = $1",
            uuid.UUID(_conclusion_id(concluded)),
        ),
    )
    assert datetime.fromisoformat(cast(str, gate["met_at"])) == at
    _ok(await plan.conclude(option="not_independent"), 201)
    assert (await plan.g2())["met"] is False


# --- rotation -----------------------------------------------------------------------------------


async def test_ac27_rotation_counts_back_along_the_chain_without_a_gap(plan: Plan) -> None:
    """Margaret sat on all seven prior years: eight served, past the seven-year review. Thomas
    sat on the four prior years without a break: five. Mia sat on the year before last but not
    last year: one (this year's) only."""
    previous = plan.eid
    chain: list[uuid.UUID] = []
    for year in range(2024, 2017, -1):
        prior = cast(
            uuid.UUID,
            await plan.seed.value(
                "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, type, "
                "status, fiscal_period_start, fiscal_period_end, created_by) VALUES ($1, $2, $3, "
                "$4, 'ebp_audit', 'delivered', make_date($5, 1, 1), make_date($5, 12, 31), $6) "
                "RETURNING id",
                plan.tenant,
                plan.site.client_id,
                plan.site.entity_id,
                f"Northwind PY{year}",
                year,
                plan.grace.user_id,
            ),
        )
        await plan.seed.run(
            "UPDATE engagements SET prior_engagement_id = $2 WHERE id = $1", previous, prior
        )
        chain.append(prior)
        previous = prior
    for n, prior in enumerate(chain):
        seats = [(plan.margaret, "engagement_partner")]
        if n < 4:
            seats.append((plan.thomas, "senior"))
        if n == 1:
            seats.append((plan.mia, "staff"))
        for who, role in seats:
            await plan.seed.run(
                "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
                "VALUES ($1, $2, $3, $4)",
                plan.tenant,
                prior,
                who.user_id,
                role,
            )
    rotation = _ok(await plan.call("GET", f"{plan.base}/rotation", plan.hannah))
    assert rotation["review_years"] == 7
    years = {
        r["user_id"]: (r["years_served"], r["familiarity_flag"])
        for r in cast(list[Json], rotation["rows"])
    }
    assert years[str(plan.margaret.user_id)] == (8, True)
    assert years[str(plan.thomas.user_id)][0] == 5
    assert years[str(plan.thomas.user_id)][1] is False
    assert years[str(plan.mia.user_id)] == (1, False)


# --- the annual confirmation is read only by who may ---------------------------------------------


async def test_annual_confirmed_is_null_for_a_reader_without_annual_read(plan: Plan) -> None:
    for member in cast(list[Json], (await plan.summary(plan.hannah))["members"]):
        assert member["annual_confirmed"] is None, member
    for member in cast(list[Json], (await plan.summary(plan.margaret))["members"]):
        assert isinstance(member["annual_confirmed"], bool), member


# --- walls (INV-3) and another firm (INV-2) -----------------------------------------------------


async def test_inv3_a_walled_member_gets_404_everywhere(plan: Plan) -> None:
    await plan.net.wall(plan.grace, plan.thomas, plan.site)
    for method, path, body in (
        ("GET", plan.base, None),
        ("GET", f"{plan.base}/nas", None),
        ("GET", f"{plan.base}/rotation", None),
        ("POST", f"{plan.base}/confirm", {"statement_version": VERSION, "statement_codes": CODES}),
    ):
        found = await plan.call(method, path, plan.thomas, body)
        assert found.status_code == 404, (path, found.text)


async def test_inv2_another_firms_person_and_ids_answer_404(plan: Plan, net: Net) -> None:
    other = await _plan(net)
    for method, path, body in (
        ("GET", plan.base, None),
        ("POST", f"{plan.base}/confirm", {"statement_version": VERSION, "statement_codes": CODES}),
        ("POST", f"{plan.base}/conclude", {"option": "independent"}),
    ):
        found = await other.call(method, path, other.margaret, body)
        assert found.status_code == 404, (path, found.text)
    assert await plan.conclusions() == 0
    assert _member(await plan.summary(plan.margaret), plan.ana)["confirmation"] == "requested"
