"""P-04-T25 acceptance (TASK-1461; ADR-161 clause 3; SHL-10): typed proposal adapters.

"Accepting a Granite Peak screening flag through the proposal route writes the same
review_decisions row AUD-03 writes today, and a shadow-stage firm sees no proposal."

Boundary: the migrated Postgres (superuser seeding of the agent's rows, as the agents write them),
the API over HTTP as each person.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Final, cast

import pytest

from .support import Net, Person, Seeder, Site

pytestmark = pytest.mark.asyncio
_RUN: Final = (
    "INSERT INTO agent_runs (tenant_id, agent_id, spec_version, engagement_id, "
    "evidence_version_id, initiator_user_id, task_scope, status, finished_at, shadow) "
    "VALUES ($1, 'evidence.screener', 1, $2, $3, $4, ARRAY['evidence.read'], 'completed', "
    "now(), $5) RETURNING id"
)


@dataclass(frozen=True)
class Firm:
    net: Net
    tenant_id: uuid.UUID
    hannah: Person
    daniel: Person

    @property
    def seed(self) -> Seeder:
        return self.net.seed


@pytest.fixture
async def firm(net: Net) -> Firm:
    seed = net.seed
    tenant_id = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'review.grammar_api', 'true', 'test-seed', 'P-04-T25')",
        tenant_id,
    )
    return Firm(net, tenant_id, await seed.person(tenant_id), await seed.person(tenant_id))


async def _site(firm: Firm, label: str) -> Site:
    seed = firm.seed
    admin = await seed.person(firm.tenant_id, "firm_admin")
    site = await seed.site(firm.tenant_id, admin.user_id, label)
    await seed.member(site, firm.hannah, "manager")
    await seed.member(site, firm.daniel, "engagement_partner")
    # The client's upload fulfils the item, so a person can decide on it (AUD-03).
    await seed.run(
        "INSERT INTO fulfilments (tenant_id, engagement_id, request_item_id, "
        "evidence_version_id, created_by_kind, created_by_id) "
        "VALUES ($1, $2, $3, $4, 'human', 'seed')",
        firm.tenant_id,
        site.engagement_id,
        site.item_id,
        site.version_id,
    )
    await seed.run("UPDATE request_items SET status = 'uploaded' WHERE id = $1", site.item_id)
    return site


async def _flag(firm: Firm, site: Site, *, cited: int = 2, shadow: bool = False) -> uuid.UUID:
    """The screener's result on the site's version, with `cited` verified citations (C4)."""
    seed = firm.seed
    run = await seed.value(
        _RUN, firm.tenant_id, site.engagement_id, site.version_id, firm.hannah.user_id, shadow
    )
    result = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO screening_results (tenant_id, engagement_id, evidence_version_id, "
            "agent_run_id, action, confidence, rationale, citations, unverified) VALUES "
            "($1, $2, $3, $4, 'ready_for_review', 0.9, 'Statement agrees to the ledger', "
            "'[]', '[]') RETURNING id",
            firm.tenant_id,
            site.engagement_id,
            site.version_id,
            run,
        ),
    )
    for n in range(1, cited + 1):
        await seed.run(
            "INSERT INTO citations (tenant_id, engagement_id, cited_from_type, cited_from_id, "
            "n, kind, source_type, source_id, locator, verified, verifier_version, "
            "created_by_kind, created_by_run_id) VALUES ($1, $2, 'screening_result', $3, $4, "
            '\'sheet_cell\', \'evidence_version\', $5, \'{"sheet": "TB", "cell": "B2"}\', '
            "true, 'v1', 'agent', $6)",
            firm.tenant_id,
            site.engagement_id,
            result,
            n,
            site.version_id,
            run,
        )
    return result


async def _decision(firm: Firm, site: Site) -> tuple[object, ...]:
    rows = await firm.seed.rows(
        "SELECT d.decision, d.reason_code, d.screening_result_id IS NOT NULL, "
        "d.corrects_proposal, d.actor_kind, d.actor_id, i.status FROM review_decisions d "
        "JOIN request_items i ON i.id = d.request_item_id WHERE d.evidence_version_id = $1",
        site.version_id,
    )
    assert len(rows) == 1
    return tuple(rows[0])


async def test_ac_accepting_the_flag_writes_the_row_aud03_writes(firm: Firm) -> None:
    granite = await _site(firm, "Granite Peak")
    flag = await _flag(firm, granite)
    ref = f"screening_result:{flag}"
    shown = await firm.net.call("GET", f"/v1/proposals/{ref}", firm.hannah)
    assert shown.status_code == 200, shown.text
    body = shown.json()
    assert body["ref"] == ref and body["kind"] == "screening_result"
    assert body["state"] == "pending" and body["version"] == 1
    assert len(body["rows"][0]["citation_ids"]) == 2 and body["rows"][0]["unsupported"] is False
    assert set(body["allowed_actions"]) == {"proposal.approve", "proposal.reject"}

    approved = await firm.net.call(
        "POST", f"/v1/proposals/{ref}/approve", firm.hannah, body={"seen_version": 1}
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["state"] == "approved"
    assert approved.json()["decision"]["decided_by_user_id"] == str(firm.hannah.user_id)
    through_proposal = await _decision(firm, granite)

    # The same flag on another file, accepted on AUD-03's own route.
    other = await _site(firm, "Granite Peak AUD-03")
    other_flag = await _flag(firm, other)
    direct = await firm.net.call(
        "POST",
        f"/v1/engagements/{other.engagement_id}/evidence-versions/{other.version_id}"
        "/decision/accept",
        firm.hannah,
        body={"seen_proposal": str(other_flag)},
    )
    assert direct.status_code in (200, 201), direct.text
    assert through_proposal == await _decision(firm, other)
    assert through_proposal == (
        "accept",
        None,
        True,
        False,
        "human",
        str(firm.hannah.user_id),
        "received",
    )
    audits = await firm.seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'review_decision.created'",
        firm.tenant_id,
    )
    assert audits == 2
    again = await firm.net.call(
        "POST", f"/v1/proposals/{ref}/approve", firm.hannah, body={"seen_version": 1}
    )
    assert again.status_code == 409 and again.json()["detail"] == "proposal_changed"


async def test_ac_a_shadow_stage_firm_sees_no_proposal(firm: Firm) -> None:
    granite = await _site(firm, "Granite Peak")
    flag = await _flag(firm, granite)
    path = f"/v1/proposals/screening_result:{flag}"
    assert (await firm.net.call("GET", path, firm.hannah)).status_code == 200
    await firm.seed.run(
        "INSERT INTO agent_stages (tenant_id, agent_id, stage, changed_by, note) "
        "VALUES ($1, 'evidence.screener', 'shadow', 'test-seed', 'PW1')",
        firm.tenant_id,
    )
    assert (await firm.net.call("GET", path, firm.hannah)).status_code == 404
    approve = await firm.net.call("POST", f"{path}/approve", firm.hannah, body={"seen_version": 1})
    assert approve.status_code == 404
    assert (
        await firm.seed.value(
            "SELECT count(*) FROM review_decisions WHERE evidence_version_id = $1",
            granite.version_id,
        )
        == 0
    )


async def test_ac_a_shadow_runs_flag_is_never_a_proposal(firm: Firm) -> None:
    granite = await _site(firm, "Granite Peak")
    flag = await _flag(firm, granite, shadow=True)  # a run that started in shadow
    shown = await firm.net.call("GET", f"/v1/proposals/screening_result:{flag}", firm.hannah)
    assert shown.status_code == 404


async def test_ac_reject_sends_the_file_back_with_the_reason(firm: Firm) -> None:
    granite = await _site(firm, "Granite Peak")
    flag = await _flag(firm, granite)
    rejected = await firm.net.call(
        "POST",
        f"/v1/proposals/screening_result:{flag}/reject",
        firm.hannah,
        body={"seen_version": 1, "reason_code": "needs_client_input"},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["state"] == "rejected"
    assert rejected.json()["decision"]["reason_code"] == "needs_client_input"
    decision = await _decision(firm, granite)
    assert decision[:2] == ("send_back", "incomplete")


async def test_ac_an_uncited_flag_cannot_be_approved_and_a_newer_one_wins(firm: Firm) -> None:
    granite = await _site(firm, "Granite Peak")
    bare = await _flag(firm, granite, cited=0)
    refused = await firm.net.call(
        "POST",
        f"/v1/proposals/screening_result:{bare}/approve",
        firm.hannah,
        body={"seen_version": 1},
    )
    assert refused.status_code == 422 and refused.json()["detail"] == "uncited_change"
    newer = await _flag(firm, granite)
    stale = await firm.net.call(
        "POST",
        f"/v1/proposals/screening_result:{bare}/reject",
        firm.hannah,
        body={"seen_version": 1, "reason_code": "other", "note": "Wrong year"},
    )
    assert stale.status_code == 409 and stale.json()["detail"] == "proposal_changed"
    shown = await firm.net.call("GET", f"/v1/proposals/screening_result:{newer}", firm.hannah)
    assert shown.json()["state"] == "pending"
    assert (
        await firm.seed.value(
            "SELECT count(*) FROM review_decisions WHERE evidence_version_id = $1",
            granite.version_id,
        )
        == 0
    )


async def test_ac_a_walled_person_gets_404_and_edits_are_refused_on_a_typed_ref(
    firm: Firm,
) -> None:
    granite = await _site(firm, "Granite Peak")
    flag = await _flag(firm, granite)
    admin = await firm.seed.person(firm.tenant_id, "firm_admin")
    await firm.net.wall(admin, firm.daniel, granite)
    walled = await firm.net.call("GET", f"/v1/proposals/screening_result:{flag}", firm.daniel)
    assert walled.status_code == 404
    edits = await firm.net.call(
        "POST",
        f"/v1/proposals/screening_result:{flag}/approve",
        firm.hannah,
        body={"seen_version": 1, "edits": [{"n": 1, "after": "x", "citation_note": "y"}]},
    )
    assert edits.status_code == 422
