"""Q-01-T30: the canary's checks in code (Q-01 F6): INV-2 over the flags, the route the boundary
allows, the page on the second consecutive failure only, and its Schedule only where an
environment names a canary firm."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import timedelta

import pytest

from abacus.kernel.config import settings
from abacus.modules.platform import api as platform
from abacus.modules.platform.api import (
    CanaryFlag,
    CanaryInput,
    CanaryWorkflow,
    expected_route,
    inv2_violations,
    should_page,
)
from abacus_tools import schedules


@pytest.mark.parametrize(
    ("flags", "broken"),
    [
        ((), []),
        ((CanaryFlag("a", (True,), False),), []),
        ((CanaryFlag("a", (False, True), False),), []),
        ((CanaryFlag("a", (False,), True),), []),  # shown Uncited
        ((CanaryFlag("a", (), True),), []),  # Uncited, nothing claimed
        ((CanaryFlag("a", (False,), False),), ["a"]),  # shown cited, nothing verified
        ((CanaryFlag("a", (), False),), ["a"]),
        ((CanaryFlag("a", (True, None), False),), ["a"]),  # a citation never checked
        ((CanaryFlag("a", (None,), True),), ["a"]),
        ((CanaryFlag("a", (True,), False), CanaryFlag("b", (False,), False)), ["b"]),
    ],
)
def test_inv2_every_flag_is_verified_or_shown_uncited(
    flags: tuple[CanaryFlag, ...], broken: list[str]
) -> None:
    assert inv2_violations(flags) == broken


def test_the_boundary_allows_one_route() -> None:
    assert expected_route("synthetic_only") == "fake"
    assert expected_route("client_data") == "bedrock"


@pytest.mark.parametrize(
    ("passed", "previous", "page"),
    [
        (True, [], False),
        (True, [True, True], False),
        (False, [], False),  # the first failure ever
        (False, [False], False),  # the first after a pass
        (False, [True], True),  # the second, with nothing before it
        (False, [True, False], True),  # the second after a pass
        (False, [True, True], False),  # the third: already paged
        (False, [False, True], False),
    ],
)
def test_pages_on_the_second_consecutive_failure_only(
    passed: bool, previous: list[bool], page: bool
) -> None:
    assert should_page(passed, previous) is page


@pytest.fixture
def canary_firm(monkeypatch: pytest.MonkeyPatch) -> Iterator[uuid.UUID]:
    tenant = uuid.uuid4()
    monkeypatch.setenv("ABACUS_CANARY_TENANT_ID", str(tenant))
    settings.cache_clear()
    yield tenant
    monkeypatch.undo()
    settings.cache_clear()


def test_no_canary_schedule_without_a_canary_firm() -> None:
    assert [job.id for job in platform.schedules()] == ["spend_anomaly:platform"]


def test_the_canary_runs_every_15_minutes_on_the_time_sensitive_queue(
    canary_firm: uuid.UUID,
) -> None:
    jobs = {job.id: job for job in schedules.declared()}
    job = jobs[f"canary:{canary_firm}"]
    assert job.workflow is CanaryWorkflow
    assert job.every == timedelta(minutes=15)
    assert job.arg == CanaryInput(str(canary_firm))
    assert platform.WORKFLOWS[CanaryWorkflow] == "time_sensitive"
    assert set(jobs) == {
        "access_end:platform",  # G-01-T13: seasonal access end, hourly (DEC-383)
        "audit_anchor:platform",  # Q-02-T21
        "audit_chain_verify:platform",  # Q-02-T21
        "audit_checkpoint:platform",  # Q-02-T20, T21
        "audit_labels:platform",  # G-02-T10 (DEC-453)
        "audit_partitions:platform",  # Q-02-T20
        "auth_session_purge:platform",  # G-02-T14
        "notification_purge:platform",
        "ses_events:platform",
        "spend_anomaly:platform",
        f"canary:{canary_firm}",
    }
