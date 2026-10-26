"""SPEC-025 AC-7 (TASK-044 and TASK-045): client data waits for the engagement to open, and then
for each team member's own independence confirmation.

Engagement level: until acceptance is `accepted` and the partner has concluded on independence
(and the letter, where the firm requires it), client invitations, connections, retrievals and
client uploads are refused for everyone, with a plain reason, audited, and nothing is created.
Person level: on an open engagement a member who has not confirmed independence is refused client
data while confirmed members are not; adding someone later restricts only them.

HTTP through `create_app()` against a real Postgres (the real independence SQL in `visible()` and
the real confirmation lookup in `authorise`). Expectations come from the spec.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import httpx
import pytest

from abacus.kernel.config import settings

from .support import Net, Person, Seeder, Site

CLIENT_DATA_READS = ("/evidence-versions", "/review-queue", "/screening-results")
COUNT_INVITATIONS = "SELECT count(*) FROM client_invitations WHERE tenant_id = $1"
COUNT_CONNECTIONS = "SELECT count(*) FROM connections WHERE tenant_id = $1"
COUNT_RUNS = "SELECT count(*) FROM sync_runs WHERE tenant_id = $1"
COUNT_VERSIONS = "SELECT count(*) FROM evidence_versions WHERE tenant_id = $1"
WHAT = ("invite", "connect", "retrieve", "upload", "inbox")
ASKED = ("/request-items", "")  # what the engagement is and what is asked: open to every member


@dataclass(frozen=True)
class Team:
    net: Net
    tenant_id: uuid.UUID
    site: Site
    partner: Person
    manager: Person
    admin: Person

    @property
    def base(self) -> str:
        return f"/v1/engagements/{self.site.engagement_id}"

    async def get(self, who: Person, tail: str) -> httpx.Response:
        return await self.net.call("GET", self.base + tail, who)

    async def clients_data(self, who: Person) -> list[int]:
        """The status of each read of the client's data: evidence, the review queue, screening
        and the files uploaded for a request item."""
        tails = (*CLIENT_DATA_READS, f"/request-items/{self.site.item_id}/uploads")
        return [(await self.get(who, tail)).status_code for tail in tails]

    async def refusals(self) -> int:
        found = await self.net.seed.value(
            "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
            "AND action = 'client_data.gate_refused'",
            self.tenant_id,
        )
        return cast(int, found)

    async def attempt(self, who: Person, what: str) -> httpx.Response:
        """One client-data action the gate guards, as `who`."""
        item = self.site.item_id
        pdf = {"Content-Type": "application/pdf"}
        if what == "invite":
            return await self.net.call(
                "POST",
                f"{self.base}/client-invitations",
                who,
                body={"email": "cfo@client.example", "role": "client_admin"},
            )
        if what == "connect":
            return await self.net.call(
                "POST", f"{self.base}/connection/start", who, body={"provider": "fake"}
            )
        if what == "retrieve":
            return await self.net.call(
                "POST",
                f"{self.base}/retrievals",
                who,
                body={
                    "request_item_id": str(item),
                    "period_start": "2025-01-01",
                    "period_end": "2025-12-31",
                },
            )
        path = (
            f"{self.base}/request-items/{item}/uploads"
            if what == "upload"
            else f"{self.base}/inbox"
        )
        return await self.net.http.post(
            f"{path}?filename=statement.pdf",
            content=b"%PDF-1.4 a statement",
            headers={**self.net.headers(who), **pdf},
        )

    async def attempts(self, who: Person) -> list[httpx.Response]:
        return [await self.attempt(who, what) for what in WHAT]


@pytest.fixture(autouse=True)
def fake_connector(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The demo ledger is a provider only where the fake connector may run (SPEC-020 Q1)."""
    monkeypatch.setenv("ABACUS_FAKE_CONNECTOR_DIR", str(tmp_path))
    settings.cache_clear()


