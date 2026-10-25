# ac-test-author: ayushkbhatia
"""SPEC-332 AC-1 to AC-11 for P-07-T35 (P-07-T38): the acceptance questionnaire from the firm's
database template, human-authored flags, manual checks, send to partner, the risk-partner review
on High, the engagement partner's three-option decision with fresh MFA, the rationale rule, the
lock, conditions, Prospect to Accepted or Declined, G1 before the letter, and the continuance's
prior year. "Daniel Reyes decides Thornbury with conditions and fresh MFA, Samuel Ito cannot
decide at any layer, and the record locks."

Read from SPEC-332 §5 Stories 1 to 3, P-07 §3.4 Story 4.1, §4.2 M5, §4.3 and §4.7, the CLI-07
screen contract, `docs/contracts/acceptance-independence.md`, the engagements matrix,
`error-codes.yaml` and the human-only register. HTTP through `create_app()` behind
`engagements.v2` and `engagements.acceptance_v2`; the record comes from ENG-03's "Start
acceptance" on a draft. The live-human layer is called through `engagements.api`, the database
layer as raw SQL, and the call-site layer through `banned_patterns`.

Spec gaps followed here (TASK-1257): the questionnaire template has no import route yet, so it is
seeded as rows (P-07 §4.2 M5's tables, TASK-1258's columns); the risk partner completes the
review on `POST …/risk-partner-review/complete` (TASK-1258: AC-4 needs a completion and the
contract had no route); the EP naming themself, or anyone not a partner, as risk partner is 422
`invalid`; a manual check is completed only by the person it was asked of (403 otherwise);
completing a condition twice is 422 `invalid`. A rationale is required for every option (SPEC-332
AC-7 and the CLI-07 deviation, over P-07 OQ-6). The `acceptance_awaiting_partner` notification is
P-07-T47's registration, so AC-3 is checked through its audit and outbox events.
"""

from __future__ import annotations

import json
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

from .support import Net, Person, Seeder

pytestmark = pytest.mark.asyncio

Json = dict[str, object]
FY_START, FY_END = date(2025, 1, 1), date(2025, 12, 31)
SECTIONS: Final = (
    ("engagement_scope", "Engagement scope and services"),
    ("integrity", "Client integrity and reputation"),
    ("fees", "Fees and collectability"),
)


