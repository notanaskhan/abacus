"""P-10-T51 (TASK-7428): the stream subjects the runtime scenario signs in as, offline."""

from __future__ import annotations

import uuid

import pytest

from abacus_tools.loadtest import stream_subjects as ss
from abacus_tools.loadtest.scenario import profile
from abacus_tools.synthetic.scenarios.brightwater_hale.loader import LoadRefused


def test_the_runtime_scenario_needs_250_subjects_at_six_streams_each() -> None:
    assert ss.runtime_subjects() == 250
    assert [ss.subjects_for(n) for n in (1, 6, 7, 1500, 2000)] == [1, 1, 2, 250, 334]
    assert ss.subjects_for(2000) <= ss.MAX_SUBJECTS


def test_the_subjects_are_the_scenarios_own_names() -> None:
    (stream,) = profile("runtime_v2").streams
    named = sorted(set(stream.subjects()))
    assert named == [ss.subject(ss.PREFIX, k) for k in range(250)]


def test_each_subject_has_a_stable_user_id() -> None:
    assert ss.subject_user(ss.PREFIX, 3) == ss.subject_user(ss.PREFIX, 3)
    assert ss.subject_user(ss.PREFIX, 3) != ss.subject_user(ss.PREFIX, 4)
    assert isinstance(ss.subject_user(ss.PREFIX, 0), uuid.UUID)


@pytest.mark.parametrize("count", [0, ss.MAX_SUBJECTS + 1])
async def test_a_count_outside_the_range_is_refused_before_connecting(count: int) -> None:
    with pytest.raises(LoadRefused, match="count is 1 to"):
        await ss.load("postgresql://nowhere.invalid/db", uuid.uuid4(), count=count)
