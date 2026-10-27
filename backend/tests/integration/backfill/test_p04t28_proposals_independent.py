# ac-test-author: ayushkbhatia
"""SPEC-360 AC-4, AC-5 (P-04-T24, T25; TASK-1464): proposals, suggestions and the typed adapters.

What the contract promises (`docs/contracts/review-grammar.md` part 2, "Live (P-04-T24, T25)",
§5, §6; ADR-005, ADR-161; DEC-600 to DEC-604, DEC-607, DEC-608):
- a proposal with one unsupported row cannot be approved until that row is cited by an edit, and
  approval records "Proposal approved by Samuel Ito" with one field version per row;
- citations are re-verified at approval (C4: verified on this engagement now), and an approved
  value never carries a citation that did not verify;
- reject takes a reason code, route names another approver, a follow-up changes nothing else;
  409 `proposal_changed` (also a replayed approval), 422 `uncited_change`, 503 with no owner;
- the threshold the policy evaluated holds: the viewer above it is refused (403 `{routed_to}`),
  also with edits, and cannot route it to themself or around the named approver;
- the agent and the platform never decide, at the matrix, the service API and the data layer
  (INV-1);
- walls, need to know, offshore (DEC-319: not a wall) and other firms (404, DEC-43);
- typed adapters: AUD-03's paths, shadow runs and shadow-stage firms see no proposal (DEC-608), a
  shadow run never supersedes a live proposal, an inbox-match rejection persists.

Boundary: `create_app()` over HTTP as each signed-in person; the agent's rows through
`agents.api.create_proposal` and `create_suggestion` on a recorded run, or seeded as the
specialists write them; outcomes read through the routes and SQL.
"""

from __future__ import annotations

import hashlib
import uuid
from decimal import Decimal
from typing import Final, cast

import pytest
from sqlalchemy import text

from abacus.kernel.db import TenantContext
from abacus.kernel.uow import Target, UnitOfWork, uow
from abacus.modules.agents import api as agents_api
from abacus.modules.agents.api import (
    AdoptedValue,
    ApprovedChangeSet,
    ProposedRow,
    ProposedValue,
    ThresholdEvaluation,
    ThresholdPolicy,
    create_proposal,
    create_suggestion,
    register_change_set_applier,
    register_suggestion_applier,
    register_threshold_policy,
)
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    authorise,
    system_context_for_run,
)
from abacus.modules.review.api import record_value

from .p04t28_support import (
    PROBE,
    PROBED,
    RETURN,
    UNOWNED,
    World,
    agent,
    audit_rows,
    cite,
    deliver,
    make_world,
    notified,
    own,
    probe,
    second_site,
)
from .support import Net, Site

pytestmark = pytest.mark.asyncio
PROPOSALS: Final = "/v1/proposals"
SUGGESTIONS: Final = "/v1/suggestions"
LINE_2A: Final = "f1040.l2a"  # Form 1040 line 2a, tax-exempt interest


WRITTEN: list[AdoptedValue] = []


async def _probe_owner(_tx: UnitOfWork, _ctx: AuthContext, value: AdoptedValue) -> None:
    """A reviewable's owner that only records what it was asked to write."""
    WRITTEN.append(value)


async def _probe_engagement(_tenant: TenantContext, target_id: uuid.UUID) -> uuid.UUID | None:
    facts = PROBED.get(target_id)
    return facts.engagement_id if facts is not None else None


register_suggestion_applier(PROBE, _probe_owner, engagement_of=_probe_engagement)

# --- A threshold policy on the server (security review M2): AJE-05 (SHL-10 d) -------------------
# The firm's policy, computed by code: an adjusting entry above 10,000.00 needs Priya Raman.
# Literals from the contract: 12,600.00 + 1,480.00 + 820.00 = 14,900.00.
AJE: Final = "indep_aje"
LIMIT: Final = Decimal("10000.00")
APPROVER: dict[uuid.UUID, uuid.UUID] = {}  # firm -> the policy-named approver
COVERED: set[uuid.UUID] = set()  # people whose own limit covers anything


async def _evaluate(
    tenant: TenantContext, _engagement: uuid.UUID, _kind: str, values: tuple[ProposedValue, ...]
) -> ThresholdEvaluation | None:
    total = sum((Decimal(str(v.after["v"])) for v in values if v.after is not None), Decimal("0"))
    over = total > LIMIT
    return ThresholdEvaluation(
        policy_id=uuid.UUID(int=0x0428),
        policy_name="BH AJE thresholds v2",
        version=2,
        result="review_required" if over else "within_threshold",
        approver_user_id=APPROVER.get(tenant.tenant_id) if over else None,
    )


async def _covers(
    _tenant: TenantContext,
    _engagement: uuid.UUID,
    person: uuid.UUID,
    evaluation: ThresholdEvaluation,
) -> bool:
    return evaluation.result == "within_threshold" or person in COVERED


async def _post_entry(tx: UnitOfWork, _ctx: AuthContext, change: ApprovedChangeSet) -> None:
    """The ledger's applier for an approved entry: each value's history through review."""
    for value in change.values:
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


register_threshold_policy(ThresholdPolicy(AJE, _evaluate, _covers))
register_change_set_applier(AJE, _post_entry)


@pytest.fixture
async def world(net: Net) -> World:
    return await make_world(net)


# --- Helpers ----------------------------------------------------------------------------------


def _row(
    target: uuid.UUID,
    field: str,
    after: str | None,
    cites: tuple[uuid.UUID, ...],
    *,
    target_type: str = RETURN,
) -> ProposedRow:
    return ProposedRow(
        target_type=target_type,
        target_id=target,
        field_key=field,
        label=f"Line {field}",
        before=None,
        after={"t": "decimal", "v": after} if after is not None else None,
        cause="schedule_k",
        citation_ids=cites,
    )


async def _k1(
    world: World,
    *,
    uncited: bool = False,
    shadow: bool = False,
    target: uuid.UUID | None = None,
) -> tuple[uuid.UUID, uuid.UUID]:
    """SHL-10 a: the Feld K-1 treatment, four cited rows (and SHL-10 c's uncited fifth)."""
    c1, c2, c3 = await cite(world), await cite(world), await cite(world)
    target = target or own(world.site)
    rows = [
        _row(target, "activity.ridgeline", "1", (c1, c2)),
        _row(target, "sch_e.p2.28a_k", None, (c1,)),
        _row(target, "sch_e.p2.28a_h", "307900", (c1,)),
        _row(target, "f8995a.p1.l1.ridgeline", "307900", (c3,)),
    ]
    if uncited:
        rows.append(_row(target, "sch_a.l5b", "18240", ()))
    proposal = await create_proposal(
        await agent(world, shadow=shadow),
        engagement_id=world.site.engagement_id,
        kind="field_change_set",
        title="K-1 treatment: Ridgeline",
        rows=rows,
        reasoning_ref="reasoning",
    )
    return proposal, target