@dataclass
class Thornbury:
    """Brightwater Hale's Estate of Walter Thornbury: Grace Holloway (firm admin) starts the
    acceptance from a Forms 706/709 draft; Daniel Reyes is the engagement partner, Samuel Ito the
    manager who prepares, Kira Ross staff; Rita Vance is another partner."""

    net: Net
    seed: Seeder
    tenant: uuid.UUID
    grace: Person
    daniel: Person
    samuel: Person
    kira: Person
    rita: Person
    client_id: uuid.UUID
    entity_id: uuid.UUID
    engagement_id: uuid.UUID | None = None

    @property
    def acc(self) -> str:
        return f"/v1/engagements/{self.engagement_id}/acceptance"

    async def call(
        self,
        method: str,
        path: str,
        who: Person,
        body: Mapping[str, object] | None = None,
        *,
        mfa: bool = True,
        key: str | None = None,
    ) -> httpx.Response:
        headers = self.net.headers(who, mfa=mfa)
        if key is not None:
            headers["Idempotency-Key"] = key
        return await self.net.http.request(method, path, json=body, headers=headers)

    async def begin(
        self,
        *,
        name: str = "Estate of Walter Thornbury 706",
        prior: uuid.UUID | None = None,
        start: date = FY_START,
        end: date = FY_END,
    ) -> httpx.Response:
        """ENG-03's "Start acceptance" on a new Forms 706/709 draft of Grace's."""
        payload: Json = {
            "name": name,
            "fiscal_period_start": start.isoformat(),
            "fiscal_period_end": end.isoformat(),
            "team": [
                {"user_id": str(self.daniel.user_id), "role": "engagement_partner"},
                {"user_id": str(self.samuel.user_id), "role": "manager"},
                {"user_id": str(self.kira.user_id), "role": "staff"},
            ],
        }
        if prior is not None:
            payload["prior_engagement_id"] = str(prior)
        draft = _json(
            await self.call(
                "POST",
                "/v1/engagement-drafts",
                self.grace,
                {
                    "client_id": str(self.client_id),
                    "client_entity_id": str(self.entity_id),
                    "type_code": "forms_706_709",
                    "payload": payload,
                },
            ),
            201,
        )
        return await self.call(
            "POST", f"/v1/engagement-drafts/{draft['id']}/start-acceptance", self.grace
        )

    async def start(
        self,
        *,
        name: str = "Estate of Walter Thornbury 706",
        prior: uuid.UUID | None = None,
        start: date = FY_START,
        end: date = FY_END,
    ) -> Json:
        """A Prospect engagement and its acceptance record."""
        started = _json(await self.begin(name=name, prior=prior, start=start, end=end), 201)
        assert started["engagement_status"] == "prospect"
        self.engagement_id = uuid.UUID(cast(str, started["engagement_id"]))
        return started

    async def record(self, who: Person | None = None) -> Json:
        return _json(await self.call("GET", self.acc, who or self.samuel))

    async def answer(self, section: str, *, who: Person | None = None, **extra: object) -> Json:
        current = {s["code"]: s for s in _sections(await self.record(who))}[section]
        body: Json = {
            "seen_version": current["version"],
            "answers": {"reviewed": True},
            "complete": True,
            **extra,
        }
        return _json(
            await self.call("PUT", f"{self.acc}/answers/{section}", who or self.samuel, body)
        )

    async def send(self, who: Person | None = None) -> httpx.Response:
        version = (await self.record()).get("version")
        return await self.call(
            "POST", f"{self.acc}/send-to-partner", who or self.samuel, {"seen_version": version}
        )

    async def ready(self) -> Json:
        """Every section answered and the record sent to Daniel."""
        for code, _ in SECTIONS:
            await self.answer(code)
        return _json(await self.send())

    async def decide(
        self,
        option: str,
        rationale: str = "Estate within the firm's tax competence; fees agreed with the executor.",
        conditions: list[Json] | None = None,
        *,
        who: Person | None = None,
        mfa: bool = True,
        seen_version: int | None = None,
    ) -> httpx.Response:
        version = seen_version
        if version is None:
            version = cast(int, (await self.record(self.daniel)).get("version"))
        return await self.call(
            "POST",
            f"{self.acc}/decision",
            who or self.daniel,
            {
                "option": option,
                "rationale": rationale,
                "conditions": conditions or [],
                "seen_version": version,
            },
            mfa=mfa,
        )

    def conditions(self) -> list[Json]:
        return [
            {
                "text": text,
                "assignee_user_id": str(self.samuel.user_id),
                "due_on": (date.today() + timedelta(days=14)).isoformat(),
            }
            for text in (
                "Obtain the executor's letters testamentary",
                "Confirm the date of death valuation approach",
                "Collect the retainer before filing",
            )
        ]

    async def status(self) -> str:
        return cast(
            str,
            await self.seed.value(
                "SELECT status FROM engagements WHERE id = $1", self.engagement_id
            ),
        )

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


def _sections(record: Json) -> list[Json]:
    return cast(list[Json], record["sections"])


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
    sections = [{"code": code, "title": title} for code, title in SECTIONS]
    await seed.run(
        "INSERT INTO acceptance_questionnaire_template_versions "
        "(tenant_id, template_id, version_no, sections, created_by) "
        "VALUES ($1, $2, 1, $3::jsonb, $4)",
        tenant,
        template,
        json.dumps(sections),
        by,
    )


async def _world(net: Net, *, template: bool = True) -> Thornbury:
    seed = net.seed
    tenant = await seed.firm()
    for flag in ("engagements.v2", "engagements.acceptance_v2"):
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'P-07-T38')",
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
    rita = await seed.person(tenant)
    await _level(seed, tenant, rita, "partner")
    marker = uuid.uuid4().hex[:6]
    client_id = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO clients (tenant_id, name) VALUES ($1, $2) RETURNING id",
            tenant,
            f"Walter Thornbury {marker}",
        ),
    )
    entity_id = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, $3) "
            "RETURNING id",
            tenant,
            client_id,
            f"Estate of Walter Thornbury {marker}",
        ),
    )
    if template:
        await _template(seed, tenant, grace.user_id)
    return Thornbury(net, seed, tenant, grace, daniel, samuel, kira, rita, client_id, entity_id)


@pytest.fixture
async def tb(net: Net) -> Thornbury:
    return await _world(net)


# ================================================================================================
# Story 1: the questionnaire (AC-1 to AC-5)
# ================================================================================================


