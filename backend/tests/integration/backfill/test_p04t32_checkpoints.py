# ac-test-author: ayushkbhatia
"""P-04-T32 (TASK-1710; ADR-160 clause 9; SHL-16; DEC-85, DEC-145, DEC-804): checkpoints live.

Acceptance (the task row): "Restoring Checkpoint 3 creates Checkpoint 7 and deletes nothing, and
approving Checkpoint 6 records one decision that SHL-16 and SHL-10 both show."

What else the contract promises (`docs/contracts/review-grammar.md`, Checkpoints):
- Current is derived: the newest approved or saved checkpoint, never a proposed or rejected one;
- the diff is code-computed: `previous` is the checkpoint's own changes with its totals,
  `current` every field whose value differs from Current;
- approve and reject take the hash the person saw (409 `checkpoint_changed`, nothing written);
  restore of Current or of a checkpoint not in effect is 422 `checkpoint_invalid`;
- rename and star change only `name` and `starred`;
- `checkpoint.approved` names the checkpoint and `checkpoint_deltas` sums its deltas (DEC-85);
  the three decisions are human-only at the service, the matrix and the audit list (0290);
- the flag off answers 404; another firm sees nothing (404).

Boundary: `create_app()` over HTTP as each signed-in person; the agent's checkpoints through
`review.api.propose_checkpoint` on a recorded run, as the agent's tools call it.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import replace
from typing import Any, Final, cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.flags import forget_flags
from abacus.modules.agents.api import ProposedRow, create_proposal
from abacus.modules.identity.api import AgentContext, Forbidden
from abacus.modules.review import checkpoints as service
from abacus.modules.review.api import ProposedChange, checkpoint_deltas, propose_checkpoint

from .p04t28_support import (
    PROBE,
    PROBED,
    RETURN,
    World,
    agent,
    audit_rows,
    cite,
    make_world,
    outbox,
    own,
    probe,
)
from .support import Net

pytestmark = pytest.mark.asyncio
Body = dict[str, Any]  # a response body as the contract shapes it
CHECKPOINTS: Final = "/v1/checkpoints"
SCOPE: Final = frozenset({"proposal.create", "suggestion.create", "checkpoint.propose"})
INT: Final = "f1040.l2b.halvard"  # the Halvard 1099-INT line (SHL-16 a)
DIV: Final = "f1040.l3b.ridgeline"


@pytest.fixture
async def world(net: Net) -> World:
    return await make_world(net)


def _hex(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _d(v: str | None) -> dict[str, object] | None:
    return None if v is None else {"t": "decimal", "v": v}


def _change(
    field: str, old: str | None, new: str | None, delta: str | None = None
) -> ProposedChange:
    return ProposedChange(
        field_key=field,
        old=_d(old),
        new=_d(new),
        cause="agent_run",
        delta_facts={"total_income": delta} if delta is not None else None,
    )


async def _return(world: World) -> uuid.UUID:
    """A return prepared by Ana, on a work item where Samuel and Hannah hold reviewer functions
    (the matrix's `function_in` for approve, reject and restore, DEC-145)."""
    target = probe(world.site, (world["ana"],))
    item = await world.seed.value(
        "INSERT INTO work_items (tenant_id, engagement_id, client_id, kind, name, created_by) "
        "VALUES ($1, $2, $3, 'tax_return', 'Form 1040 Halvard', $4) RETURNING id",
        world.tenant_id,
        world.site.engagement_id,
        world.site.client_id,
        world["hannah"].user_id,
    )
    for who, function in (("samuel", "detail_reviewer"), ("hannah", "manager_reviewer")):
        await world.seed.run(
            "INSERT INTO work_item_assignments (tenant_id, work_item_id, engagement_id, user_id, "
            "function, assigned_by) VALUES ($1, $2, $3, $4, $5, $6)",
            world.tenant_id,
            item,
            world.site.engagement_id,
            world[who].user_id,
            function,
            world["hannah"].user_id,
        )
    PROBED[target] = replace(PROBED[target], work_item_id=cast(uuid.UUID, item))
    return target


async def _bot(world: World) -> AgentContext:
    return await agent(world, SCOPE)


async def _propose(
    world: World, target: uuid.UUID, *changes: ProposedChange, tag: str
) -> tuple[uuid.UUID, str]:
    digest = _hex(f"{target}:{tag}")
    checkpoint = await propose_checkpoint(
        await _bot(world),
        PROBE,
        target,
        changes,
        author_kind="agent",
        cause="agent_run",
        content_hash=digest,
    )
    return checkpoint, f"sha256:{digest}"


async def _save(world: World, target: uuid.UUID, who: str, name: str | None = None) -> Body:
    body: dict[str, object] = {"target_type": PROBE, "target_id": str(target)}
    if name is not None:
        body["name"] = name
    saved = await world.call("POST", CHECKPOINTS, who, body)
    assert saved.status_code == 201, saved.text
    return saved.json()


async def _decide(world: World, checkpoint: uuid.UUID, seen: str, verb: str = "approve") -> Body:
    body: dict[str, object] = {"seen_hash": seen}
    if verb == "reject":
        body["reason"] = "Wrong year's statement"
    decided = await world.call("POST", f"{CHECKPOINTS}/{checkpoint}/{verb}", "samuel", body)
    assert decided.status_code == 200, decided.text
    return decided.json()


async def _history(world: World, target: uuid.UUID, filter: str = "all") -> Body:
    found = await world.call(
        "GET", f"{CHECKPOINTS}?target_type={PROBE}&target_id={target}&filter={filter}", "samuel"
    )
    assert found.status_code == 200, found.text
    return found.json()


async def _counts(world: World, target: uuid.UUID) -> tuple[int, int, int]:
    row = (
        await world.seed.rows(
            "SELECT (SELECT count(*) FROM checkpoints WHERE target_id = $1) AS c, "
            "(SELECT count(*) FROM checkpoint_diffs d JOIN checkpoints c "
            "ON c.id = d.checkpoint_id WHERE c.target_id = $1) AS d, "
            "(SELECT count(*) FROM checkpoint_decisions x JOIN checkpoints c "
            "ON c.id = x.checkpoint_id WHERE c.target_id = $1) AS x",
            target,
        )
    )[0]
    return int(row["c"]), int(row["d"]), int(row["x"])


async def _six(world: World) -> tuple[uuid.UUID, dict[int, uuid.UUID], uuid.UUID]:
    """The SHL-16 story on one return: 1 saved by Ana, 2 and 3 approved, 4 rejected, 5 approved,
    6 the agent's proposal (an SHL-10 change set), still proposed."""
    target = await _return(world)
    ids: dict[int, uuid.UUID] = {
        1: uuid.UUID((await _save(world, target, "ana", "Before K-1"))["id"])
    }
    ids[2], seen = await _propose(world, target, _change(INT, None, "2190", "2190"), tag="2")
    await _decide(world, ids[2], seen)
    ids[3], seen = await _propose(
        world, target, _change(INT, "2190", "2310", "120"), _change(DIV, None, "400"), tag="3"
    )
    await _decide(world, ids[3], seen)
    ids[4], seen = await _propose(world, target, _change(DIV, "400", "4000", "3600"), tag="4")
    await _decide(world, ids[4], seen, "reject")
    ids[5], seen = await _propose(world, target, _change(INT, "2310", "2410", "100"), tag="5")
    await _decide(world, ids[5], seen)
    # 6: the agent's change set, then its checkpoint naming it (ids are the database's).
    row_target = own(world.site)
    proposal = await create_proposal(
        await _bot(world),
        engagement_id=world.site.engagement_id,
        kind="field_change_set",
        title="Dividends: Ridgeline",
        rows=[
            ProposedRow(
                target_type=RETURN,
                target_id=row_target,
                field_key=DIV,
                label="Line 3b",
                before=None,
                after={"t": "decimal", "v": "450"},
                cause="schedule_b",
                citation_ids=(await cite(world),),
            )
        ],
        reasoning_ref="reasoning",
    )
    ids[6] = await propose_checkpoint(
        await _bot(world),
        PROBE,
        target,
        [_change(DIV, "400", "450", "50")],
        author_kind="agent",
        cause="agent_run",
        content_hash=_hex(f"{target}:6"),
        proposal_id=proposal,
    )
    return target, ids, proposal


# --- The acceptance ------------------------------------------------------------------------------


async def test_ac_approving_checkpoint_6_records_one_decision_shl16_and_shl10_both_show(
    world: World,
) -> None:
    target, ids, proposal = await _six(world)
    approved = await _decide(world, ids[6], f"sha256:{_hex(f'{target}:6')}")
    assert approved["status"] == "approved" and approved["current"] is True
    decision = approved["decision"]
    assert decision["decision"] == "approved"
    assert decision["decided_by_name"] == "Samuel Ito"

    # One person's act: one proposal decision, one checkpoint decision naming it.
    proposal_decisions = await world.seed.rows(
        "SELECT id, decision FROM proposal_decisions WHERE proposal_id = $1", proposal
    )
    assert [r["decision"] for r in proposal_decisions] == ["approved"]
    linked = await world.seed.rows(
        "SELECT proposal_decision_id FROM checkpoint_decisions WHERE checkpoint_id = $1", ids[6]
    )
    assert [r["proposal_decision_id"] for r in linked] == [proposal_decisions[0]["id"]]
    assert decision["proposal_decision_id"] == str(proposal_decisions[0]["id"])

    # SHL-10 shows the same decision.
    shown = await world.call("GET", f"/v1/proposals/{proposal}", "samuel")
    assert shown.status_code == 200, shown.text
    assert shown.json()["state"] == "approved"
    assert shown.json()["decision"]["id"] == decision["proposal_decision_id"]

    # A second approval through either surface changes nothing.
    again = await world.call(
        "POST",
        f"{CHECKPOINTS}/{ids[6]}/approve",
        "hannah",
        {"seen_hash": f"sha256:{_hex(f'{target}:6')}"},
    )
    assert again.status_code == 409 and again.json()["detail"] == "checkpoint_changed"
    assert (
        len(
            await world.seed.rows(
                "SELECT 1 FROM proposal_decisions WHERE proposal_id = $1", proposal
            )
        )
        == 1
    )


async def test_ac_restoring_checkpoint_3_creates_checkpoint_7_and_deletes_nothing(
    world: World,
) -> None:
    target, ids, _ = await _six(world)
    await _decide(world, ids[6], f"sha256:{_hex(f'{target}:6')}")
    before = await _counts(world, target)
    assert before == (6, 6, 5)  # 6 checkpoints; 6 diffs; a decision on each of 2 to 6

    restored = await world.call(
        "POST",
        f"{CHECKPOINTS}/{ids[3]}/restore",
        "samuel",
        {"seen_hash": f"sha256:{_hex(f'{target}:3')}"},
    )
    assert restored.status_code == 201, restored.text
    seven = restored.json()
    assert seven["seq"] == 7 and seven["cause"] == "restore" and seven["status"] == "saved"
    assert seven["restored_from_id"] == str(ids[3]) and seven["current"] is True
    assert seven["author_kind"] == "person" and seven["author_name"] == "Samuel Ito"
    assert seven["decision"]["decision"] == "restored"

    # Nothing deleted: every earlier row is still there, unchanged; 7 adds its own.
    after = await _counts(world, target)
    assert after == (7, before[1] + 2, before[2] + 1)
    statuses = await world.seed.rows(
        "SELECT seq, status FROM checkpoints WHERE target_id = $1 ORDER BY seq", target
    )
    assert [(r["seq"], r["status"]) for r in statuses] == [
        (1, "saved"),
        (2, "approved"),
        (3, "approved"),
        (4, "rejected"),
        (5, "approved"),
        (6, "approved"),
        (7, "saved"),
    ]

    # Checkpoint 7's changes take Current (6) back to Checkpoint 3: INT 2410 → 2310, DIV 450 → 400.
    detail = await world.call("GET", f"{CHECKPOINTS}/{seven['id']}?compare=previous", "samuel")
    assert detail.status_code == 200, detail.text
    diff = {r["field_key"]: (r["old"], r["new"]) for r in detail.json()["diff"]}
    assert diff == {INT: ("2410", "2310"), DIV: ("450", "400")}
    assert detail.json()["compared_to_id"] == str(ids[6])

    # Compared with Current, Checkpoint 3 now differs in nothing.
    compared = await world.call("GET", f"{CHECKPOINTS}/{ids[3]}?compare=current", "samuel")
    assert compared.json()["diff"] == [] and compared.json()["compared_to_id"] == seven["id"]
    assert await audit_rows(world, "checkpoint.restored") == [
        ("human", str(world["samuel"].user_id))
    ]


# --- Current, the history and the diff ---------------------------------------------------------


async def test_current_is_the_newest_in_effect_and_never_a_proposed_or_rejected_one(
    world: World,
) -> None:
    target, ids, _ = await _six(world)
    found = await _history(world, target)
    assert [i["seq"] for i in found["items"]] == [6, 5, 4, 3, 2, 1]  # newest first
    assert found["current_checkpoint_id"] == str(ids[5])
    assert [i["seq"] for i in found["items"] if i["current"]] == [5]
    assert found["total"] == 6
    by_seq = {i["seq"]: i for i in found["items"]}
    assert by_seq[6]["status"] == "proposed" and by_seq[6]["proposal_id"] is not None
    assert sorted(by_seq[6]["allowed_actions"]) == [
        "checkpoint.approve",
        "checkpoint.reject",
        "checkpoint.rename",
    ]
    assert "checkpoint.restore" in by_seq[3]["allowed_actions"]
    assert "checkpoint.restore" not in by_seq[5]["allowed_actions"]  # Current
    assert "checkpoint.restore" not in by_seq[4]["allowed_actions"]  # rejected
    assert by_seq[4]["decision"]["reason"] == "Wrong year's statement"
    assert by_seq[1]["author_name"] == "Ana Cruz" and by_seq[1]["name"] == "Before K-1"
    assert by_seq[2]["author_name"] == "Accrued Agent"
    assert by_seq[3]["summary"] == "halvard (2190 → 2310) and 1 more"
    assert found["allowed_actions"] == ["checkpoint.create"]

    agent_only = await _history(world, target, "agent")
    assert [i["seq"] for i in agent_only["items"]] == [6, 5, 4, 3, 2]
    named = await _history(world, target, "named")
    assert [i["seq"] for i in named["items"]] == [1]


async def test_the_diff_and_totals_are_code_computed(world: World) -> None:
    _, ids, _ = await _six(world)
    own_changes = await world.call("GET", f"{CHECKPOINTS}/{ids[3]}", "samuel")
    body = own_changes.json()
    assert body["compare"] == "previous" and body["compared_to_id"] == str(ids[2])
    assert {r["field_key"]: (r["old"], r["new"]) for r in body["diff"]} == {
        INT: ("2190", "2310"),
        DIV: (None, "400"),
    }
    assert body["totals"] == [{"label": "total income", "value": "120", "ties": False}]
    assert body["steps"] == []
    # Against Current (5): only INT differs (2410 now, 2310 at 3).
    compared = await world.call("GET", f"{CHECKPOINTS}/{ids[3]}?compare=current", "samuel")
    assert {r["field_key"]: (r["old"], r["new"]) for r in compared.json()["diff"]} == {
        INT: ("2410", "2310")
    }
    # A rejected checkpoint compares as itself on top of what was in effect before it.
    rejected = await world.call("GET", f"{CHECKPOINTS}/{ids[4]}?compare=current", "samuel")
    assert {r["field_key"]: (r["old"], r["new"]) for r in rejected.json()["diff"]} == {
        INT: ("2410", "2310"),
        DIV: ("400", "4000"),
    }


async def test_approved_carries_the_summed_deltas(world: World) -> None:
    target = await _return(world)
    checkpoint, seen = await _propose(
        world,
        target,
        _change(INT, "2190", "2310", "120"),
        _change(DIV, "400", "380", "-20"),
        tag="deltas",
    )
    await _decide(world, checkpoint, seen)
    events = [e for e in await outbox(world, "checkpoint.approved")]
    assert len(events) == 1
    assert events[0].payload["has_deltas"] is True
    assert "deltas" not in events[0].payload  # Restricted figures stay out of the outbox
    assert await checkpoint_deltas(
        TenantContext(world.tenant_id, "system", "t-01"), checkpoint
    ) == {"total_income": "100"}
    assert events[0].payload["checkpoint_id"] == str(checkpoint)
    assert await audit_rows(world, "checkpoint.approved") == [
        ("human", str(world["samuel"].user_id))
    ]
    assert len(await outbox(world, "checkpoint.recorded")) == 1


# --- Refusals ---------------------------------------------------------------------------------


async def test_a_stale_hash_or_a_decided_checkpoint_answers_checkpoint_changed(
    world: World,
) -> None:
    target = await _return(world)
    checkpoint, seen = await _propose(world, target, _change(INT, None, "1"), tag="stale")
    stale = await world.call(
        "POST",
        f"{CHECKPOINTS}/{checkpoint}/approve",
        "samuel",
        {"seen_hash": f"sha256:{_hex('another')}"},
    )
    assert stale.status_code == 409 and stale.json()["detail"] == "checkpoint_changed"
    assert await _counts(world, target) == (1, 1, 0)
    await _decide(world, checkpoint, seen, "reject")
    late = await world.call(
        "POST", f"{CHECKPOINTS}/{checkpoint}/approve", "samuel", {"seen_hash": seen}
    )
    assert late.status_code == 409 and late.json()["detail"] == "checkpoint_changed"
    assert await _counts(world, target) == (1, 1, 1)


async def test_restoring_current_or_a_rejected_checkpoint_is_invalid(world: World) -> None:
    target, ids, _ = await _six(world)
    for seq in (5, 4, 6):
        refused = await world.call(
            "POST",
            f"{CHECKPOINTS}/{ids[seq]}/restore",
            "samuel",
            {"seen_hash": f"sha256:{_hex(f'{target}:{seq}')}"},
        )
        assert refused.status_code == 422, (seq, refused.text)
        assert refused.json()["detail"] == "checkpoint_invalid"
    assert (await _counts(world, target))[0] == 6


async def test_rename_and_star_change_only_name_and_starred(world: World) -> None:
    target, ids, _ = await _six(world)
    renamed = await world.call(
        "PATCH", f"{CHECKPOINTS}/{ids[3]}", "ana", {"name": "Filed figures", "starred": True}
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == "Filed figures" and renamed.json()["starred"] is True
    assert renamed.json()["status"] == "approved"
    starred_only = await world.call("PATCH", f"{CHECKPOINTS}/{ids[3]}", "ana", {"starred": False})
    assert starred_only.json()["name"] == "Filed figures"
    assert starred_only.json()["starred"] is False
    cleared = await world.call("PATCH", f"{CHECKPOINTS}/{ids[3]}", "ana", {"name": None})
    assert cleared.json()["name"] is None
    assert await _counts(world, target) == (6, 6, 4)  # 6 still proposed: decisions on 2 to 5


async def test_rejecting_a_proposals_checkpoint_rejects_the_proposal_with_the_reason(
    world: World,
) -> None:
    target, ids, proposal = await _six(world)
    rejected = await _decide(world, ids[6], f"sha256:{_hex(f'{target}:6')}", "reject")
    assert rejected["status"] == "rejected"
    assert rejected["decision"]["reason"] == "Wrong year's statement"
    shown = (await world.call("GET", f"/v1/proposals/{proposal}", "samuel")).json()
    assert shown["state"] == "rejected"
    assert shown["decision"]["reason_code"] == "other"
    assert shown["decision"]["note"] == "Wrong year's statement"
    assert rejected["decision"]["proposal_decision_id"] == shown["decision"]["id"]


async def test_approving_on_shl10_moves_the_checkpoint_too(world: World) -> None:
    _, ids, proposal = await _six(world)
    approved = await world.call(
        "POST", f"/v1/proposals/{proposal}/approve", "samuel", {"seen_version": 1, "edits": []}
    )
    assert approved.status_code == 200, approved.text
    card = (await world.call("GET", f"{CHECKPOINTS}/{ids[6]}", "samuel")).json()["checkpoint"]
    assert card["status"] == "approved" and card["current"] is True
    assert card["decision"]["proposal_decision_id"] == approved.json()["decision"]["id"]


async def test_agent_and_system_never_decide_and_staff_cannot_approve(world: World) -> None:
    target = await _return(world)
    checkpoint, seen = await _propose(world, target, _change(INT, None, "1"), tag="inv1")
    bot = await _bot(world)
    for act in (
        service.approve(bot, checkpoint, seen),
        service.reject(bot, checkpoint, seen, "no"),
        service.restore(bot, checkpoint, seen),
        service.save(bot, PROBE, target, None),
    ):
        with pytest.raises(Forbidden):
            await act
    staff = await world.call(
        "POST", f"{CHECKPOINTS}/{checkpoint}/approve", "ana", {"seen_hash": seen}
    )
    assert staff.status_code == 403
    assert await _counts(world, target) == (1, 1, 0)


async def test_the_flag_off_answers_404_and_another_firm_sees_nothing(
    world: World, net: Net
) -> None:
    target, ids, _ = await _six(world)
    other = await make_world(net, "Halvard Family Office")
    elsewhere = await other.call("GET", f"{CHECKPOINTS}/{ids[3]}", "samuel")
    assert elsewhere.status_code == 404
    await world.seed.run(
        "UPDATE feature_flag_states SET value = 'false' WHERE tenant_id = $1 "
        "AND flag = 'review.grammar_api'",
        world.tenant_id,
    )
    forget_flags()
    off = await world.call(
        "GET", f"{CHECKPOINTS}?target_type={PROBE}&target_id={target}", "samuel"
    )
    assert off.status_code == 404
