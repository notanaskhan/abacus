# ac-test-author: ayushkbhatia
"""P-07-T44 (ADR-078): the independent acceptance suite for P-07-T42's single intake commit
(CLI-06 a-f, h, i). "The Thornbury estate is added under Walter Thornbury with three return work
items in one transaction and a replayed key returns the same result."

Read from P-07 §3.3 Story 3.1, §4.2 M8, §4.3 and OQ-2, `docs/contracts/intake-import.md` (v1,
DEC-374), the organisations matrix, `error-codes.yaml` and the conflict-check contract, before
T42's code. HTTP through `create_app()` behind `clients.v2` (CLI-06's flag), with
`engagements.v2` and `engagements.acceptance_v2` for the conflict check and the acceptance
record. Rows are read back as the superuser.

Covered: atomicity (a failure inside the commit leaves no client entity, engagement, contact,
relationship or work item behind), `Idempotency-Key` replay (same key, same answer, nothing more
written; same key with another body refused; a committed draft answers its first result),
Prospect-only creation under `client.intake` (OQ-2: the firm admin creates Prospect engagements
only; a role without the action and the agent are refused), a cleared conflict check before the
commit (409 `gate_unmet`), estate validation (`date_of_death_required` for Form 706) and the SSN
guard on a real tenant.

Spec gaps followed here (TASK-1324):
- The intake carries no TIN (DEC-374: every TIN-named field is the masked shape; the entity's
  TIN is sealed afterwards), so the SSN guard is on the draft's text: an SSN or ITIN form in a
  name or contact field on a firm that is not synthetic is refused 422 `tin_kind_not_allowed`
  (P-07 OQ-4's rule and code), at autosave, before anything is stored; an EIN form is not.
- The conflict check that clears the commit is one run on the draft itself (subject
  `client_intake_draft`), named by `payload.conflict_check_id`; a check on another subject, or
  one with a standing hit, is 409 `gate_unmet`.
- Form 56 is a service line item that creates no work item (P-07 §2 CLI-06); the 706 service
  names the forms it creates (`forms: ["706"]`), so the estate has three return work items.
- One Prospect engagement per engagement type and period: the three tax returns share one
  `tax_compliance` engagement (Story 3.1).
- The acceptance record's kind is `new_engagement_existing_client` for an entity added under an
  existing client (Story 3.1), whatever engagements that client already has.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Final, cast

import httpx
import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.identity.api import RULES, AuthContext, Forbidden

from .support import Net, Person, Seeder

pytestmark = pytest.mark.asyncio

Json = dict[str, object]
DRAFTS: Final = "/v1/client-intake-drafts"
FY_START, FY_END = date(2026, 1, 1), date(2026, 12, 31)
DIED: Final = date(2026, 3, 14)
FLAGS: Final = ("clients.v2", "engagements.v2", "engagements.acceptance_v2")
SECTIONS: Final = (("engagement_scope", "Engagement scope and services"),)


@dataclass
class World:
    """Brightwater Hale: Grace Holloway (firm admin) adds the Estate of Walter Thornbury under
    the existing client Walter Thornbury; Daniel Reyes is the engagement partner (a partner),
    Samuel Ito the manager who clears conflict hits, Kira Ross staff."""

    net: Net
    seed: Seeder
    tenant: uuid.UUID
    grace: Person
    daniel: Person
    samuel: Person
    kira: Person
    walter: uuid.UUID  # the client
    walter_entity: uuid.UUID  # the decedent's own entity
    marker: str

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
        self,
        *,
        date_of_death: date | None = DIED,
        contact_name: str | None = None,
        check: object | None = None,
    ) -> Json:
        """CLI-06 b to e: the estate under Walter, decedent → estate, Paul Thornbury executor,
        Form 706, the estate's 1041, the final 1040 and Form 56, Daniel as partner."""
        entity: Json = {
            "mode": "existing_client",
            "client_id": str(self.walter),
            "entity_name": f"Estate of Walter Thornbury {self.marker}",
            "entity_type": "estate",
        }
        if date_of_death is not None:
            entity["date_of_death"] = date_of_death.isoformat()
        period = {
            "fiscal_period_start": FY_START.isoformat(),
            "fiscal_period_end": FY_END.isoformat(),
        }
        out: Json = {
            "entity": entity,
            "relationships": [{"kind": "estate_of", "related_entity_id": str(self.walter_entity)}],
            "contacts": [
                {
                    "display_name": contact_name or f"Paul Thornbury {self.marker}",
                    "email": f"paul.{self.marker}@example.test",
                    "roles": ["executor"],
                }
            ],
            "services": [
                {"type_code": "forms_706_709", "forms": ["706"], **period},
                {"type_code": "form_1041", **period},
                {"type_code": "form_1040", **period},
                {"type_code": "form_56"},
            ],
            "engagement_partner_user_id": str(self.daniel.user_id),
        }
        if check is not None:
            out["conflict_check_id"] = str(check)
        return out

    async def draft(self, payload: Json | None = None, *, who: Person | None = None) -> Json:
        return _json(
            await self.call(
                "POST", DRAFTS, who or self.grace, {"step": "entity", "payload": payload or {}}
            ),
            201,
        )

    async def save(self, draft: Json, payload: Json, *, step: str = "review") -> Json:
        return _json(
            await self.call(
                "PATCH",
                f"{DRAFTS}/{draft['id']}",
                self.grace,
                {"seen_version": draft["version"], "step": step, "payload": payload},
            )
        )

    async def cleared_check(self, draft_id: object, *, clear: bool = True) -> uuid.UUID:
        """Step 5: the conflict check over the four names, run on the draft; every hit (Walter
        himself, the family) cleared by Samuel as not adverse."""
        check = _json(
            await self.call(
                "POST",
                "/v1/conflict-checks",
                self.grace,
                {
                    "subject": {"kind": "client_intake_draft", "id": str(draft_id)},
                    "names": [
                        f"Estate of Walter Thornbury {self.marker}",
                        f"Walter Thornbury {self.marker}",
                        f"Paul Thornbury {self.marker}",
                        f"Harriet Thornbury {self.marker}",
                    ],
                },
            ),
            201,
        )
        if clear:
            for result in cast(list[Json], check["results"]):
                _json(
                    await self.call(
                        "POST",
                        f"/v1/conflict-checks/{check['id']}/results/{result['id']}/clear",
                        self.samuel,
                        {
                            "assessment": "same_family_not_adverse",
                            "reason": "The decedent's own estate; the executor is his son.",
                        },
                    )
                )
        return uuid.UUID(cast(str, check["id"]))

    async def ready(self) -> Json:
        """A complete draft with a cleared conflict check on it."""
        draft = await self.draft(self.payload())
        check = await self.cleared_check(draft["id"])
        return await self.save(draft, self.payload(check=check))

    async def commit_intake(
        self,
        draft: Json,
        *,
        start_acceptance: bool = True,
        key: str | None = None,
        who: Person | None = None,
    ) -> httpx.Response:
        return await self.call(
            "POST",
            f"{DRAFTS}/{draft['id']}/commit",
            who or self.grace,
            {"start_acceptance": start_acceptance},
            key=key or f"intake-{uuid.uuid4().hex}",
        )

    async def count(self, sql: str) -> int:
        return cast(int, await self.seed.value(sql, self.tenant))

    async def footprint(self) -> dict[str, int]:
        """What a commit writes, firm-wide."""
        return {
            table: await self.count(sql)
            for table, sql in (
                ("clients", "SELECT count(*) FROM clients WHERE tenant_id = $1"),
                ("client_entities", "SELECT count(*) FROM client_entities WHERE tenant_id = $1"),
                ("engagements", "SELECT count(*) FROM engagements WHERE tenant_id = $1"),
                ("work_items", "SELECT count(*) FROM work_items WHERE tenant_id = $1"),
                ("contacts", "SELECT count(*) FROM contacts WHERE tenant_id = $1"),
                ("contact_roles", "SELECT count(*) FROM contact_roles WHERE tenant_id = $1"),
                (
                    "entity_relationships",
                    "SELECT count(*) FROM entity_relationships WHERE tenant_id = $1",
                ),
                (
                    "acceptance_records",
                    "SELECT count(*) FROM acceptance_records WHERE tenant_id = $1",
                ),
            )
        }