@pytest.mark.xfail(
    strict=True,
    reason="TASK-1258: P-07-T35 not built; acceptance routes answer 501 (main at #409)",
)
async def test_ac1_the_record_starts_in_draft_with_the_firms_template_sections(
    tb: Thornbury,
) -> None:
    started = await tb.start()
    record = await tb.record()
    assert record["id"] == started["acceptance_record_id"]
    assert record["status"] == "draft"
    assert record["kind"] == "new_client"
    assert record["template_name"] == "Tax engagements v2"
    assert record["prepared_by"] == str(tb.grace.user_id)
    assert [(s["code"], s["title"]) for s in _sections(record)] == list(SECTIONS)
    assert {s["answer_state"] for s in _sections(record)} == {"pending"}
    assert record["decision"] is None
    assert await tb.status() == "prospect"
    # A second start from another draft for the same engagement is not needed: the record is
    # the engagement's one record, read by every team member and refused to anyone outside.
    assert (await tb.record(tb.kira))["id"] == record["id"]


@pytest.mark.xfail(
    strict=True,
    reason="TASK-1258: P-07-T35 not built; acceptance routes answer 501 (main at #409)",
)
async def test_ac1_a_firm_without_a_questionnaire_template_cannot_start_acceptance(
    net: Net,
) -> None:
    tb = await _world(net, template=False)
    _refusal(await tb.begin(), 409, "acceptance_template_missing")
    assert (
        await tb.seed.value("SELECT count(*) FROM engagements WHERE tenant_id = $1", tb.tenant)
        == 0
    )


@pytest.mark.xfail(
    strict=True,
    reason="TASK-1258: P-07-T35 not built; acceptance routes answer 501 (main at #409)",
)
async def test_ac1_send_to_partner_is_refused_while_a_manual_check_is_open(
    tb: Thornbury,
) -> None:
    await tb.start()
    for code, _ in SECTIONS:
        await tb.answer(code)
    check = _json(
        await tb.call(
            "POST",
            f"{tb.acc}/manual-checks/fees/request",
            tb.samuel,
            {"requested_of": str(tb.grace.user_id)},
        ),
        201,
    )
    assert check["requested_of"] == str(tb.grace.user_id)
    assert check["requested_by"] == str(tb.samuel.user_id)
    fees = {s["code"]: s for s in _sections(await tb.record())}["fees"]
    assert fees["answer_state"] == "manual_check_open"
    facts = _refusal(await tb.send(), 409, "acceptance_not_ready")
    assert "fees" in json.dumps(facts)
    assert (await tb.record())["status"] == "draft"
    # Only the person it was asked of completes it.
    refused = await tb.call(
        "POST", f"{tb.acc}/manual-checks/fees/complete", tb.samuel, {"note": "Checked by me"}
    )
    assert refused.status_code == 403, refused.text
    done = _json(
        await tb.call(
            "POST",
            f"{tb.acc}/manual-checks/fees/complete",
            tb.grace,
            {"note": "Estate set up in the practice-management system"},
        )
    )
    assert done["completed_by"] == str(tb.grace.user_id)
    fees = {s["code"]: s for s in _sections(await tb.record())}["fees"]
    assert fees["answer_state"] == "manual_check_done"
    assert _json(await tb.send())["status"] == "awaiting_partner"
    assert await tb.audit("acceptance.manual_check_requested") == [
        ("human", str(tb.samuel.user_id))
    ]
    assert await tb.audit("acceptance.manual_check_completed") == [
        ("human", str(tb.grace.user_id))
    ]


@pytest.mark.xfail(
    strict=True,
    reason="TASK-1258: P-07-T35 not built; acceptance routes answer 501 (main at #409)",
)
async def test_ac1_staff_without_the_prepare_right_cannot_change_the_record(
    tb: Thornbury,
) -> None:
    await tb.start()
    record = await tb.record()
    section = _sections(record)[0]
    refused = await tb.call(
        "PUT",
        f"{tb.acc}/answers/{section['code']}",
        tb.kira,
        {"seen_version": section["version"], "answers": {"x": 1}, "complete": True},
    )
    assert refused.status_code == 403, refused.text
    refused = await tb.call(
        "POST",
        f"{tb.acc}/flags",
        tb.kira,
        {"severity": "low", "title": "Staff note", "body": "Not mine to add"},
    )
    assert refused.status_code == 403, refused.text


