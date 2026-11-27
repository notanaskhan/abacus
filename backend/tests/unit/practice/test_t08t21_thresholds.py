"""T-08-T21 (TASK-9016; DEC-6022): the threshold a deadline has reached, by days left."""

from __future__ import annotations

from abacus.modules.practice.deadline_alerts import threshold_for


def test_t08t21_thresholds_by_days_left() -> None:
    assert [threshold_for(d) for d in (-1, 0, 1, 2, 7, 8)] == [
        None, "t_minus_1", "t_minus_1", "t_minus_7", "t_minus_7", None,
    ]  # fmt: skip
