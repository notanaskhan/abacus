"""P-02-T13 (TASK-7723; P-02 §10 item 6; DEC-4726): the search load test's verdict and guards.

The 1M-document run itself is local and manual (`loadtest/search.py`); here: P-02's two targets
are applied as written, the run report is read the way `run.py` writes it, a hosted environment
is refused, and the profile carries the 250 ms first-group target.
"""

from __future__ import annotations

import pytest

from abacus_tools.loadtest import search
from abacus_tools.loadtest.scenario import profile


def _report(p95: float | None) -> dict[str, object]:
    groups: list[dict[str, object]] = [{"name": "search_all", "p95_ms": 900.0}]
    if p95 is not None:
        groups.append({"name": "search_first", "p95_ms": p95})
    return {
        "scenario": "search_december",
        "started_at": "2026-09-14T14:24:00+00:00",
        "groups": groups,
    }


def test_the_first_group_p95_is_read_from_the_run_report() -> None:
    assert search.first_group_p95(_report(212.0)) == 212.0
    assert search.first_group_p95(_report(None)) is None


def test_both_targets_pass_at_and_under_their_limits() -> None:
    verdict = search.judge(250.0, 40, 5.0, 1_000_000, 1_000_000)
    assert verdict.passed, verdict.failures


@pytest.mark.parametrize(
    ("p95", "lag_n", "lag", "docs", "why"),
    [
        (251.0, 40, 1.0, 1_000_000, "first-group p95"),
        (None, 40, 1.0, 1_000_000, "no search_first group"),
        (120.0, 40, 5.5, 1_000_000, "relay lag p95"),
        (120.0, 0, None, 1_000_000, "no document was reindexed"),
        (120.0, 40, 1.0, 999_999, "under 1000000"),
    ],
)
def test_a_missed_target_fails_and_says_which(
    p95: float | None, lag_n: int, lag: float | None, docs: int, why: str
) -> None:
    verdict = search.judge(p95, lag_n, lag, docs, 1_000_000)
    assert not verdict.passed
    assert any(why in f for f in verdict.failures), verdict.failures


def test_a_hosted_environment_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Settings:
        environment = "staging"

    monkeypatch.setattr(search, "settings", lambda: _Settings())
    assert search.main(["clean", "--tenant", "00000000-0000-0000-0000-000000000001"]) == 2


def test_the_december_profile_holds_the_first_group_target() -> None:
    december = profile("search_december")
    first = next(g for g in december.groups if g.name == "search_first")
    assert first.p95_ms == search.FIRST_GROUP_P95_MS
    assert all(s.method == "POST" for s in first.steps)  # search text only in a POST body
