"""W-01-T18 (TASK-8333; ADR-078): AC suite 2 for N's red Connect work, written outside the
implementing sessions from W-01 §3 F4, F5 and SPEC acceptance AC-13 to AC-16, AC-27 to AC-30.

ac-test-author: ayushkbhatia

- AC-13/14: health transitions over every (status, probe) pair: only connected and
  needs-attention installs move; a refused token is always one step to Needs reauth.
- AC-15: the admission precondition across every install status.
- AC-16: a scripted sequence of probes writes at most one event per change (one notification).
- AC-27 to AC-30 (membership-end revocation, client-company walls, fake-adapter refusal,
  retention registration) run against Postgres at the end pass with W-01-T15's projection.
"""

from __future__ import annotations

import itertools

import pytest

from abacus.modules.integrations.dependents import admission_failure
from abacus.modules.integrations.health import FAILURES_TO_ATTENTION, Probe, Status, transition

STATUSES: tuple[Status, ...] = (
    "connecting",
    "connected",
    "needs_attention",
    "needs_reauth",
    "paused",
    "disconnected",
)
PROBES: tuple[Probe, ...] = ("ok", "unauthorized", "server_error", "timeout", "throttled")
MOVABLE = frozenset({"connected", "needs_attention"})


@pytest.mark.parametrize(("status", "probe"), list(itertools.product(STATUSES, PROBES)))
def test_ac13_only_connected_or_needs_attention_installs_move(
    status: Status, probe: Probe
) -> None:
    step = transition(status, probe, 0)
    if status not in MOVABLE:
        assert (step.status, step.event) == (status, None)
    if status in MOVABLE and probe == "unauthorized":
        assert (step.status, step.event) == ("needs_reauth", "token_expired")


def test_ac14_needs_attention_only_after_the_threshold_and_never_before() -> None:
    step = transition("connected", "server_error", 0)
    seen: list[str] = []
    for _ in range(FAILURES_TO_ATTENTION - 1):
        seen.append(step.status)
        step = transition(step.status, "server_error", step.failures)
    assert set(seen) == {"connected"}
    assert step.status == "needs_attention"


@pytest.mark.parametrize("status", STATUSES)
def test_ac15_admission_admits_only_a_connected_install(status: str) -> None:
    found = admission_failure(["cch_axcess_tax"], {"cch_axcess_tax": status})
    assert (found is None) == (status == "connected")
    if status == "needs_reauth":
        assert found == ("cch_axcess_tax", "integration_reauth_required")


def test_ac16_a_probe_sequence_writes_one_event_per_change() -> None:
    probes: list[Probe] = [
        "ok",
        "unauthorized",
        "unauthorized",
        "ok",
        "server_error",
        "unauthorized",
    ]
    status: Status = "connected"
    failures = 0
    events: list[str] = []
    for probe in probes:
        step = transition(status, probe, failures)
        if step.event is not None:
            events.append(step.event)
        status, failures = step.status, step.failures
    assert events == ["token_expired"]
    assert status == "needs_reauth"