@pytest.mark.xfail(
    strict=True,
    reason="TASK-1258: P-07-T35 not built; acceptance routes answer 501 (main at #409)",
)
async def test_ac2_a_flag_is_authored_by_the_person_and_never_changes(tb: Thornbury) -> None:
    await tb.start()
    source = str(uuid.uuid4())
    flag = _json(
        await tb.call(
            "POST",
            f"{tb.acc}/flags",
            tb.samuel,
            {
                "severity": "medium",
                "title": "Gross estate above the basic exclusion",
                "body": "About $16.4M against $15,000,000: Form 706 is required.",
                "sources": [{"kind": "evidence_version", "id": source}],
            },
        ),
        201,
    )
    assert flag["authored_by"] == str(tb.samuel.user_id)
    assert flag["severity"] == "medium"
    assert flag["sources"] == [{"kind": "evidence_version", "id": source}]
    record = await tb.record(tb.daniel)
    assert [f["id"] for f in cast(list[Json], record["flags"])] == [flag["id"]]
    assert await tb.audit("acceptance.flag_added") == [("human", str(tb.samuel.user_id))]
    # Free text is sealed at rest.
    rows = await tb.seed.rows(
        "SELECT * FROM acceptance_flags WHERE id = $1", uuid.UUID(cast(str, flag["id"]))
    )
    assert "16.4M" not in str(dict(rows[0]))
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await tb.seed.run(
            "UPDATE acceptance_flags SET severity = 'low' WHERE tenant_id = $1", tb.tenant
        )
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await tb.seed.run("DELETE FROM acceptance_flags WHERE tenant_id = $1", tb.tenant)
    # A flag authored by anything but a person is refused by the database.
    with pytest.raises(asyncpg.CheckViolationError):
        await tb.seed.run(
            "INSERT INTO acceptance_flags (tenant_id, record_id, severity, title_sealed, "
            "body_sealed, source_refs, authored_by, authored_kind) "
            "SELECT tenant_id, record_id, severity, title_sealed, body_sealed, source_refs, "
            "authored_by, 'agent' FROM acceptance_flags WHERE id = $1",
            uuid.UUID(cast(str, flag["id"])),
        )


@pytest.mark.xfail(
    strict=True,
    reason="TASK-1258: P-07-T35 not built; acceptance routes answer 501 (main at #409)",
)
async def test_ac3_send_to_partner_moves_draft_to_awaiting_partner_audited_and_emitted(
    tb: Thornbury,
) -> None:
    await tb.start()
    record = await tb.ready()
    assert record["status"] == "awaiting_partner"
    assert record["sent_to_partner_by"] == str(tb.samuel.user_id)
    assert record["sent_to_partner_at"] is not None
    assert await tb.audit("acceptance.sent_to_partner") == [("human", str(tb.samuel.user_id))]
    events = await tb.seed.rows(
        "SELECT payload FROM outbox WHERE tenant_id = $1 "
        "AND event_type = 'acceptance.sent_to_partner'",
        tb.tenant,
    )
    assert len(events) == 1
    assert str(tb.engagement_id) in str(events[0]["payload"])
    # Sending twice is not a second state change.
    again = await tb.send()
    assert again.status_code == 409, again.text


@pytest.mark.xfail(
    strict=True,
    reason="TASK-1258: P-07-T35 not built; acceptance routes answer 501 (main at #409)",
)
async def test_ac4_a_high_risk_record_waits_for_another_partners_completed_review(
    tb: Thornbury,
) -> None:
    await tb.start()
    await tb.answer("integrity", risk_rating="high")
    await tb.ready()
    assert (await tb.record())["risk_rating"] == "high"
    _refusal(await tb.decide("accept"), 409, "review_required")
    review = f"{tb.acc}/risk-partner-review"
    # Never the EP, never someone who is not a partner.
    for who in (tb.daniel, tb.samuel):
        refused = await tb.call("POST", review, tb.daniel, {"partner_id": str(who.user_id)})
        _refusal(refused, 422, "invalid")
    # Only the EP picks the risk partner.
    refused = await tb.call("POST", review, tb.samuel, {"partner_id": str(tb.rita.user_id)})
    assert refused.status_code == 403, refused.text
    requested = _json(
        await tb.call("POST", review, tb.daniel, {"partner_id": str(tb.rita.user_id)}), 201
    )
    assert requested["partner_id"] == str(tb.rita.user_id)
    assert requested["completed_at"] is None
    _refusal(await tb.decide("accept"), 409, "review_required")
    # Only the named risk partner completes it.
    for who in (tb.daniel, tb.samuel):
        refused = await tb.call("POST", f"{review}/complete", who, {})
        assert refused.status_code == 403, refused.text
    completed = _json(await tb.call("POST", f"{review}/complete", tb.rita, {}))
    assert completed["completed_at"] is not None
    assert await tb.audit("acceptance.review_requested") == [("human", str(tb.daniel.user_id))]
    assert await tb.audit("acceptance.review_completed") == [("human", str(tb.rita.user_id))]
    decided = _json(await tb.decide("accept"), 201)
    assert decided["status"] == "decided"
    review_out = cast(Json, decided["risk_partner_review"])
    assert review_out["partner_id"] == str(tb.rita.user_id)