def _json(response: httpx.Response, status: int = 200) -> Json:
    assert response.status_code == status, response.text
    return cast(Json, response.json())


def _refusal(response: httpx.Response, status: int, detail: str) -> Json:
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


async def _template(seed: Seeder, tenant: uuid.UUID, by: uuid.UUID) -> None:
    """The firm's "Tax engagements v2" questionnaire: database content (P-07 §4.2 M5)."""
    template = await seed.value(
        "INSERT INTO acceptance_questionnaire_templates (tenant_id, name, family, created_by) "
        "VALUES ($1, 'Tax engagements v2', 'tax', $2) RETURNING id",
        tenant,
        by,
    )
    await seed.run(
        "INSERT INTO acceptance_questionnaire_template_versions "
        "(tenant_id, template_id, version_no, sections, created_by) "
        "VALUES ($1, $2, 1, $3::jsonb, $4)",
        tenant,
        template,
        json.dumps([{"code": c, "title": t} for c, t in SECTIONS]),
        by,
    )


async def _world(net: Net, *, template: bool = True, synthetic: bool = False) -> World:
    seed = net.seed
    tenant = await seed.firm()
    if synthetic:
        await seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", tenant)
    for flag in FLAGS:
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'P-07-T44')",
            tenant,
            flag,
        )
    grace = await seed.person(tenant, "firm_admin")
    daniel = await seed.person(tenant)
    await _level(seed, tenant, daniel, "partner")
    samuel = await seed.person(tenant)
    await _level(seed, tenant, samuel, "manager")
    kira = await seed.person(tenant)
    await _level(seed, tenant, kira, "staff")
    marker = uuid.uuid4().hex[:6]
    walter = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO clients (tenant_id, name) VALUES ($1, $2) RETURNING id",
            tenant,
            f"Walter Thornbury {marker}",
        ),
    )
    walter_entity = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, $3) "
            "RETURNING id",
            tenant,
            walter,
            f"Walter Thornbury {marker}",
        ),
    )
    if template:
        await _template(seed, tenant, grace.user_id)
    return World(net, seed, tenant, grace, daniel, samuel, kira, walter, walter_entity, marker)


