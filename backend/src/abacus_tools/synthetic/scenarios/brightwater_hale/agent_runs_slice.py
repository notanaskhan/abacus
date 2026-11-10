"""The `agent_runs` slice (P-09-T12; P-09 §3, §5.4; DEC-3121): run #4127, Northwind Robotics
401(k) Plan PY2025's planning run, recorded through the agents module's synthetic-only run
recorder (`agents.api` `record_synthetic_run`, P-09-T07) at the 9:41 AM snapshot of Mon Sep 14,
2026, as Marcus Delaney started it.

The plan is the handoff's projection, "14 workpapers · 5 levels": Foundation 1 · Planning 5 ·
Sampling 1 · Testing 4 · Completion 3 (1 + 5 + 1 + 4 + 3 = 14). At 9:41 the trial balance is done
(9:26), Planning materiality is blocked on Margaret Okonkwo's decision (9:27), one Planning step is
running, two wait on inputs and one is queued; the later levels are queued. Steps the handoff
names keep their workpaper code; the rest are labelled by their level, never invented.

After the snapshot (P-10-T36, DEC-3300 row): Internal control fails at 9:58 on the pack
configuration error and Margaret Okonkwo's 11:12 decision releases materiality, each through the
recorder's `advance_synthetic_step`; a load at 9:41 stops before both.

Not here (DEC-3121): #4118 and the Aug 17 failure are firm-level runs (no engagement; a run row
needs one until P-10's firm-scope runs), and Copperleaf's Run 2 needs C-01's close engagement;
those stay fixture-only, their figures footed from the same book
(`backend/tests/golden/scenario/brightwater_hale/agent_runs_figures.json`). Opt-in
(`--slice agent_runs`), after `audit_core`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final
from zoneinfo import ZoneInfo

from abacus_tools.synthetic.scenarios.brightwater_hale.prng import stable_id
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "agent_runs"
NEEDS: Final = ("audit_core",)
CLIENT: Final = "Northwind Robotics, Inc."
RUN_ID: Final = stable_id("agent-run:northwind-py2025-planning-4127")
_CT: Final = ZoneInfo("America/Chicago")
SNAPSHOT: Final = datetime(2026, 9, 14, 9, 41, tzinfo=_CT)
STARTED: Final = datetime(2026, 9, 14, 9, 24, tzinfo=_CT)
# P-10-T36 (SHL-13 frames 6 and 4): after the 9:41 snapshot, through the recorder's service.
IC_FAILED: Final = datetime(2026, 9, 14, 9, 58, tzinfo=_CT)
DECIDED: Final = datetime(2026, 9, 14, 11, 12, tzinfo=_CT)
# (at, seat, step key, step state, run state, error code): the seat is the person the recorder
# writes as (Marcus started the run; Margaret's decision releases materiality).
ADVANCES: Final[tuple[tuple[datetime, str, str, str, str, str | None], ...]] = (
    (IC_FAILED, "MD", "workpapers.internal_control", "failed", "running", "pack_configuration"),
    (DECIDED, "MO", "workpapers.materiality", "succeeded", "running", None),
)

# (key, level, label, state at 9:41)
STEPS: Final[tuple[tuple[str, int, str, str], ...]] = (
    ("workpapers.trial_balance", 1, "Run trial balance workpaper", "succeeded"),
    ("workpapers.materiality", 2, "Propose materiality", "blocked"),
    ("workpapers.risk_assessment", 2, "Draft risk assessment", "running"),
    ("workpapers.audit_planning", 2, "General audit planning", "waiting_on_inputs"),
    ("workpapers.internal_control", 2, "Internal control", "waiting_on_inputs"),
    ("planning_5", 2, "Planning", "queued"),
    ("sampling_1", 3, "Sampling", "queued"),
    ("testing_1", 4, "Testing", "queued"),
    ("testing_2", 4, "Testing", "queued"),
    ("testing_3", 4, "Testing", "queued"),
    ("testing_4", 4, "Testing", "queued"),
    ("completion_1", 5, "Completion", "queued"),
    ("completion_2", 5, "Completion", "queued"),
    ("completion_3", 5, "Completion", "queued"),
)


@register_slice(SLICE)
def agent_runs_events() -> list[Event]:
    return [
        Event(
            f"agent-run:{RUN_ID}",
            SNAPSHOT,
            "agents.run_recorded",
            "MD",  # Marcus Delaney starts it (J03 step 6)
            SLICE,
            {
                "run_id": RUN_ID,
                "agent_id": "engagement.agent",  # its planning run (CHECK: module.name)
                "run_number": 4127,
                "state": "running",
                "started_at": STARTED.isoformat(),
                "plan_decided_at": STARTED.isoformat(),
                "blocked_on": {"kind": "decision", "question_key": "materiality"},
                "steps": [
                    {"key": k, "level": lv, "label": label, "state": st}
                    for k, lv, label, st in STEPS
                ],
            },
            client=CLIENT,
        ),
        *(
            Event(
                f"agent-run-step:{RUN_ID}:{key}:{at.strftime('%H%M')}",
                at,
                "agents.run_step_advanced",
                seat,
                SLICE,
                {
                    "run_id": RUN_ID,
                    "key": key,
                    "state": state,
                    "run_state": run_state,
                    "error_code": error,
                },
                client=CLIENT,
            )
            for at, seat, key, state, run_state, error in ADVANCES
        ),
    ]
