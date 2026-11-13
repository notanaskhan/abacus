"""W-02-T13 (TASK-7714; W-02 §5.3; DEC-4717): WB-01's sessions in the scenario.

Row acceptance: "seed-demo equals fixture mode; figures foot." The slice's rows are the fixture's
(same titles, same stable ids, same order and states), Copperleaf's row carries Copperleaf in its
client scope (Hannah sees it locked), rows 2 and 5 are via Agent, and three close runs run.
"""

from __future__ import annotations

import re
from pathlib import Path

from abacus_tools.synthetic.scenarios.brightwater_hale import workbench_slice as wb
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import slice_events

FIXTURE = (
    Path(__file__).resolve().parents[4] / "apps/web/src/fixtures/seed/tpl04-sessions.ts"
).read_text()


def test_the_eight_rows_are_the_fixtures_in_order() -> None:
    titles = re.findall(r'title: "([^"]+)"', FIXTURE)[:8]
    assert [r[2] for r in wb.ROWS] == titles
    keys = re.findall(r'stableId\("session:([a-z0-9-]+)"\)', FIXTURE)
    assert [r[0] for r in wb.ROWS] == keys[: len(wb.ROWS)]


def test_row_states_via_agent_and_the_locked_copperleaf_row() -> None:
    states = [r[4] for r in wb.ROWS]
    assert states[0] == "awaiting_answer" and states[1] == "ready_for_review"
    via = [i + 1 for i, r in enumerate(wb.ROWS) if r[3] != "manual"]
    assert via == [2, 5]
    assert [r[6] for r in wb.ROWS].count(wb.COPPERLEAF) == 1


def test_three_close_runs_run_and_every_event_is_on_the_slice() -> None:
    assert len(wb.CLOSE_RUNS) == 3
    events = slice_events(wb.SLICE)
    recorded = [e for e in events if e.kind == "workbench.session_recorded"]
    assert len(recorded) == 11
    assert sum(1 for e in recorded if e.data["state"] == "running") == 3