@pytest.mark.xfail(
    strict=True,
    reason="TASK-1258: P-07-T35 not built; acceptance routes answer 501 (main at #409)",
)
async def test_ac5_a_continuance_shows_the_prior_years_decision_and_conditions(
    tb: Thornbury,
) -> None:
    await tb.start()
    await tb.ready()
    _json(await tb.decide("accept_with_conditions", conditions=tb.conditions()), 201)
    prior = tb.engagement_id
    await tb.start(
        name="Estate of Walter Thornbury 1041 FY2026",
        prior=prior,
        start=date(2026, 1, 1),
        end=date(2026, 12, 31),
    )
    assert tb.engagement_id != prior
    record = await tb.record(tb.daniel)
    assert record["kind"] == "continuance"
    previous = cast(Json, record["prior"])
    assert previous["engagement_id"] == str(prior)
    assert previous["option"] == "accept_with_conditions"
    assert previous["decided_at"] is not None
    texts = sorted(cast(str, c["text"]) for c in cast(list[Json], previous["conditions"]))
    assert texts == sorted(cast(str, c["text"]) for c in tb.conditions())


# ================================================================================================
# Story 2: the decision (AC-6 to AC-10)
# ================================================================================================


@pytest.mark.xfail(
    strict=True,
    reason="TASK-1258: P-07-T35 not built; acceptance routes answer 501 (main at #409)",
)
async def test_ac6_daniel_decides_thornbury_with_conditions_and_the_record_locks(
    tb: Thornbury,
) -> None:
    await tb.start()
    await tb.ready()
    decided = _json(await tb.decide("accept_with_conditions", conditions=tb.conditions()), 201)
    assert decided["status"] == "decided"
    decision = cast(Json, decided["decision"])
    assert decision["option"] == "accept_with_conditions"
    assert decision["decided_by"] == str(tb.daniel.user_id)
    assert cast(str, decision["rationale"]).startswith("Estate within")
    conditions = cast(list[Json], decided["conditions"])
    assert len(conditions) == 3
    assert {c["assignee_user_id"] for c in conditions} == {str(tb.samuel.user_id)}
    assert all(c["completed_at"] is None for c in conditions)
    assert await tb.audit("acceptance.decided") == [("human", str(tb.daniel.user_id))]
    assert (
        await tb.seed.value(
            "SELECT count(*) FROM acceptance_decisions WHERE tenant_id = $1", tb.tenant
        )
        == 1
    )
    # Locked: every edit answers 409 decision_locked.
    section = _sections(await tb.record())[0]
    attempts = [
        (
            "PUT",
            f"{tb.acc}/answers/{section['code']}",
            tb.samuel,
            {"seen_version": section["version"], "answers": {"late": True}, "complete": True},
        ),
        (
            "POST",
            f"{tb.acc}/flags",
            tb.samuel,
            {"severity": "low", "title": "Late flag", "body": "After the decision"},
        ),
        (
            "POST",
            f"{tb.acc}/manual-checks/fees/request",
            tb.samuel,
            {"requested_of": str(tb.grace.user_id)},
        ),
        ("POST", f"{tb.acc}/send-to-partner", tb.samuel, {"seen_version": decided["version"]}),
        ("POST", f"{tb.acc}/risk-partner-review", tb.daniel, {"partner_id": str(tb.rita.user_id)}),
    ]
    for method, path, who, body in attempts:
        _refusal(await tb.call(method, path, who, body), 409, "decision_locked")
    _refusal(await tb.decide("decline"), 409, "decision_locked")
    assert (
        await tb.seed.value(
            "SELECT count(*) FROM acceptance_decisions WHERE tenant_id = $1", tb.tenant
        )
        == 1
    )
    after = await tb.record(tb.daniel)
    assert cast(Json, after["decision"])["option"] == "accept_with_conditions"


@pytest.mark.xfail(
    strict=True,
    reason="TASK-1258: P-07-T35 not built; acceptance routes answer 501 (main at #409)",
)
async def test_ac6_the_decision_row_is_insert_only_and_one_per_record(tb: Thornbury) -> None:
    await tb.start()
    await tb.ready()
    _json(await tb.decide("accept"), 201)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await tb.seed.run(
            "UPDATE acceptance_decisions SET option = 'decline' WHERE tenant_id = $1", tb.tenant
        )
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await tb.seed.run("DELETE FROM acceptance_decisions WHERE tenant_id = $1", tb.tenant)
    with pytest.raises(asyncpg.UniqueViolationError):
        await tb.seed.run(
            "INSERT INTO acceptance_decisions (tenant_id, record_id, option, rationale_sealed, "
            "decided_by, mfa_verified_at, actor_kind) SELECT tenant_id, record_id, 'decline', "
            "rationale_sealed, decided_by, mfa_verified_at, 'human' FROM acceptance_decisions "
            "WHERE tenant_id = $1",
            tb.tenant,
        )
    # The rationale is sealed at rest.
    row = await tb.seed.rows("SELECT * FROM acceptance_decisions WHERE tenant_id = $1", tb.tenant)
    assert "Estate within" not in str(dict(row[0]))


