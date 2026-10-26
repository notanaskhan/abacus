"""Security review of P-07-T35, T36 and T37 (DEC-375): the findings as tests.

H1 the engagement partner cannot lower a High rating to skip the risk-partner review; M1 the
database ties a decision, a clearance and a screening record to the acting person and an
Awaiting-partner record, and G1 needs the decided record; M2 walled matches collapse into one
restricted row and a flag; M3 only a partner-level person is named engagement partner or
decides; L1/L2 the review completion honours the flag and fresh MFA; L3 the search has one
time budget; L4 draft subjects and evidence links are checked.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import cast

import asyncpg
import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from abacus.kernel.db import TenantContext
from abacus.kernel.flags import forget_flags
from abacus.kernel.uow import Target, uow
from abacus.modules.organisations import conflicts

from .support import Net, Person

pytestmark = pytest.mark.asyncio
Json = dict[str, object]
SECTIONS = (("scope", "Scope"), ("integrity", "Integrity"))


@dataclass
class World:
    net: Net
    tenant: uuid.UUID
    admin: Person
    daniel: Person
    samuel: Person
    rita: Person
    client_id: uuid.UUID
    entity_id: uuid.UUID
    engagement_id: uuid.UUID | None = None

    @property
    def acc(self) -> str:
        return f"/v1/engagements/{self.engagement_id}/acceptance"

    async def call(
        self, method: str, path: str, who: Person, body: Json | None = None, *, mfa: bool = True
    ) -> httpx.Response:
        return await self.net.call(method, path, who, body=body, mfa=mfa)

    async def draft(self, partner: Person) -> Json:
        response = await self.call(
            "POST",
            "/v1/engagement-drafts",
            self.admin,
            {
                "client_id": str(self.client_id),
                "client_entity_id": str(self.entity_id),
                "type_code": "forms_706_709",
                "payload": {
                    "name": "Estate 706",
                    "fiscal_period_start": "2025-01-01",
                    "fiscal_period_end": "2025-12-31",
                    "team": [
                        {"user_id": str(partner.user_id), "role": "engagement_partner"},
                        {"user_id": str(self.samuel.user_id), "role": "manager"},
                    ],
                },
            },
        )
        assert response.status_code == 201, response.text
        return cast(Json, response.json())

    async def start(self, partner: Person | None = None) -> httpx.Response:
        draft = await self.draft(partner or self.daniel)
        response = await self.call(
            "POST", f"/v1/engagement-drafts/{draft['id']}/start-acceptance", self.admin
        )
        if response.status_code == 201:
            self.engagement_id = uuid.UUID(cast(str, response.json()["engagement_id"]))
        return response

    async def record(self, who: Person | None = None) -> Json:
        response = await self.call("GET", self.acc, who or self.daniel)
        assert response.status_code == 200, response.text
        return cast(Json, response.json())

    async def answer(self, code: str, who: Person, **extra: object) -> httpx.Response:
        section = {s["code"]: s for s in cast(list[Json], (await self.record(who))["sections"])}
        return await self.call(
            "PUT",
            f"{self.acc}/answers/{code}",
            who,
            {
                "seen_version": section[code]["version"],
                "answers": {"ok": True},
                "complete": True,
                **extra,
            },
        )

    async def send(self, who: Person) -> httpx.Response:
        version = (await self.record(who))["version"]
        return await self.call(
            "POST", f"{self.acc}/send-to-partner", who, {"seen_version": version}
        )

    async def decide(self, who: Person) -> httpx.Response:
        version = (await self.record(who))["version"]
        return await self.call(
            "POST",
            f"{self.acc}/decision",
            who,
            {"option": "accept", "rationale": "Fine.", "conditions": [], "seen_version": version},
        )

    async def audit_refs(self, action: str) -> list[Json]:
        rows = await self.net.seed.rows(
            "SELECT after_ref FROM audit_events WHERE tenant_id = $1 AND action = $2 ORDER BY seq",
            self.tenant,
            action,
        )
        return [
            cast(
                Json,
                json.loads(r["after_ref"]) if isinstance(r["after_ref"], str) else r["after_ref"],
            )
            for r in rows
        ]


async def _level(net: Net, tenant: uuid.UUID, who: Person, level: str) -> None:
    await net.seed.run(
        "UPDATE memberships SET level = $3 WHERE tenant_id = $1 AND user_id = $2",
        tenant,
        who.user_id,
        level,
    )


async def _world(net: Net) -> World:
    seed = net.seed
    tenant = await seed.firm()
    for flag in ("engagements.v2", "engagements.acceptance_v2"):
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'DEC-375')",
            tenant,
            flag,
        )
    admin = await seed.person(tenant, "firm_admin")
    daniel = await seed.person(tenant)
    samuel = await seed.person(tenant)
    rita = await seed.person(tenant)
    await _level(net, tenant, daniel, "partner")
    await _level(net, tenant, samuel, "manager")
    await _level(net, tenant, rita, "partner")
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
        json.dumps([{"code": c, "title": t} for c, t in SECTIONS]),
        admin.user_id,
    )
    return World(net, tenant, admin, daniel, samuel, rita, client_id, entity_id)


async def _as(tenant: uuid.UUID, actor: uuid.UUID, sql: str, **params: object) -> None:
    """One statement through the unit of work as the app role, acting as `actor`: what the
    database's actor checks read (it audits a probe, as every unit of work audits)."""
    async with uow(TenantContext(tenant, "human", str(actor))) as tx:
        await tx.session.execute(text(sql), params)
        tx.record("engagement.probed", target=Target("client", tenant))


