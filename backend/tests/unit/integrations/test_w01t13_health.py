"""W-01-T13 (red): the health rule. A scripted 401 marks the install Needs reauth within one tick
and writes one token_expired event; repeated probes change nothing more (one notification)."""

from __future__ import annotations

import pytest

from abacus.modules.integrations.health import Status, transition


def test_ac_a_401_marks_needs_reauth_within_one_tick_with_one_event() -> None:
    step = transition("connected", "unauthorized", 0)
    assert (step.status, step.event, step.reason) == (
        "needs_reauth",
        "token_expired",
        "token_expired",
    )
    again = transition(step.status, "unauthorized", 0)
    assert again.event is None and again.status == "needs_reauth"  # never twice
    assert transition("needs_reauth", "ok", 0).status == "needs_reauth"  # only a reconnect


def test_three_server_errors_in_a_row_need_attention_and_a_healthy_probe_recovers() -> None:
    s = transition("connected", "server_error", 0)
    s = transition(s.status, "timeout", s.failures)
    assert s.status == "connected" and s.failures == 2
    s = transition(s.status, "server_error", s.failures)
    assert (s.status, s.event) == ("needs_attention", "health_failed")
    back = transition(s.status, "ok", s.failures)
    assert (back.status, back.event) == ("connected", "health_recovered")


@pytest.mark.parametrize("status", ["paused", "connecting", "disconnected"])
def test_the_monitor_never_moves_a_paused_connecting_or_disconnected_install(
    status: Status,
) -> None:
    assert transition(status, "unauthorized", 0).event is None


def test_a_throttle_changes_nothing() -> None:
    assert transition("connected", "throttled", 1).failures == 1