@pytest.mark.xfail(
    strict=True,
    reason="TASK-1258: P-07-T35 not built; acceptance routes answer 501 (main at #409)",
)
async def test_ac6_a_decision_on_a_stale_version_answers_409(tb: Thornbury) -> None:
    await tb.start()
    record = await tb.ready()
    stale = cast(int, record["version"])
    await tb.call(
        "POST",
        f"{tb.acc}/flags",
        tb.samuel,
        {"severity": "low", "title": "Late note", "body": "Added after sending"},
    )
    _refusal(await tb.decide("accept", seen_version=stale), 409, "stale_version")
    assert (await tb.record())["decision"] is None


@pytest.mark.xfail(
    strict=True,
    reason="TASK-1258: P-07-T35 not built; acceptance routes answer 501 (main at #409)",
)
async def test_ac6_a_draft_record_is_not_ready_for_decision(tb: Thornbury) -> None:
    await tb.start()
    _refusal(await tb.decide("accept"), 409, "acceptance_not_ready")
    assert await tb.status() == "prospect"


@pytest.mark.xfail(
    strict=True,
    reason="TASK-1258: P-07-T35 not built; acceptance routes answer 501 (main at #409)",
)
async def test_ac7_a_rationale_is_required_and_conditions_for_accept_with_conditions(
    tb: Thornbury,
) -> None:
    await tb.start()
    await tb.ready()
    for option in ("accept", "accept_with_conditions", "decline"):
        for blank in ("", "   "):
            facts = _refusal(
                await tb.decide(
                    option, blank, tb.conditions() if option == "accept_with_conditions" else None
                ),
                422,
                "rationale_required",
            )
            assert facts.get("field") == "rationale"
    facts = _refusal(await tb.decide("accept_with_conditions"), 422, "rationale_required")
    assert facts.get("field") == "conditions"
    assert (await tb.record())["decision"] is None
    assert await tb.audit("acceptance.decided") == []


@pytest.mark.xfail(
    strict=True,
    reason="TASK-1258: P-07-T35 not built; acceptance routes answer 501 (main at #409)",
)
async def test_ac8_accept_moves_prospect_to_accepted_and_g1_is_met_by_daniel(
    tb: Thornbury,
) -> None:
    await tb.start()
    await tb.ready()
    decided = _json(await tb.decide("accept"), 201)
    assert await tb.status() == "accepted"
    gates = {
        cast(str, g["gate"]): g
        for g in cast(
            list[Json],
            _json(await tb.call("GET", f"/v1/engagements/{tb.engagement_id}/gates", tb.daniel)),
        )
    }
    assert gates["G1"]["met"] is True
    record = _json(await tb.call("GET", f"/v1/engagements/{tb.engagement_id}/record", tb.daniel))
    g1 = next(g for g in cast(list[Json], record["gates"]) if g["gate"] == "G1")
    assert g1["met"] is True
    assert g1["met_by_user_id"] == str(tb.daniel.user_id)
    assert cast(Json, decided["decision"])["decided_at"] is not None
    assert await tb.audit("engagement.accepted") == [("human", str(tb.daniel.user_id))]


@pytest.mark.xfail(
    strict=True,
    reason="TASK-1258: P-07-T35 not built; acceptance routes answer 501 (main at #409)",
)
async def test_ac8_decline_moves_to_declined_and_no_letter_can_be_recorded(
    tb: Thornbury,
) -> None:
    await tb.start()
    await tb.ready()
    declined = _json(
        await tb.decide("decline", "The executor will not engage on the firm's terms."), 201
    )
    assert declined["status"] == "declined"
    assert cast(Json, declined["decision"])["option"] == "decline"
    assert await tb.status() == "declined"
    today = datetime.now(UTC).date().isoformat()
    facts = _refusal(
        await tb.call(
            "PUT",
            f"/v1/engagements/{tb.engagement_id}/letter/record",
            tb.daniel,
            {"mode": "signed", "client_signed_on": today, "firm_signed_on": today},
        ),
        409,
        "gate_unmet",
    )
    assert facts.get("gate") == "G1"