async def _team(net: Net, seed: Seeder, *, opened: bool) -> Team:
    tenant_id = await seed.firm()
    admin = await seed.person(tenant_id, "firm_admin")
    site = await seed.site(tenant_id, admin.user_id, "gate", opened=opened)
    partner, manager = await seed.person(tenant_id), await seed.person(tenant_id)
    await seed.member(site, partner, "engagement_partner")
    await seed.member(site, manager, "manager")
    # ADR-164 items 2-3 (superseding SPEC-025 AC-7 in part): TASK-045's read gate is what a
    # firm gets with `g2_blocks_view` on, for an attest client's engagement. This suite proves
    # that gate; test_g2_v2 proves the default.
    await seed.attest(tenant_id, site.engagement_id)
    await seed.blocks_view(tenant_id, admin.user_id)
    return Team(net, tenant_id, site, partner, manager, admin)


# --- the engagement is open or it is not ---------------------------------------------------------


async def _record(team: Team, **given: object) -> None:
    body = {"decision": "accepted", "documented_at": "Acceptance memo, 12 Oct", **given}
    response = await team.net.call("PUT", f"{team.base}/acceptance", team.partner, body=body)
    assert response.status_code == 200, response.text


async def _concluded_before_v2(team: Team) -> None:
    """The partner's SPEC-025 conclusion as a row written before independence v2 (0175): since
    DEC-429 (P-07-T41 security review) a row the app writes through SPEC-025's route no longer
    meets G2, so the open engagement is seeded the way rows from before 0175 stand."""
    await team.net.seed.run(
        "INSERT INTO engagement_acceptance (tenant_id, engagement_id, kind, decision, "
        "decided_by, documented_at, independence_concluded_by, independence_concluded_at, "
        "independence_documented_at) VALUES ($1, $2, 'continuance', 'accepted', $3, "
        "'Acceptance memo, 12 Oct', $3, clock_timestamp(), 'Memo 2')",
        team.tenant_id,
        team.site.engagement_id,
        str(team.partner.user_id),
    )


async def _closed_by(team: Team, reason: str) -> None:
    if reason == "acceptance_declined":
        await _record(team, decision="declined")
    elif reason == "independence_conclusion_missing":
        await _record(team)
    elif reason == "letter_missing":
        await _record(team)
        await _concluded_before_v2(team)
        policy = await team.net.call(
            "PUT", "/v1/firm/letter-policy", team.admin, body={"required": True}
        )
        assert policy.status_code == 200, policy.text


REASONS = (
    "acceptance_missing",
    "acceptance_declined",
    "independence_conclusion_missing",
    "letter_missing",
)


@pytest.mark.parametrize("reason", REASONS)
async def test_ac7_until_the_engagement_is_open_client_data_actions_are_refused_with_the_reason(
    net: Net, seed: Seeder, reason: str
) -> None:
    team = await _team(net, seed, opened=False)
    await _closed_by(team, reason)
    for who in (team.partner, team.manager):  # refused for everyone
        responses = await team.attempts(who)
        assert [r.status_code for r in responses] == [409] * 5, [r.text for r in responses]
        assert {r.json()["detail"] for r in responses} == {reason}
    assert await team.refusals() >= 10  # each refusal is audited
    assert await seed.value(COUNT_INVITATIONS, team.tenant_id) == 0
    assert await seed.value(COUNT_CONNECTIONS, team.tenant_id) == 0
    assert await seed.value(COUNT_RUNS, team.tenant_id) == 0
    assert await seed.value(COUNT_VERSIONS, team.tenant_id) == 1  # the seeded one, no upload


async def test_ac7_once_the_engagement_is_open_the_actions_reach_their_own_checks(
    net: Net, seed: Seeder
) -> None:
    team = await _team(net, seed, opened=False)
    assert [r.status_code for r in await team.attempts(team.partner)] == [409] * 5
    await _record(team)
    await _concluded_before_v2(team)
    invited = await team.attempt(team.partner, "invite")
    assert invited.status_code == 201, invited.text  # the gate is open: the invitation is made
    started = await team.attempt(team.partner, "connect")
    assert started.status_code == 403  # now authorisation decides: only the client connects
    retrieval = await team.attempt(team.partner, "retrieve")
    assert retrieval.json().get("detail") not in REASONS  # whatever it says, not the gate's


async def test_ac7_a_gate_refusal_for_another_firms_engagement_is_not_found_not_closed(
    net: Net, seed: Seeder
) -> None:
    team = await _team(net, seed, opened=False)
    stranger_firm = await seed.firm()
    stranger = await seed.person(stranger_firm, "firm_admin")
    response = await net.call(
        "POST",
        f"{team.base}/client-invitations",
        stranger,
        body={"email": "cfo@client.example", "role": "client_admin"},
    )
    assert response.status_code == 404  # the gate does not reveal that the engagement exists