@pytest.fixture
async def w(net: Net) -> World:
    return await _world(net)


# --- the Thornbury estate in one commit -------------------------------------------------------


async def test_ac_the_estate_is_added_under_walter_with_three_returns_in_one_commit(
    w: World,
) -> None:
    before = await w.footprint()
    draft = await w.ready()
    done = _json(await w.commit_intake(draft), 201)

    # DEC-62: the estate is a new entity of the existing client, whose name stays "Walter".
    assert done["client_id"] == str(w.walter)
    entity = uuid.UUID(cast(str, done["client_entity_id"]))
    row = (
        await w.seed.rows(
            "SELECT client_id, name, entity_type, date_of_death FROM client_entities "
            "WHERE id = $1",
            entity,
        )
    )[0]
    assert row["client_id"] == w.walter
    assert row["name"] == f"Estate of Walter Thornbury {w.marker}"
    assert row["entity_type"] == "estate"
    assert row["date_of_death"] == DIED
    assert await w.seed.value("SELECT name FROM clients WHERE id = $1", w.walter) == (
        f"Walter Thornbury {w.marker}"
    )

    # One Prospect tax_compliance engagement holding the 706, the estate 1041 and the final
    # 1040; Form 56 is a line item and creates no work item.
    engagements = cast(list[str], done["engagement_ids"])
    assert len(engagements) == 1
    assert done["engagement_status"] == "prospect"
    eng = (
        await w.seed.rows(
            "SELECT status, type, client_id, client_entity_id FROM engagements WHERE id = $1",
            uuid.UUID(engagements[0]),
        )
    )[0]
    assert (eng["status"], eng["type"]) == ("prospect", "tax_compliance")
    assert (eng["client_id"], eng["client_entity_id"]) == (w.walter, entity)
    items = await w.seed.rows(
        "SELECT id, kind, name FROM work_items WHERE engagement_id = $1 ORDER BY name",
        uuid.UUID(engagements[0]),
    )
    assert [(r["kind"], r["name"]) for r in items] == [
        ("tax_return", "Form 1040"),
        ("tax_return", "Form 1041"),
        ("tax_return", "Form 706"),
    ]
    assert sorted(cast(list[str], done["work_item_ids"])) == sorted(str(r["id"]) for r in items)

    # The decedent → estate edge, Paul Thornbury the executor, the check linked, the record open.
    assert (
        await w.seed.value(
            "SELECT kind FROM entity_relationships WHERE from_entity_id = $1 "
            "AND to_entity_id = $2",
            entity,
            w.walter_entity,
        )
        == "estate_of"
    )
    contact = await w.seed.rows(
        "SELECT c.id, c.client_id, r.role, r.scope_kind, r.scope_id FROM contacts c "
        "JOIN contact_roles r ON r.contact_id = c.id WHERE c.tenant_id = $1 "
        "AND c.display_name = $2",
        w.tenant,
        f"Paul Thornbury {w.marker}",
    )
    assert [(r["client_id"], r["role"], r["scope_kind"], r["scope_id"]) for r in contact] == [
        (w.walter, "executor", "client_entity", entity)
    ]
    assert done["conflict_check_id"] == draft["payload"]["conflict_check_id"]  # pyright: ignore[reportIndexIssue] -- a JSON object
    record = await w.seed.rows(
        "SELECT id, engagement_id, kind FROM acceptance_records WHERE tenant_id = $1", w.tenant
    )
    assert [(str(r["id"]), str(r["engagement_id"]), r["kind"]) for r in record] == [
        (done["acceptance_record_id"], engagements[0], "new_engagement_existing_client")
    ]

    # One transaction: exactly these rows, and one `client_intake.committed` by Grace.
    after = await w.footprint()
    assert {k: after[k] - before[k] for k in after} == {
        "clients": 0,
        "client_entities": 1,
        "engagements": 1,
        "work_items": 3,
        "contacts": 1,
        "contact_roles": 1,
        "entity_relationships": 1,
        "acceptance_records": 1,
    }
    audit = await w.seed.rows(
        "SELECT actor_kind, actor_id FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'client_intake.committed'",
        w.tenant,
    )
    assert [(r["actor_kind"], str(r["actor_id"])) for r in audit] == [
        ("human", str(w.grace.user_id))
    ]
    # The engagement partner is on the team.
    assert await w.seed.value(
        "SELECT count(*) FROM engagement_members WHERE engagement_id = $1 AND user_id = $2",
        uuid.UUID(engagements[0]),
        w.daniel.user_id,
    )


