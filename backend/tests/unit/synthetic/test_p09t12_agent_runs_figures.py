"""P-09-T12 (TASK-6521; DEC-3121): the E0 runs' figures foot.

Row acceptance: "Footing tests prove 2,625, 79 = 10 + 26 + 26 + 17, 14 = 1 + 5 + 1 + 4 + 3 and
73,166.90 - 1,684.54 = 71,482.36."
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

BOOK = json.loads(
    (Path(__file__).resolve().parents[2] / "golden" / "scenario" / "brightwater_hale"
     / "agent_runs_figures.json").read_text()
)  # fmt: skip


def test_4118_reads_2625_records() -> None:
    read = BOOK["run_4118"]["records_read"]
    assert read["returns"] + read["engagements"] + read["binders"] + read["activity"] == 2625
    assert read["total"] == 2625


def test_79_open_returns() -> None:
    assert sum(BOOK["run_4118"]["open_returns"]["parts"]) == 79 == BOOK["run_4118"]["citations"]


def test_4127_has_14_workpapers_over_5_levels() -> None:
    levels = BOOK["run_4127"]["levels"]
    assert len(levels) == 5 and sum(levels) == 14 == BOOK["run_4127"]["workpapers"]


def test_copperleaf_square_net() -> None:
    sq = {k: Decimal(v) for k, v in BOOK["copperleaf_run_2"]["square"].items()}
    assert sq["gross"] - sq["fees"] == sq["net"] == Decimal("71482.36")
    run = BOOK["copperleaf_run_2"]
    assert run["done"] + run["running"] == run["steps"] == 9


def test_the_slice_records_4127_from_the_book() -> None:
    from abacus_tools.synthetic.scenarios.brightwater_hale import agent_runs_slice as s

    event, *later = s.agent_runs_events()
    assert event.kind == "agents.run_recorded"
    # P-10-T36: after the 9:41 snapshot, internal control fails (9:58) and materiality is decided
    # (11:12), each a later event, so a 9:41 load is the same run P-09-T12 recorded.
    assert [e.kind for e in later] == ["agents.run_step_advanced"] * 2
    assert all(e.at > event.at for e in later)
    steps = event.data["steps"]
    assert len(steps) == 14  # type: ignore[arg-type]  # a list
    assert [st["level"] for st in steps].count(2) == 5  # type: ignore[index, union-attr]  # dicts
