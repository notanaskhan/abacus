"""SPEC-003 AC-6, AC-7, AC-8, AC-13, AC-14: migration 0013, the work slot ledger and its functions
(TASK-018 interface contract 018b, "Database", and contract revision 1; ADR-071).

The ledger (`work_slots`, `work_waiters`, `work_grants`) is platform-owned: the app reaches it only
through `work_slot_acquire`, `work_slot_release` and `work_slot_renew`, which take the tenant from
the session. Calls here run as `abacus_app` through `tenant_connection` (each call commits, as in
`kernel.slots`); setup and time travel (expired leases, old waiters, past grants) are written as
the superuser. The ledger is shared by the whole database, so every test starts from an empty one.
Expectations come from the contract, not the implementation.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast

import asyncpg
import pytest
from sqlalchemy import text
from temporalio.testing import ActivityEnvironment

from abacus.kernel.db import TenantContext, tenant_connection
from abacus.modules.agents.activities import create_run_activity
from abacus.modules.agents.workflow_types import ScreeningInput
from abacus.modules.connections.api import start_retrieval
from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .support import PERIOD, Migrated, Seeder, World, retrieve

CLASSES = ("interactive", "time_sensitive", "background", "batch")
TABLES = ("work_slots", "work_waiters", "work_grants")
FUNCTIONS = {
    "work_slot_acquire": "work_slot_acquire(text, uuid, text, integer, integer, integer, integer)",
    "work_slot_release": "work_slot_release(text)",
    "work_slot_renew": "work_slot_renew(text, integer)",
}
Decision = tuple[bool, str | None, datetime | None]

READ = {
    "work_slots": "SELECT * FROM work_slots",
    "work_waiters": "SELECT * FROM work_waiters",
    "work_grants": "SELECT * FROM work_grants",
}
ASSIGN = {
    "queued_reason = 'firm_cap'": "UPDATE sync_runs SET queued_reason = 'firm_cap' WHERE id = $1",
    "estimated_start_at = now()": "UPDATE sync_runs SET estimated_start_at = now() WHERE id = $1",
}
CLEAR = {
    "work_slots": "DELETE FROM work_slots",
    "work_waiters": "DELETE FROM work_waiters",
    "work_grants": "DELETE FROM work_grants",
}


@dataclass(frozen=True)
class Firm:
    tenant_id: uuid.UUID

    @property
    def ctx(self) -> TenantContext:
        return TenantContext(self.tenant_id, "system", "work-slots-test")


@pytest.fixture(autouse=True)
async def empty_ledger(seed: Seeder) -> None:
    for table in TABLES:
        await seed.run(CLEAR[table])


@pytest.fixture
async def firm(seed: Seeder) -> Firm:
    return Firm(await seed.firm())


@pytest.fixture
async def other(seed: Seeder) -> Firm:
    return Firm(await seed.firm())


async def acquire(
    who: Firm,
    holder: str,
    engagement: uuid.UUID | None = None,
    work_class: str = "interactive",
    *,
    firm_cap: int = 20,
    engagement_cap: int = 10,
    capacity: int = 50,
    lease: int = 900,
) -> Decision:
    async with tenant_connection(who.ctx) as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT granted, reason, estimated_start_at FROM work_slot_acquire("
                    ":h, :e, :c, :f, :g, :k, :l)"
                ),
                {
                    "h": holder,
                    "e": engagement,
                    "c": work_class,
                    "f": firm_cap,
                    "g": engagement_cap,
                    "k": capacity,
                    "l": lease,
                },
            )
        ).one()
        await conn.commit()
    return bool(row[0]), row[1], row[2]


async def release(who: Firm, holder: str) -> None:
    async with tenant_connection(who.ctx) as conn:
        await conn.execute(text("SELECT work_slot_release(:h)"), {"h": holder})
        await conn.commit()


async def renew(who: Firm, holder: str, lease: int = 900) -> bool:
    async with tenant_connection(who.ctx) as conn:
        found = await conn.scalar(
            text("SELECT work_slot_renew(:h, :l)"), {"h": holder, "l": lease}
        )
        await conn.commit()
    return bool(found)


async def holders(seed: Seeder, who: Firm | None = None) -> set[str]:
    rows = await seed.rows(
        "SELECT holder FROM work_slots WHERE $1::uuid IS NULL OR tenant_id = $1",
        who.tenant_id if who else None,
    )
    return {str(r["holder"]) for r in rows}


async def waiters(seed: Seeder, who: Firm | None = None) -> set[str]:
    rows = await seed.rows(
        "SELECT holder FROM work_waiters WHERE $1::uuid IS NULL OR tenant_id = $1",
        who.tenant_id if who else None,
    )
    return {str(r["holder"]) for r in rows}


async def lease_of(seed: Seeder, who: Firm, holder: str) -> datetime:
    return cast(
        datetime,
        await seed.value(
            "SELECT lease_until FROM work_slots WHERE tenant_id = $1 AND holder = $2",
            who.tenant_id,
            holder,
        ),
    )


async def _occupy(seed: Seeder, who: Firm, count: int, work_class: str = "interactive") -> None:
    """Slots held by `who` (seeded as the superuser, with a future lease), without any grant."""
    for n in range(count):
        await seed.run(
            "INSERT INTO work_slots (tenant_id, holder, engagement_id, work_class, acquired_at, "
            "lease_until) VALUES ($1, $2, NULL, $3, now(), now() + interval '1 hour')",
            who.tenant_id,
            f"seeded:{uuid.uuid4()}:{n}",
            work_class,
        )


# --- AC-6, AC-7: the caps hold -------------------------------------------------------------------


async def test_ac6_a_firm_at_its_cap_waits_with_firm_cap_until_a_slot_frees(
    seed: Seeder, firm: Firm
) -> None:
    for n in range(2):
        assert await acquire(firm, f"h{n}", firm_cap=2) == (True, None, None)
    granted, reason, _ = await acquire(firm, "h2", firm_cap=2)
    assert (granted, reason) == (False, "firm_cap")
    await release(firm, "h0")
    assert (await acquire(firm, "h2", firm_cap=2))[0] is True
    assert await holders(seed, firm) == {"h1", "h2"}


async def test_ac6_other_firms_proceed_while_a_firm_is_at_its_cap(firm: Firm, other: Firm) -> None:
    assert (await acquire(firm, "a0", firm_cap=1))[0] is True
    assert (await acquire(firm, "a1", firm_cap=1))[0] is False
    assert (await acquire(other, "b0", firm_cap=1)) == (True, None, None)


@pytest.mark.parametrize("work_class", [c for c in CLASSES if c != "interactive"])
async def test_ac6_the_firm_cap_is_per_class(firm: Firm, work_class: str) -> None:
    assert (await acquire(firm, "busy", None, "interactive", firm_cap=1))[0] is True
    assert (await acquire(firm, "second", None, "interactive", firm_cap=1))[1] == "firm_cap"
    assert (await acquire(firm, "other", None, work_class, firm_cap=1))[0] is True


async def test_ac6_a_cap_of_zero_never_grants_and_the_work_stays_queued(
    seed: Seeder, firm: Firm
) -> None:
    for _ in range(3):
        granted, reason, _ = await acquire(firm, "paused", firm_cap=0)
        assert (granted, reason) == (False, "firm_cap")
    assert await holders(seed, firm) == set()
    assert await waiters(seed, firm) == {"paused"}  # waiting, not dropped
    granted, reason, _ = await acquire(firm, "e", uuid.uuid4(), engagement_cap=0, firm_cap=5)
    assert (granted, reason) == (False, "engagement_cap")  # an engagement cap of 0 pauses it too


async def test_ac7_an_engagement_at_its_cap_waits_but_its_siblings_run(
    seed: Seeder, firm: Firm
) -> None:
    busy, sibling = uuid.uuid4(), uuid.uuid4()
    assert (await acquire(firm, "e0", busy, engagement_cap=1))[0] is True
    granted, reason, _ = await acquire(firm, "e1", busy, engagement_cap=1)
    assert (granted, reason) == (False, "engagement_cap")
    assert (await acquire(firm, "s0", sibling, engagement_cap=1)) == (True, None, None)
    await release(firm, "e0")
    assert (await acquire(firm, "e1", busy, engagement_cap=1))[0] is True


async def test_ac7_the_engagement_cap_cannot_exceed_the_firm_cap(firm: Firm) -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    assert (await acquire(firm, "a0", a, firm_cap=2, engagement_cap=2))[0] is True
    assert (await acquire(firm, "b0", b, firm_cap=2, engagement_cap=2))[0] is True
    granted, reason, _ = await acquire(firm, "a1", a, firm_cap=2, engagement_cap=2)
    assert (granted, reason) == (False, "firm_cap")


async def test_ac6_the_class_capacity_holds_across_firms(firm: Firm, other: Firm) -> None:
    assert (await acquire(firm, "a0", capacity=2))[0] is True
    assert (await acquire(other, "b0", capacity=2))[0] is True
    granted, reason, _ = await acquire(other, "b1", capacity=2)
    assert (granted, reason) == (False, "class_capacity")


async def test_ac6_class_capacity_is_per_class(firm: Firm) -> None:
    assert (await acquire(firm, "i0", None, "interactive", capacity=1))[0] is True
    assert (await acquire(firm, "b0", None, "batch", capacity=1))[0] is True
    assert (await acquire(firm, "i1", None, "interactive", capacity=1))[1] == "class_capacity"


# --- the reason and the estimate: the caller's own counts only -----------------------------------


async def test_ac13_the_reason_comes_from_the_callers_own_counts_never_another_firms(
    seed: Seeder, firm: Firm, other: Firm
) -> None:
    await _occupy(seed, firm, 5)  # one firm fills the class, and is at its own cap
    granted, reason, _ = await acquire(other, "b0", capacity=5, firm_cap=1)
    # `other` holds nothing: it waits because the class is full, whatever `firm` is doing
    assert (granted, reason) == (False, "class_capacity")
    granted, reason, _ = await acquire(firm, "a-new", capacity=50, firm_cap=5)
    assert (granted, reason) == (False, "firm_cap")


async def test_ac13_the_engagement_reason_is_for_the_callers_own_engagement(
    seed: Seeder, firm: Firm
) -> None:
    engagement = uuid.uuid4()
    await seed.run(
        "INSERT INTO work_slots (tenant_id, holder, engagement_id, work_class, acquired_at, "
        "lease_until) VALUES ($1, 'e0', $2, 'interactive', now(), now() + interval '1 hour')",
        firm.tenant_id,
        engagement,
    )
    granted, reason, _ = await acquire(firm, "e1", engagement, engagement_cap=1)
    assert (granted, reason) == (False, "engagement_cap")


async def test_ac13_the_estimate_is_null_without_recent_grants(seed: Seeder, other: Firm) -> None:
    await _occupy(seed, other, 1)
    granted, reason, estimate = await acquire(other, "w", capacity=1)
    assert (granted, reason, estimate) == (False, "class_capacity", None)
    await seed.run("DELETE FROM work_grants")
    assert (await acquire(other, "w", capacity=1))[2] is None


async def test_ac13_the_estimate_is_a_whole_minute_in_the_near_future_with_recent_grants(
    seed: Seeder, firm: Firm
) -> None:
    await _occupy(seed, firm, 1)
    for _ in range(10):  # one a minute over the last ten
        await seed.run(
            "INSERT INTO work_grants (tenant_id, work_class, granted_at) "
            "VALUES ($1, 'interactive', now() - interval '2 minutes')",
            firm.tenant_id,
        )
    granted, reason, estimate = await acquire(firm, "w", capacity=1)
    assert (granted, reason) == (False, "class_capacity")
    assert estimate is not None
    assert (estimate.second, estimate.microsecond) == (0, 0)  # rounded up to whole minutes
    now = datetime.now(UTC)
    assert now < estimate <= now + timedelta(minutes=3)


async def test_ac13_grants_older_than_ten_minutes_give_no_estimate(
    seed: Seeder, firm: Firm
) -> None:
    await _occupy(seed, firm, 1)
    await seed.run(
        "INSERT INTO work_grants (tenant_id, work_class, granted_at) "
        "VALUES ($1, 'interactive', now() - interval '11 minutes')",
        firm.tenant_id,
    )
    assert (await acquire(firm, "w", capacity=1))[2] is None


async def test_ac13_a_decision_has_only_the_callers_own_fields(
    seed: Seeder, firm: Firm, other: Firm
) -> None:
    await _occupy(seed, other, 1)
    async with tenant_connection(firm.ctx) as conn:
        result = await conn.execute(
            text("SELECT * FROM work_slot_acquire('w', NULL, 'interactive', 20, 10, 1, 900)")
        )
        assert list(result.keys()) == ["granted", "reason", "estimated_start_at"]
        await conn.rollback()


# --- AC-8: fair order across firms, oldest first within a firm -----------------------------------


async def test_ac8_a_firm_granted_recently_waits_behind_a_firm_not_granted(
    seed: Seeder, firm: Firm, other: Firm
) -> None:
    assert (await acquire(firm, "a-first", capacity=1))[0] is True
    assert (await acquire(firm, "a-next", capacity=1))[1] == "class_capacity"  # older waiter
    assert (await acquire(other, "b-next", capacity=1))[1] == "class_capacity"
    await release(firm, "a-first")
    # a-next is older, but its firm was granted a moment ago: b-next goes first
    assert (await acquire(firm, "a-next", capacity=1))[0] is False
    assert (await acquire(other, "b-next", capacity=1))[0] is True
    assert await holders(seed) == {"b-next"}
    await release(other, "b-next")
    assert (await acquire(firm, "a-next", capacity=1))[
        0
    ] is True  # now b was granted more recently


async def test_ac8_firms_take_turns_when_both_always_have_waiters(
    seed: Seeder, firm: Firm, other: Firm
) -> None:
    order: list[str] = []
    assert (await acquire(other, "seed-holder", capacity=1))[0] is True
    pending = {"a": [f"a{n}" for n in range(3)], "b": [f"b{n}" for n in range(3)]}
    for holder in pending["a"]:
        await acquire(firm, holder, capacity=1)
    for holder in pending["b"]:
        await acquire(other, holder, capacity=1)
    await release(other, "seed-holder")
    who = {"a": firm, "b": other}
    for _ in range(6):
        for key in ("a", "b"):
            if pending[key] and (await acquire(who[key], pending[key][0], capacity=1))[0]:
                order.append(pending[key].pop(0))
                await release(who[key], order[-1])
                break
        else:
            pytest.fail("nobody was granted a free slot")
    firms = [name[0] for name in order]
    assert sorted(firms) == ["a"] * 3 + ["b"] * 3
    assert all(firms[i] != firms[i + 1] for i in range(5)), (
        order
    )  # round-robin: never twice in a row


async def test_ac8_within_a_firm_the_oldest_waiter_goes_first(seed: Seeder, firm: Firm) -> None:
    assert (await acquire(firm, "holder", capacity=1))[0] is True
    for name in ("w1", "w2", "w3"):
        assert (await acquire(firm, name, capacity=1))[1] == "class_capacity"
        await asyncio.sleep(0.02)
    await release(firm, "holder")
    assert (await acquire(firm, "w3", capacity=1))[0] is False
    assert (await acquire(firm, "w2", capacity=1))[0] is False
    assert (await acquire(firm, "w1", capacity=1))[0] is True


async def test_ac8_a_waiter_blocked_by_a_cap_does_not_hold_up_an_eligible_one(
    seed: Seeder, firm: Firm, other: Firm
) -> None:
    # firm is at its cap of 1 and is the oldest waiter; other is eligible and goes first
    assert (await acquire(firm, "a-held", firm_cap=1, capacity=2))[0] is True
    assert (await acquire(firm, "a-wait", firm_cap=1, capacity=2))[1] == "firm_cap"
    assert (await acquire(other, "b0", firm_cap=1, capacity=2))[0] is True


async def test_ac8_a_firms_grants_older_than_ten_minutes_no_longer_count_against_it(
    seed: Seeder, firm: Firm, other: Firm
) -> None:
    await seed.run(
        "INSERT INTO work_grants (tenant_id, work_class, granted_at) "
        "VALUES ($1, 'interactive', now() - interval '11 minutes')",
        firm.tenant_id,
    )
    await _occupy(seed, other, 1)
    assert (await acquire(firm, "a", capacity=2))[0] is True  # the old grant is forgotten


# --- leases and stale waiters --------------------------------------------------------------------


async def test_ac6_an_expired_lease_is_reclaimed_by_the_next_acquire(
    seed: Seeder, firm: Firm, other: Firm
) -> None:
    assert (await acquire(other, "crashed", capacity=1))[0] is True
    assert (await acquire(firm, "w", capacity=1))[1] == "class_capacity"
    await seed.run("UPDATE work_slots SET lease_until = now() - interval '1 second'")
    assert (await acquire(firm, "w", capacity=1))[0] is True
    assert await holders(seed) == {"w"}


async def test_ac6_a_live_lease_is_not_reclaimed(seed: Seeder, firm: Firm, other: Firm) -> None:
    assert (await acquire(other, "alive", capacity=1, lease=3600))[0] is True
    assert (await acquire(firm, "w", capacity=1))[0] is False
    assert await holders(seed) == {"alive"}


async def test_ac6_a_waiter_unseen_for_five_minutes_is_dropped(
    seed: Seeder, firm: Firm, other: Firm
) -> None:
    await seed.run(
        "INSERT INTO work_waiters (tenant_id, holder, engagement_id, work_class, waiting_since, "
        "last_seen) VALUES ($1, 'gone', NULL, 'interactive', now() - interval '1 hour', "
        "now() - interval '6 minutes')",
        other.tenant_id,
    )
    assert (await acquire(firm, "live", capacity=1))[0] is True  # 'gone' did not hold it up
    assert "gone" not in await waiters(seed)


async def test_ac6_a_waiter_unseen_for_over_three_minutes_does_not_hold_up_others(
    seed: Seeder, firm: Firm, other: Firm
) -> None:
    await seed.run(
        "INSERT INTO work_waiters (tenant_id, holder, engagement_id, work_class, waiting_since, "
        "last_seen) VALUES ($1, 'quiet', NULL, 'interactive', now() - interval '1 hour', "
        "now() - interval '4 minutes')",
        other.tenant_id,
    )
    assert (await acquire(firm, "live", capacity=1))[0] is True
    assert "quiet" in await waiters(
        seed
    )  # not yet dropped (under five minutes), just not eligible


async def test_ac6_a_waiter_that_asks_again_is_live_again(
    seed: Seeder, firm: Firm, other: Firm
) -> None:
    assert (await acquire(other, "holder", capacity=1))[0] is True
    assert (await acquire(other, "w-old", capacity=1))[1] == "class_capacity"
    await seed.run("UPDATE work_waiters SET last_seen = now() - interval '4 minutes'")
    assert (await acquire(other, "w-old", capacity=1))[1] == "class_capacity"  # seen again
    await seed.run("DELETE FROM work_slots")
    assert (await acquire(other, "w-new", capacity=1))[0] is False  # w-old is live and older
    assert (await acquire(other, "w-old", capacity=1))[0] is True


async def test_ac6_a_waiter_keeps_its_place_when_it_asks_again(seed: Seeder, firm: Firm) -> None:
    await _occupy(seed, firm, 1)
    await acquire(firm, "w", capacity=1)
    [first] = await seed.rows("SELECT waiting_since FROM work_waiters WHERE holder = 'w'")
    await asyncio.sleep(0.05)
    await acquire(firm, "w", capacity=1)
    [again] = await seed.rows("SELECT waiting_since FROM work_waiters WHERE holder = 'w'")
    assert first["waiting_since"] == again["waiting_since"]


async def test_ac6_a_firm_has_a_bounded_number_of_waiters_per_class(
    seed: Seeder, firm: Firm, other: Firm
) -> None:
    await _occupy(seed, other, 1)
    for n in range(4):  # 4 x max(firm_cap, 1)
        assert (await acquire(firm, f"w{n}", firm_cap=1, capacity=1))[1] == "class_capacity"
    granted, reason, estimate = await acquire(firm, "w4", firm_cap=1, capacity=1)
    assert (granted, reason, estimate) == (False, "firm_cap", None)
    assert await waiters(seed, firm) == {"w0", "w1", "w2", "w3"}  # w4 was not added
    assert (await acquire(firm, "w0", firm_cap=1, capacity=1))[1] == "class_capacity"  # known one
    # another class is unaffected
    assert (await acquire(firm, "b0", None, "batch", firm_cap=1, capacity=5))[0] is True


async def test_ac6_the_waiter_bound_follows_the_firm_cap(
    seed: Seeder, firm: Firm, other: Firm
) -> None:
    await _occupy(seed, other, 1)
    for n in range(8):  # 4 x 2
        assert (await acquire(firm, f"w{n}", firm_cap=2, capacity=1))[1] == "class_capacity"
    assert (await acquire(firm, "w8", firm_cap=2, capacity=1))[1] == "firm_cap"
    paused = Firm(await seed.firm())
    for n in range(5):  # a paused firm (cap 0) has 4 x 1 places, and waits with `firm_cap`
        assert (await acquire(paused, f"p{n}", firm_cap=0))[1] == "firm_cap"
    assert await waiters(seed, paused) == {"p0", "p1", "p2", "p3"}


# --- idempotent acquire, release, renew ----------------------------------------------------------


async def test_ac6_acquire_is_idempotent_and_renews_for_a_holder_already_holding(
    seed: Seeder, firm: Firm
) -> None:
    assert await acquire(firm, "h", firm_cap=1) == (True, None, None)
    await seed.run("UPDATE work_slots SET lease_until = now() + interval '10 seconds'")
    assert await acquire(firm, "h", firm_cap=1) == (True, None, None)  # even at its cap
    assert await holders(seed, firm) == {"h"}
    assert await seed.value("SELECT count(*) FROM work_slots") == 1
    assert await lease_of(seed, firm, "h") > datetime.now(UTC) + timedelta(seconds=800)
    assert await seed.value("SELECT count(*) FROM work_grants") == 1  # one grant, not two


async def test_ac6_a_holder_that_was_reclaimed_and_asks_again_waits_like_anyone(
    seed: Seeder, firm: Firm, other: Firm
) -> None:
    assert (await acquire(firm, "h", capacity=1))[0] is True
    await seed.run("UPDATE work_slots SET lease_until = now() - interval '1 second'")
    assert (await acquire(other, "x", capacity=1))[0] is True  # reclaims h
    assert (await acquire(firm, "h", capacity=1))[0] is False


async def test_ac6_the_lease_given_is_the_lease_asked_for(seed: Seeder, firm: Firm) -> None:
    await acquire(firm, "h", lease=120)
    left = (await lease_of(seed, firm, "h")) - datetime.now(UTC)
    assert timedelta(seconds=100) < left <= timedelta(seconds=121)


async def test_ac6_release_frees_the_slot_and_the_waiter_and_is_idempotent(
    seed: Seeder, firm: Firm
) -> None:
    await acquire(firm, "held")
    await _occupy(seed, firm, 1)
    await acquire(firm, "waiting", capacity=1)
    await release(firm, "held")
    await release(firm, "waiting")
    await release(firm, "never-seen")
    await release(firm, "held")
    assert "held" not in await holders(seed, firm)
    assert await waiters(seed, firm) == set()


async def test_ac6_renew_extends_a_held_lease_and_reports_unknown_holders(
    seed: Seeder, firm: Firm
) -> None:
    await acquire(firm, "h", lease=60)
    assert await renew(firm, "h", 900) is True
    assert await lease_of(seed, firm, "h") > datetime.now(UTC) + timedelta(seconds=800)
    assert await renew(firm, "never-granted") is False
    await release(firm, "h")
    assert await renew(firm, "h") is False


async def test_ac6_a_waiting_holder_cannot_renew(firm: Firm, other: Firm, seed: Seeder) -> None:
    await _occupy(seed, other, 1)
    await acquire(firm, "w", capacity=1)
    assert await renew(firm, "w") is False


# --- tenant isolation of the functions -----------------------------------------------------------


async def test_ac6_release_and_renew_work_only_within_the_callers_tenant(
    seed: Seeder, firm: Firm, other: Firm
) -> None:
    await acquire(firm, "mine")
    before = await lease_of(seed, firm, "mine")
    assert await renew(other, "mine") is False
    await release(other, "mine")  # someone else's holder: nothing happens
    assert await holders(seed, firm) == {"mine"}
    assert await lease_of(seed, firm, "mine") == before
    await release(firm, "mine")
    assert await holders(seed) == set()


async def test_ac6_a_waiter_cannot_be_released_by_another_tenant(
    seed: Seeder, firm: Firm, other: Firm
) -> None:
    await _occupy(seed, firm, 1)
    await acquire(firm, "w", capacity=1)
    await release(other, "w")
    assert await waiters(seed, firm) == {"w"}


async def test_ac6_the_same_holder_id_in_two_firms_never_crosses(
    seed: Seeder, firm: Firm, other: Firm
) -> None:
    assert (await acquire(firm, "same", capacity=5))[0] is True
    assert (await acquire(other, "same", capacity=5))[0] is True  # its own slot, not a renewal
    rows = await seed.rows("SELECT tenant_id FROM work_slots WHERE holder = 'same'")
    assert {r["tenant_id"] for r in rows} == {firm.tenant_id, other.tenant_id}
    await release(other, "same")
    assert await holders(seed, firm) == {"same"}
    assert await holders(seed, other) == set()


async def test_ac6_a_colliding_holder_waiting_in_another_firm_is_not_touched(
    seed: Seeder, firm: Firm, other: Firm
) -> None:
    await _occupy(seed, firm, 1)
    await acquire(firm, "same", capacity=1)
    await seed.run("UPDATE work_waiters SET last_seen = now() - interval '2 minutes'")
    [before] = await seed.rows("SELECT last_seen FROM work_waiters")
    assert (await acquire(other, "same", capacity=1))[1] == "class_capacity"
    rows = await seed.rows("SELECT tenant_id, last_seen FROM work_waiters ORDER BY last_seen")
    assert len(rows) == 2
    assert (
        next(r for r in rows if r["tenant_id"] == firm.tenant_id)["last_seen"]
        == before["last_seen"]
    )


# --- no tenant, invalid arguments ----------------------------------------------------------------


async def _as_app(migrated_db: Migrated, tenant: str | None) -> asyncpg.Connection:
    conn = await asyncpg.connect(migrated_db.app_url.replace("+asyncpg", ""))
    if tenant is not None:
        await conn.execute("SELECT set_config('app.tenant_id', $1, false)", tenant)
    return conn


ACQUIRE = "SELECT * FROM work_slot_acquire('h', NULL, "
CALLS = {
    "acquire": ACQUIRE + "'interactive', 1, 1, 1, 60)",
    "release": "SELECT work_slot_release('h')",
    "renew": "SELECT work_slot_renew('h', 60)",
}


@pytest.mark.parametrize("tenant", [None, ""])
@pytest.mark.parametrize("call", sorted(CALLS))
async def test_ac6_without_a_tenant_every_function_raises(
    migrated_db: Migrated, call: str, tenant: str | None
) -> None:
    conn = await _as_app(migrated_db, tenant)
    try:
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.fetch(CALLS[call])
    finally:
        await conn.close()


INVALID = {
    "unknown class": ACQUIRE + "'urgent', 1, 1, 1, 60)",
    "empty class": ACQUIRE + "'', 1, 1, 1, 60)",
    "negative firm cap": ACQUIRE + "'batch', -1, 1, 1, 60)",
    "negative engagement cap": ACQUIRE + "'batch', 1, -1, 1, 60)",
    "firm cap too big": ACQUIRE + "'batch', 10001, 1, 1, 60)",
    "engagement cap too big": ACQUIRE + "'batch', 1, 10001, 1, 60)",
    "zero capacity": ACQUIRE + "'batch', 1, 1, 0, 60)",
    "capacity too big": ACQUIRE + "'batch', 1, 1, 10001, 60)",
    "zero lease": ACQUIRE + "'batch', 1, 1, 1, 0)",
    "lease too long": ACQUIRE + "'batch', 1, 1, 1, 3601)",
    "renew zero lease": "SELECT work_slot_renew('h', 0)",
    "renew lease too long": "SELECT work_slot_renew('h', 3601)",
}


@pytest.mark.parametrize("name", sorted(INVALID))
async def test_ac6_invalid_arguments_raise_invalid_parameter_value(
    migrated_db: Migrated, name: str, firm: Firm
) -> None:
    conn = await _as_app(migrated_db, str(firm.tenant_id))
    try:
        with pytest.raises(asyncpg.InvalidParameterValueError):
            await conn.fetch(INVALID[name])
    finally:
        await conn.close()


@pytest.mark.parametrize(
    "call",
    [
        "SELECT * FROM work_slot_acquire('h', NULL, 'batch', 0, 0, 1, 1)",
        "SELECT * FROM work_slot_acquire('h', NULL, 'batch', 10000, 10000, 10000, 3600)",
        "SELECT work_slot_renew('h', 1)",
        "SELECT work_slot_renew('h', 3600)",
    ],
)
async def test_ac6_the_bounds_themselves_are_valid(
    migrated_db: Migrated, firm: Firm, call: str
) -> None:
    conn = await _as_app(migrated_db, str(firm.tenant_id))
    try:
        await conn.fetch(call)
    finally:
        await conn.close()


async def test_ac6_a_holder_that_is_empty_or_too_long_is_refused(
    migrated_db: Migrated, firm: Firm
) -> None:
    conn = await _as_app(migrated_db, str(firm.tenant_id))
    try:
        for holder in ("", "x" * 301):
            with pytest.raises(asyncpg.CheckViolationError):
                await conn.fetch(
                    "SELECT * FROM work_slot_acquire($1, NULL, 'batch', 1, 1, 1, 60)", holder
                )
        await conn.fetch(
            "SELECT * FROM work_slot_acquire($1, NULL, 'batch', 1, 1, 1, 60)", "x" * 300
        )
    finally:
        await conn.close()


# --- privileges: the app reaches the ledger only through the three functions ---------------------


@pytest.mark.parametrize("table", TABLES)
@pytest.mark.parametrize(
    "privilege", ["SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"]
)
async def test_ac6_the_app_has_no_privilege_on_the_ledger_tables(
    seed: Seeder, table: str, privilege: str
) -> None:
    assert (
        await seed.value("SELECT has_table_privilege('abacus_app', $1, $2)", table, privilege)
        is False
    )


@pytest.mark.parametrize("table", TABLES)
async def test_ac6_the_app_has_no_column_privileges_on_the_ledger_tables(
    seed: Seeder, table: str
) -> None:
    for privilege in ("SELECT", "INSERT", "UPDATE", "REFERENCES"):
        assert (
            await seed.value(
                "SELECT has_any_column_privilege('abacus_app', $1, $2)", table, privilege
            )
            is False
        )


@pytest.mark.parametrize("table", TABLES)
async def test_ac6_public_has_no_privilege_on_the_ledger_tables(seed: Seeder, table: str) -> None:
    grants = await seed.rows(
        "SELECT a.grantee, a.privilege_type FROM pg_class c, aclexplode(c.relacl) a "
        "WHERE c.oid = $1::regclass AND a.grantee <> c.relowner",
        table,
    )
    assert grants == []


@pytest.mark.parametrize("table", TABLES)
async def test_ac6_the_app_cannot_read_or_write_the_ledger_directly(
    migrated_db: Migrated, firm: Firm, table: str
) -> None:
    conn = await _as_app(migrated_db, str(firm.tenant_id))
    try:
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.fetch(READ[table])
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.execute(CLEAR[table])
    finally:
        await conn.close()


@pytest.mark.parametrize("table", TABLES)
async def test_ac6_the_ledger_tables_have_row_level_security_enabled_and_no_policy(
    seed: Seeder, table: str
) -> None:
    [row] = await seed.rows(
        "SELECT relrowsecurity, pg_get_userbyid(relowner) AS owner FROM pg_class "
        "WHERE oid = $1::regclass",
        table,
    )
    assert row["relrowsecurity"] is True
    assert row["owner"] == "abacus_owner"
    assert (
        await seed.value("SELECT count(*) FROM pg_policy WHERE polrelid = $1::regclass", table)
        == 0
    )


@pytest.mark.parametrize("name", sorted(FUNCTIONS))
async def test_ac6_the_app_may_execute_each_function_and_public_may_not(
    seed: Seeder, name: str
) -> None:
    signature = FUNCTIONS[name]
    assert (
        await seed.value("SELECT has_function_privilege('abacus_app', $1, 'EXECUTE')", signature)
        is True
    )
    public = await seed.value(
        "SELECT count(*) FROM pg_proc p, aclexplode(p.proacl) a "
        "WHERE p.oid = $1::regprocedure AND a.grantee = 0",
        signature,
    )
    assert public == 0
    for role in ("abacus_relay", "abacus_identity"):
        assert (
            await seed.value("SELECT has_function_privilege($1, $2, 'EXECUTE')", role, signature)
            is False
        )


async def test_ac6_the_app_can_execute_only_the_three_slot_functions(seed: Seeder) -> None:
    rows = await seed.rows(
        "SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
        "WHERE n.nspname = 'public' AND p.proname LIKE 'work_slot%' "
        "AND has_function_privilege('abacus_app', p.oid, 'EXECUTE')"
    )
    assert {r["proname"] for r in rows} == set(FUNCTIONS)


@pytest.mark.parametrize("name", sorted(FUNCTIONS))
async def test_ac6_each_function_is_a_pinned_definer_owned_by_the_owner_with_timeouts(
    seed: Seeder, name: str
) -> None:
    [row] = await seed.rows(
        "SELECT prosecdef, pg_get_userbyid(proowner) AS owner, "
        "coalesce(proconfig, '{}') AS config "
        "FROM pg_proc WHERE oid = $1::regprocedure",
        FUNCTIONS[name],
    )
    assert row["prosecdef"] is True
    assert row["owner"] == "abacus_owner"
    config = {str(c).split("=", 1)[0]: str(c).split("=", 1)[1] for c in row["config"]}
    assert config["search_path"] == "pg_catalog, public, pg_temp"
    assert config["lock_timeout"] == "5s"
    assert config["statement_timeout"] == "10s"


async def test_ac6_the_tables_are_listed_as_platform_tables_in_schema_check() -> None:
    for table in TABLES:
        assert table in sc.NON_TENANT_TABLES
        assert table in sc.GLOBAL_TABLES
        assert sc.TABLE_OWNERS[table] == "kernel.slots"
    assert {"work_slot_acquire", "work_slot_release", "work_slot_renew"} <= sc.DEFINER_FUNCTIONS


def test_ac6_schema_check_passes_on_the_migrated_database(migrated_db: Migrated) -> None:
    assert sc.check(migrated_db.owner_url, migrated_db.app_url) == []


# --- run columns: queued_reason and estimated_start_at -------------------------------------------

REASONS = ["firm_cap", "engagement_cap", "class_capacity", "provider_capacity", "deferred"]


@pytest.mark.parametrize("table", ["sync_runs", "agent_runs"])
async def test_ac13_the_app_may_update_the_two_queued_columns_and_the_old_columns_only(
    seed: Seeder, table: str
) -> None:
    for column in ("queued_reason", "estimated_start_at"):
        assert (
            await seed.value(
                "SELECT has_column_privilege('abacus_app', $1, $2, 'UPDATE')", table, column
            )
            is True
        )
        assert (
            await seed.value(
                "SELECT has_column_privilege('abacus_app', $1, $2, 'INSERT')", table, column
            )
            is False
        )
    assert (
        await seed.value(
            "SELECT has_column_privilege('abacus_app', $1, 'tenant_id', 'UPDATE')", table
        )
        is False
    )


async def _running_sync_run(world: World) -> uuid.UUID:
    started = await start_retrieval(
        world.requester.context(),
        engagement_id=world.engagement_id,
        request_item_id=world.item_id,
        period=PERIOD,
    )
    return started.run_id


@pytest.mark.parametrize("reason", REASONS)
async def test_ac13_a_running_sync_run_may_be_queued_with_each_reason(
    seed: Seeder, world: World, reason: str
) -> None:
    run_id = await _running_sync_run(world)
    await seed.run(
        "UPDATE sync_runs SET queued_reason = $2, estimated_start_at = now() WHERE id = $1",
        run_id,
        reason,
    )
    assert await seed.value("SELECT queued_reason FROM sync_runs WHERE id = $1", run_id) == reason


async def test_ac13_an_unknown_queued_reason_is_a_check_violation(
    seed: Seeder, world: World
) -> None:
    run_id = await _running_sync_run(world)
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.run("UPDATE sync_runs SET queued_reason = 'because' WHERE id = $1", run_id)


async def test_ac13_a_queued_reason_needs_the_reason_not_the_status(
    seed: Seeder, world: World
) -> None:
    run_id = await _running_sync_run(world)
    await seed.run("UPDATE sync_runs SET estimated_start_at = now() WHERE id = $1", run_id)
    assert await seed.value("SELECT queued_reason FROM sync_runs WHERE id = $1", run_id) is None


@pytest.mark.parametrize(
    "assignment", ["queued_reason = 'firm_cap'", "estimated_start_at = now()"]
)
async def test_ac13_a_sync_run_that_is_not_running_must_have_both_null(
    seed: Seeder, world: World, assignment: str
) -> None:
    run_id = await _running_sync_run(world)
    await seed.run(ASSIGN[assignment], run_id)
    with pytest.raises(asyncpg.CheckViolationError):  # ending it without clearing is refused
        await seed.run(
            "UPDATE sync_runs SET status = 'failed', failure_code = 'internal_error', "
            "finished_at = now() WHERE id = $1",
            run_id,
        )
    await seed.run(
        "UPDATE sync_runs SET queued_reason = NULL, estimated_start_at = NULL, "
        "status = 'failed', failure_code = 'internal_error', finished_at = now() WHERE id = $1",
        run_id,
    )
    assert await seed.value("SELECT status FROM sync_runs WHERE id = $1", run_id) == "failed"


async def test_ac13_a_finished_agent_run_must_have_both_null_and_reasons_are_checked(
    seed: Seeder, world: World
) -> None:
    result = await retrieve(world)
    made = await ActivityEnvironment().run(
        create_run_activity,
        ScreeningInput(
            str(world.tenant_id),
            str(result.evidence_version_id),
            str(uuid.uuid4()),
            str(world.requester.user_id),
        ),
    )
    assert isinstance(made, str)
    run_id = uuid.UUID(made)
    await seed.run("UPDATE agent_runs SET queued_reason = 'class_capacity' WHERE id = $1", run_id)
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.run("UPDATE agent_runs SET queued_reason = 'because' WHERE id = $1", run_id)
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.run(
            "UPDATE agent_runs SET status = 'failed', failure_code = 'cancelled', "
            "finished_at = now() WHERE id = $1",
            run_id,
        )
    await seed.run(
        "UPDATE agent_runs SET queued_reason = NULL, status = 'failed', "
        "failure_code = 'cancelled', finished_at = now() WHERE id = $1",
        run_id,
    )
    assert await seed.value("SELECT status FROM agent_runs WHERE id = $1", run_id) == "failed"


async def test_ac13_the_app_can_set_and_clear_the_queued_columns_on_a_running_run(
    seed: Seeder, world: World
) -> None:
    run_id = await _running_sync_run(world)
    ctx = TenantContext(world.tenant_id, "system", "test")
    async with tenant_connection(ctx) as conn:
        await conn.execute(
            text(
                "UPDATE sync_runs SET queued_reason = 'firm_cap', estimated_start_at = now() "
                "WHERE id = :id"
            ),
            {"id": run_id},
        )
        await conn.commit()
    assert (
        await seed.value("SELECT queued_reason FROM sync_runs WHERE id = $1", run_id) == "firm_cap"
    )
    async with tenant_connection(ctx) as conn:
        await conn.execute(
            text(
                "UPDATE sync_runs SET queued_reason = NULL, estimated_start_at = NULL "
                "WHERE id = :id"
            ),
            {"id": run_id},
        )
        await conn.commit()
    assert await seed.value("SELECT queued_reason FROM sync_runs WHERE id = $1", run_id) is None


async def test_ac13_the_app_cannot_use_the_columns_to_reach_other_tenants_runs(
    seed: Seeder, world: World, other: Firm
) -> None:
    run_id = await _running_sync_run(world)
    async with tenant_connection(other.ctx) as conn:
        result = await conn.execute(
            text("UPDATE sync_runs SET queued_reason = 'firm_cap' WHERE id = :id RETURNING id"),
            {"id": run_id},
        )
        assert result.all() == []
        await conn.commit()
    assert await seed.value("SELECT queued_reason FROM sync_runs WHERE id = $1", run_id) is None


# --- migration 0013, down and up -----------------------------------------------------------------


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _revision(database: sc.Database) -> str:
    return str(
        asyncio.run(
            Seeder(database.superuser_dsn).value("SELECT version_num FROM alembic_version")
        )
    )


async def _exists(seed: Seeder) -> dict[str, object]:
    return {
        "tables": await seed.value(
            "SELECT count(*) FROM pg_class WHERE relname IN ('work_slots', 'work_waiters', "
            "'work_grants') AND relkind = 'r'"
        ),
        "functions": await seed.value(
            "SELECT count(*) FROM pg_proc WHERE proname LIKE 'work_slot%'"
        ),
        "columns": await seed.value(
            "SELECT count(*) FROM information_schema.columns WHERE table_name IN "
            "('sync_runs', 'agent_runs') AND column_name IN "
            "('queued_reason', 'estimated_start_at')"
        ),
        "constraints": await seed.value(
            "SELECT count(*) FROM pg_constraint WHERE conname IN "
            "('sync_runs_queued_running', 'agent_runs_queued_running')"
        ),
    }


def test_ac13_migration_0013_downgrades_and_upgrades_again(private_db: sc.Database) -> None:
    seed = Seeder(private_db.superuser_dsn)
    head = _revision(private_db)  # 0013 or a later migration on top of it
    assert head >= "0013"
    assert asyncio.run(_exists(seed)) == {
        "tables": 3,
        "functions": 3,
        "columns": 4,
        "constraints": 2,
    }
    asyncio.run(
        seed.run(
            "INSERT INTO work_slots (holder, tenant_id, work_class, acquired_at, lease_until) "
            "VALUES ('h', gen_random_uuid(), 'batch', now(), now() + interval '1 hour')"
        )
    )
    migrate(private_db.owner_url, "0012", down=True)
    assert _revision(private_db) == "0012"
    assert asyncio.run(_exists(seed)) == {
        "tables": 0,
        "functions": 0,
        "columns": 0,
        "constraints": 0,
    }
    migrate(private_db.owner_url, "head")
    assert _revision(private_db) == head
    assert asyncio.run(_exists(seed))["tables"] == 3
    assert asyncio.run(seed.value("SELECT count(*) FROM work_slots")) == 0
    assert sc.check(private_db.owner_url, private_db.app_url) == []


def test_ac13_after_a_round_trip_the_functions_and_grants_work_again(
    private_db: sc.Database,
) -> None:
    seed = Seeder(private_db.superuser_dsn)

    async def work() -> None:
        tenant = await seed.firm()
        conn = await asyncpg.connect(private_db.app_url.replace("+asyncpg", ""))
        try:
            await conn.execute("SELECT set_config('app.tenant_id', $1, false)", str(tenant))
            row = await conn.fetchrow(
                "SELECT * FROM work_slot_acquire('h', NULL, 'batch', 5, 2, 10, 60)"
            )
            assert row is not None
            assert row["granted"] is True
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await conn.fetch("SELECT * FROM work_slots")
        finally:
            await conn.close()
        assert (
            await seed.value(
                "SELECT has_column_privilege('abacus_app', 'sync_runs', 'queued_reason', 'UPDATE')"
            )
            is True
        )

    asyncio.run(work())