async def test_ac_create_without_acceptance_opens_no_record(w: World) -> None:
    """ "Create": the same write without the acceptance record (lands on CLI-02)."""
    done = _json(await w.commit_intake(await w.ready(), start_acceptance=False), 201)
    assert done["acceptance_record_id"] is None
    assert done["engagement_status"] == "prospect"
    assert not await w.count("SELECT count(*) FROM acceptance_records WHERE tenant_id = $1")


# --- Idempotency-Key replay ---------------------------------------------------------------------


async def test_ac_a_replayed_key_answers_the_same_and_writes_nothing_more(w: World) -> None:
    draft = await w.ready()
    key = f"thornbury-{w.marker}-commit"
    first = _json(await w.commit_intake(draft, key=key), 201)
    written = await w.footprint()

    again = await w.commit_intake(draft, key=key)
    assert again.status_code == 201
    assert again.json() == first
    assert await w.footprint() == written

    # The same key with another request is refused, not replayed.
    _refusal(
        await w.commit_intake(draft, key=key, start_acceptance=False),
        422,
        "idempotency_key_reused",
    )
    # A committed draft answers its first result to a new key, and writes nothing.
    other = _json(await w.commit_intake(draft, key=f"thornbury-{w.marker}-retry"), 201)
    assert other == first
    assert await w.footprint() == written
    assert (
        await w.count(
            "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
            "AND action = 'client_intake.committed'"
        )
        == 1
    )


