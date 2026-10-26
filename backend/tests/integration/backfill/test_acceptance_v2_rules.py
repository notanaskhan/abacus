"""P-07-T35 (TASK-1258; DEC-372) beyond the independent suite: the database guards of migration
0163 (status moves, the lock, manual-check completion), "Start acceptance" (idempotent, needs an
engagement partner, the record's kind), and SPEC-025's acceptance route kept as an adapter that
cannot contradict the record."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import cast

import asyncpg
import httpx
import pytest
from sqlalchemy import text

from abacus.kernel.db import TenantContext
from abacus.kernel.uow import Target, uow

from .support import Net, Person

pytestmark = pytest.mark.asyncio
Json = dict[str, object]


@dataclass
class World:
    net: Net
    tenant: uuid.UUID
    admin: Person
    partner: Person
    manager: Person
    client_id: uuid.UUID
    entity_id: uuid.UUID

    async def call(
        self, method: str, path: str, who: Person, body: Json | None = None
    ) -> httpx.Response:
        return await self.net.call(method, path, who, body=body)

    async def draft(self, *, team: list[Json] | None = None, name: str = "Estate 706") -> Json:
        response = await self.call(
            "POST",
            "/v1/engagement-drafts",
            self.admin,
            {
                "client_id": str(self.client_id),
                "client_entity_id": str(self.entity_id),
                "type_code": "forms_706_709",
                "payload": {
                    "name": name,
                    "fiscal_period_start": "2025-01-01",
                    "fiscal_period_end": "2025-12-31",
                    "team": team
                    if team is not None
                    else [
                        {"user_id": str(self.partner.user_id), "role": "engagement_partner"},
                        {"user_id": str(self.manager.user_id), "role": "manager"},
                    ],
                },
            },
        )
        assert response.status_code == 201, response.text
        return cast(Json, response.json())

    async def start(self, draft: Json) -> httpx.Response:
        return await self.call(
            "POST", f"/v1/engagement-drafts/{draft['id']}/start-acceptance", self.admin
        )


async def _world(net: Net) -> World:
    seed = net.seed
    tenant = await seed.firm()
    for flag in ("engagements.v2", "engagements.acceptance_v2"):
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'TASK-1258')",
            tenant,
            flag,
        )
    admin = await seed.person(tenant, "firm_admin")
    partner = await seed.person(tenant)
    manager = await seed.person(tenant)
    for who, level in ((partner, "partner"), (manager, "manager")):
        await seed.run(
            "UPDATE memberships SET level = $3 WHERE tenant_id = $1 AND user_id = $2",
            tenant,
            who.user_id,
            level,
        )
    client_id = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO clients (tenant_id, name) VALUES ($1, 'Walter Thornbury') RETURNING id",
            tenant,
        ),
    )
    entity_id = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO client_entities (tenant_id, client_id, name) "
            "VALUES ($1, $2, 'Estate of Walter Thornbury') RETURNING id",
            tenant,
            client_id,
        ),
    )
    template = await seed.value(
        "INSERT INTO acceptance_questionnaire_templates (tenant_id, name, family, created_by) "
        "VALUES ($1, 'Tax engagements v2', 'tax', $2) RETURNING id",
        tenant,
        admin.user_id,
    )
    await seed.run(
        "INSERT INTO acceptance_questionnaire_template_versions "
        "(tenant_id, template_id, version_no, sections, created_by) "
        "VALUES ($1, $2, 1, $3::jsonb, $4)",
        tenant,
        template,
        json.dumps([{"code": "scope", "title": "Scope"}]),
        admin.user_id,
    )
    return World(net, tenant, admin, partner, manager, client_id, entity_id)


async def test_start_acceptance_is_idempotent_and_needs_an_engagement_partner(net: Net) -> None:
    w = await _world(net)
    no_partner = await w.draft(team=[{"user_id": str(w.manager.user_id), "role": "manager"}])
    refused = await w.start(no_partner)
    assert refused.status_code == 422, refused.text
    assert refused.json()["detail"] == "draft_incomplete"
    draft = await w.draft()
    first = await w.start(draft)
    assert first.status_code == 201, first.text
    again = await w.start(draft)
    assert again.status_code == 201, again.text
    assert again.json() == first.json()
    engagement = first.json()["engagement_id"]
    status = await net.seed.value(
        "SELECT status FROM engagements WHERE id = $1", uuid.UUID(engagement)
    )
    assert status == "prospect"
    members = await net.seed.rows(
        "SELECT user_id, role FROM engagement_members WHERE engagement_id = $1",
        uuid.UUID(engagement),
    )
    assert {(r["user_id"], r["role"]) for r in members} == {
        (w.partner.user_id, "engagement_partner"),
        (w.manager.user_id, "manager"),
    }
    # The draft's G1 reads the prospect's record: unmet until the partner decides.
    got = await w.call("GET", f"/v1/engagement-drafts/{draft['id']}", w.admin)
    g1 = next(g for g in cast(list[Json], got.json()["gates"]) if g["gate"] == "G1")
    assert g1["met"] is False
    # A second engagement of the client is an existing client's new engagement.
    other = await w.start(await w.draft(name="Estate 1041"))
    record = await w.call(
        "GET", f"/v1/engagements/{other.json()['engagement_id']}/acceptance", w.partner
    )
    assert record.json()["kind"] == "new_engagement_existing_client"


async def test_the_database_guards_the_record(net: Net) -> None:
    w = await _world(net)
    started = (await w.start(await w.draft())).json()
    record = uuid.UUID(cast(str, started["acceptance_record_id"]))
    seed = net.seed
    # A manual check is completed only by the person it was asked of (while a Draft).
    check = await seed.value(
        "INSERT INTO acceptance_manual_checks (tenant_id, record_id, section_code, requested_of, "
        "requested_by) VALUES ($1, $2, 'scope', $3, $4) RETURNING id",
        w.tenant,
        record,
        w.manager.user_id,
        w.partner.user_id,
    )
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.run(
            "UPDATE acceptance_manual_checks SET completed_by = $2 WHERE id = $1",
            check,
            w.partner.user_id,
        )
    await seed.run(
        "UPDATE acceptance_manual_checks SET completed_by = $2 WHERE id = $1",
        check,
        w.manager.user_id,
    )
    with pytest.raises(asyncpg.InsufficientPrivilegeError):  # completed once
        await seed.run(
            "UPDATE acceptance_manual_checks SET note_sealed = NULL WHERE id = $1", check
        )
    # No skipping a state, and no decided record without its decision row.
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.run("UPDATE acceptance_records SET status = 'decided' WHERE id = $1", record)
    await seed.run(
        "UPDATE acceptance_records SET status = 'awaiting_partner' WHERE id = $1", record
    )
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.run("UPDATE acceptance_records SET status = 'decided' WHERE id = $1", record)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await seed.run("DELETE FROM acceptance_records WHERE id = $1", record)
    # Decided: the record and its children are locked.
    # As the app writes it: through the unit of work, the acting partner (0165).
    async with uow(TenantContext(w.tenant, "human", str(w.partner.user_id))) as tx:
        await tx.session.execute(
            text(
                "INSERT INTO acceptance_decisions (tenant_id, record_id, option, "
                "rationale_sealed, decided_by, mfa_verified_at) VALUES (:tenant, :record, "
                "'accept', '\\x00'::bytea, :by, now())"
            ),
            {"tenant": w.tenant, "record": record, "by": w.partner.user_id},
        )
        tx.record("engagement.probed", target=Target("client", w.client_id))
    await seed.run("UPDATE acceptance_records SET status = 'decided' WHERE id = $1", record)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await seed.run("UPDATE acceptance_records SET risk_rating = 'low' WHERE id = $1", record)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await seed.run(
            "INSERT INTO acceptance_answers (tenant_id, record_id, section_code, state, "
            "updated_by) VALUES ($1, $2, 'scope', 'complete', $3)",
            w.tenant,
            record,
            w.manager.user_id,
        )


async def test_spec025s_route_cannot_contradict_the_record(net: Net) -> None:
    w = await _world(net)
    started = (await w.start(await w.draft())).json()
    eid = started["engagement_id"]
    legacy = f"/v1/engagements/{eid}/acceptance"
    body: Json = {"decision": "accepted", "documented_at": "Acceptance memo"}
    refused = await w.call("PUT", legacy, w.partner, body)
    assert refused.status_code == 409, refused.text
    assert refused.json()["detail"] == "decision_locked"
    assert await net.seed.value(
        "SELECT status FROM engagements WHERE id = $1", uuid.UUID(eid)
    ) == ("prospect")
    acc = f"/v1/engagements/{eid}/acceptance"
    record = (await w.call("GET", acc, w.manager)).json()
    section = record["sections"][0]
    put = await w.call(
        "PUT",
        f"{acc}/answers/scope",
        w.manager,
        {"seen_version": section["version"], "answers": {"ok": True}, "complete": True},
    )
    assert put.status_code == 200, put.text
    version = (await w.call("GET", acc, w.manager)).json()["version"]
    sent = await w.call("POST", f"{acc}/send-to-partner", w.manager, {"seen_version": version})
    assert sent.status_code == 200, sent.text
    decided = await w.call(
        "POST",
        f"{acc}/decision",
        w.partner,
        {
            "option": "accept",
            "rationale": "Fine.",
            "conditions": [],
            "seen_version": sent.json()["version"],
        },
    )
    assert decided.status_code == 201, decided.text
    declined = await w.call("PUT", legacy, w.partner, {**body, "decision": "declined"})
    assert declined.status_code == 409, declined.text
    same = await w.call(
        "PUT",
        legacy,
        w.partner,
        {**body, "independence_concluded": True, "independence_documented_at": "Memo"},
    )
    assert same.status_code == 200, same.text
    assert await net.seed.value(
        "SELECT status FROM engagements WHERE id = $1", uuid.UUID(eid)
    ) == ("accepted")