@pytest.mark.xfail(
    strict=True,
    reason="TASK-1258: P-07-T35 not built; acceptance routes answer 501 (main at #409)",
)
async def test_ac8_conditions_belong_only_to_accept_with_conditions(tb: Thornbury) -> None:
    await tb.start()
    await tb.ready()
    _refusal(await tb.decide("accept", conditions=tb.conditions()), 422, "invalid")
    assert (await tb.record())["decision"] is None


@pytest.mark.xfail(
    strict=True,
    reason="TASK-1258: P-07-T35 not built; acceptance routes answer 501 (main at #409)",
)
async def test_ac9_completing_a_condition_is_an_insert_only_event_by_a_person(
    tb: Thornbury,
) -> None:
    await tb.start()
    await tb.ready()
    decided = _json(await tb.decide("accept_with_conditions", conditions=tb.conditions()), 201)
    condition = cast(list[Json], decided["conditions"])[0]
    path = f"{tb.acc}/conditions/{condition['id']}/complete"
    refused = await tb.call("POST", path, tb.kira, {"note": "Not mine"})
    assert refused.status_code == 403, refused.text
    done = _json(await tb.call("POST", path, tb.samuel, {"note": "Letters testamentary on file"}))
    assert done["completed_by"] == str(tb.samuel.user_id)
    assert done["completed_at"] is not None
    _refusal(await tb.call("POST", path, tb.samuel, {}), 422, "invalid")
    record = await tb.record(tb.daniel)
    open_ = [c for c in cast(list[Json], record["conditions"]) if c["completed_at"] is None]
    assert len(open_) == 2
    assert await tb.audit("acceptance.condition_completed") == [("human", str(tb.samuel.user_id))]
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await tb.seed.run(
            "DELETE FROM acceptance_condition_events WHERE tenant_id = $1", tb.tenant
        )
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await tb.seed.run("DELETE FROM acceptance_conditions WHERE tenant_id = $1", tb.tenant)


@pytest.mark.xfail(
    strict=True,
    reason="TASK-1258: P-07-T35 not built; acceptance routes answer 501 (main at #409)",
)
async def test_ac10_samuel_cannot_decide_at_the_matrix_and_daniel_needs_fresh_mfa(
    tb: Thornbury,
) -> None:
    await tb.start()
    await tb.ready()
    for who in (tb.samuel, tb.kira, tb.grace, tb.rita):
        refused = await tb.decide("accept", who=who)
        assert refused.status_code in (403, 404), (who, refused.text)
    refused = await tb.decide("accept", mfa=False)
    assert refused.status_code == 403, refused.text
    assert (await tb.record())["decision"] is None
    assert await tb.status() == "prospect"
    assert await tb.audit("acceptance.decided") == []
    # The decide control is the engagement partner's alone.
    assert "acceptance.decide" not in cast(list[str], (await tb.record())["allowed_actions"])
    assert "acceptance.decide" in cast(list[str], (await tb.record(tb.daniel))["allowed_actions"])


async def test_ac10_the_matrix_holds_the_decision_for_the_engagement_partner_alone() -> None:
    rule = RULES["acceptance.decide"]
    assert {r for r, d in rule.decisions.items() if d != "deny"} == {"engagement_partner"}
    assert rule.decisions.get("agent") == "deny"
    assert rule.decisions.get("system") == "deny"


@pytest.mark.xfail(
    strict=True,
    reason="TASK-1258: P-07-T35 not built; acceptance routes answer 501 (main at #409)",
)
async def test_ac10_an_agent_or_system_context_is_refused_by_the_service(
    tb: Thornbury,
) -> None:
    from abacus.modules.engagements import api as engagements_api

    # P-07 §4.1 names the public decision function; looked up by name so this suite type-checks
    # before T35 adds it.
    function = "decide_acceptance"
    decide = cast(Callable[..., Awaitable[object]], getattr(engagements_api, function))

    await tb.start()
    record = await tb.ready()
    fresh = datetime.now(UTC) - timedelta(minutes=1)
    for kind in ("agent", "system"):
        ctx = AuthContext(
            TenantContext(tb.tenant, cast(ActorKind, kind), str(tb.daniel.user_id)),
            tb.daniel.user_id,
            uuid.uuid4(),
            None,
            fresh,
        )
        with pytest.raises(Forbidden):
            await decide(
                ctx,
                cast(uuid.UUID, tb.engagement_id),
                option="accept",
                rationale="An agent may never decide.",
                conditions=[],
                seen_version=cast(int, record["version"]),
            )
    # A client principal with the EP's user id is refused too.
    client_ctx = AuthContext(
        TenantContext(tb.tenant, "human", str(tb.daniel.user_id)),
        tb.daniel.user_id,
        uuid.uuid4(),
        None,
        fresh,
        client=True,
    )
    with pytest.raises(Forbidden):
        await decide(
            client_ctx,
            cast(uuid.UUID, tb.engagement_id),
            option="accept",
            rationale="A client never decides.",
            conditions=[],
            seen_version=cast(int, record["version"]),
        )
    assert (await tb.record())["decision"] is None