async def test_ac_commit_requires_an_idempotency_key(w: World) -> None:
    draft = await w.ready()
    response = await w.net.http.post(
        f"{DRAFTS}/{draft['id']}/commit",
        json={"start_acceptance": True},
        headers=w.net.headers(w.grace),
    )
    assert response.status_code == 422
    assert not await w.count("SELECT count(*) FROM engagements WHERE tenant_id = $1")


# --- atomicity ----------------------------------------------------------------------------------


async def test_ac_a_failure_inside_the_commit_leaves_nothing_behind(net: Net) -> None:
    """No questionnaire template: opening the acceptance record fails after the entity, the
    engagement and its work items were written, and the whole unit of work rolls back."""
    w = await _world(net, template=False)
    before = await w.footprint()
    draft = await w.ready()
    _refusal(await w.commit_intake(draft), 409, "acceptance_template_missing")
    assert await w.footprint() == before
    assert not await w.count(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'client_intake.committed'"
    )
    # The draft is still open: "Create" (no acceptance record) then succeeds.
    still = _json(await w.call("GET", f"{DRAFTS}/{draft['id']}", w.grace))
    assert still["committed_client_id"] is None
    done = _json(await w.commit_intake(draft, start_acceptance=False), 201)
    assert len(cast(list[str], done["work_item_ids"])) == 3


# --- Prospect only, under client.intake ---------------------------------------------------------


async def test_ac_the_firm_admin_creates_prospect_engagements_only(w: World) -> None:
    """OQ-2: Grace (firm admin) holds `client.intake`, which creates Prospect engagements only;
    nothing is accepted by the commit."""
    done = _json(await w.commit_intake(await w.ready()), 201)
    statuses = await w.seed.rows(
        "SELECT DISTINCT status FROM engagements WHERE tenant_id = $1", w.tenant
    )
    assert [r["status"] for r in statuses] == ["prospect"]
    assert not await w.count("SELECT count(*) FROM acceptance_decisions WHERE tenant_id = $1")
    assert done["engagement_status"] == "prospect"


async def test_ac_a_role_without_client_intake_is_refused(w: World) -> None:
    draft = await w.ready()
    # Kira (staff) holds no `client.intake`: no draft of her own, and not Grace's commit.
    assert (await w.call("POST", DRAFTS, w.kira, {"step": "entity"})).status_code == 403
    assert (await w.commit_intake(draft, who=w.kira)).status_code == 403
    # Samuel (manager) holds the action, but the draft is Grace's own: 404.
    assert (await w.commit_intake(draft, who=w.samuel)).status_code == 404
    assert not await w.count("SELECT count(*) FROM engagements WHERE tenant_id = $1")


async def test_ac_the_agent_and_the_system_never_commit(w: World) -> None:
    rule = RULES["client.intake"]
    assert rule.decisions.get("agent") == "deny"
    assert rule.decisions.get("system") == "deny"
    from abacus.modules.engagements.api import commit_client_intake

    draft = await w.ready()
    for kind in ("agent", "system"):
        ctx = AuthContext(
            TenantContext(w.tenant, kind, str(w.grace.user_id)),
            w.grace.user_id,
            uuid.uuid4(),
            None,
            None,
        )
        with pytest.raises(Forbidden):
            await commit_client_intake(ctx, uuid.UUID(cast(str, draft["id"])), True)
    assert not await w.count("SELECT count(*) FROM engagements WHERE tenant_id = $1")


# --- the conflict check comes first -------------------------------------------------------------