async def _aje(
    world: World,
    amounts: tuple[str, ...] = ("12600.00", "1480.00", "820.00"),
    *,
    uncited: bool = False,
) -> tuple[uuid.UUID, uuid.UUID]:
    """AJE-05 as an adjusting-entry proposal; the server evaluates its threshold."""
    APPROVER[world.tenant_id] = world["priya"].user_id
    COVERED.add(world["priya"].user_id)
    target = own(world.site)
    rows = [
        _row(target, f"aje05.line{n}", amount, (await cite(world),))
        for n, amount in enumerate(amounts, start=1)
    ]
    if uncited:
        rows.append(_row(target, f"aje05.line{len(amounts) + 1}", "0.00", ()))
    proposal = await create_proposal(
        await agent(world),
        engagement_id=world.site.engagement_id,
        kind=AJE,
        title="AJE-05 · Copperleaf",
        rows=rows,
        reasoning_ref="reasoning",
    )
    return proposal, target


async def _versions(world: World, target: uuid.UUID) -> list[tuple[object, ...]]:
    rows = await world.seed.rows(
        "SELECT field_key, value_source, cause, actor_kind, actor_id, citation_ids, "
        "citation_note_sealed IS NOT NULL FROM field_value_versions WHERE tenant_id = $1 "
        "AND target_id = $2 ORDER BY field_key",
        world.tenant_id,
        target,
    )
    return [tuple(r.values()) for r in rows]


async def _state(world: World, proposal: uuid.UUID) -> tuple[str, int]:
    row = (await world.seed.rows("SELECT state, version FROM proposals WHERE id = $1", proposal))[
        0
    ]
    return str(row["state"]), int(row["version"])


async def _decisions(world: World, proposal: uuid.UUID) -> list[str]:
    rows = await world.seed.rows(
        "SELECT decision FROM proposal_decisions WHERE proposal_id = $1", proposal
    )
    return sorted(str(r["decision"]) for r in rows)


async def _nothing_decided(world: World, proposal: uuid.UUID, target: uuid.UUID) -> None:
    assert (await _state(world, proposal))[0] == "pending"
    assert await _decisions(world, proposal) == []
    assert await _versions(world, target) == []


# --- AC-4: the unsupported row, and approval ---------------------------------------------------