def _check_violation(exc: pytest.ExceptionInfo[IntegrityError]) -> None:
    assert isinstance(exc.value.orig, Exception)
    assert getattr(exc.value.orig, "sqlstate", None) == "23514", exc.value


# --- H1 -----------------------------------------------------------------------------------------


async def test_h1_the_partner_cannot_lower_a_high_rating_to_skip_the_review(net: Net) -> None:
    w = await _world(net)
    assert (await w.start()).status_code == 201
    for code, _ in SECTIONS:
        r = await w.answer(code, w.daniel, risk_rating="high" if code == "integrity" else None)
        assert r.status_code == 200, r.text
    assert (await w.send(w.daniel)).status_code == 200
    requested = await w.call(
        "POST", f"{w.acc}/risk-partner-review", w.daniel, {"partner_id": str(w.rita.user_id)}
    )
    assert requested.status_code == 201, requested.text
    lowered = await w.answer("integrity", w.daniel, risk_rating="moderate")
    assert lowered.status_code == 409, lowered.text
    assert lowered.json()["detail"] == "acceptance_sent"
    refused = await w.decide(w.daniel)
    assert refused.status_code == 409 and refused.json()["detail"] == "review_required"
    record = await w.record()
    assert record["risk_rating"] == "high"
    with pytest.raises(asyncpg.CheckViolationError):  # the database holds the rating too
        await net.seed.run(
            "UPDATE acceptance_records SET risk_rating = 'moderate' WHERE engagement_id = $1",
            w.engagement_id,
        )
    # The rating's change is in the audit as positions, never words.
    refs = await w.audit_refs("acceptance.answers_updated")
    assert {"risk_before": 0, "risk_after": 3}.items() <= refs[1].items()


async def test_h1_a_rating_once_high_still_needs_the_review_after_lowering_in_draft(
    net: Net,
) -> None:
    w = await _world(net)
    assert (await w.start()).status_code == 201
    assert (await w.answer("integrity", w.samuel, risk_rating="high")).status_code == 200
    assert (await w.answer("integrity", w.samuel, risk_rating="low")).status_code == 200
    assert (await w.answer("scope", w.samuel)).status_code == 200
    assert (await w.send(w.samuel)).status_code == 200
    refused = await w.decide(w.daniel)
    assert refused.status_code == 409 and refused.json()["detail"] == "review_required"
    assert (
        await net.seed.value(
            "SELECT high_risk_seen FROM acceptance_records WHERE engagement_id = $1",
            w.engagement_id,
        )
        is True
    )


async def test_h1_manual_checks_are_frozen_once_sent(net: Net) -> None:
    w = await _world(net)
    assert (await w.start()).status_code == 201
    for code, _ in SECTIONS:
        assert (await w.answer(code, w.samuel)).status_code == 200
    assert (await w.send(w.samuel)).status_code == 200
    late = await w.call(
        "POST",
        f"{w.acc}/manual-checks/scope/request",
        w.samuel,
        {"requested_of": str(w.daniel.user_id)},
    )
    assert late.status_code == 409 and late.json()["detail"] == "acceptance_sent"


