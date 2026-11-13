"""WB-01's sessions (W-02-T13; TASK-7714; W-02 §5.3 `wb01-list-e0`, `wb01c-running-three`,
`wb01g-locked-copperleaf`; DEC-4717): the eight §9.6 rows and the three close runs, through the
workbench module's synthetic-only recorder, as their owners, at the demo clock.

The rows are the fixture's (`apps/web/src/fixtures/seed/tpl04-sessions.ts`, stable ids
`session:<key>`), so `make seed-demo` and fixture mode answer the same list: row 1 Hannah's
"TY2025 season progress by office" awaiting her answer (9:21 AM), row 2 the Season Progress
Reporter's weekly run ready for review (via Agent, a schedule), Marcus Delaney's Northwind
planning run, Hannah's Granite Peak analytics, Grace Holloway's Request Chaser (via Agent), Raj
Malhotra's Copperleaf payroll session (Copperleaf in its client scope: Hannah sees it locked),
Kevin Osei's Whitley CP2000 draft and Daniel Reyes' year-end planning screen; then the three
close runs Margaret Okonkwo sees running (engagement runs via Agent). Opt-in (`--slice
workbench`), after `audit_core` (the clients).

Deviations: the thread items of the J11 run (P-10's `j11-adhoc-session`, its plan, questions and
workbook) are not seeded here; row 1 carries only its first message. The seeded rows' engagement
refs are left empty (membership comes from the owner's office: Chicago for Hannah, DEC-4601 Q1).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Final

from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import CT
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "workbench"
NEEDS: Final = ("audit_core",)
FLAGS: Final = ("workbench.enabled",)
REPLAY_FROM: Final = datetime(2026, 9, 1, 8, 3, tzinfo=CT)
COPPERLEAF: Final = "Copperleaf Coffee Roasters, Inc."

# (key, seat, title, origin, state, last activity CT, client scope by name, first message)
ROWS: Final = (
    ("ty2025-season-progress", "HL", "TY2025 season progress by office", "manual",
     "awaiting_answer", datetime(2026, 9, 14, 9, 21, tzinfo=CT), None,
     "Build me a workbook of TY2025 return progress by office, with stalled returns."),
    ("season-progress-reporter", "HL", "Season Progress Reporter — weekly run", "schedule",
     "ready_for_review", datetime(2026, 9, 14, 9, 0, tzinfo=CT), None, None),
    ("northwind-planning", "MD", "Run Northwind 401(k) planning workpapers", "manual", "live",
     datetime(2026, 9, 13, 10, 0, tzinfo=CT), None, None),
    ("granite-analytics", "HL", "Granite Peak preliminary analytics", "manual", "live",
     datetime(2026, 9, 13, 9, 0, tzinfo=CT), None, None),
    ("request-chaser", "GH", "Request Chaser — daily", "schedule", "complete",
     datetime(2026, 9, 13, 8, 0, tzinfo=CT), None, None),
    ("copperleaf-payroll", "RM", "Explain Copperleaf July→August payroll change", "manual", "live",
     datetime(2026, 9, 12, 10, 0, tzinfo=CT), COPPERLEAF, None),
    ("whitley-cp2000", "KO", "Draft CP2000 response — Whitley", "manual", "live",
     datetime(2026, 9, 11, 10, 0, tzinfo=CT), None, None),
    ("year-end-planning", "DR", "Year-end planning screen — 1040 clients", "manual", "live",
     datetime(2026, 9, 9, 10, 0, tzinfo=CT), None, None),
)  # fmt: skip
CLOSE_RUNS: Final = (
    ("copperleaf-close", "RM", "Copperleaf Coffee Roasters — August 2026 close, Run 2",
     datetime(2026, 9, 14, 9, 6, tzinfo=CT), COPPERLEAF),
    ("cedar-hollow-close", "EG", "Cedar Hollow Farms — August 2026 close",
     datetime(2026, 9, 14, 8, 52, tzinfo=CT), None),
    ("hollis-creek-close", "EW", "Hollis Creek Veterinary — August 2026 close",
     datetime(2026, 9, 14, 9, 12, tzinfo=CT), None),
)  # fmt: skip


@register_slice(SLICE)
def workbench_events() -> list[Event]:
    events = [
        Event(f"flag:{flag}", REPLAY_FROM, "platform.flag_set", "system", SLICE, {"flag": flag})
        for flag in FLAGS
    ]
    n = 0
    for key, seat, title, origin, state, at, client, message in ROWS:
        n += 1
        events.append(
            Event(
                f"workbench:session:{key}", REPLAY_FROM + timedelta(seconds=n),
                "workbench.session_recorded", seat, SLICE,
                {"key": key, "title": title, "origin": origin, "state": state,
                 "at": at.isoformat(), "client": client, "message": message},
            )
        )  # fmt: skip
    for key, seat, title, at, client in CLOSE_RUNS:
        n += 1
        events.append(
            Event(
                f"workbench:session:{key}", REPLAY_FROM + timedelta(seconds=n),
                "workbench.session_recorded", seat, SLICE,
                {"key": key, "title": title, "origin": "engagement_run", "state": "running",
                 "at": at.isoformat(), "client": client, "message": None},
            )
        )  # fmt: skip
    return events


__all__ = ["CLOSE_RUNS", "ROWS", "SLICE", "workbench_events"]