# --- each member's own independence --------------------------------------------------------------


async def test_ac7_an_unconfirmed_member_is_refused_client_data_and_a_confirmed_one_is_not(
    net: Net, seed: Seeder
) -> None:
    team = await _team(net, seed, opened=True)
    newcomer = await seed.person(team.tenant_id)
    added = await net.call(
        "POST",
        f"{team.base}/team",
        team.partner,
        body={"user_id": str(newcomer.user_id), "role": "senior"},
    )
    assert added.status_code == 201, added.text
    assert await team.clients_data(team.partner) == [200] * 4
    assert await team.clients_data(team.manager) == [200] * 4  # adding restricts none
    assert await team.clients_data(newcomer) == [403] * 4
    status = await seed.value(
        "SELECT status FROM independence_confirmations WHERE engagement_id = $1 AND user_id = $2",
        team.site.engagement_id,
        newcomer.user_id,
    )
    assert status == "requested"  # "anyone who joins later is asked too" (AC-5)


async def test_ac7_an_unconfirmed_member_still_sees_the_engagement_and_what_is_asked(
    net: Net, seed: Seeder
) -> None:
    team = await _team(net, seed, opened=True)
    newcomer = await seed.person(team.tenant_id)
    await net.call(
        "POST",
        f"{team.base}/team",
        team.partner,
        body={"user_id": str(newcomer.user_id), "role": "staff"},
    )
    for tail in ASKED:
        assert (await team.get(newcomer, tail)).status_code == 200, tail
    assert (await team.get(newcomer, "/setup")).status_code == 200
    mine = await net.call("GET", "/v1/firm/confirmations", newcomer)
    assert [c["engagement_id"] for c in mine.json()] == [str(team.site.engagement_id)]


async def test_ac7_confirming_opens_client_data_to_that_person_only(
    net: Net, seed: Seeder
) -> None:
    team = await _team(net, seed, opened=True)
    first, second = await seed.person(team.tenant_id), await seed.person(team.tenant_id)
    for who in (first, second):
        await net.call(
            "POST",
            f"{team.base}/team",
            team.partner,
            body={"user_id": str(who.user_id), "role": "senior"},
        )
    confirmed = await net.call("POST", f"{team.base}/independence", first, body={"confirm": True})
    assert confirmed.status_code == 200, confirmed.text
    assert await team.clients_data(first) == [200] * 4
    assert await team.clients_data(second) == [403] * 4
    assert "independence.confirmed" in await seed.actions(team.tenant_id)


async def test_ac7_declining_keeps_client_data_closed_to_that_person(
    net: Net, seed: Seeder
) -> None:
    team = await _team(net, seed, opened=True)
    member = await seed.person(team.tenant_id)
    await net.call(
        "POST",
        f"{team.base}/team",
        team.partner,
        body={"user_id": str(member.user_id), "role": "senior"},
    )
    declined = await net.call(
        "POST",
        f"{team.base}/independence",
        member,
        body={"confirm": False, "note": "I banked with them until last year."},
    )
    assert declined.status_code == 200, declined.text
    assert await team.clients_data(member) == [403] * 4
    assert await team.clients_data(team.partner) == [200] * 4


async def test_ac7_confirming_on_one_engagement_does_not_open_another(
    net: Net, seed: Seeder
) -> None:
    team = await _team(net, seed, opened=True)
    other = await seed.site(team.tenant_id, team.admin.user_id, "second", opened=True)
    await seed.attest(team.tenant_id, other.engagement_id)
    member = await seed.person(team.tenant_id)
    await net.call(
        "POST",
        f"{team.base}/team",
        team.partner,
        body={"user_id": str(member.user_id), "role": "senior"},
    )
    await seed.run(  # on the second engagement too, not yet confirmed there
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES ($1, $2, $3, 'senior')",
        team.tenant_id,
        other.engagement_id,
        member.user_id,
    )
    await net.call("POST", f"{team.base}/independence", member, body={"confirm": True})
    assert await team.clients_data(member) == [200] * 4
    refused = await net.call(
        "GET", f"/v1/engagements/{other.engagement_id}/evidence-versions", member
    )
    assert refused.status_code == 403
