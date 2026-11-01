"""The `pilot` slice (TASK-2470; DEC-1530): Brightwater Hale as the synthetic test pilot firm.

No pilot firm is live (DEC-1391), so the ops rows that need one run against Brightwater Hale under
the pilot code `PF-X1` (`deploy/windows.yaml`, with no `real_data_since`, so no freeze ever
applies to it; `docs/ops/go-live/PF-X1.md`). This slice gives the firm the one pilot fact that
lives in its tenant: enrolments, so `make pilot-metrics` has work items to write
`pilot_metric_snapshots` for. Each goes through `platform.api.enrol_pilot`, the service
`make pilot-enrol` calls, as the platform on behalf of the rehearsal operator.

Enrolled in shadow mode, the way every pilot starts (Q-04 §4): the Feld 2025 return (the tax
pilot's work, J06) and Northwind's EBP audit (the audit pilot's, J02 and J04's PBC through the
portal, which W4 and W5 read). The window runs from the firm's first day on the timeline to the
end of the 2027 autumn window, so it covers M11 to M13. Moving a mode stays the operator's
(`make pilot-enrol mode`), never the seed's.

Opt-in (`--slice pilot`, which brings `binders` for the return and `portal` for the client
people W4 counts). Synthetic evidence only: whatever runs on PF-X1 is reported as the test firm's,
never as a live firm's (DEC-1530).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Final

from abacus_tools.synthetic.scenarios.brightwater_hale.audits import AUDITS
from abacus_tools.synthetic.scenarios.brightwater_hale.prng import stable_id
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import SETUP_AT
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "pilot"
NEEDS: Final = ("binders", "portal")  # `expand_slices` expands one level
PILOT_CODE: Final = "PF-X1"
WINDOW_START: Final = date(2026, 9, 1)
WINDOW_END: Final = date(2027, 10, 20)  # the 2027 autumn window's last day
BASELINE_DAYS: Final = 14
# The rehearsal operator: platform staff, not a firm member (pilot_enrolments.created_by).
OPERATOR: Final = stable_id("operator:pilot-test-firm")
FELD: Final = "Jonah & Claire Feld"
NORTHWIND: Final = AUDITS[0]
# (kind, target): a 2025 return by client, or an audit by label.
ENROLMENTS: Final[tuple[tuple[str, str], ...]] = (
    ("return", FELD),
    ("audit", NORTHWIND.label),
)


@register_slice(SLICE)
def pilot_events() -> list[Event]:
    at = SETUP_AT + timedelta(hours=6)
    return [
        Event(
            f"pilot-enrol:{kind}:{target}",
            at + timedelta(seconds=n),
            "platform.pilot_enrolled",
            "system",
            SLICE,
            {
                "kind": kind,
                "target": target,
                "window_start": WINDOW_START.isoformat(),
                "window_end": WINDOW_END.isoformat(),
                "baseline_days": BASELINE_DAYS,
                "operator": OPERATOR,
            },
        )
        for n, (kind, target) in enumerate(ENROLMENTS)
    ]


__all__ = [
    "BASELINE_DAYS",
    "ENROLMENTS",
    "NEEDS",
    "OPERATOR",
    "PILOT_CODE",
    "SLICE",
    "WINDOW_END",
    "WINDOW_START",
    "pilot_events",
]