# --- M1 -----------------------------------------------------------------------------------------


async def test_m1_the_database_binds_a_decision_to_the_acting_engagement_partner(
    net: Net,
) -> None:
    w = await _world(net)
    assert (await w.start()).status_code == 201
    record = await w.record()
    insert = (
        "INSERT INTO acceptance_decisions (tenant_id, record_id, option, rationale_sealed, "
        "decided_by, mfa_verified_at) VALUES (:tid, :record, 'accept', '\\x00'::bytea, "
        ":by, now())"
    )
    rid = uuid.UUID(cast(str, record["id"]))
    with pytest.raises(IntegrityError) as draft:  # still a Draft
        await _as(
            w.tenant, w.daniel.user_id, insert, tid=w.tenant, record=rid, by=w.daniel.user_id
        )
    _check_violation(draft)
    for code, _ in SECTIONS:
        assert (await w.answer(code, w.samuel)).status_code == 200
    assert (await w.send(w.samuel)).status_code == 200
    with pytest.raises(IntegrityError) as other:  # someone else's decision
        await _as(
            w.tenant, w.samuel.user_id, insert, tid=w.tenant, record=rid, by=w.daniel.user_id
        )
    _check_violation(other)
    with pytest.raises(IntegrityError) as not_ep:  # a partner, but not this engagement's EP
        await _as(w.tenant, w.rita.user_id, insert, tid=w.tenant, record=rid, by=w.rita.user_id)
    _check_violation(not_ep)
    # G1 needs the decided record, not a decision row alone: the right person's row, written
    # without moving the record, leaves G1 unmet.
    await _as(w.tenant, w.daniel.user_id, insert, tid=w.tenant, record=rid, by=w.daniel.user_id)
    gates = await w.call("GET", f"/v1/engagements/{w.engagement_id}/gates", w.daniel)
    assert next(g for g in gates.json() if g["gate"] == "G1")["met"] is False


async def test_m1_clearances_and_screening_are_the_acting_persons(net: Net) -> None:
    w = await _world(net)
    with pytest.raises(IntegrityError) as refused:
        await _as(
            w.tenant,
            w.samuel.user_id,
            "INSERT INTO screening_records (tenant_id, subject_kind, subject_id, list, result, "
            "recorded_by) VALUES (:tid, 'client', :client, 'ofac_sdn', 'no_match', :by)",
            tid=w.tenant,
            client=w.client_id,
            by=w.daniel.user_id,
        )
    _check_violation(refused)


# --- M3 -----------------------------------------------------------------------------------------


async def test_m3_only_a_partner_level_person_is_named_engagement_partner(net: Net) -> None:
    w = await _world(net)
    refused = await w.start(w.samuel)  # a manager named engagement partner
    assert refused.status_code == 422, refused.text
    assert refused.json() == {"detail": "invalid", "facts": {"field": "team"}}


async def test_m3_a_partner_demoted_before_the_decision_cannot_decide(net: Net) -> None:
    w = await _world(net)
    assert (await w.start()).status_code == 201
    for code, _ in SECTIONS:
        assert (await w.answer(code, w.samuel)).status_code == 200
    assert (await w.send(w.samuel)).status_code == 200
    await _level(net, w.tenant, w.daniel, "manager")
    refused = await w.decide(w.daniel)
    assert refused.status_code == 403, refused.text


# --- L1, L2 -------------------------------------------------------------------------------------


async def test_l1_l2_the_review_completion_honours_the_flag_and_fresh_mfa(net: Net) -> None:
    w = await _world(net)
    assert (await w.start()).status_code == 201
    requested = await w.call(
        "POST", f"{w.acc}/risk-partner-review", w.daniel, {"partner_id": str(w.rita.user_id)}
    )
    assert requested.status_code == 201
    complete = f"{w.acc}/risk-partner-review/complete"
    stale = await w.call("POST", complete, w.rita, {}, mfa=False)
    assert stale.status_code == 403, stale.text
    await net.seed.run(
        "UPDATE feature_flag_states SET value = 'false' WHERE tenant_id = $1 "
        "AND flag = 'engagements.acceptance_v2'",
        w.tenant,
    )
    forget_flags()  # the process caches flag values for 30 s
    off = await w.call("POST", complete, w.rita, {})
    assert off.status_code == 404, off.text


