"""Q-03-T087: red batch runs resolved within one working day (the integration lane).

Acceptance: every red batch run of the period is resolved within one working day and no
generated file is hand-merged (the latter is `make check-generated` and the API client's drift
check). These tests pin the measurement: which runs count, how a red streak ends, and that a
weekend does not count against the lane.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from abacus_tools.ci import integration_lane as lane


def _run(i: int, when: str, conclusion: str, branch: str = "main") -> dict[str, object]:
    return {
        "databaseId": i,
        "headBranch": branch,
        "headSha": f"{i:040x}",
        "status": "completed",
        "conclusion": conclusion,
        "createdAt": when,
        "updatedAt": when,
    }


def test_only_main_and_batch_branches_and_red_or_green_runs_count() -> None:
    raw = [
        _run(1, "2027-05-03T10:00:00Z", "failure"),
        _run(2, "2027-05-03T11:00:00Z", "failure", "s15c-q03-t087"),  # a task branch
        _run(3, "2027-05-03T12:00:00Z", "cancelled"),
        _run(4, "2027-05-03T13:00:00Z", "success", "review-s15b"),
        _run(5, "2027-05-03T14:00:00Z", "timed_out", "batch-s16"),
        {**_run(6, "2027-05-03T15:00:00Z", "success"), "status": "in_progress"},
    ]
    assert [r.id for r in lane.runs(raw)] == [1, 4, 5]


def test_a_streak_ends_at_the_next_green_on_its_own_branch() -> None:
    found = lane.runs(
        [
            _run(1, "2027-05-03T10:00:00Z", "failure"),
            _run(2, "2027-05-03T12:00:00Z", "failure"),
            _run(3, "2027-05-03T13:00:00Z", "success", "review-x"),  # another branch
            _run(4, "2027-05-03T16:00:00Z", "success"),
        ]
    )
    (streak,) = [s for s in lane.streaks(found) if s.branch == "main"]
    assert (streak.first_red.id, streak.reds, streak.green and streak.green.id) == (1, 2, 4)


def test_a_weekend_does_not_count_against_the_lane() -> None:
    friday = datetime(2027, 5, 7, 18, tzinfo=UTC)
    monday = datetime(2027, 5, 10, 12, tzinfo=UTC)
    assert lane.working_time(friday, monday) == timedelta(hours=6 + 12)


def test_more_than_one_working_day_breaches_and_less_does_not() -> None:
    now = datetime(2027, 5, 12, 12, tzinfo=UTC)
    quick = lane.streaks(
        lane.runs(
            [
                _run(1, "2027-05-03T10:00:00Z", "failure"),
                _run(2, "2027-05-04T09:00:00Z", "success"),
            ]
        )
    )
    slow = lane.streaks(
        lane.runs(
            [
                _run(3, "2027-05-03T10:00:00Z", "failure"),
                _run(4, "2027-05-04T11:00:00Z", "success"),
            ]
        )
    )
    assert not quick[0].breached(now) and slow[0].breached(now)


def test_an_unresolved_streak_counts_up_to_now_and_is_reported_still_red() -> None:
    found = lane.streaks(lane.runs([_run(1, "2027-05-03T10:00:00Z", "failure")]))
    now = datetime(2027, 5, 5, 10, tzinfo=UTC)
    assert found[0].green is None and found[0].breached(now)
    assert "**still red**" in lane.report(found, now)


def test_main_exits_one_on_a_breach_and_writes_the_table(tmp_path: Path) -> None:
    runs = tmp_path / "runs.json"
    runs.write_text(
        json.dumps(
            [
                _run(1, "2027-05-03T10:00:00Z", "failure"),
                _run(2, "2027-05-06T10:00:00Z", "success"),
            ]
        ),
        encoding="utf-8",
    )
    out = tmp_path / "lane.md"
    assert lane.main(["--runs", str(runs), "--md", str(out)]) == 1
    assert "| no |" in out.read_text(encoding="utf-8")
    assert lane.main(["--runs", str(runs), "--since", "2027-05-04"]) == 0  # only the green remains