async def test_ac_no_commit_without_a_cleared_conflict_check(w: World) -> None:
    draft = await w.draft()

    # No check at all.
    draft = await w.save(draft, w.payload())
    facts = _refusal(await w.commit_intake(draft), 409, "gate_unmet")
    assert facts.get("gate") == "conflict_check"

    # A check whose hits stand (nobody cleared Walter's own match).
    standing = await w.cleared_check(draft["id"], clear=False)
    draft = await w.save(draft, w.payload(check=standing))
    _refusal(await w.commit_intake(draft), 409, "gate_unmet")

    # A cleared check, but run on another draft.
    other = await w.draft(w.payload())
    foreign = await w.cleared_check(other["id"])
    draft = await w.save(draft, w.payload(check=foreign))
    _refusal(await w.commit_intake(draft), 409, "gate_unmet")
    assert not await w.count("SELECT count(*) FROM engagements WHERE tenant_id = $1")

    # This draft's check, every hit cleared by a manager: the commit goes through.
    cleared = await w.cleared_check(draft["id"])
    draft = await w.save(draft, w.payload(check=cleared))
    done = _json(await w.commit_intake(draft), 201)
    assert done["conflict_check_id"] == str(cleared)


# --- estate validation --------------------------------------------------------------------------


async def test_ac_form_706_needs_the_date_of_death(w: World) -> None:
    """CLI-06 i: "Required for Form 706 due date" is `date_of_death_required`; Next is refused
    and so is the commit."""
    draft = await w.draft(w.payload(date_of_death=None))
    check = await w.cleared_check(draft["id"])
    draft = await w.save(draft, w.payload(date_of_death=None, check=check), step="services")
    v = _json(
        await w.call("POST", f"{DRAFTS}/{draft['id']}/validate", w.grace, {"step": "services"})
    )
    assert v["valid"] is False
    assert {"field": "entity.date_of_death", "code": "date_of_death_required"} in cast(
        list[Json], v["problems"]
    )
    facts = _refusal(await w.commit_intake(draft), 422, "draft_incomplete")
    assert facts.get("step") == "services"
    assert not await w.count("SELECT count(*) FROM engagements WHERE tenant_id = $1")

    draft = await w.save(draft, w.payload(check=check), step="services")
    v = _json(
        await w.call("POST", f"{DRAFTS}/{draft['id']}/validate", w.grace, {"step": "services"})
    )
    assert v["valid"] is True and v["problems"] == []
    _json(await w.commit_intake(draft), 201)


# --- the SSN guard on a real tenant -------------------------------------------------------------


async def test_ac_an_ssn_or_itin_never_rests_in_a_draft_on_a_real_tenant(w: World) -> None:
    """P-07 OQ-4: SSN and ITIN entry is refused on a real (non-synthetic) tenant until C19. The
    draft holds no TIN field, so the guard reads its text: refused at autosave, nothing stored."""
    leaked = "Paul Thornbury 912-70-1234"  # a 9xx ITIN-form fake
    _refusal(
        await w.call(
            "POST",
            DRAFTS,
            w.grace,
            {"step": "contacts", "payload": w.payload(contact_name=leaked)},
        ),
        422,
        "tin_kind_not_allowed",
    )
    draft = await w.draft()
    _refusal(
        await w.call(
            "PATCH",
            f"{DRAFTS}/{draft['id']}",
            w.grace,
            {
                "seen_version": draft["version"],
                "step": "contacts",
                "payload": w.payload(contact_name=leaked),
            },
        ),
        422,
        "tin_kind_not_allowed",
    )
    stored = await w.seed.rows(
        "SELECT payload::text AS p FROM client_intake_drafts WHERE tenant_id = $1", w.tenant
    )
    assert stored and not [r for r in stored if "1234" in cast(str, r["p"])]
    # An EIN form is accepted on a real tenant (OQ-4).
    _json(
        await w.call(
            "PATCH",
            f"{DRAFTS}/{draft['id']}",
            w.grace,
            {
                "seen_version": draft["version"],
                "payload": w.payload(contact_name="Thornbury Holdings 91-2345678"),
            },
        )
    )


async def test_ac_the_guard_is_for_real_tenants_only(net: Net) -> None:
    w = await _world(net, synthetic=True)
    _json(
        await w.call(
            "POST",
            DRAFTS,
            w.grace,
            {"step": "contacts", "payload": w.payload(contact_name="Paul 912-70-1234")},
        ),
        201,
    )