@pytest.mark.xfail(
    strict=True,
    reason="TASK-1258: P-07-T35 not built; acceptance routes answer 501 (main at #409)",
)
async def test_ac10_the_database_refuses_a_decision_row_written_by_a_non_human(
    tb: Thornbury,
) -> None:
    await tb.start()
    await tb.ready()
    record_id = await tb.seed.value(
        "SELECT id FROM acceptance_records WHERE engagement_id = $1", tb.engagement_id
    )
    for kind in ("agent", "system", "policy"):
        with pytest.raises(asyncpg.CheckViolationError):
            await tb.seed.run(
                "INSERT INTO acceptance_decisions (tenant_id, record_id, option, "
                "rationale_sealed, decided_by, mfa_verified_at, actor_kind) "
                "VALUES ($1, $2, 'accept', '\\x00'::bytea, $3, now(), $4)",
                tb.tenant,
                record_id,
                tb.daniel.user_id,
                kind,
            )
    # `acceptance.decided` is in the human-only register: no agent may be its audit actor.
    register = (
        Path(__file__).resolve().parents[4] / "docs/architecture/human-only-actions.yaml"
    ).read_text(encoding="utf-8")
    assert "action: acceptance.decided" in register


@pytest.mark.xfail(
    strict=True,
    reason="TASK-1258: P-07-T35 not built; acceptance routes answer 501 (main at #409)",
)
async def test_ac10_only_the_acceptance_module_may_call_the_decision_function(
    tmp_path: Path,
) -> None:
    """The banned-pattern layer: any other module naming `decide_acceptance` fails the gate."""
    rel = "src/abacus/modules/requests/sneaky.py"
    calls = "from abacus.modules.engagements.api import decide_acceptance\n"

    def found(text: str) -> list[str]:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return [v.rule_id for v in banned_patterns.scan(tmp_path) if v.path == rel]

    assert found("VALUE = 1\n") == []
    assert found(calls) != []


# ================================================================================================
# Story 3: G1 before the letter (AC-11)
# ================================================================================================


@pytest.mark.xfail(
    strict=True,
    reason="TASK-1258: P-07-T35 not built; acceptance routes answer 501 (main at #409)",
)
async def test_ac11_a_letter_dated_before_the_decision_answers_409(tb: Thornbury) -> None:
    await tb.start()
    await tb.ready()
    decided = _json(await tb.decide("accept"), 201)
    decided_on = (
        datetime.fromisoformat(cast(str, cast(Json, decided["decision"])["decided_at"]))
        .astimezone(UTC)
        .date()
    )
    letter = f"/v1/engagements/{tb.engagement_id}/letter/record"
    before = (decided_on - timedelta(days=1)).isoformat()
    _refusal(
        await tb.call(
            "PUT",
            letter,
            tb.daniel,
            {
                "mode": "signed",
                "client_signed_on": before,
                "firm_signed_on": decided_on.isoformat(),
            },
        ),
        409,
        "letter_before_acceptance",
    )
    ok = _json(
        await tb.call(
            "PUT",
            letter,
            tb.daniel,
            {
                "mode": "signed",
                "client_signed_on": decided_on.isoformat(),
                "firm_signed_on": decided_on.isoformat(),
            },
        )
    )
    assert ok["engagement_id"] == str(tb.engagement_id)


# ================================================================================================
# Walls (INV-3) and tenancy
# ================================================================================================


@pytest.mark.xfail(
    strict=True,
    reason="TASK-1258: P-07-T35 not built; acceptance routes answer 501 (main at #409)",
)
async def test_inv3_a_walled_team_member_and_another_firm_get_404(tb: Thornbury, net: Net) -> None:
    await tb.start()
    walled = _json(
        await tb.call(
            "POST",
            "/v1/walls",
            tb.grace,
            {"user_id": str(tb.kira.user_id), "client_id": str(tb.client_id)},
        ),
        201,
    )
    assert walled
    assert (await tb.call("GET", tb.acc, tb.kira)).status_code == 404
    other = await net.seed.firm()
    stranger = await net.seed.person(other, "firm_admin")
    response = await net.call("GET", tb.acc, stranger)
    assert response.status_code == 404, response.text