async def test_ac4_an_unsupported_row_blocks_approval_until_an_edit_cites_it(
    world: World,
) -> None:
    proposal, target = await _k1(world, uncited=True)
    path = f"{PROPOSALS}/{proposal}"
    shown = await world.call("GET", path, "samuel")
    assert shown.status_code == 200, shown.text
    body = shown.json()
    assert body["state"] == "pending" and body["version"] == 1 and body["change_count"] == 5
    assert [r["n"] for r in body["rows"]] == [1, 2, 3, 4, 5]
    assert [r["unsupported"] for r in body["rows"]] == [False, False, False, False, True]

    refused = await world.call("POST", f"{path}/approve", "samuel", {"seen_version": 1})
    assert refused.status_code == 422, refused.text
    assert refused.json() == {"detail": "uncited_change", "facts": {"count": 1, "row": 5}}
    await _nothing_decided(world, proposal, target)

    # An edit without a citation note fails the schema; on an unknown row it is invalid.
    no_note = await world.call(
        "POST", f"{path}/approve", "samuel", {"seen_version": 1, "edits": [{"n": 5, "after": "1"}]}
    )
    assert no_note.status_code == 422
    unknown = await world.call(
        "POST",
        f"{path}/approve",
        "samuel",
        {"seen_version": 1, "edits": [{"n": 9, "after": "1", "citation_note": "Statement"}]},
    )
    assert unknown.status_code == 422 and unknown.json()["detail"] == "proposal_invalid"
    await _nothing_decided(world, proposal, target)

    edited = await world.call(
        "POST",
        f"{path}/approve",
        "samuel",
        {
            "seen_version": 1,
            "edits": [{"n": 5, "after": "18240", "citation_note": "Co-op statement, p. 2"}],
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["state"] == "approved_with_edits"
    assert edited.json()["decision"]["decision"] == "approved_with_edits"
    versions = await _versions(world, target)
    assert len(versions) == 5  # one field version per row
    by_field = {v[0]: v for v in versions}
    assert by_field["sch_a.l5b"][1:3] == ("human", "edit")
    assert by_field["sch_a.l5b"][6] is True  # the person's citation note, sealed
    for field in ("activity.ridgeline", "sch_e.p2.28a_k", "sch_e.p2.28a_h"):
        assert by_field[field][1:3] == ("agent_suggested", "suggestion_adopted")
    assert {v[3] for v in versions} == {"human"}
    assert {v[4] for v in versions} == {str(world["samuel"].user_id)}


async def test_ac4_approval_records_proposal_approved_by_samuel_ito_one_version_per_row(
    world: World,
) -> None:
    proposal, target = await _k1(world)
    approved = await world.call(
        "POST", f"{PROPOSALS}/{proposal}/approve", "samuel", {"seen_version": 1, "edits": []}
    )
    assert approved.status_code == 200, approved.text
    body = approved.json()
    assert body["state"] == "approved"
    assert body["decision"]["decision"] == "approved"
    assert body["decision"]["decided_by_name"] == "Samuel Ito"
    assert body["decision"]["decided_by_user_id"] == str(world["samuel"].user_id)
    versions = await _versions(world, target)
    assert [v[0] for v in versions] == [
        "activity.ridgeline",
        "f8995a.p1.l1.ridgeline",
        "sch_e.p2.28a_h",
        "sch_e.p2.28a_k",
    ]
    assert {v[1:5] for v in versions} == {
        ("agent_suggested", "suggestion_adopted", "human", str(world["samuel"].user_id))
    }
    assert await audit_rows(world, "proposal.approved") == [
        ("human", str(world["samuel"].user_id))
    ]
    decided = await world.seed.value(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 AND event_type = 'proposal.decided'",
        world.tenant_id,
    )
    assert decided == 1
    # Every row's suggestion is adopted with the proposal.
    statuses = await world.seed.rows(
        "SELECT DISTINCT status FROM suggestions WHERE proposal_id = $1", proposal
    )
    assert [r["status"] for r in statuses] == ["adopted"]


# --- Citation re-checks ------------------------------------------------------------------------


async def test_ac4_a_citation_that_stops_verifying_is_rechecked_at_approval(world: World) -> None:
    cited = await cite(world)
    target = own(world.site)
    proposal = await create_proposal(
        await agent(world),
        engagement_id=world.site.engagement_id,
        kind="field_change_set",
        title="Interest income",
        rows=[_row(target, "sch_b.p1.l1.halvard", "2310", (cited,))],
    )
    path = f"{PROPOSALS}/{proposal}"
    assert (await world.call("GET", path, "samuel")).json()["rows"][0]["unsupported"] is False
    # The verifier withdraws the citation after the agent proposed (C4: verified now).
    await world.seed.run_untriggered(
        "UPDATE citations SET verified = false, verification_reason = 'value_mismatch' "
        "WHERE id = $1",
        cited,
    )
    assert (await world.call("GET", path, "samuel")).json()["rows"][0]["unsupported"] is True
    refused = await world.call("POST", f"{path}/approve", "samuel", {"seen_version": 1})
    assert refused.status_code == 422, refused.text
    assert refused.json() == {"detail": "uncited_change", "facts": {"count": 1, "row": 1}}
    await _nothing_decided(world, proposal, target)


async def test_ac4_a_citation_on_another_engagement_never_supports_a_row(world: World) -> None:
    other = await second_site(world, "Copperleaf")
    foreign = await cite(world, site=other)
    target = own(world.site)
    proposal = await create_proposal(
        await agent(world),
        engagement_id=world.site.engagement_id,
        kind="field_change_set",
        title="Interest income",
        rows=[_row(target, "sch_b.p1.l1.halvard", "2310", (foreign,))],
    )
    shown = (await world.call("GET", f"{PROPOSALS}/{proposal}", "samuel")).json()
    assert shown["rows"][0]["unsupported"] is True
    refused = await world.call(
        "POST", f"{PROPOSALS}/{proposal}/approve", "samuel", {"seen_version": 1}
    )
    assert refused.status_code == 422 and refused.json()["detail"] == "uncited_change"
    await _nothing_decided(world, proposal, target)


async def test_ac4_an_edited_row_keeps_no_citation_that_did_not_verify(world: World) -> None:
    """Security review: uncited ids are dropped before the field is written. The person's
    citation note stands in for the agent's claim; the unverified id is not the value's source."""
    bad = await cite(world, verified=False)
    good = await cite(world)
    target = own(world.site)
    proposal = await create_proposal(
        await agent(world),
        engagement_id=world.site.engagement_id,
        kind="field_change_set",
        title="Real estate taxes",
        rows=[
            _row(target, "sch_a.l5b", "18240", (bad,)),
            _row(target, "sch_e.p2.28a_h", "307900", (good,)),
        ],
    )
    approved = await world.call(
        "POST",
        f"{PROPOSALS}/{proposal}/approve",
        "samuel",
        {
            "seen_version": 1,
            "edits": [{"n": 1, "after": "18240", "citation_note": "Co-op statement, p. 2"}],
        },
    )
    assert approved.status_code == 200, approved.text
    by_field = {v[0]: v for v in await _versions(world, target)}
    assert bad not in cast(list[uuid.UUID], by_field["sch_a.l5b"][5])
    assert list(cast(list[uuid.UUID], by_field["sch_e.p2.28a_h"][5])) == [good]


# --- Staleness and replays ---------------------------------------------------------------------


async def test_ac4_a_stale_version_and_a_replayed_approval_answer_proposal_changed(
    world: World,
) -> None:
    proposal, target = await _k1(world)
    path = f"{PROPOSALS}/{proposal}/approve"
    stale = await world.call("POST", path, "samuel", {"seen_version": 2})
    assert stale.status_code == 409, stale.text
    assert stale.json() == {"detail": "proposal_changed", "facts": {"version": 1}}
    await _nothing_decided(world, proposal, target)

    assert (await world.call("POST", path, "samuel", {"seen_version": 1})).status_code == 200
    _, version = await _state(world, proposal)
    assert version > 1  # every decision moves the version (DEC-607)
    for who in ("samuel", "priya"):  # a replay, and a second person on the same screen
        again = await world.call("POST", path, who, {"seen_version": 1})
        assert again.status_code == 409, again.text
        assert again.json() == {"detail": "proposal_changed", "facts": {"version": version}}
    rejected = await world.call(
        "POST",
        f"{PROPOSALS}/{proposal}/reject",
        "priya",
        {"seen_version": 1, "reason_code": "wrong_treatment"},
    )
    assert rejected.status_code == 409 and rejected.json()["detail"] == "proposal_changed"
    assert await _decisions(world, proposal) == ["approved"]
    assert len(await _versions(world, target)) == 4  # written once
    assert len(await audit_rows(world, "proposal.approved")) == 1


# --- Reject, follow-up, no owner ---------------------------------------------------------------


async def test_ac4_reject_takes_a_reason_code_and_writes_no_field(world: World) -> None:
    proposal, target = await _k1(world)
    path = f"{PROPOSALS}/{proposal}/reject"
    other = await world.call("POST", path, "samuel", {"seen_version": 1, "reason_code": "other"})
    assert other.status_code == 422 and other.json()["detail"] == "proposal_invalid"
    unknown = await world.call("POST", path, "samuel", {"seen_version": 1, "reason_code": "meh"})
    assert unknown.status_code == 422
    await _nothing_decided(world, proposal, target)

    rejected = await world.call(
        "POST", path, "samuel", {"seen_version": 1, "reason_code": "needs_client_input"}
    )
    assert rejected.status_code == 200, rejected.text
    body = rejected.json()
    assert body["state"] == "rejected"
    assert body["decision"]["reason_code"] == "needs_client_input"
    assert body["decision"]["decided_by_name"] == "Samuel Ito"
    assert await _versions(world, target) == []
    statuses = await world.seed.rows(
        "SELECT DISTINCT status FROM suggestions WHERE proposal_id = $1", proposal
    )
    assert [r["status"] for r in statuses] == ["dismissed"]
    assert await audit_rows(world, "proposal.rejected") == [
        ("human", str(world["samuel"].user_id))
    ]


async def test_ac4_a_follow_up_is_recorded_sealed_and_changes_nothing_else(world: World) -> None:
    proposal, target = await _k1(world)
    marker = f"Check the final K-1 {uuid.uuid4().hex[:8]}"
    key = {"Idempotency-Key": str(uuid.uuid4())}
    path = f"{PROPOSALS}/{proposal}/follow-up"
    recorded = await world.call_with("POST", path, "ana", {"text": marker}, key)
    assert recorded.status_code in (200, 201), recorded.text
    retried = await world.call_with("POST", path, "ana", {"text": marker}, key)
    assert retried.status_code == recorded.status_code  # a retry records nothing again
    reused = await world.call_with("POST", path, "ana", {"text": "Another question"}, key)
    assert reused.status_code == 422 and reused.json()["detail"] == "idempotency_key_reused"
    assert await _state(world, proposal) == ("pending", 1)
    assert await _versions(world, target) == []
    assert await audit_rows(world, "proposal.follow_up_recorded") == [
        ("human", str(world["ana"].user_id))
    ]
    plain = await world.seed.value(
        "SELECT count(*) FROM proposal_decisions d WHERE d.proposal_id = $1 "
        "AND row_to_json(d)::text LIKE '%' || $2 || '%'",
        proposal,
        marker,
    )
    assert plain == 0  # the note is sealed


async def test_ac4_no_owner_to_write_a_row_answers_503_and_writes_nothing(world: World) -> None:
    target = own(world.site)
    proposal = await create_proposal(
        await agent(world),
        engagement_id=world.site.engagement_id,
        kind="field_change_set",
        title="Unowned field",
        rows=[_row(target, "line.one", "100", (await cite(world),), target_type=UNOWNED)],
    )
    refused = await world.call(
        "POST", f"{PROPOSALS}/{proposal}/approve", "samuel", {"seen_version": 1}
    )
    assert refused.status_code == 503, refused.text
    await _nothing_decided(world, proposal, target)


@pytest.mark.xfail(
    strict=True,
    reason="ED-170: 503 answers 'service unavailable', not the contract's fixed code "
    "'service_unavailable' (review-grammar.md §6 part 2); recorded in "
    "work/tasks/TASK-1464-p04t28-independent-ac-tests.md (TASK-1464)",
)
async def test_ac4_no_owner_answers_the_fixed_code_service_unavailable(world: World) -> None:
    proposal = await create_proposal(
        await agent(world),
        engagement_id=world.site.engagement_id,
        kind="field_change_set",
        title="Unowned field",
        rows=[_row(own(world.site), "line.one", "100", (await cite(world),), target_type=UNOWNED)],
    )
    refused = await world.call(
        "POST", f"{PROPOSALS}/{proposal}/approve", "samuel", {"seen_version": 1}
    )
    assert refused.json() == {"detail": "service_unavailable"}


# --- The threshold: self-approval and routing around it ---------------------------------------


async def test_ac4_the_viewer_above_the_threshold_is_refused_also_with_edits(
    world: World,
) -> None:
    proposal, target = await _aje(world, uncited=True)
    path = f"{PROPOSALS}/{proposal}"
    shown = (await world.call("GET", path, "raj")).json()
    assert shown["policy"]["routed_to_name"] == "Priya Raman"
    assert shown["policy"]["routed_to_user_id"] == str(world["priya"].user_id)
    assert "proposal.approve" not in shown["allowed_actions"]
    forbidden = {"detail": "forbidden", "facts": {"routed_to": str(world["priya"].user_id)}}

    plain = await world.call("POST", f"{path}/approve", "raj", {"seen_version": 1})
    assert plain.status_code == 403 and plain.json() == forbidden
    edits = {
        "seen_version": 1,
        "edits": [{"n": 4, "after": "0.00", "citation_note": "Reclass, no amount"}],
    }
    with_edits = await world.call("POST", f"{path}/approve", "raj", edits)
    assert with_edits.status_code == 403, with_edits.text
    assert with_edits.json() == forbidden
    await _nothing_decided(world, proposal, target)

    # The run's preparer (Hannah directed the agent) never approves it, even if her own limit
    # would cover it, and nobody routes it to her (self-approval).
    COVERED.add(world["hannah"].user_id)
    by_preparer = await world.call("POST", f"{path}/approve", "hannah", edits)
    assert by_preparer.status_code == 403, by_preparer.text
    to_preparer = await world.call(
        "POST",
        f"{path}/route",
        "raj",
        {"seen_version": 1, "approver_user_id": str(world["hannah"].user_id)},
    )
    assert to_preparer.status_code == 422, to_preparer.text
    await _nothing_decided(world, proposal, target)

    by_priya = await world.call("POST", f"{path}/approve", "priya", edits)
    assert by_priya.status_code == 200, by_priya.text
    assert by_priya.json()["decision"]["decided_by_name"] == "Priya Raman"
    assert len(await _versions(world, target)) == 4


async def test_ac4_the_threshold_is_the_servers_and_is_rechecked_on_approve_with_edits(
    world: World,
) -> None:
    """Security review M2: the agent never states the policy, and an edit that takes the entry
    above the viewer's limit is weighed again before anything is written."""
    within, within_target = await _aje(world, ("820.00",))
    shown = (await world.call("GET", f"{PROPOSALS}/{within}", "raj")).json()
    assert shown["policy"]["result"] == "within_threshold"
    assert shown["policy"]["routed_to_user_id"] is None
    assert "proposal.approve" in shown["allowed_actions"]
    raised = await world.call(
        "POST",
        f"{PROPOSALS}/{within}/approve",
        "raj",
        {
            "seen_version": 1,
            "edits": [{"n": 1, "after": "14900.00", "citation_note": "AJE-05 support, p. 3"}],
        },
    )
    assert raised.status_code == 403, raised.text
    assert raised.json() == {
        "detail": "forbidden",
        "facts": {"routed_to": str(world["priya"].user_id)},
    }
    await _nothing_decided(world, within, within_target)
    plain = await world.call("POST", f"{PROPOSALS}/{within}/approve", "raj", {"seen_version": 1})
    assert plain.status_code == 200, plain.text  # inside Raj's limit as proposed


async def test_ac4_routing_to_oneself_or_to_someone_who_cannot_approve_is_invalid(
    world: World,
) -> None:
    proposal, target = await _aje(world)
    path = f"{PROPOSALS}/{proposal}/route"
    for who, approver in (("raj", "raj"), ("raj", "kevin")):
        refused = await world.call(
            "POST",
            path,
            who,
            {"seen_version": 1, "approver_user_id": str(world[approver].user_id)},
        )
        assert refused.status_code == 422, (approver, refused.text)
        assert refused.json()["detail"] == "proposal_invalid"
    stranger = await world.call(
        "POST", path, "raj", {"seen_version": 1, "approver_user_id": str(uuid.uuid4())}
    )
    assert stranger.status_code == 422
    staff = await world.call(
        "POST", path, "lena", {"seen_version": 1, "approver_user_id": str(world["priya"].user_id)}
    )
    assert staff.status_code == 403  # proposal.route holds no staff cell
    await _nothing_decided(world, proposal, target)


async def test_ac4_routing_around_the_policy_named_approver_is_refused(world: World) -> None:
    """Security review: Raj, above the threshold, may not hand the proposal to another senior
    below it; nor, once routed to Priya, may it come back to Raj."""
    proposal, target = await _aje(world)
    path = f"{PROPOSALS}/{proposal}"
    around = await world.call(
        "POST",
        f"{path}/route",
        "raj",
        {"seen_version": 1, "approver_user_id": str(world["samuel"].user_id)},
    )
    if around.status_code == 200:
        version = around.json()["version"]
        by_samuel = await world.call(
            "POST", f"{path}/approve", "samuel", {"seen_version": version}
        )
        assert by_samuel.status_code == 403, by_samuel.text
    else:
        assert around.status_code in (403, 422), around.text
    assert await _decisions(world, proposal) in ([], ["routed"])
    assert await _versions(world, target) == []

    fresh, fresh_target = await _aje(world)
    fresh_path = f"{PROPOSALS}/{fresh}"
    to_priya = await world.call(
        "POST",
        f"{fresh_path}/route",
        "raj",
        {"seen_version": 1, "approver_user_id": str(world["priya"].user_id)},
    )
    assert to_priya.status_code == 200, to_priya.text
    assert to_priya.json()["state"] == "pending"
    version = to_priya.json()["version"]
    assert version > 1
    back = await world.call(
        "POST",
        f"{fresh_path}/route",
        "priya",
        {"seen_version": version, "approver_user_id": str(world["raj"].user_id)},
    )
    if back.status_code == 200:
        again = back.json()["version"]
        by_raj = await world.call("POST", f"{fresh_path}/approve", "raj", {"seen_version": again})
        assert by_raj.status_code == 403, by_raj.text
    else:
        assert back.status_code in (403, 422), back.text
    assert await _versions(world, fresh_target) == []


async def test_ac6_a_routed_proposal_tells_the_named_approver_once_never_the_router(
    world: World,
) -> None:
    proposal, _ = await _k1(world)
    routed = await world.call(
        "POST",
        f"{PROPOSALS}/{proposal}/route",
        "raj",
        {"seen_version": 1, "approver_user_id": str(world["priya"].user_id)},
    )
    assert routed.status_code == 200, routed.text
    assert await audit_rows(world, "proposal.routed") == [("human", str(world["raj"].user_id))]
    assert await deliver(world, "proposal.routed") == 1
    assert await notified(world, "proposal_routed") == [world["priya"].user_id]


# --- Suggestions -------------------------------------------------------------------------------


async def _suggestion(world: World, *, cited: bool = True) -> tuple[uuid.UUID, uuid.UUID]:
    target = own(world.site)
    cites = (await cite(world),) if cited else ()
    found = await create_suggestion(
        await agent(world),
        engagement_id=world.site.engagement_id,
        target_type=RETURN,
        target_id=target,
        field_key=LINE_2A,
        proposed_value={"t": "decimal", "v": "1550"},
        citation_ids=cites,
    )
    return found, target


async def test_ac4_a_suggestion_is_adopted_as_proposed_once(world: World) -> None:
    suggestion, target = await _suggestion(world)
    path = f"{SUGGESTIONS}/{suggestion}/adopt"
    staff = await world.call("POST", path, "ana", {"seen_version": 1})
    assert staff.status_code == 403  # suggestion.resolve holds no staff cell
    adopted = await world.call("POST", path, "samuel", {"seen_version": 1})
    assert adopted.status_code == 200, adopted.text
    assert adopted.json()["status"] == "adopted" and adopted.json()["decision"] == "adopted"
    assert adopted.json()["decided_by_user_id"] == str(world["samuel"].user_id)
    again = await world.call("POST", path, "samuel", {"seen_version": 1})
    assert again.status_code == 409 and again.json()["detail"] == "suggestion_changed"
    versions = await _versions(world, target)
    assert [v[:4] for v in versions] == [
        (LINE_2A, "agent_suggested", "suggestion_adopted", "human")
    ]
    assert await audit_rows(world, "suggestion.adopted") == [
        ("human", str(world["samuel"].user_id))
    ]


async def test_ac4_an_uncited_suggestion_is_adopted_only_as_an_edit_with_a_note(
    world: World,
) -> None:
    suggestion, target = await _suggestion(world, cited=False)
    path = f"{SUGGESTIONS}/{suggestion}/adopt"
    bare = await world.call("POST", path, "samuel", {"seen_version": 1})
    assert bare.status_code == 422 and bare.json()["detail"] == "uncited_change"
    no_note = await world.call("POST", path, "samuel", {"seen_version": 1, "edited_value": "1550"})
    assert no_note.status_code == 422 and no_note.json()["detail"] == "proposal_invalid"
    stale = await world.call(
        "POST",
        path,
        "samuel",
        {"seen_version": 2, "edited_value": "1550", "citation_note": "K-1 box 18A"},
    )
    assert stale.status_code == 409 and stale.json()["detail"] == "suggestion_changed"
    assert await _versions(world, target) == []
    edited = await world.call(
        "POST",
        path,
        "samuel",
        {"seen_version": 1, "edited_value": "1550", "citation_note": "K-1 box 18A"},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["status"] == "edited" and edited.json()["decision"] == "edited"
    assert [v[1:3] for v in await _versions(world, target)] == [("human", "edit")]


async def test_ac4_dismiss_and_a_change_sets_row_is_decided_only_with_its_proposal(
    world: World,
) -> None:
    suggestion, target = await _suggestion(world)
    dismissed = await world.call(
        "POST",
        f"{SUGGESTIONS}/{suggestion}/dismiss",
        "samuel",
        {"seen_version": 1, "reason_code": "wrong_treatment"},
    )
    assert dismissed.status_code == 200, dismissed.text
    assert dismissed.json()["status"] == "dismissed"
    assert await _versions(world, target) == []

    proposal, k1_target = await _k1(world)
    row = (await world.call("GET", f"{PROPOSALS}/{proposal}", "samuel")).json()["rows"][0]
    for verb in ("adopt", "dismiss"):
        alone = await world.call(
            "POST", f"{SUGGESTIONS}/{row['suggestion_id']}/{verb}", "samuel", {"seen_version": 1}
        )
        assert alone.status_code == 422 and alone.json()["detail"] == "proposal_invalid"
    await _nothing_decided(world, proposal, k1_target)


# --- Roles the matrix denies -------------------------------------------------------------------


async def test_ac4_the_roles_the_matrix_denies_are_refused(world: World) -> None:
    proposal, target = await _k1(world)
    path = f"{PROPOSALS}/{proposal}"
    assert (await world.call("GET", path, "kevin")).status_code == 200  # the QC reviewer reads
    kevin_view = (await world.call("GET", path, "kevin")).json()
    assert not {"proposal.approve", "proposal.reject", "proposal.route"} & set(
        kevin_view["allowed_actions"]
    )
    for verb, body in (
        ("approve", {"seen_version": 1}),
        ("reject", {"seen_version": 1, "reason_code": "wrong_treatment"}),
        ("route", {"seen_version": 1, "approver_user_id": str(world["priya"].user_id)}),
        ("follow-up", {"text": "Why passive?"}),
    ):
        refused = await world.call_with(
            "POST", f"{path}/{verb}", "kevin", body, {"Idempotency-Key": str(uuid.uuid4())}
        )
        assert refused.status_code == 403, (verb, refused.text)
    await _nothing_decided(world, proposal, target)


# --- INV-1: the agent and the platform never decide --------------------------------------------
VERDICTS: Final = (
    "proposal.approve",
    "proposal.reject",
    "proposal.route",
    "proposal.undo",
    "proposal.follow_up",
    "suggestion.resolve",
)


async def test_inv1_the_matrix_refuses_the_agent_and_the_platform_every_verdict(
    world: World,
) -> None:
    resource = Resource.engagement(world.tenant_id, world.site.engagement_id, archived=False)
    acting = await agent(world, frozenset({*VERDICTS, "proposal.create"}))  # even in scope
    platform = system_context_for_run(
        tenant_id=world.tenant_id,
        run_id=uuid.uuid4(),
        engagement_id=world.site.engagement_id,
        on_behalf_of=world["samuel"].user_id,
    )
    for action in VERDICTS:
        for ctx in (acting, platform):
            with pytest.raises(Forbidden):
                await authorise(ctx, action, resource)
    await authorise(acting, "proposal.create", resource)  # what it may do: propose


async def test_inv1_the_public_service_api_offers_no_verdict_to_call() -> None:
    """PROPOSAL-001 (DEC-604): `agents.api` exports none of the verdicts, so no other module
    and no agent activity can reach them except through a person's route."""
    exported = set(dir(agents_api))
    for name in (
        "approve_proposal",
        "reject_proposal",
        "route_proposal",
        "adopt_suggestion",
        "dismiss_suggestion",
        "record_follow_up",
    ):
        assert name not in exported


async def test_inv1_the_data_layer_refuses_a_verdict_written_as_the_agent_or_platform(
    world: World,
) -> None:
    proposal, target = await _k1(world)
    suggestion, _ = await _suggestion(world)
    acting = await agent(world)
    platform = system_context_for_run(
        tenant_id=world.tenant_id,
        run_id=uuid.uuid4(),
        engagement_id=world.site.engagement_id,
        on_behalf_of=world["samuel"].user_id,
    )
    writes = (
        (
            "UPDATE proposals SET state = 'approved', version = version + 1 WHERE id = :id",
            proposal,
        ),
        (
            "UPDATE suggestions SET status = 'adopted', version = version + 1 WHERE id = :id",
            suggestion,
        ),
    )
    for tenant in (acting.tenant, platform.tenant):
        for sql, row_id in writes:
            with pytest.raises(Exception):  # noqa: B017 -- the guard's error class is the DB's
                async with uow(tenant) as tx:
                    found = await tx.session.execute(text(sql), {"id": row_id})
                    assert (
                        cast(int, getattr(found, "rowcount", 1)) == 1
                    )  # visible: only a guard refuses
                    tx.record("proposal.probed", target=Target("proposal", row_id))
    # The verdicts' audit actions are on the human-only list, refused as the agent (0097, 0231).
    for action in ("proposal.approved", "proposal.rejected", "suggestion.adopted"):
        with pytest.raises(Exception):  # noqa: B017
            async with uow(acting.tenant) as tx:
                tx.record(action, target=Target("proposal", proposal))
    await _nothing_decided(world, proposal, target)
    status = await world.seed.value("SELECT status FROM suggestions WHERE id = $1", suggestion)
    assert status == "pending"
    assert await audit_rows(world, "proposal.approved") == []


# --- Walls, need to know, offshore, other firms ------------------------------------------------


async def test_ac4_a_walled_person_and_a_non_member_see_and_decide_nothing(world: World) -> None:
    proposal, target = await _k1(world)
    suggestion, s_target = await _suggestion(world)
    path = f"{PROPOSALS}/{proposal}"
    await world.net.wall(world.admin, world["samuel"], world.site)
    outsider = await world.seed.person(world.tenant_id)  # same firm, no role on the engagement
    for who in (world["samuel"], outsider):
        read = await world.call("GET", path, who)
        assert read.status_code in (403, 404), read.text
        assert "K-1 treatment" not in read.text
        approve = await world.call("POST", f"{path}/approve", who, {"seen_version": 1})
        assert approve.status_code in (403, 404)
        adopt = await world.call(
            "POST", f"{SUGGESTIONS}/{suggestion}/adopt", who, {"seen_version": 1}
        )
        assert adopt.status_code in (403, 404)
    # A wall answers 404, never 403 (DEC-43).
    assert (await world.call("GET", path, "samuel")).status_code == 404
    assert (
        await world.call("POST", f"{path}/approve", "samuel", {"seen_version": 1})
    ).status_code == 404
    await _nothing_decided(world, proposal, target)
    assert await _versions(world, s_target) == []


async def test_ac4_offshore_is_not_a_wall_but_a_wall_binds_an_offshore_member(
    world: World,
) -> None:
    """DEC-319: offshore refuses only `not_offshore` actions; no C3 row carries it."""
    await world.seed.run(
        "UPDATE memberships SET offshore = true WHERE tenant_id = $1 AND user_id = ANY($2)",
        world.tenant_id,
        [world["raj"].user_id, world["samuel"].user_id],
    )
    proposal, target = await _k1(world)
    approved = await world.call(
        "POST", f"{PROPOSALS}/{proposal}/approve", "raj", {"seen_version": 1}
    )
    assert approved.status_code == 200, approved.text
    assert len(await _versions(world, target)) == 4

    walled, walled_target = await _k1(world)
    await world.net.wall(world.admin, world["samuel"], world.site)
    for verb, body in (
        ("approve", {"seen_version": 1}),
        ("reject", {"seen_version": 1, "reason_code": "wrong_treatment"}),
    ):
        refused = await world.call("POST", f"{PROPOSALS}/{walled}/{verb}", "samuel", body)
        assert refused.status_code == 404, refused.text
    await _nothing_decided(world, walled, walled_target)


async def test_ac4_another_firm_sees_and_decides_nothing(world: World, net: Net) -> None:
    proposal, target = await _k1(world)
    suggestion, s_target = await _suggestion(world)
    elsewhere = await make_world(net, "Northwind elsewhere")
    stranger = elsewhere["samuel"]
    for tenant in (None, world.tenant_id):  # its own firm, and naming ours
        assert (
            await world.call("GET", f"{PROPOSALS}/{proposal}", stranger, tenant=tenant)
        ).status_code == 404
        for path, body in (
            (f"{PROPOSALS}/{proposal}/approve", {"seen_version": 1}),
            (
                f"{PROPOSALS}/{proposal}/reject",
                {"seen_version": 1, "reason_code": "wrong_treatment"},
            ),
            (f"{SUGGESTIONS}/{suggestion}/adopt", {"seen_version": 1}),
        ):
            refused = await world.call("POST", path, stranger, body, tenant=tenant)
            assert refused.status_code == 404, refused.text
    await _nothing_decided(world, proposal, target)
    assert await _versions(world, s_target) == []


async def test_ac4_a_row_on_another_engagements_target_is_never_written(world: World) -> None:
    """Security review: the target must belong to the proposal's engagement. A reviewable on
    Copperleaf is offered as a row of a Northwind proposal."""
    other = await second_site(world, "Copperleaf")
    foreign = probe(other, (world["ana"],))
    try:
        proposal: uuid.UUID | None = await create_proposal(
            await agent(world),
            engagement_id=world.site.engagement_id,
            kind="field_change_set",
            title="Cross-engagement row",
            rows=[_row(foreign, "line.one", "100", (await cite(world),), target_type=PROBE)],
        )
    except Exception:  # refused at creation is a pass (invisible, never written)
        proposal = None
    if proposal is not None:
        approve = await world.call(
            "POST", f"{PROPOSALS}/{proposal}/approve", "samuel", {"seen_version": 1}
        )
        assert approve.status_code != 200, approve.text
    assert not [v for v in WRITTEN if v.target_id == foreign]
    assert await _versions(world, foreign) == []


# --- Shadow runs are invisible -----------------------------------------------------------------


async def _shadow_k1(world: World, target: uuid.UUID) -> uuid.UUID | None:
    """The same fields proposed by a run in shadow; refusing to store it is also invisible."""
    try:
        shadow, _ = await _k1(world, shadow=True, target=target)
    except Exception:  # refused at creation is a pass (invisible, never written)
        return None
    return shadow


@pytest.mark.xfail(
    strict=True,
    reason="ED-171: a generic proposal from a shadow run, or in a shadow-stage firm, is served "
    "(200, approve allowed), against SPEC-036 AC-5; recorded in "
    "work/tasks/TASK-1464-p04t28-independent-ac-tests.md (TASK-1464)",
)
async def test_ac4_a_shadow_runs_generic_proposal_is_invisible(world: World) -> None:
    _, target = await _k1(world)
    shadow = await _shadow_k1(world, target)
    if shadow is None:
        return
    for method, path, body in (
        ("GET", f"{PROPOSALS}/{shadow}", None),
        ("POST", f"{PROPOSALS}/{shadow}/approve", {"seen_version": 1}),
        (
            "POST",
            f"{PROPOSALS}/{shadow}/reject",
            {"seen_version": 1, "reason_code": "other", "note": "x"},
        ),
    ):
        hidden = await world.call(method, path, "samuel", body)
        assert hidden.status_code == 404, (path, hidden.text)
    assert await _versions(world, target) == []


async def test_ac4_a_shadow_run_never_supersedes_the_live_proposal(world: World) -> None:
    """Security review: a shadow run on the same fields leaves the live proposal as it was."""
    live, target = await _k1(world)
    await _shadow_k1(world, target)
    assert await _state(world, live) == ("pending", 1)
    shown = (await world.call("GET", f"{PROPOSALS}/{live}", "samuel")).json()
    assert shown["state"] == "pending" and shown["version"] == 1
    approved = await world.call(
        "POST", f"{PROPOSALS}/{live}/approve", "samuel", {"seen_version": 1}
    )
    assert approved.status_code == 200, approved.text


@pytest.mark.xfail(
    strict=True,
    reason="ED-171: a generic proposal from a shadow run, or in a shadow-stage firm, is served "
    "(200, approve allowed), against SPEC-036 AC-5; recorded in "
    "work/tasks/TASK-1464-p04t28-independent-ac-tests.md (TASK-1464)",
)
async def test_ac4_a_shadow_stage_firm_sees_no_generic_proposal(world: World) -> None:
    proposal, target = await _k1(world)
    await world.seed.run(
        "INSERT INTO agent_stages (tenant_id, agent_id, stage, changed_by, note) "
        "VALUES ($1, 'evidence.screener', 'shadow', 'test-seed', 'PW1')",
        world.tenant_id,
    )
    assert (await world.call("GET", f"{PROPOSALS}/{proposal}", "samuel")).status_code == 404
    approve = await world.call(
        "POST", f"{PROPOSALS}/{proposal}/approve", "samuel", {"seen_version": 1}
    )
    assert approve.status_code == 404
    await _nothing_decided(world, proposal, target)


# --- AC-5: the typed adapters ------------------------------------------------------------------


async def _uploaded(world: World, label: str) -> Site:
    """A client upload fulfilling a request item, so a person can decide on it (AUD-03)."""
    site = await second_site(world, label)
    await world.seed.run(
        "INSERT INTO fulfilments (tenant_id, engagement_id, request_item_id, "
        "evidence_version_id, created_by_kind, created_by_id) "
        "VALUES ($1, $2, $3, $4, 'human', 'seed')",
        world.tenant_id,
        site.engagement_id,
        site.item_id,
        site.version_id,
    )
    await world.seed.run(
        "UPDATE request_items SET status = 'uploaded' WHERE id = $1", site.item_id
    )
    return site


async def _screening(world: World, site: Site, *, shadow: bool = False) -> uuid.UUID:
    """The screener's result on the site's version with two verified citations (C4)."""
    run = await world.seed.value(
        "INSERT INTO agent_runs (tenant_id, agent_id, spec_version, engagement_id, "
        "evidence_version_id, initiator_user_id, task_scope, status, finished_at, shadow) "
        "VALUES ($1, 'evidence.screener', 1, $2, $3, $4, ARRAY['evidence.read'], 'completed', "
        "now(), $5) RETURNING id",
        world.tenant_id,
        site.engagement_id,
        site.version_id,
        world["hannah"].user_id,
        shadow,
    )
    result = cast(
        uuid.UUID,
        await world.seed.value(
            "INSERT INTO screening_results (tenant_id, engagement_id, evidence_version_id, "
            "agent_run_id, action, confidence, rationale, citations, unverified) VALUES "
            "($1, $2, $3, $4, 'ready_for_review', 0.9, 'Statement agrees to the ledger', "
            "'[]', '[]') RETURNING id",
            world.tenant_id,
            site.engagement_id,
            site.version_id,
            run,
        ),
    )
    for n in (1, 2):
        await world.seed.run(
            "INSERT INTO citations (tenant_id, engagement_id, cited_from_type, cited_from_id, "
            "n, kind, source_type, source_id, locator, verified, verifier_version, "
            "created_by_kind, created_by_run_id, shadow) VALUES ($1, $2, 'screening_result', "
            "$3, $4, 'sheet_cell', 'evidence_version', $5, "
            '\'{"sheet": "TB", "cell": "B2"}\', true, \'v1\', \'agent\', $6, $7)',
            world.tenant_id,
            site.engagement_id,
            result,
            n,
            site.version_id,
            run,
            shadow,
        )
    return result


async def _review_decisions(world: World, site: Site) -> list[tuple[object, ...]]:
    rows = await world.seed.rows(
        "SELECT decision, reason_code, actor_kind, actor_id FROM review_decisions "
        "WHERE evidence_version_id = $1",
        site.version_id,
    )
    return [tuple(r.values()) for r in rows]


async def test_ac5_a_typed_reject_maps_its_reason_and_a_typed_approve_takes_no_edits(
    world: World,
) -> None:
    granite = await _uploaded(world, "Granite Peak")
    ref = f"screening_result:{await _screening(world, granite)}"
    edits = await world.call(
        "POST",
        f"{PROPOSALS}/{ref}/approve",
        "hannah",
        {"seen_version": 1, "edits": [{"n": 1, "after": "x", "citation_note": "y"}]},
    )
    assert edits.status_code == 422
    assert await _review_decisions(world, granite) == []
    rejected = await world.call(
        "POST",
        f"{PROPOSALS}/{ref}/reject",
        "hannah",
        {"seen_version": 1, "reason_code": "unsupported_value"},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["state"] == "rejected"
    decisions = await _review_decisions(world, granite)
    assert len(decisions) == 1
    assert decisions[0][1:] == ("does_not_agree", "human", str(world["hannah"].user_id))
    replay = await world.call(
        "POST",
        f"{PROPOSALS}/{ref}/reject",
        "hannah",
        {"seen_version": 1, "reason_code": "unsupported_value"},
    )
    assert replay.status_code == 409 and replay.json()["detail"] == "proposal_changed"
    assert len(await _review_decisions(world, granite)) == 1


async def test_ac5_a_shadow_run_never_supersedes_the_live_typed_proposal(world: World) -> None:
    granite = await _uploaded(world, "Granite Peak")
    live = await _screening(world, granite)
    shadow = await _screening(world, granite, shadow=True)  # newer, but a shadow run's
    hidden = await world.call("GET", f"{PROPOSALS}/screening_result:{shadow}", "hannah")
    assert hidden.status_code == 404
    shown = await world.call("GET", f"{PROPOSALS}/screening_result:{live}", "hannah")
    assert shown.status_code == 200, shown.text
    assert shown.json()["state"] == "pending"
    approved = await world.call(
        "POST", f"{PROPOSALS}/screening_result:{live}/approve", "hannah", {"seen_version": 1}
    )
    assert approved.status_code == 200, approved.text
    for verb, body in (
        ("approve", {"seen_version": 1}),
        ("reject", {"seen_version": 1, "reason_code": "other", "note": "x"}),
    ):
        refused = await world.call(
            "POST", f"{PROPOSALS}/screening_result:{shadow}/{verb}", "hannah", body
        )
        assert refused.status_code == 404


async def test_ac5_a_shadow_stage_firm_and_a_walled_person_see_no_typed_proposal(
    world: World,
) -> None:
    granite = await _uploaded(world, "Granite Peak")
    ref = f"screening_result:{await _screening(world, granite)}"
    await world.net.wall(world.admin, world["priya"], granite)
    assert (await world.call("GET", f"{PROPOSALS}/{ref}", "priya")).status_code == 404
    assert (
        await world.call("POST", f"{PROPOSALS}/{ref}/approve", "priya", {"seen_version": 1})
    ).status_code == 404
    await world.seed.run(
        "INSERT INTO agent_stages (tenant_id, agent_id, stage, changed_by, note) "
        "VALUES ($1, 'evidence.screener', 'shadow', 'test-seed', 'PW1')",
        world.tenant_id,
    )
    for method, path, body in (
        ("GET", f"{PROPOSALS}/{ref}", None),
        ("POST", f"{PROPOSALS}/{ref}/approve", {"seen_version": 1}),
        (
            "POST",
            f"{PROPOSALS}/{ref}/reject",
            {"seen_version": 1, "reason_code": "other", "note": "x"},
        ),
    ):
        assert (await world.call(method, path, "hannah", body)).status_code == 404
    assert await _review_decisions(world, granite) == []


async def test_ac5_an_inbox_match_rejection_persists_and_the_file_keeps_waiting(
    world: World,
) -> None:
    site = await second_site(world, "Copperleaf inbox")
    fingerprint = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
    inbox_file = await world.seed.value(
        "INSERT INTO inbox_files (tenant_id, engagement_id, file_name, media_type, size_bytes, "
        "fingerprint, storage_key, storage_version_id, uploaded_by, uploaded_by_staff) VALUES "
        "($1, $2, 'trust-report.pdf', 'application/pdf', 10, $3, $4, 'v1', $5, true) "
        "RETURNING id",
        world.tenant_id,
        site.engagement_id,
        fingerprint,
        f"tenants/{world.tenant_id}/sha256/{fingerprint}",
        world["ana"].user_id,
    )
    run = await world.seed.value(
        "INSERT INTO agent_runs (tenant_id, agent_id, spec_version, engagement_id, "
        "inbox_file_id, initiator_user_id, task_scope, status, finished_at) VALUES ($1, "
        "'evidence.matcher', 1, $2, $3, $4, ARRAY['evidence.read'], 'completed', now()) "
        "RETURNING id",
        world.tenant_id,
        site.engagement_id,
        inbox_file,
        world["hannah"].user_id,
    )
    match = await world.seed.value(
        "INSERT INTO inbox_match_runs (tenant_id, engagement_id, inbox_file_id, agent_run_id, "
        "prompt_ref, none_fit) VALUES ($1, $2, $3, $4, 'evidence.inbox_match@v2', false) "
        "RETURNING id",
        world.tenant_id,
        site.engagement_id,
        inbox_file,
        run,
    )
    await world.seed.run(
        "INSERT INTO inbox_match_proposals (tenant_id, match_id, rank, request_item_id, "
        "confidence, rationale, citations, shown) VALUES ($1, $2, 1, $3, 0.94, 'Trust report', "
        "'[]'::jsonb, true)",
        world.tenant_id,
        match,
        site.item_id,
    )
    ref = f"{PROPOSALS}/inbox_match:{match}"
    shown = await world.call("GET", ref, "hannah")
    assert shown.status_code == 200, shown.text
    assert shown.json()["state"] == "pending"
    rejected = await world.call(
        "POST", f"{ref}/reject", "hannah", {"seen_version": 1, "reason_code": "wrong_treatment"}
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["state"] == "rejected"
    assert (await world.call("GET", ref, "hannah")).json()["state"] == "rejected"  # persists
    replay = await world.call(
        "POST", f"{ref}/reject", "hannah", {"seen_version": 1, "reason_code": "wrong_treatment"}
    )
    assert replay.status_code == 409 and replay.json()["detail"] == "proposal_changed"
    approve = await world.call("POST", f"{ref}/approve", "hannah", {"seen_version": 1})
    assert approve.status_code == 409 and approve.json()["detail"] == "proposal_changed"
    status = await world.seed.value("SELECT status FROM inbox_files WHERE id = $1", inbox_file)
    assert status == "waiting"  # rejecting a match is not discarding the client's file
    assert await audit_rows(world, "proposal.rejected") == [
        ("human", str(world["hannah"].user_id))
    ]
