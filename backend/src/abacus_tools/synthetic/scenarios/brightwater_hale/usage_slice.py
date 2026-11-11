"""The `agent_minutes` slice (P-10-T42; P-10 §3.10, §8 `ledger-sep-oct`; DEC-3401): Brightwater
Hale's agent-minute ledger, posted through `platform.api` `record_synthetic_minutes`, the code a
completed run's `agent_run.completed` takes.

- **ENG-06a (Northwind Robotics 401(k) Plan PY2025):** 412 = 46 + 24 + 342 from runs #4019 (PBC
  list builder, Aug 31), #4064 (Document classifier & matcher, Sep 1-14) and #4102 (Plan provisions
  extraction, Sep 11). All three completed in the usage month Aug 15 to Sep 14, 2026 (`2026-08`).
  Run #4127, started 9:24 AM on Sep 14, is still running: "Minutes post when the run completes"
  (AC-M4), so it posts nothing here.
- **ADM-14a (Thu Oct 1, usage month Sep 15 to Oct 14, `2026-09`):** 14,920 = Tax 8,640 + Audit &
  assurance 4,610 + Client accounting 1,420 + Advisory & attest 120 + Firm operations 130. The
  handoff gives the month by service line only, so each service line posts one `history` line
  ("Earlier runs"), never invented runs; 20,000 included minutes sit on the firm's plan row.

Runs #4019, #4064 and #4102 completed before the recorded runs (#4127 is the first recorded one),
so their ledger lines carry stable synthetic run ids. Opt-in (`--slice agent_minutes`), after
`audit_core`; the plan row's included minutes are set whether or not `tax_board` loaded first.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Final
from zoneinfo import ZoneInfo

from abacus_tools.synthetic.scenarios.brightwater_hale.prng import stable_id
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "agent_minutes"
NEEDS: Final = ("audit_core",)
CT: Final = ZoneInfo("America/Chicago")
NORTHWIND: Final = "Northwind Robotics, Inc."
INCLUDED_MINUTES: Final = 20_000
# Where the plan's included minutes sit: the firm's tax_returns entitlement row.
INCLUDED_ON_MODULE: Final = "tax_returns"
MS: Final = 60_000

# (run number, capability, completed on, minutes, phase): ENG-06's three completed runs.
NORTHWIND_RUNS: Final = (
    (4019, "requests.pbc_list_builder", date(2026, 8, 31), 46, "planning"),
    (4064, "evidence.matcher", date(2026, 9, 14), 24, "fieldwork"),
    (4102, "ebp.provisions_extractor", date(2026, 9, 11), 342, "planning"),
)
ENG06_TOTAL: Final = 412  # 46 + 24 + 342

# ADM-14a by service line, the usage month Sep 15 to Oct 14, 2026, as at Thu Oct 1.
SEPTEMBER_BY_LINE: Final = (
    ("tax", 8_640),
    ("audit", 4_610),
    ("cas", 1_420),
    ("advisory", 120),
    ("firm", 130),
)
ADM14_TOTAL: Final = 14_920  # 8,640 + 4,610 + 1,420 + 120 + 130
SEPTEMBER_POSTED_ON: Final = date(2026, 10, 1)
POSTED_AT: Final = datetime(2026, 10, 1, 9, 15, tzinfo=CT)  # "Metered by Accrued · 9:15 AM"


def run_id_for(label: str) -> str:
    return stable_id(f"agent-minutes:{label}")


@register_slice(SLICE)
def usage_events() -> list[Event]:
    events = [
        Event(
            "agent_minutes:included",
            datetime(2026, 9, 15, 0, 5, tzinfo=CT),
            "platform.agent_minutes_included",
            "system",
            SLICE,
            {"module": INCLUDED_ON_MODULE, "minutes": INCLUDED_MINUTES},
        )
    ]
    for number, capability, on, minutes, phase in NORTHWIND_RUNS:
        events.append(
            Event(
                f"agent_minutes:northwind:{number}",
                datetime(on.year, on.month, on.day, 17, 0, tzinfo=CT),
                "platform.agent_minutes_posted",
                "system",
                SLICE,
                {
                    "run_id": run_id_for(f"northwind-{number}"),
                    "run_number": number,
                    "capability": capability,
                    "completed_on": on.isoformat(),
                    "agent_ms": minutes * MS,
                    "minutes": minutes,
                    "service_line": "audit",
                    "phase": phase,
                    "engagement": "northwind",
                },
                client=NORTHWIND,
            )
        )
    for line, minutes in SEPTEMBER_BY_LINE:
        events.append(
            Event(
                f"agent_minutes:september:{line}",
                POSTED_AT,
                "platform.agent_minutes_posted",
                "system",
                SLICE,
                {
                    "run_id": run_id_for(f"september-{line}"),
                    "run_number": None,
                    "capability": "history",
                    "completed_on": SEPTEMBER_POSTED_ON.isoformat(),
                    "agent_ms": minutes * MS,
                    "minutes": minutes,
                    "service_line": line,
                    "phase": None,
                    "engagement": None,
                },
            )
        )
    return events
