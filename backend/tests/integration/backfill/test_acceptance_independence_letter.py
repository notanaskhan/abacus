# ac-test-author: ayushkbhatia
"""SPEC-025 AC-4, AC-5 and AC-6 (TASK-044; back-filled by Q-03-T008) against C1's G1-G3 gate
facts. AC-7 is `test_independence_gate.py`; AC-9 (screen states) is the web suite.

- AC-4: only the engagement partner records acceptance or continuance (decision, where it is
  documented, an optional file, a new client's predecessor auditor and date communicated) and
  their independence conclusion, with fresh MFA; both are audited; a declined engagement stays
  closed to client data.
- AC-5: each team member is asked to confirm independence, confirms or declines with a note to the
  partner, and the engagement shows each person's state; anyone who joins later is asked too.
- AC-6: the letter's status, date and signed copy or link are recorded and audited; "not required
  this year" needs a reason.
- C1 (`docs/contracts/work-items.md`, DEC-39): G1 is the acceptance decision, G2 the partner's
  independence conclusion, G3 the letter; `GET /v1/engagements/{id}` reports each with its
  blockers, and the server decides them. Q-03 §3.2 B1: no gate fact can be written by the agent
  principal (INV-1, I-AGENT-NEVER), and every recorded fact is audited as a human (INV-5).

HTTP through `create_app()` against the integration suite's migrated Postgres; the agent's
refusal through the public `authorise` with a real agent context. Expectations come from the
spec and the contracts, not the implementation.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Final, cast

import httpx
import pytest
from types_boto3_s3 import S3Client

from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.storage import s3_client
from abacus.modules.evidence import storage
from abacus.modules.identity.api import Forbidden, Resource, agent_context_for_run, authorise

from .support import Net, Person, Role, Seeder, Site

# The acceptance and letter files are stored write-once in the evidence bucket. Wire storage to
# this session's S3 container, never the settings default (the dev stack's S3, absent on CI).
BUCKET: Final = "backfill-acceptance-letter"
MASTER: Final = b"backfill-acceptance-letter-master-key-0123"


@pytest.fixture(scope="module")
def raw(s3_settings: dict[str, str]) -> Iterator[S3Client]:
    client = s3_client(
        endpoint_url=s3_settings["endpoint_url"],
        access_key=s3_settings["access_key"],
        secret_key=s3_settings["secret_key"],
        region=s3_settings["region"],
    )
    client.create_bucket(Bucket=BUCKET, ObjectLockEnabledForBucket=True)
    yield client


@pytest.fixture(autouse=True)
def wired(raw: S3Client) -> Iterator[None]:
    reset_key_service()
    storage.reset_storage()
    configure_key_service(LocalKeyService(MASTER))
    storage.configure_storage(raw, BUCKET)
    yield
    storage.reset_storage()
    reset_key_service()


GATE_FACT_ACTIONS = ("acceptance.record", "letter.record", "independence.confirm")
STAFF_OTHERS = ("manager", "senior", "staff", "reviewer")


@dataclass(frozen=True)
class Engagement:
    net: Net
    seed: Seeder
    tenant_id: uuid.UUID
    site: Site
    admin: Person
    partner: Person
    manager: Person
    senior: Person

    @property
    def base(self) -> str:
        return f"/v1/engagements/{self.site.engagement_id}"

    async def accept(self, who: Person | None = None, **given: object) -> httpx.Response:
        body = {"decision": "accepted", "documented_at": "PPC 1-200", **given}
        return await self.net.call(
            "PUT", f"{self.base}/acceptance", who or self.partner, body=body
        )

    async def letter(self, who: Person | None = None, **body: object) -> httpx.Response:
        return await self.net.call("PUT", f"{self.base}/letter", who or self.partner, body=body)

    async def answer(
        self, who: Person, *, confirm: bool, note: str | None = None
    ) -> httpx.Response:
        body: dict[str, object] = {"confirm": confirm}
        if note is not None:
            body["note"] = note
        return await self.net.call("POST", f"{self.base}/independence", who, body=body)

    async def setup(self, who: Person | None = None) -> dict[str, object]:
        response = await self.net.call("GET", f"{self.base}/setup", who or self.partner)
        assert response.status_code == 200, response.text
        return cast(dict[str, object], response.json())

    async def gates(self) -> dict[str, tuple[bool, list[str]]]:
        response = await self.net.call("GET", self.base, self.partner)
        assert response.status_code == 200, response.text
        return {g["gate"]: (g["met"], sorted(g["blockers"])) for g in response.json()["gates"]}

    async def join(self, who: Person, role: str) -> None:
        added = await self.net.call(
            "POST",
            f"{self.base}/team",
            self.partner,
            body={"user_id": str(who.user_id), "role": role},
        )
        assert added.status_code == 201, added.text

    async def audited(self, action: str) -> list[str]:
        """The actor kind of each audit row of `action` in this firm."""
        rows = await self.seed.rows(
            "SELECT actor_kind FROM audit_events WHERE tenant_id = $1 AND action = $2",
            self.tenant_id,
            action,
        )
        return [str(r["actor_kind"]) for r in rows]

    async def invite(self) -> httpx.Response:
        return await self.net.call(
            "POST",
            f"{self.base}/client-invitations",
            self.partner,
            body={"email": "cfo@client.example", "role": "client_admin"},
        )


@pytest.fixture
async def eng(net: Net, seed: Seeder) -> Engagement:
    tenant_id = await seed.firm()
    admin = await seed.person(tenant_id, "firm_admin")
    site = await seed.site(tenant_id, admin.user_id, "accept", opened=False)
    people = [await seed.person(tenant_id) for _ in range(3)]
    for who, role in zip(people, ("engagement_partner", "manager", "senior"), strict=True):
        await seed.member(site, who, role)  # an already-confirmed team
    return Engagement(net, seed, tenant_id, site, admin, *people)


def _confirmation(setup: dict[str, object], who: Person) -> dict[str, object]:
    found = [
        c
        for c in cast(list[dict[str, object]], setup["confirmations"])
        if c["user_id"] == str(who.user_id)
    ]
    assert len(found) == 1, setup["confirmations"]
    return found[0]


# --- C1 gates G1 to G3, decided on the server ----------------------------------------------------


async def test_ac4_g1_and_g2_are_unmet_until_the_partner_records_each_fact(
    eng: Engagement,
) -> None:
    gates = await eng.gates()
    assert gates["G1"] == (False, ["acceptance"])
    assert gates["G2"] == (False, ["independence_conclusion"])
    assert (await eng.accept()).status_code == 200
    gates = await eng.gates()
    assert gates["G1"] == (True, [])
    assert gates["G2"] == (False, ["independence_conclusion"])
    concluded = await eng.accept(independence_concluded=True, independence_documented_at="Memo 2")
    assert concluded.status_code == 200, concluded.text
    # Spec drift (DEC-429, P-07-T41 security review): SPEC-332 AC-18 and AC-19 make G2 the
    # engagement partner's CLI-08 conclusion; SPEC-025's route still documents its conclusion on
    # a firm without independence v2, but a row it writes after 0175 never meets G2.
    assert (await eng.gates())["G2"] == (False, ["independence_conclusion"])


async def test_ac6_g3_is_unmet_until_the_letter_is_recorded_whatever_the_firm_policy(
    eng: Engagement,
) -> None:
    assert (await eng.gates())["G3"] == (False, ["engagement_letter"])


async def test_ac6_with_the_letter_required_g3_waits_for_a_signed_letter(eng: Engagement) -> None:
    policy = await eng.net.call(
        "PUT", "/v1/firm/letter-policy", eng.admin, body={"required": True}
    )
    assert policy.status_code == 200, policy.text
    assert (await eng.gates())["G3"] == (False, ["engagement_letter"])
    assert (await eng.letter(status="sent", letter_date="2026-01-20")).status_code == 200
    assert (await eng.gates())["G3"] == (False, ["engagement_letter"])  # sent is not signed
    signed = await eng.letter(
        status="signed", letter_date="2026-02-03", link="https://dms.example/l"
    )
    assert signed.status_code == 200, signed.text
    assert (await eng.gates())["G3"] == (True, [])


async def test_ac6_not_required_this_year_with_its_reason_meets_g3(eng: Engagement) -> None:
    policy = await eng.net.call(
        "PUT", "/v1/firm/letter-policy", eng.admin, body={"required": True}
    )
    assert policy.status_code == 200, policy.text
    recorded = await eng.letter(status="not_required_this_year", reason="Multi-year letter")
    assert recorded.status_code == 200, recorded.text
    assert (await eng.gates())["G3"] == (True, [])


async def test_ac4_a_declined_engagement_fails_g1_and_stays_closed_to_client_data(
    eng: Engagement,
) -> None:
    declined = await eng.accept(
        decision="declined", independence_concluded=True, independence_documented_at="Memo 2"
    )
    assert declined.status_code == 200, declined.text
    assert (await eng.gates())["G1"] == (False, ["acceptance_declined"])
    refused = await eng.invite()
    assert (refused.status_code, refused.json()["detail"]) == (409, "acceptance_declined")
    assert (
        await eng.seed.value(
            "SELECT count(*) FROM client_invitations WHERE tenant_id = $1", eng.tenant_id
        )
        == 0
    )


async def test_ac4_a_later_decision_supersedes_the_earlier_one(eng: Engagement) -> None:
    assert (await eng.accept(decision="declined")).status_code == 200
    assert (await eng.gates())["G1"][0] is False
    assert (await eng.accept(decision="accepted")).status_code == 200
    assert (await eng.gates())["G1"] == (True, [])
    acceptance = cast(dict[str, object], (await eng.setup())["acceptance"])
    assert acceptance["decision"] == "accepted"


# --- INV-1: no gate fact is written by the agent principal ---------------------------------------


@pytest.mark.parametrize("action", GATE_FACT_ACTIONS)
async def test_ac4_the_agent_is_refused_every_gate_fact_even_for_the_partner(
    eng: Engagement, action: str
) -> None:
    agent = await agent_context_for_run(
        tenant_id=eng.tenant_id,
        run_id=uuid.uuid4(),
        agent_id="engagement.agent",
        engagement_id=eng.site.engagement_id,
        task_scope=frozenset(GATE_FACT_ACTIONS),  # even when the run was given them
        initiator_user_id=eng.partner.user_id,
    )
    resource = Resource.engagement(eng.tenant_id, eng.site.engagement_id, archived=False)
    with pytest.raises(Forbidden):
        await authorise(agent, action, resource)


@pytest.mark.parametrize(
    "action",
    [
        "engagement.acceptance_recorded",
        "engagement.letter_recorded",
        "independence.confirmed",
        "independence.declined",
    ],
)
async def test_ac4_the_database_refuses_a_gate_fact_audited_as_the_agent(
    eng: Engagement, action: str
) -> None:
    """I-AGENT-NEVER at the data layer (Q-02-T17): the register of human-only audit actions,
    which the database enforces, holds every gate fact SPEC-025 §14 audits."""
    listed = await eng.seed.value("SELECT abacus_human_only_actions()")
    assert action in cast(list[str], listed)


async def test_ac4_every_recorded_gate_fact_is_audited_as_a_human(eng: Engagement) -> None:
    assert (
        await eng.accept(independence_concluded=True, independence_documented_at="Memo 2")
    ).status_code == 200
    assert (await eng.letter(status="signed", letter_date="2026-02-03")).status_code == 200
    newcomer = await eng.seed.person(eng.tenant_id)
    await eng.join(newcomer, "staff")
    assert (await eng.answer(newcomer, confirm=True)).status_code == 200
    for action in (
        "engagement.acceptance_recorded",
        "engagement.letter_recorded",
        "independence.confirmed",
    ):
        kinds = await eng.audited(action)
        assert kinds, action
        assert set(kinds) == {"human"}, (action, kinds)


# --- AC-4: acceptance and the partner's independence conclusion ----------------------------------


async def test_ac4_the_partner_records_a_new_clients_acceptance_with_its_predecessor(
    eng: Engagement,
) -> None:
    recorded = await eng.accept(
        kind="new_client",
        documented_at="Acceptance memo, binder 1-200",
        predecessor_auditor="Marsh & Pell LLP",
        predecessor_communicated_on="2026-01-15",
        independence_concluded=True,
        independence_documented_at="Independence memo 1-210",
    )
    assert recorded.status_code == 200, recorded.text
    acceptance = cast(dict[str, object], recorded.json()["acceptance"])
    assert (
        acceptance["kind"],
        acceptance["decision"],
        acceptance["documented_at"],
        acceptance["predecessor_auditor"],
        acceptance["predecessor_communicated_on"],
        acceptance["independence_documented_at"],
    ) == (
        "new_client",
        "accepted",
        "Acceptance memo, binder 1-200",
        "Marsh & Pell LLP",
        "2026-01-15",
        "Independence memo 1-210",
    )
    assert acceptance["independence_concluded_at"] is not None
    assert "engagement.acceptance_recorded" in await eng.seed.actions(eng.tenant_id)


@pytest.mark.parametrize("role", ["admin", *STAFF_OTHERS])
async def test_ac4_only_the_engagement_partner_records_acceptance(
    eng: Engagement, role: str
) -> None:
    who = {"admin": eng.admin, "manager": eng.manager, "senior": eng.senior}.get(role)
    if who is None:
        who = await eng.seed.person(eng.tenant_id)
        await eng.seed.member(eng.site, who, cast(Role, role))
    before = await eng.seed.actions(eng.tenant_id)
    refused = await eng.accept(who, independence_concluded=True, independence_documented_at="M")
    assert refused.status_code == 403, refused.text
    assert await eng.seed.actions(eng.tenant_id) == before
    assert (await eng.setup())["acceptance"] is None


async def test_ac4_the_partner_needs_a_fresh_sign_in_to_record_acceptance(eng: Engagement) -> None:
    response = await eng.net.call(
        "PUT",
        f"{eng.base}/acceptance",
        eng.partner,
        body={"decision": "accepted", "documented_at": "PPC 1-200"},
        mfa=False,
    )
    assert response.status_code == 403, response.text
    assert (await eng.gates())["G1"] == (False, ["acceptance"])


async def test_ac4_acceptance_needs_where_it_is_documented(eng: Engagement) -> None:
    response = await eng.accept(documented_at="")
    assert response.status_code == 422, response.text
    assert (await eng.setup())["acceptance"] is None


async def test_ac4_another_firm_cannot_record_acceptance(eng: Engagement) -> None:
    other = await eng.seed.firm()
    stranger = await eng.seed.person(other, "firm_admin")
    response = await eng.accept(stranger)
    assert response.status_code == 404, response.text


async def test_ac4_the_partner_attaches_an_acceptance_file_kept_as_an_attachment(
    eng: Engagement,
) -> None:
    assert (await eng.accept()).status_code == 200
    uploaded = await eng.net.http.post(
        f"{eng.base}/acceptance/file?filename=acceptance.pdf",
        content=b"%PDF-1.4 acceptance memo",
        headers={**eng.net.headers(eng.partner), "Content-Type": "application/pdf"},
    )
    assert uploaded.status_code == 201, uploaded.text
    acceptance = cast(dict[str, object], (await eng.setup())["acceptance"])
    assert acceptance["file_name"] == "acceptance.pdf"
    read = await eng.net.call("GET", f"{eng.base}/acceptance/file", eng.manager)
    assert read.status_code == 200, read.text
    assert read.content == b"%PDF-1.4 acceptance memo"
    assert read.headers["content-disposition"].startswith("attachment")  # never inline


# --- AC-5: everyone's independence ---------------------------------------------------------------


async def test_ac5_a_member_who_joins_is_asked_and_the_engagement_shows_their_state(
    eng: Engagement,
) -> None:
    newcomer = await eng.seed.person(eng.tenant_id)
    await eng.join(newcomer, "staff")
    assert _confirmation(await eng.setup(), newcomer)["status"] == "requested"
    assert _confirmation(await eng.setup(), eng.senior)["status"] == "confirmed"
    mine = await eng.net.call("GET", "/v1/firm/confirmations", newcomer)
    assert mine.status_code == 200, mine.text
    (open_one,) = mine.json()
    assert open_one["engagement_id"] == str(eng.site.engagement_id)
    assert open_one["status"] == "requested"
    assert open_one["statement"]  # the fixed statement they confirm
    assert "independence.requested" in await eng.seed.actions(eng.tenant_id)


async def test_ac5_a_member_confirms_for_themself_and_is_no_longer_asked(eng: Engagement) -> None:
    newcomer = await eng.seed.person(eng.tenant_id)
    await eng.join(newcomer, "senior")
    confirmed = await eng.answer(newcomer, confirm=True)
    assert confirmed.status_code == 200, confirmed.text
    mine = _confirmation(confirmed.json(), newcomer)
    assert mine["status"] == "confirmed"
    assert mine["answered_at"] is not None
    assert (await eng.net.call("GET", "/v1/firm/confirmations", newcomer)).json() == []
    assert "independence.confirmed" in await eng.seed.actions(eng.tenant_id)


async def test_ac5_a_member_declines_with_a_note_that_the_partner_and_manager_read(
    eng: Engagement,
) -> None:
    newcomer = await eng.seed.person(eng.tenant_id)
    await eng.join(newcomer, "staff")
    note = "My spouse holds shares in the client."
    declined = await eng.answer(newcomer, confirm=False, note=note)
    assert declined.status_code == 200, declined.text
    for reader in (eng.partner, eng.manager):
        seen = _confirmation(await eng.setup(reader), newcomer)
        assert (seen["status"], seen["note"]) == ("declined", note)
    assert "independence.declined" in await eng.seed.actions(eng.tenant_id)


async def test_ac5_a_declined_note_is_not_shown_to_other_members(eng: Engagement) -> None:
    newcomer = await eng.seed.person(eng.tenant_id)
    await eng.join(newcomer, "staff")
    note = "My spouse holds shares in the client."
    assert (await eng.answer(newcomer, confirm=False, note=note)).status_code == 200
    seen = _confirmation(await eng.setup(eng.senior), newcomer)
    assert seen["status"] == "declined"
    assert seen["note"] is None  # SPEC-025 §13: notes for the partner and manager only


async def test_ac5_declining_needs_a_note_for_the_partner(eng: Engagement) -> None:
    newcomer = await eng.seed.person(eng.tenant_id)
    await eng.join(newcomer, "staff")
    refused = await eng.answer(newcomer, confirm=False)
    assert 400 <= refused.status_code < 500, refused.text
    assert _confirmation(await eng.setup(), newcomer)["status"] == "requested"


async def test_ac5_someone_off_the_team_cannot_answer_for_the_engagement(eng: Engagement) -> None:
    outsider = await eng.seed.person(eng.tenant_id, "practice_leader")
    refused = await eng.answer(outsider, confirm=True)
    assert refused.status_code in (403, 404), refused.text
    found = await eng.seed.value(
        "SELECT count(*) FROM independence_confirmations WHERE user_id = $1", outsider.user_id
    )
    assert found == 0


# --- AC-6: the engagement letter -----------------------------------------------------------------


@pytest.mark.parametrize("by", ["partner", "manager"])
async def test_ac6_the_partner_or_manager_records_a_signed_letter(
    eng: Engagement, by: str
) -> None:
    who = eng.partner if by == "partner" else eng.manager
    recorded = await eng.letter(
        who, status="signed", letter_date="2026-02-03", link="https://dms.example/letter-42"
    )
    assert recorded.status_code == 200, recorded.text
    letter = cast(dict[str, object], recorded.json()["letter"])
    assert (letter["status"], letter["letter_date"], letter["link"]) == (
        "signed",
        "2026-02-03",
        "https://dms.example/letter-42",
    )
    assert await eng.audited("engagement.letter_recorded") == ["human"]


@pytest.mark.parametrize("role", ["admin", "senior"])
async def test_ac6_others_cannot_record_the_letter(eng: Engagement, role: str) -> None:
    who = eng.admin if role == "admin" else eng.senior
    refused = await eng.letter(who, status="signed", letter_date="2026-02-03")
    assert refused.status_code == 403, refused.text
    assert (await eng.setup())["letter"] is None


async def test_ac6_not_required_this_year_needs_a_reason(eng: Engagement) -> None:
    refused = await eng.letter(status="not_required_this_year")
    assert 400 <= refused.status_code < 500, refused.text
    assert (await eng.setup())["letter"] is None
    recorded = await eng.letter(
        status="not_required_this_year", reason="Continuing letter covers FY2026"
    )
    assert recorded.status_code == 200, recorded.text
    letter = cast(dict[str, object], recorded.json()["letter"])
    assert (letter["status"], letter["reason"]) == (
        "not_required_this_year",
        "Continuing letter covers FY2026",
    )


async def test_ac6_the_signed_copy_is_stored_and_read_back_as_an_attachment(
    eng: Engagement,
) -> None:
    assert (await eng.letter(status="signed", letter_date="2026-02-03")).status_code == 200
    uploaded = await eng.net.http.post(
        f"{eng.base}/letter/file?filename=letter-signed.pdf",
        content=b"%PDF-1.4 signed letter",
        headers={**eng.net.headers(eng.manager), "Content-Type": "application/pdf"},
    )
    assert uploaded.status_code == 201, uploaded.text
    assert cast(dict[str, object], (await eng.setup())["letter"])["file_name"] == (
        "letter-signed.pdf"
    )
    read = await eng.net.call("GET", f"{eng.base}/letter/file", eng.senior)
    assert read.status_code == 200, read.text
    assert read.content == b"%PDF-1.4 signed letter"
    assert read.headers["content-disposition"].startswith("attachment")
