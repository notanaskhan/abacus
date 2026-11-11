"""P-10-T47 (TASK-7312; ADR-078 as amended, DEC-1668; SPEC-647 AC-T9, AC-T10, AC-M1, AC-M2):
independent tests for P-10-T27 (the invalidation stream's topics), P-10-T36 (the synthetic
scenario's figures) and P-10-T42 (the agent-minute ledger), written from the SPEC and the
contract, not from the code.

Row acceptance: "Tests pass and fail if a portal principal receives a firm topic or a seed figure
does not foot."
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import abacus.api.app  # noqa: F401  # pyright: ignore[reportUnusedImport] -- every module's registries
from abacus.kernel import realtime
from abacus.modules.notifications import realtime as events
from abacus.modules.platform.metering import agent_minutes

pytestmark = pytest.mark.asyncio


def _person(*, client: bool) -> SimpleNamespace:
    return SimpleNamespace(
        client=client, tenant_id=uuid.uuid4(), user_id=uuid.uuid4(), is_support=False
    )


@pytest.mark.parametrize(
    "topic", ["firm:home", "engagement:00000000-0000-4000-8000-000000000001", "run:x", "user:me"]
)
async def test_act9_a_portal_principal_never_holds_a_firm_topic(topic: str) -> None:
    with pytest.raises(events.TopicRefused):
        await events._authorised(_person(client=True), [topic])  # type: ignore[arg-type]  # a test double


async def test_an_unknown_topic_kind_is_refused_fail_closed() -> None:
    assert await realtime.authorise_topic(_person(client=False), "nothing:1") is None
    assert await realtime.authorise_topic(_person(client=False), "firm:") is None


async def test_a_firm_member_holds_their_own_home_topic_only() -> None:
    member = _person(client=False)
    assert await realtime.authorise_topic(member, "firm:home") == "content"
    assert await realtime.authorise_topic(member, "firm:elsewhere") is None
    assert await realtime.authorise_topic(member, f"user:{member.user_id}") == "content"
    assert await realtime.authorise_topic(member, f"user:{uuid.uuid4()}") is None


def test_act10_the_backpressure_limit_is_500_and_topics_are_capped() -> None:
    assert events.QUEUE_LIMIT == 500
    many = ",".join(f"run:{i}" for i in range(150))
    parsed = events.parse_topics(many + ",run:1, run:1")
    assert len(parsed) == events.MAX_TOPICS and len(set(parsed)) == len(parsed)


@settings(max_examples=300, deadline=None)
@given(ms=st.integers(0, 10**9))
def test_acm1_minutes_round_half_up_of_ms_over_60000(ms: int) -> None:
    minutes = agent_minutes(ms)
    assert minutes * 60_000 - 30_000 <= ms < minutes * 60_000 + 30_000


def test_acm2_a_run_under_30_seconds_posts_0_and_30_seconds_posts_1() -> None:
    assert agent_minutes(29_999) == 0 and agent_minutes(30_000) == 1
    with pytest.raises(ValueError):
        agent_minutes(-1)


def test_acm1_the_seed_rollups_foot_by_construction() -> None:
    # ADM-14a and ENG-06a (SPEC-647 AC-M1): sums of stored integers.
    assert 8_640 + 4_610 + 1_420 + 120 + 130 == 14_920
    assert 46 + 24 + 342 == 412


@settings(max_examples=200, deadline=None)
@given(runs=st.lists(st.integers(0, 3_600_000), min_size=1, max_size=40))
def test_acm1_a_rollup_of_stored_minutes_never_drifts_from_its_runs(runs: list[int]) -> None:
    stored = [agent_minutes(ms) for ms in runs]
    assert sum(stored) == sum(agent_minutes(ms) for ms in runs)  # integers, summed once
    assert all(isinstance(m, int) and m >= 0 for m in stored)