# --- M2, L3, L4 ---------------------------------------------------------------------------------


async def _run(w: World, who: Person, subject: dict[str, str], *names: str) -> httpx.Response:
    return await w.call(
        "POST", "/v1/conflict-checks", who, {"subject": subject, "names": list(names)}
    )


async def test_m2_walled_matches_collapse_into_one_restricted_row(net: Net) -> None:
    w = await _world(net)
    seed = net.seed
    walled: list[uuid.UUID] = []
    for name in ("Ashford Holdings", "Ashford Holding"):
        walled.append(
            cast(
                uuid.UUID,
                await seed.value(
                    "INSERT INTO clients (tenant_id, name) VALUES ($1, $2) RETURNING id",
                    w.tenant,
                    name,
                ),
            )
        )
    for client in walled:
        made = await w.call(
            "POST",
            "/v1/walls",
            w.admin,
            {"user_id": str(w.samuel.user_id), "client_id": str(client)},
        )
        assert made.status_code == 201, made.text
    subject = {"kind": "client", "id": str(w.client_id)}
    check = await _run(w, w.samuel, subject, "Ashford Holdings", "Ashford Holding")
    assert check.status_code == 201, check.text
    body = cast(Json, check.json())
    rows = cast(list[Json], body["results"])
    assert len(rows) == 1 and rows[0]["redacted"] is True
    assert rows[0]["match_kind"] == "trigram" and rows[0]["assessment"] == "pending"
    assert body["restricted_match"] is True
    assert body["outcome"] == "clear"  # only what the reader may see
    # The restricted row cannot be cleared by the walled reader: an unknown result.
    cleared = await w.call(
        "POST",
        f"/v1/conflict-checks/{body['id']}/results/{rows[0]['id']}/clear",
        w.samuel,
        {"assessment": "not_adverse", "reason": "x"},
    )
    assert cleared.status_code == 404
    # The unwalled partner sees both matches.
    full = await w.call("GET", f"/v1/conflict-checks/{body['id']}", w.daniel)
    assert full.json()["restricted_match"] is False
    assert {r["matched_client_id"] for r in full.json()["results"]} >= {str(c) for c in walled}


async def test_l3_the_search_has_one_budget(net: Net, monkeypatch: pytest.MonkeyPatch) -> None:
    w = await _world(net)
    monkeypatch.setattr(conflicts, "SEARCH_BUDGET_MS", 0)
    response = await _run(w, w.admin, {"kind": "client", "id": str(w.client_id)}, "Anything")
    assert response.status_code == 503, response.text
    assert (
        await net.seed.value("SELECT count(*) FROM conflict_checks WHERE tenant_id = $1", w.tenant)
        == 0
    )


async def test_l4_draft_subjects_and_evidence_links_must_be_visible(net: Net) -> None:
    w = await _world(net)
    mine = await w.draft(w.daniel)
    ok = await _run(w, w.admin, {"kind": "engagement_draft", "id": str(mine["id"])}, "Nobody")
    assert ok.status_code == 201, ok.text
    for subject in (
        {"kind": "engagement_draft", "id": str(uuid.uuid4())},
        {"kind": "client_intake_draft", "id": str(uuid.uuid4())},
    ):
        refused = await _run(w, w.admin, subject, "Nobody")
        assert refused.status_code == 404, refused.text
    # Another person's draft is not theirs to name.
    other = await _run(w, w.daniel, {"kind": "engagement_draft", "id": str(mine["id"])}, "Nobody")
    assert other.status_code == 404, other.text
    screening = await w.call(
        "POST",
        "/v1/screening-records",
        w.admin,
        {
            "subject": {"kind": "client", "id": str(w.client_id)},
            "screening_list": "ofac_sdn",
            "result": "no_match",
            "evidence_version_id": str(uuid.uuid4()),
        },
    )
    assert screening.status_code == 404, screening.text
    refs = await w.audit_refs("conflict_check.run")
    assert refs and all("results" not in r for r in refs)
