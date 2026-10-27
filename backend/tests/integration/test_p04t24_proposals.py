"""P-04-T24 acceptance (TASK-1460; ADR-161 clauses 1 and 2; SHL-10): proposals and suggestions.

"A proposal with one unsupported row cannot be approved until that row is removed or cited, and
approval records Proposal approved by Samuel Ito with one field version per row."

The target is a test field owner (`probe_return`) whose registered applier writes each value
through `review.api.record_value`. Citations are C4 rows on the engagement, verified by code; a row
whose citation is missing or no longer verified is unsupported (422 `uncited_change`).
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import cast

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from abacus.kernel.db import TenantContext, configure_engine, dispose_engine, tenant_connection
from abacus.kernel.uow import UnitOfWork
from abacus.modules.agents.api import (
    AdoptedValue,
    PolicyEval,
    ProposedRow,
    create_proposal,
    create_suggestion,
    register_suggestion_applier,
    register_suggestion_target,
)
from abacus.modules.agents.proposals import approve_proposal, reject_proposal
from abacus.modules.identity.api import (
    AgentContext,
    AuthContext,
    Forbidden,
    agent_context_for_run,
)
from abacus.modules.review.api import record_value

from .agent_tests.support import Role
from .conftest import MigratedDatabase
from .review_support import Cast, make_cast

pytestmark = pytest.mark.asyncio
TARGET = "probe_return"
UNOWNED = "probe_unowned"
APPLIED: list[AdoptedValue] = []


async def _apply(tx: UnitOfWork, _ctx: AuthContext, value: AdoptedValue) -> None:
    """The owner's applier: its own record would change here; the history is review's."""
    APPLIED.append(value)
    await record_value(
        tx,
        engagement_id=value.engagement_id,
        target_type=value.target_type,
        target_id=value.target_id,
        field_key=value.field_key,
        value=value.value,
        value_source=value.value_source,
        cause=value.cause,
        suggestion_id=value.suggestion_id,
        checkpoint_id=value.checkpoint_id,
        citation_ids=value.citation_ids,
        citation_note=value.citation_note,
    )


register_suggestion_applier(TARGET, _apply)
register_suggestion_target(UNOWNED)  # accepts suggestions, but nobody writes them (503)


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()


async def _named(team: Cast, key: str, name: str, role: Role) -> None:
    who = await team.seed.person(team.tenant)
    await team.seed.run("UPDATE users SET display_name = $1 WHERE id = $2", name, who.user_id)
    await team.seed.member(team.engagement, who, role)
    team.people[key] = who


@pytest.fixture
async def team(migrated_db: MigratedDatabase) -> Cast:
    found = await make_cast(migrated_db.superuser_dsn)
    await _named(found, "samuel", "Samuel Ito", "senior")
    await _named(found, "raj", "Raj Malhotra", "senior")
    await _named(found, "priya", "Priya Raman", "manager")
    return found


async def _agent(team: Cast) -> AgentContext:
    run_id = uuid.uuid4()
    await team.seed.run(
        "INSERT INTO agent_runs (id, tenant_id, agent_id, spec_version, engagement_id, "
        "initiator_user_id, task_scope, status, finished_at, output) VALUES ($1, $2, "
        "'evidence.screener', 1, $3, $4, ARRAY['proposal.create'], 'completed', now(), $5)",
        run_id,
        team.tenant,
        team.engagement,
        team["hannah"].user_id,
        json.dumps(
            {
                "reasoning": "Prior-year treatment and the draft K-1 support passive.",
                "policy_note": "Return proposals need a Tax Reviewer.",
            }
        ),
    )
    return await agent_context_for_run(
        tenant_id=team.tenant,
        run_id=run_id,
        agent_id="evidence.screener",
        engagement_id=team.engagement,
        task_scope=frozenset({"proposal.create", "suggestion.create"}),
        initiator_user_id=team["hannah"].user_id,
    )


async def _cite(team: Cast, *, verified: bool = True) -> uuid.UUID:
    """A C4 citation on the engagement, verified by code (or not)."""
    return cast(
        uuid.UUID,
        await team.seed.value(
            "INSERT INTO citations (tenant_id, engagement_id, cited_from_type, cited_from_id, n, "
            "kind, source_type, source_id, locator, verified, verification_reason, "
            "verifier_version, created_by_kind, created_by_run_id) VALUES ($1, $2, "
            "'proposal_probe', $3, 1, 'record_field', 'tax_return', $3, "
            '\'{"record_type": "tax_return", "field": "line"}\', $4, $5, \'v1\', '
            "'agent', $3) RETURNING id",
            team.tenant,
            team.engagement,
            uuid.uuid4(),
            verified,
            None if verified else "value_mismatch",
        ),
    )


def _row(
    field: str, after: str | None, cites: tuple[uuid.UUID, ...], target: uuid.UUID
) -> ProposedRow:
    return ProposedRow(
        target_type=TARGET,
        target_id=target,
        field_key=field,
        label=f"Line {field}",
        before=None,
        after={"t": "decimal", "v": after} if after is not None else None,
        cause="schedule_k",
        citation_ids=cites,
    )


async def _k1(
    team: Cast, *, uncited: bool, policy: PolicyEval | None = None
) -> tuple[uuid.UUID, uuid.UUID]:
    """SHL-10 a's Feld K-1 treatment as four rows (and, with `uncited`, SHL-10 c's fifth)."""
    c1, c2, c3 = await _cite(team), await _cite(team), await _cite(team)
    target = uuid.uuid4()
    rows = [
        _row("sch_e.p2.28a_k", None, (c1,), target),
        _row("sch_e.p2.28a_h", "307900", (c1,), target),
        _row("f8995a.p1.l1", "307900", (c3,), target),
        _row("activity.ridgeline", "1", (c1, c2), target),
    ]
    if uncited:
        rows.append(_row("sch_a.5b", "18240", (), target))
    proposal = await create_proposal(
        await _agent(team),
        engagement_id=team.engagement,
        kind="field_change_set",
        title="K-1 treatment: Ridgeline",
        rows=rows,
        reasoning_ref="reasoning",
        policy=policy,
    )
    return proposal, target


async def _versions(team: Cast, target: uuid.UUID) -> list[tuple[object, ...]]:
    found = await team.seed.rows(
        "SELECT field_key, seq, value_source, cause, actor_kind, actor_id, "
        "citation_note_sealed IS NOT NULL FROM field_value_versions WHERE target_id = $1 "
        "ORDER BY field_key",
        target,
    )
    return [tuple(r) for r in found]


async def test_ac_the_unsupported_row_blocks_approval_until_it_is_cited_by_an_edit(
    team: Cast,
) -> None:
    proposal, target = await _k1(team, uncited=True)
    path = f"/v1/proposals/{proposal}"
    shown = await team.call("samuel")("GET", path)
    assert shown.status_code == 200, shown.text
    body = shown.json()
    assert body["state"] == "pending" and body["version"] == 1 and body["change_count"] == 5
    assert [r["unsupported"] for r in body["rows"]] == [False, False, False, False, True]
    assert body["reasoning"].startswith("Prior-year treatment")
    assert set(body["allowed_actions"]) == {
        "proposal.approve",
        "proposal.reject",
        "proposal.route",
        "proposal.follow_up",
    }

    refused = await team.call("samuel")("POST", f"{path}/approve", json={"seen_version": 1})
    assert refused.status_code == 422, refused.text
    assert refused.json()["detail"] == "uncited_change"
    assert refused.json()["facts"] == {"count": 1, "row": 5}
    assert await _versions(team, target) == []  # nothing written

    edited = await team.call("samuel")(
        "POST",
        f"{path}/approve",
        json={
            "seen_version": 1,
            "edits": [{"n": 5, "after": "18240", "citation_note": "Co-op statement, p. 2"}],
        },
    )
    assert edited.status_code == 200, edited.text
    out = edited.json()
    assert out["state"] == "approved_with_edits"
    assert out["decision"]["decision"] == "approved_with_edits"
    assert out["decision"]["decided_by_name"] == "Samuel Ito"
    assert out["allowed_actions"] == []
    samuel = str(team["samuel"].user_id)
    versions = await _versions(team, target)
    assert len(versions) == 5  # one field version per row
    by_field = {v[0]: v for v in versions}
    assert by_field["sch_a.5b"][2:] == ("human", "edit", "human", samuel, True)
    for field in ("sch_e.p2.28a_k", "sch_e.p2.28a_h", "f8995a.p1.l1", "activity.ridgeline"):
        assert by_field[field][2:] == (
            "agent_suggested",
            "suggestion_adopted",
            "human",
            samuel,
            False,
        )


async def test_ac_approval_records_proposal_approved_by_samuel_ito(team: Cast) -> None:
    proposal, target = await _k1(team, uncited=False)
    approved = await team.call("samuel")(
        "POST", f"/v1/proposals/{proposal}/approve", json={"seen_version": 1, "edits": []}
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["state"] == "approved"
    assert approved.json()["decision"]["decided_by_name"] == "Samuel Ito"
    audit = await team.seed.rows(
        "SELECT actor_kind, actor_id FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'proposal.approved' AND target_id = $2",
        team.tenant,
        str(proposal),
    )
    assert [tuple(a) for a in audit] == [("human", str(team["samuel"].user_id))]
    assert len(await _versions(team, target)) == 4
    statuses = await team.seed.rows(
        "SELECT status FROM suggestions WHERE proposal_id = $1", proposal
    )
    assert {s[0] for s in statuses} == {"adopted"}
    assert (
        await team.value(
            "SELECT count(*) FROM proposal_decisions WHERE proposal_id = $1", proposal
        )
        == 1
    )
    # A second approval, or one on the version before it, is a changed proposal.
    again = await team.call("hannah")(
        "POST", f"/v1/proposals/{proposal}/approve", json={"seen_version": 1}
    )
    assert again.status_code == 409 and again.json()["detail"] == "proposal_changed"


async def test_ac_a_citation_no_longer_verified_makes_its_row_unsupported(team: Cast) -> None:
    proposal, _ = await _k1(team, uncited=False)
    cited = await team.seed.rows(
        "SELECT citation_ids FROM proposal_rows WHERE proposal_id = $1 AND n = 3", proposal
    )
    citation = cast(list[uuid.UUID], cited[0][0])[0]
    await team.seed.run(
        "INSERT INTO citation_events (tenant_id, citation_id, kind, cause_ref, actor_kind) "
        "VALUES ($1, $2, 'broken', 'withdrawn:probe', 'system')",
        team.tenant,
        citation,
    )
    refused = await team.call("samuel")(
        "POST", f"/v1/proposals/{proposal}/approve", json={"seen_version": 1}
    )
    assert refused.status_code == 422 and refused.json()["facts"] == {"count": 1, "row": 3}


async def test_ac_reject_with_a_reason_dismisses_its_suggestions(team: Cast) -> None:
    proposal, target = await _k1(team, uncited=False)
    rejected = await team.call("samuel")(
        "POST",
        f"/v1/proposals/{proposal}/reject",
        json={"seen_version": 1, "reason_code": "needs_client_input"},
    )
    assert rejected.status_code == 200, rejected.text
    body = rejected.json()
    assert body["state"] == "rejected"
    assert body["decision"]["reason_code"] == "needs_client_input"
    assert body["decision"]["decided_by_name"] == "Samuel Ito"
    assert await _versions(team, target) == []
    statuses = await team.seed.rows(
        "SELECT status FROM suggestions WHERE proposal_id = $1", proposal
    )
    assert {s[0] for s in statuses} == {"dismissed"}
    other = await team.call("samuel")(
        "POST",
        f"/v1/proposals/{proposal}/reject",
        json={"seen_version": 2, "reason_code": "other"},
    )
    assert other.status_code == 422  # `other` needs a note


async def test_ac_over_threshold_routes_to_a_named_approver(team: Cast) -> None:
    policy = PolicyEval(
        policy_id=uuid.uuid4(),
        policy_name="BH AJE thresholds v2",
        version=2,
        result="review_required",
        routed_to_user_id=team["priya"].user_id,
        note_ref="policy_note",
    )
    proposal, _ = await _k1(team, uncited=False, policy=policy)
    path = f"/v1/proposals/{proposal}"
    shown = (await team.call("raj")("GET", path)).json()
    assert shown["policy"]["policy_name"] == "BH AJE thresholds v2"
    assert shown["policy"]["routed_to_name"] == "Priya Raman"
    assert shown["policy"]["note"] == "Return proposals need a Tax Reviewer."
    assert "proposal.approve" not in shown["allowed_actions"]
    refused = await team.call("raj")("POST", f"{path}/approve", json={"seen_version": 1})
    assert refused.status_code == 403, refused.text
    assert refused.json()["facts"] == {"routed_to": str(team["priya"].user_id)}
    # The agent's routing told Priya (agent-originated); Raj sends it on to Margaret.
    routed = await team.call("raj")(
        "POST",
        f"{path}/route",
        json={"seen_version": 1, "approver_user_id": str(team["margaret"].user_id)},
    )
    assert routed.status_code == 200, routed.text
    assert routed.json()["version"] == 2 and routed.json()["state"] == "pending"
    assert routed.json()["decision"]["decision"] == "routed"
    events = await team.seed.rows(
        "SELECT payload->>'approver_user_id', payload->>'by_user' FROM outbox "
        "WHERE tenant_id = $1 AND event_type = 'proposal.routed' ORDER BY seq",
        team.tenant,
    )
    assert [tuple(e) for e in events] == [
        (str(team["priya"].user_id), None),
        (str(team["margaret"].user_id), str(team["raj"].user_id)),
    ]
    priya = await team.call("priya")("POST", f"{path}/approve", json={"seen_version": 2})
    assert priya.status_code == 403
    margaret = await team.call("margaret")("POST", f"{path}/approve", json={"seen_version": 2})
    assert margaret.status_code == 200, margaret.text
    assert margaret.json()["decision"]["decided_by_name"] == "Margaret Okonkwo"
    # Routing to yourself, or to someone who may not approve, is refused.
    other, _ = await _k1(team, uncited=False)
    self_route = await team.call("raj")(
        "POST",
        f"/v1/proposals/{other}/route",
        json={"seen_version": 1, "approver_user_id": str(team["raj"].user_id)},
    )
    assert self_route.status_code == 422


async def test_ac_ask_follow_up_records_a_sealed_note_and_leaves_it_pending(team: Cast) -> None:
    proposal, _ = await _k1(team, uncited=True)
    asked = await team.call("ana")(
        "POST",
        f"/v1/proposals/{proposal}/follow-up",
        json={"text": "Which statement supports the co-op share?"},
    )
    assert asked.status_code == 200, asked.text
    body = asked.json()
    assert body["state"] == "pending" and body["version"] == 1
    assert body["decision"]["decision"] == "follow_up"
    assert body["decision"]["note"] == "Which statement supports the co-op share?"
    sealed = await team.value(
        "SELECT note_sealed FROM proposal_decisions WHERE proposal_id = $1", proposal
    )
    assert b"co-op share" not in cast(bytes, sealed)


async def test_ac_no_owner_to_write_answers_503_and_writes_nothing(team: Cast) -> None:
    c1 = await _cite(team)
    proposal = await create_proposal(
        await _agent(team),
        engagement_id=team.engagement,
        kind="field_change_set",
        title="Unowned",
        rows=[
            ProposedRow(
                UNOWNED, uuid.uuid4(), "f1", "Field", None, {"t": "text", "v": "x"}, "k", (c1,)
            )
        ],
    )
    refused = await team.call("samuel")(
        "POST", f"/v1/proposals/{proposal}/approve", json={"seen_version": 1}
    )
    assert refused.status_code == 503
    assert await team.value("SELECT state FROM proposals WHERE id = $1", proposal) == "pending"
    assert (
        await team.value(
            "SELECT count(*) FROM proposal_decisions WHERE proposal_id = $1", proposal
        )
        == 0
    )


async def test_ac_suggestions_adopt_edit_and_dismiss(team: Cast) -> None:
    agent = await _agent(team)
    target = uuid.uuid4()

    async def suggest(cites: tuple[uuid.UUID, ...]) -> uuid.UUID:
        return await create_suggestion(
            agent,
            engagement_id=team.engagement,
            target_type=TARGET,
            target_id=target,
            field_key="f1040.l2a",
            proposed_value={"t": "decimal", "v": "1550"},
            citation_ids=cites,
        )

    cited = await suggest((await _cite(team),))
    adopted = await team.call("hannah")(
        "POST", f"/v1/suggestions/{cited}/adopt", json={"seen_version": 1}
    )
    assert adopted.status_code == 200, adopted.text
    assert adopted.json()["status"] == "adopted" and adopted.json()["decision"] == "adopted"
    again = await team.call("hannah")(
        "POST", f"/v1/suggestions/{cited}/adopt", json={"seen_version": 1}
    )
    assert again.status_code == 409 and again.json()["detail"] == "suggestion_changed"

    uncited = await suggest((await _cite(team, verified=False),))
    refused = await team.call("hannah")(
        "POST", f"/v1/suggestions/{uncited}/adopt", json={"seen_version": 1}
    )
    assert refused.status_code == 422 and refused.json()["detail"] == "uncited_change"
    no_note = await team.call("hannah")(
        "POST",
        f"/v1/suggestions/{uncited}/adopt",
        json={"seen_version": 1, "edited_value": "1600"},
    )
    assert no_note.status_code == 422
    edited = await team.call("hannah")(
        "POST",
        f"/v1/suggestions/{uncited}/adopt",
        json={"seen_version": 1, "edited_value": "1600", "citation_note": "K-1 box 18A"},
    )
    assert edited.status_code == 200 and edited.json()["status"] == "edited"

    dismissed_id = await suggest(())
    dismissed = await team.call("hannah")(
        "POST",
        f"/v1/suggestions/{dismissed_id}/dismiss",
        json={"seen_version": 1, "reason_code": "wrong_treatment"},
    )
    assert dismissed.status_code == 200 and dismissed.json()["status"] == "dismissed"
    versions = await _versions(team, target)
    assert [(v[1], v[2], v[3]) for v in versions] == [
        (1, "agent_suggested", "suggestion_adopted"),
        (2, "human", "edit"),
    ]


async def test_ac_agents_and_the_platform_never_decide(team: Cast) -> None:
    """INV-1 at the service, the route and the data layer."""
    proposal, _ = await _k1(team, uncited=False)
    agent = await _agent(team)
    with pytest.raises(Forbidden):
        await approve_proposal(agent, proposal, seen_version=1, edits=[])
    system = AuthContext(
        TenantContext(team.tenant, "system", "probe"), uuid.uuid4(), uuid.uuid4(), None, None
    )
    with pytest.raises(Forbidden):
        await reject_proposal(system, proposal, seen_version=1, reason_code="other", note="x")
    assert (
        await team.call("thomas")(
            "POST", f"/v1/proposals/{proposal}/approve", json={"seen_version": 1}
        )
    ).status_code == 403
    # 0230: the app may not move the state without the person's decision row, and an agent may
    # not move it at all.
    actors = (
        TenantContext(team.tenant, "agent", f"agent:evidence.screener:{agent.agent_run_id}"),
        TenantContext(team.tenant, "human", str(team["hannah"].user_id)),
    )
    for actor in actors:
        with pytest.raises(DBAPIError):
            async with tenant_connection(actor) as conn:
                await conn.execute(
                    text("UPDATE proposals SET state = 'approved' WHERE id = :id"),
                    {"id": proposal},
                )
    assert await team.value("SELECT state FROM proposals WHERE id = $1", proposal) == "pending"
