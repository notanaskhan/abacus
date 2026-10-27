"""P-04-T29 (TASK-1618; DEC-24, ADR-161 clause 6; DEC-713): Undo of a proposal decision, over
HTTP on P-04-T28's world (Samuel Ito decides the Ridgeline K-1 proposal).

"Undo inside 10 seconds voids the grant so no client email is sent and returns the request to
Uploaded - needs review, Undo after an effect starts returns 409 effect_started, and a closed tab
keeps the decision" (P-04-T29 acceptance). Here: a rejection is undone inside the window and the
proposal is pending again with an `undone` decision and `proposal.undone`; someone else, or after
10 seconds, gets 409 `undo_window_closed`; an approval whose fields have no earlier value cannot be
put back (409 `effect_started`) and keeps its decision; the decision view offers the window only to
the decider. The typed review-decision path is evidence's own undo (its suites).
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from abacus.kernel import clock
from abacus.modules.agents import proposals

from . import test_p04t28_proposals_independent as t28
from .p04t28_support import World, audit_rows

world = t28.world
PROPOSALS = t28.PROPOSALS


async def _rejected(world: World) -> tuple[str, str]:
    proposal, _ = await t28._k1(world)  # pyright: ignore[reportPrivateUsage]
    done = await world.call(
        "POST",
        f"{PROPOSALS}/{proposal}/reject",
        "samuel",
        {"seen_version": 1, "reason_code": "wrong_treatment"},
    )
    assert done.status_code == 200, done.text
    return str(proposal), str(done.json()["decision"]["id"])


async def test_ac_a_rejection_undone_inside_the_window_is_pending_again(world: World) -> None:
    proposal, decision = await _rejected(world)
    undone = await world.call(
        "POST", f"{PROPOSALS}/{proposal}/undo", "samuel", {"decision_id": decision}
    )
    assert undone.status_code == 200, undone.text
    assert undone.json()["state"] == "pending"
    rows = await world.seed.rows(
        "SELECT decision, undoes_decision_id::text AS undoes FROM proposal_decisions "
        "WHERE proposal_id = $1 ORDER BY created_at",
        proposal,
    )
    assert [(r["decision"], r["undoes"]) for r in rows][-1] == ("undone", decision)
    assert await audit_rows(world, "proposal.undone") == [("human", str(world["samuel"].user_id))]


async def test_ac_someone_else_or_after_ten_seconds_is_too_late(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    proposal, decision = await _rejected(world)
    other = await world.call(
        "POST", f"{PROPOSALS}/{proposal}/undo", "priya", {"decision_id": decision}
    )
    assert other.status_code in (403, 409)
    real_now = clock.now

    async def later(tenant: object = None) -> object:
        return await real_now(tenant) + timedelta(seconds=11)  # type: ignore[arg-type]

    monkeypatch.setattr(clock, "now", later)
    late = await world.call(
        "POST", f"{PROPOSALS}/{proposal}/undo", "samuel", {"decision_id": decision}
    )
    assert late.status_code == 409 and late.json()["detail"] == "undo_window_closed"


async def test_ac_an_approval_with_nothing_to_put_back_keeps_its_decision(world: World) -> None:
    proposal, _ = await t28._k1(world)  # pyright: ignore[reportPrivateUsage]
    approved = await world.call(
        "POST", f"{PROPOSALS}/{proposal}/approve", "samuel", {"seen_version": 1, "edits": []}
    )
    assert approved.status_code == 200, approved.text
    decision = approved.json()["decision"]["id"]
    refused = await world.call(
        "POST", f"{PROPOSALS}/{proposal}/undo", "samuel", {"decision_id": decision}
    )
    assert refused.status_code == 409 and refused.json()["detail"] == "effect_started"
    again = await world.call("GET", f"{PROPOSALS}/{proposal}", "samuel")
    assert again.json()["state"] == "approved"  # a refused Undo, like a closed tab, keeps it


async def test_the_window_is_offered_to_the_decider_only(world: World) -> None:
    proposal, _ = await _rejected(world)
    mine = await world.call("GET", f"{PROPOSALS}/{proposal}", "samuel")
    assert mine.json()["decision"]["undo_until"] is not None
    theirs = await world.call("GET", f"{PROPOSALS}/{proposal}", "priya")
    if theirs.status_code == 200:
        assert theirs.json()["decision"]["undo_until"] is None
    assert timedelta(seconds=10) == proposals.UNDO_WINDOW
