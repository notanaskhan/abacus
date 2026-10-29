# ac-test-author: ayushkbhatia
"""P-07-T44, second session (ADR-078, TASK-1349): independent AC tests for P-07-T42's single
intake commit (CLI-06), written from the contract and not from T42's code or TASK-1324's suite.

"Atomicity, Idempotency-Key replay, Prospect-only creation under client.intake, conflict check
required before commit, estate validation, SSN guard on real tenants."

Sources: `docs/contracts/intake-import.md` (§1 "Behaviour" and "Live intake", §2, §6, §7), the
organisations matrix (`client.intake`, `client.create`), DEC-43 (walls), DEC-430 and DEC-441.
HTTP through `create_app()` behind `clients.v2` (with `engagements.v2` and
`engagements.acceptance_v2` for the conflict check and the acceptance record).

The cast (synthetic): Brightwater Hale adds the Estate of Walter Thornbury under the existing
client Walter Thornbury. Grace Holloway (firm admin) runs the intake; Daniel Reyes (partner) is
the engagement partner; Samuel Ito (manager) clears conflict hits; Kira Ross (staff) holds no
intake right.

Readings of the contract this suite takes (TASK-1349):
- a refused commit (any 4xx) writes nothing at all, and the draft stays committable;
- "a committed draft answers its stored result again", under any key and either body;
- concurrent commits of one draft create one client entity, whatever each answers.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, cast

import httpx
import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.db.session import ActorKind
from abacus.modules.engagements.api import commit_client_intake
from abacus.modules.identity.api import RULES, AuthContext, Forbidden

from .support import Net, Person, Seeder

Json = dict[str, object]
DRAFTS: Final = "/v1/client-intake-drafts"
FLAGS: Final = ("clients.v2", "engagements.v2", "engagements.acceptance_v2")
FOOTPRINT: Final = (
    "SELECT count(*) FROM clients WHERE tenant_id = $1",
    "SELECT count(*) FROM client_entities WHERE tenant_id = $1",
    "SELECT count(*) FROM engagements WHERE tenant_id = $1",
    "SELECT count(*) FROM work_items WHERE tenant_id = $1",
    "SELECT count(*) FROM contacts WHERE tenant_id = $1",
    "SELECT count(*) FROM entity_relationships WHERE tenant_id = $1",
    "SELECT count(*) FROM acceptance_records WHERE tenant_id = $1",
)


@dataclass
class Intake:
    net: Net
    seed: Seeder
    tenant: uuid.UUID
    grace: Person
    daniel: Person
    samuel: Person
    kira: Person
    walter: uuid.UUID
    walter_entity: uuid.UUID
    tag: str

    async def call(
        self,
        method: str,
        path: str,
        who: Person,
        body: Mapping[str, object] | None = None,
        *,
        key: str | None = None,
    ) -> httpx.Response:
        headers = self.net.headers(who)
        if key is not None:
            headers["Idempotency-Key"] = key
        return await self.net.http.request(method, path, json=body, headers=headers)

    def payload(
        self, *, estate: str | None = None, check: object = None, died: bool = True
    ) -> Json:
        entity: Json = {
            "mode": "existing_client",
            "client_id": str(self.walter),
            "entity_name": estate or f"Estate of Walter Thornbury {self.tag}",
            "entity_type": "estate",
        }
        if died:
            entity["date_of_death"] = "2026-03-14"
        period = {"fiscal_period_start": "2026-01-01", "fiscal_period_end": "2026-12-31"}
        body: Json = {
            "entity": entity,
            "relationships": [{"kind": "estate_of", "related_entity_id": str(self.walter_entity)}],
            "contacts": [
                {
                    "display_name": f"Paul Thornbury {self.tag}",
                    "email": f"paul.{self.tag}@example.test",
                    "roles": ["executor"],
                }
            ],
            "services": [
                {"type_code": "forms_706_709", "forms": ["706"], **period},
                {"type_code": "form_1041", **period},
                {"type_code": "form_1040", **period},
            ],
            "engagement_partner_user_id": str(self.daniel.user_id),
        }
        if check is not None:
            body["conflict_check_id"] = str(check)
        return body

    async def create(self, payload: Json, who: Person | None = None) -> Json:
        return _ok(
            await self.call(
                "POST", DRAFTS, who or self.grace, {"step": "entity", "payload": payload}
            ),
            201,
        )

    async def save(self, draft: Json, payload: Json, who: Person | None = None) -> Json:
        return _ok(
            await self.call(
                "PATCH",
                f"{DRAFTS}/{draft['id']}",
                who or self.grace,
                {"seen_version": draft["version"], "step": "review", "payload": payload},
            )
        )

    async def check(self, draft: Json, *, clear: bool = True) -> uuid.UUID:
        run = _ok(
            await self.call(
                "POST",
                "/v1/conflict-checks",
                self.grace,
                {
                    "subject": {"kind": "client_intake_draft", "id": str(draft["id"])},
                    "names": [f"Estate of Walter Thornbury {self.tag}"],
                },
            ),
            201,
        )
        if clear:
            for result in cast(list[Json], run["results"]):
                _ok(
                    await self.call(
                        "POST",
                        f"/v1/conflict-checks/{run['id']}/results/{result['id']}/clear",
                        self.samuel,
                        {
                            "assessment": "same_family_not_adverse",
                            "reason": "The decedent's own estate.",
                        },
                    )
                )
        return uuid.UUID(cast(str, run["id"]))

    async def ready(self, who: Person | None = None) -> Json:
        draft = await self.create(self.payload(), who)
        check = await self.check(draft)
        return await self.save(draft, self.payload(check=check), who)

    async def commit_intake(
        self,
        draft: Json,
        *,
        key: str | None = None,
        start_acceptance: bool = False,
        who: Person | None = None,
    ) -> httpx.Response:
        return await self.call(
            "POST",
            f"{DRAFTS}/{draft['id']}/commit",
            who or self.grace,
            {"start_acceptance": start_acceptance},
            key=key or uuid.uuid4().hex,
        )

    async def footprint(self) -> list[int]:
        return [cast(int, await self.seed.value(sql, self.tenant)) for sql in FOOTPRINT]

    async def estates(self) -> int:
        return cast(
            int,
            await self.seed.value(
                "SELECT count(*) FROM client_entities WHERE tenant_id = $1 AND name = $2",
                self.tenant,
                f"Estate of Walter Thornbury {self.tag}",
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


async def _level(seed: Seeder, tenant: uuid.UUID, who: Person, level: str) -> None:
    await seed.run(
        "UPDATE memberships SET level = $3 WHERE tenant_id = $1 AND user_id = $2",
        tenant,
        who.user_id,
        level,
    )


async def _intake(net: Net, *, template: bool = True, synthetic: bool = False) -> Intake:
    seed = net.seed
    tenant = await seed.firm()
    if synthetic:
        await seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", tenant)
    for flag in FLAGS:
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'TASK-1349')",
            tenant,
            flag,
        )
    grace = await seed.person(tenant, "firm_admin")
    people = [await seed.person(tenant) for _ in range(3)]
    for who, level in zip(people, ("partner", "manager", "staff"), strict=True):
        await _level(seed, tenant, who, level)
    tag = uuid.uuid4().hex[:6]
    walter = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO clients (tenant_id, name) VALUES ($1, $2) RETURNING id",
            tenant,
            f"Walter Thornbury {tag}",
        ),
    )
    walter_entity = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, $3) "
            "RETURNING id",
            tenant,
            walter,
            f"Walter Thornbury {tag}",
        ),
    )
    if template:
        template_id = await seed.value(
            "INSERT INTO acceptance_questionnaire_templates (tenant_id, name, family, created_by) "
            "VALUES ($1, 'Tax engagements', 'tax', $2) RETURNING id",
            tenant,
            grace.user_id,
        )
        await seed.run(
            "INSERT INTO acceptance_questionnaire_template_versions "
            "(tenant_id, template_id, version_no, sections, created_by) "
            "VALUES ($1, $2, 1, $3::jsonb, $4)",
            tenant,
            template_id,
            json.dumps([{"code": "scope", "title": "Scope and services"}]),
            grace.user_id,
        )
    daniel, samuel, kira = people
    return Intake(net, seed, tenant, grace, daniel, samuel, kira, walter, walter_entity, tag)


@pytest.fixture
async def intake(net: Net) -> Intake:
    return await _intake(net)


# --- the key comes first -------------------------------------------------------------------------


async def test_ac_the_key_is_required_before_anything_else_answers(intake: Intake) -> None:
    for draft_id in (uuid.uuid4(), (await intake.ready())["id"]):
        missing = await intake.call(
            "POST", f"{DRAFTS}/{draft_id}/commit", intake.grace, {"start_acceptance": False}
        )
        assert missing.status_code == 422, missing.text
    assert await intake.estates() == 0


# --- replay --------------------------------------------------------------------------------------


async def test_ac_the_same_key_with_another_body_is_refused(intake: Intake) -> None:
    draft = await intake.ready()
    key = uuid.uuid4().hex
    answered = await intake.commit_intake(draft, key=key)
    assert answered.status_code in (200, 201), answered.text
    before = await intake.footprint()
    reused = await intake.commit_intake(draft, key=key, start_acceptance=True)
    _refused(reused, 422, "idempotency_key_reused")
    assert await intake.footprint() == before


async def test_ac_a_committed_draft_answers_its_stored_result_under_any_key(
    intake: Intake,
) -> None:
    draft = await intake.ready()
    first = await intake.commit_intake(draft)
    assert first.status_code in (200, 201), first.text
    before = await intake.footprint()
    for start in (False, True):
        again = await intake.commit_intake(draft, start_acceptance=start)
        assert again.status_code in (200, 201), again.text
        assert again.json() == first.json()
    assert await intake.footprint() == before
    assert await intake.estates() == 1


async def _race(intake: Intake) -> list[httpx.Response]:
    draft = await intake.ready()
    key = uuid.uuid4().hex
    return list(
        await asyncio.gather(
            intake.commit_intake(draft, key=key),
            intake.commit_intake(draft, key=key),
            intake.commit_intake(draft),
            intake.commit_intake(draft),
        )
    )


async def test_ac_concurrent_commits_of_one_draft_create_one_estate(intake: Intake) -> None:
    answers = await _race(intake)
    assert await intake.estates() == 1
    won = {a.json()["client_entity_id"] for a in answers if a.status_code in (200, 201)}
    assert len(won) == 1, [a.text for a in answers]


async def test_ac_a_losing_concurrent_commit_answers_the_result_or_409_never_500(
    intake: Intake,
) -> None:
    # Three drafts raced in turn, so the defect shows whatever the scheduling of one race.
    answers: list[httpx.Response] = []
    for n in range(3):
        intake.tag = f"{intake.tag[:6]}{n}"
        answers += await _race(intake)
    assert all(a.status_code in (200, 201, 409) for a in answers), [a.text for a in answers]


# --- atomicity -----------------------------------------------------------------------------------


async def test_ac_a_commit_refused_inside_its_unit_of_work_leaves_nothing(net: Net) -> None:
    """With `start_acceptance` and no questionnaire for the tax family the commit is refused
    (409 `acceptance_template_missing`): nothing of the client entity, engagements, work items,
    contacts or relationships remains, and the same draft then commits without acceptance."""
    intake = await _intake(net, template=False)
    draft = await intake.ready()
    before = await intake.footprint()
    _refused(
        await intake.commit_intake(draft, start_acceptance=True),
        409,
        "acceptance_template_missing",
    )
    assert await intake.footprint() == before
    assert (await intake.call("GET", f"{DRAFTS}/{draft['id']}", intake.grace)).json()[
        "committed_client_id"
    ] is None
    done = await intake.commit_intake(draft)
    assert done.status_code in (200, 201), done.text
    assert await intake.estates() == 1


async def test_ac_one_commit_writes_the_whole_estate_as_prospect(intake: Intake) -> None:
    draft = await intake.ready()
    before = await intake.footprint()
    done = await intake.commit_intake(draft, start_acceptance=True)
    assert done.status_code in (200, 201), done.text
    out = done.json()
    assert out["client_id"] == str(intake.walter)
    assert out["engagement_status"] == "prospect"
    statuses = await intake.seed.rows(
        "SELECT status FROM engagements WHERE id = ANY($1::uuid[])",
        [uuid.UUID(e) for e in cast(list[str], out["engagement_ids"])],
    )
    assert statuses and {r["status"] for r in statuses} == {"prospect"}
    assert len(cast(list[str], out["work_item_ids"])) == 3
    assert out["acceptance_record_id"] is not None
    after = await intake.footprint()
    # One entity under the existing client and no new client.
    assert after[0] == before[0] and after[1] == before[1] + 1
    # Audited on the client in the same transaction.
    actions = await intake.seed.actions(intake.tenant)
    assert "client_intake.committed" in actions and "client_entity.created" in actions


async def test_ac_a_committed_draft_takes_no_further_update(intake: Intake) -> None:
    draft = await intake.ready()
    assert (await intake.commit_intake(draft)).status_code in (200, 201)
    current = _ok(await intake.call("GET", f"{DRAFTS}/{draft['id']}", intake.grace))
    edited = await intake.call(
        "PATCH",
        f"{DRAFTS}/{draft['id']}",
        intake.grace,
        {"seen_version": current["version"], "payload": intake.payload(estate="Someone else")},
    )
    assert 400 <= edited.status_code < 500, edited.text
    assert await intake.estates() == 1


# --- the conflict check --------------------------------------------------------------------------


async def test_ac_no_commit_while_the_check_has_an_uncleared_hit(intake: Intake) -> None:
    draft = await intake.create(intake.payload())
    check = await intake.check(draft, clear=False)
    draft = await intake.save(draft, intake.payload(check=check))
    facts = _refused(await intake.commit_intake(draft), 409, "gate_unmet")
    assert facts.get("gate") == "conflict_check", facts
    assert await intake.estates() == 0


async def test_ac_a_name_changed_after_clearance_needs_a_new_check(intake: Intake) -> None:
    draft = await intake.ready()
    renamed = intake.payload(
        estate=f"Estate of W. Thornbury {intake.tag}",
        check=cast(Json, draft["payload"])["conflict_check_id"],
    )
    draft = await intake.save(draft, renamed)
    _refused(await intake.commit_intake(draft), 409, "gate_unmet")
    assert await intake.estates() == 0


# --- who: client.intake, people, firms and walls -------------------------------------------------


def test_ac_client_intake_denies_the_agent_and_the_system() -> None:
    for action in ("client.intake", "client_import.run"):
        assert RULES[action].decisions.get("agent") == "deny", action
        assert RULES[action].decisions.get("system") == "deny", action


async def test_ac_an_agent_or_system_context_never_commits(intake: Intake) -> None:
    draft = await intake.ready()
    for kind in ("agent", "system"):
        ctx = AuthContext(
            TenantContext(intake.tenant, cast(ActorKind, kind), str(intake.grace.user_id)),
            intake.grace.user_id,
            uuid.uuid4(),
            "firm_admin",
            datetime.now(UTC) - timedelta(minutes=1),
        )
        with pytest.raises(Forbidden):
            await commit_client_intake(ctx, uuid.UUID(cast(str, draft["id"])), False)
    assert await intake.estates() == 0


async def test_ac_staff_without_client_intake_are_refused(intake: Intake) -> None:
    refused = await intake.call("POST", DRAFTS, intake.kira, {"step": "entity", "payload": {}})
    assert refused.status_code == 403, refused.text


async def test_ac_another_persons_draft_is_unknown(intake: Intake) -> None:
    draft = await intake.ready()
    path = f"{DRAFTS}/{draft['id']}"
    for method, suffix, body in (
        ("GET", "", None),
        ("PATCH", "", {"seen_version": draft["version"], "payload": intake.payload()}),
        ("POST", "/validate", {"step": "review"}),
        ("DELETE", "", None),
    ):
        found = await intake.call(method, path + suffix, intake.daniel, body)
        assert found.status_code == 404, (method, suffix, found.text)
    assert (await intake.commit_intake(draft, who=intake.daniel)).status_code == 404
    assert await intake.estates() == 0


async def test_inv2_another_firms_admin_and_client_are_unknown(intake: Intake, net: Net) -> None:
    other = await _intake(net)
    draft = await intake.ready()
    assert (await other.call("GET", f"{DRAFTS}/{draft['id']}", other.grace)).status_code == 404
    assert (await other.commit_intake(draft, who=other.grace)).status_code == 404
    # Their own draft naming our client as the existing client never writes into either firm.
    theirs = await other.create(intake.payload())
    before = await intake.footprint(), await other.footprint()
    attempt = await other.commit_intake(theirs, who=other.grace)
    assert 400 <= attempt.status_code < 500, attempt.text
    assert (await intake.footprint(), await other.footprint()) == before


async def test_inv3_a_walled_client_is_never_a_candidate_nor_a_target(intake: Intake) -> None:
    walled = await intake.call(
        "POST",
        "/v1/walls",
        intake.grace,
        {"user_id": str(intake.samuel.user_id), "client_id": str(intake.walter)},
    )
    assert walled.status_code == 201, walled.text
    dedupe = _ok(
        await intake.call(
            "POST",
            "/v1/clients/dedupe",
            intake.samuel,
            {"name": f"Estate of Walter Thornbury {intake.tag}"},
        )
    )
    assert str(intake.walter) not in json.dumps(dedupe)
    assert f"Walter Thornbury {intake.tag}" not in json.dumps(dedupe)
    created = await intake.call(
        "POST", DRAFTS, intake.samuel, {"step": "entity", "payload": intake.payload()}
    )
    if created.status_code == 201:
        draft = created.json()
        assert (await intake.commit_intake(draft, who=intake.samuel)).status_code in (
            404,
            409,
            422,
        )
    else:
        assert created.status_code == 404, created.text
    assert await intake.estates() == 0


async def test_ac_dedupe_scores_the_estate_against_walter(intake: Intake) -> None:
    dedupe = _ok(
        await intake.call(
            "POST",
            "/v1/clients/dedupe",
            intake.grace,
            {"name": f"Estate of Walter Thornbury {intake.tag}", "kind": "trust_family"},
        )
    )
    top = cast(list[Json], dedupe["candidates"])[0]
    assert top["client_id"] == str(intake.walter)
    assert top["basis"] == "name"
    assert top["score"] == pytest.approx(0.96)


# --- estate validation and the SSN guard ---------------------------------------------------------


async def test_ac_form_706_needs_the_date_of_death(intake: Intake) -> None:
    """The date of death is the entity's, required because Form 706 is a service: reported on
    the services step, and the commit is refused there."""
    draft = await intake.create(intake.payload(died=False))
    check = await intake.check(draft)
    draft = await intake.save(draft, intake.payload(died=False, check=check))
    found = _ok(
        await intake.call(
            "POST", f"{DRAFTS}/{draft['id']}/validate", intake.grace, {"step": "services"}
        )
    )
    problems = {(p["field"], p["code"]) for p in cast(list[Json], found["problems"])}
    assert ("entity.date_of_death", "date_of_death_required") in problems
    assert found["valid"] is False
    before = await intake.footprint()
    facts = _refused(await intake.commit_intake(draft), 422, "draft_incomplete")
    assert facts.get("step") == "services", facts
    assert await intake.footprint() == before


async def test_ac_an_itin_form_on_autosave_is_refused_before_it_is_stored(intake: Intake) -> None:
    draft = await intake.create(intake.payload())
    payload = intake.payload()
    contacts = cast(list[Json], payload["contacts"])
    contacts[0]["display_name"] = "Paul Thornbury 912-70-1234"
    refused = await intake.call(
        "PATCH",
        f"{DRAFTS}/{draft['id']}",
        intake.grace,
        {"seen_version": draft["version"], "payload": payload},
    )
    _refused(refused, 422, "tin_kind_not_allowed")
    stored = await intake.seed.rows(
        "SELECT d::text AS t FROM client_intake_drafts d WHERE tenant_id = $1", intake.tenant
    )
    assert all("912-70-1234" not in cast(str, r["t"]) for r in stored)
    assert all("912701234" not in cast(str, r["t"]) for r in stored)


async def test_ac_the_guard_lets_a_synthetic_firm_and_an_ein_form_through(net: Net) -> None:
    synthetic = await _intake(net, synthetic=True)
    payload = synthetic.payload()
    cast(list[Json], payload["contacts"])[0]["display_name"] = "Paul Thornbury 912-70-1234"
    assert (
        await synthetic.call(
            "POST", DRAFTS, synthetic.grace, {"step": "entity", "payload": payload}
        )
    ).status_code == 201
    real = await _intake(net)
    payload = real.payload(estate=f"Thornbury Trust 91-2345678 {real.tag}")
    assert (
        await real.call("POST", DRAFTS, real.grace, {"step": "entity", "payload": payload})
    ).status_code == 201


async def test_ac_the_routes_answer_without_a_flag(intake: Intake) -> None:
    """`clients.v2` retired with P-07-T59 (DEC-905): no flag row stands between Grace and a
    draft."""
    await intake.seed.run("DELETE FROM feature_flag_states WHERE tenant_id = $1", intake.tenant)
    found = await intake.call("POST", DRAFTS, intake.grace, {"step": "entity", "payload": {}})
    assert found.status_code == 201, found.text
