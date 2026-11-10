"""P-10-T36 (TASK-6721; P-10 §3.4, SHL-13, WB-09, AUD-02): the runtime scenario's later run
states, the export profile at the 9:41 snapshot and the FakeModel trajectories, pure.

The load through the service (record, then advance at 9:58 and 11:12) and the export's
equivalence run at the S35 end pass on Docker
(`tests/integration/test_p10t36_run_fixture_equivalence.py`).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from abacus_tools.evals import trajectory
from abacus_tools.synthetic import fixture_export
from abacus_tools.synthetic.scenarios.brightwater_hale import agent_runs_slice as runs
from abacus_tools.synthetic.scenarios.brightwater_hale.loader import HANDLERS

CT = ZoneInfo("America/Chicago")
BOOK = json.loads(
    (
        Path(__file__).resolve().parents[2]
        / "golden/scenario/brightwater_hale/agent_runs_figures.json"
    ).read_text()
)


def test_the_later_states_are_the_books_times_and_the_loader_handles_them() -> None:
    events = runs.agent_runs_events()
    assert {e.kind for e in events} <= set(HANDLERS)
    advanced = {e.data["key"]: e for e in events if e.kind == "agents.run_step_advanced"}
    ic = advanced["workpapers.internal_control"]
    assert ic.at == datetime.fromisoformat(BOOK["run_4127"]["internal_control_failed"])
    assert (ic.data["state"], ic.data["error_code"]) == ("failed", "pack_configuration")
    decided = advanced["workpapers.materiality"]
    assert decided.at == datetime(2026, 9, 14, 11, 12, tzinfo=CT)
    assert decided.actor == "MO" and decided.data["state"] == "succeeded"
    assert all(e.at > runs.SNAPSHOT for e in advanced.values())


def test_the_run_snapshot_exports_the_run_view_and_items_as_marcus() -> None:
    profile = fixture_export.PROFILES[fixture_export.RUN_SNAPSHOT]
    assert profile.slices == ("agent_runs",)
    assert {r.name for r in profile.reads} == {"run-4127", "run-4127-items"}
    assert {r.persona for r in profile.reads} == {"marcus-delaney"}


def test_the_scenario_runs_trajectories_pass_every_grader() -> None:
    cases = {c.id: c for c in trajectory.load()}
    for case_id in ("pass_bh_4118_season_progress", "pass_bh_4127_northwind_planning"):
        assert trajectory.grade_case(cases[case_id]).passed
    seen = cases["pass_bh_4118_season_progress"].trajectory
    assert seen is not None
    numbers = seen.answer.numbers
    assert [n.text for n in numbers] == [str(BOOK["run_4118"]["open_returns"]["total"])]
