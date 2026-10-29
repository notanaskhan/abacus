# ac-test-author: ayushkbhatia
"""P-04-T33 (TASK-1733; ADR-078 independent; P-04-T29, DEC-713, DEC-823): Undo and the effect
hold, from the plan and the contract, not from P-04-T29's tests.

Acceptance (the task row): "Tests written in ayushkbhatia's session pass and fail if an external
effect fires before not_before."

- The decision row is written at once (before the window closes), with its decider.
- Undo inside the window writes an `undone` row naming the decision and `proposal.undone`.
- A held effect's grant: never consumable before `not_before` (`GrantNotYetDue`, the dispatcher
  retries); an Undo voids it and it is never consumable after; once consumed, an Undo cannot void
  it (`void_grant` answers False, the route `effect_started`).
- Temporal replay: no proposal effect is hosted by Temporal (DEC-713), so there is no history to
  replay; the dispatcher's retry on `GrantNotYetDue` is the hold (asserted here).

Boundary: the proposal routes over HTTP on P-04-T28's world; grants through `identity.api`.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import timedelta

import pytest

from abacus.kernel.clock import system_now
from abacus.kernel.uow import Target, uow
from abacus.modules.engagements.api import get_ref
from abacus.modules.identity.api import (
    AuthContext,
    GrantNotYetDue,
    consume_grant,
    issue_grant,
    member_context,
    void_grant,
)

from . import test_p04t28_proposals_independent as t28
from .p04t28_support import World, audit_rows

world = t28.world
PROPOSALS = t28.PROPOSALS
PAYLOAD = hashlib.sha256(b"Ridgeline K-1 follow-up email, as approved").hexdigest()
ACTION = "proposal.approve"


async def _samuel(world: World) -> AuthContext:
    ctx = await member_context(world.tenant_id, world["samuel"].user_id)
    assert ctx is not None
    return ctx


async def _grant(world: World, *, starts_in: timedelta) -> uuid.UUID:
    ctx = await _samuel(world)
    ref = await get_ref(ctx, world.site.engagement_id)
    now = system_now()
    async with uow(ctx.tenant) as tx:
        grant = await issue_grant(
            tx,
            ctx,
            action=ACTION,
            resource=ref.resource(),
            subject=Target("proposal", uuid.uuid4()),
            payload_sha256=PAYLOAD,
            not_before=now + starts_in,
            expires_at=now + starts_in + timedelta(days=1),
        )
        tx.record("approval_grant.issued", target=Target("approval_grant", grant))
    return grant


# --- The acceptance: an external effect never fires before not_before ---------------------------


async def test_ac_an_effect_cannot_fire_before_not_before(world: World) -> None:
    grant = await _grant(world, starts_in=timedelta(seconds=10))
    with pytest.raises(GrantNotYetDue):
        await consume_grant(world.tenant_id, grant, uuid.uuid4(), PAYLOAD)
    used = await world.seed.value("SELECT used_at FROM approval_grants WHERE id = $1", grant)
    assert used is None


async def test_ac_an_undo_inside_the_window_voids_the_held_effect(world: World) -> None:
    grant = await _grant(world, starts_in=timedelta(seconds=10))
    ctx = await _samuel(world)
    async with uow(ctx.tenant) as tx:
        assert await void_grant(tx, grant)
    await world.seed.run_untriggered(
        "UPDATE approval_grants SET not_before = now() - interval '1 second' WHERE id = $1",
        grant,
    )
    assert not await consume_grant(world.tenant_id, grant, uuid.uuid4(), PAYLOAD)


async def test_ac_once_the_effect_started_an_undo_cannot_void_it(world: World) -> None:
    grant = await _grant(world, starts_in=timedelta(seconds=0))
    consumer = uuid.uuid4()
    assert await consume_grant(world.tenant_id, grant, consumer, PAYLOAD)
    ctx = await _samuel(world)
    async with uow(ctx.tenant) as tx:
        voided = await void_grant(tx, grant)
        tx.record("approval_grant.probe", target=Target("approval_grant", grant))
    assert not voided
    assert await consume_grant(world.tenant_id, grant, consumer, PAYLOAD)  # a retried delivery
    assert not await consume_grant(world.tenant_id, grant, uuid.uuid4(), PAYLOAD)


async def test_another_payload_never_fires(world: World) -> None:
    grant = await _grant(world, starts_in=timedelta(seconds=0))
    other = hashlib.sha256(b"an edited email").hexdigest()
    assert not await consume_grant(world.tenant_id, grant, uuid.uuid4(), other)


# --- The decision and its Undo, from the contract ---------------------------------------------


async def _reject(world: World) -> tuple[str, str]:
    proposal, _ = await t28._k1(world)  # pyright: ignore[reportPrivateUsage] -- T28's own K-1 fixture
    done = await world.call(
        "POST",
        f"{PROPOSALS}/{proposal}/reject",
        "samuel",
        {"seen_version": 1, "reason_code": "wrong_treatment"},
    )
    assert done.status_code == 200, done.text
    return str(proposal), str(done.json()["decision"]["id"])


async def test_the_decision_row_is_written_at_once_with_its_decider(world: World) -> None:
    proposal, decision = await _reject(world)
    row = await world.seed.rows(
        "SELECT decision, decided_by::text AS decided_by, created_at FROM proposal_decisions "
        "WHERE id = $1",
        uuid.UUID(decision),
    )
    assert row[0]["decision"] == "rejected"
    assert row[0]["decided_by"] == str(world["samuel"].user_id)
    assert system_now() - row[0]["created_at"] < timedelta(seconds=10)
    state = await world.seed.value(
        "SELECT state FROM proposals WHERE id = $1", uuid.UUID(proposal)
    )
    assert state == "rejected"


async def test_an_undo_inside_the_window_writes_the_undone_event(world: World) -> None:
    proposal, decision = await _reject(world)
    undone = await world.call(
        "POST", f"{PROPOSALS}/{proposal}/undo", "samuel", {"decision_id": decision}
    )
    assert undone.status_code == 200, undone.text
    last = await world.seed.rows(
        "SELECT decision, undoes_decision_id::text AS undoes FROM proposal_decisions "
        "WHERE proposal_id = $1 ORDER BY created_at DESC LIMIT 1",
        uuid.UUID(proposal),
    )
    assert (last[0]["decision"], last[0]["undoes"]) == ("undone", decision)
    assert ("human", str(world["samuel"].user_id)) in await audit_rows(world, "proposal.undone")


async def test_a_second_undo_of_the_same_decision_is_refused(world: World) -> None:
    proposal, decision = await _reject(world)
    first = await world.call(
        "POST", f"{PROPOSALS}/{proposal}/undo", "samuel", {"decision_id": decision}
    )
    assert first.status_code == 200
    again = await world.call(
        "POST", f"{PROPOSALS}/{proposal}/undo", "samuel", {"decision_id": decision}
    )
    assert again.status_code == 409
