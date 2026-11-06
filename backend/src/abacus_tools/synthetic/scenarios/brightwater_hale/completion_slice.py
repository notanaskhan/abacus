"""The `completion` slice (A-06-T28; A-06 §5; AUD-20; DEC-2373): Brightwater Hale's ASC 962 Defined
contribution checklist, 142 synthetic firm-worded items, through the import route's service and
published by a person. The wording is keyed placeholders, as the standards slice keeps checklist
text (ADR-056), and is never licensed text.

Not here (DEC-2373): findings F-01 to F-09, AJE-1, RJE-1, PAJE-1/2, the SUM conclusion, 14 notes,
26 sign-offs and Marcus Delaney's stale L2, FS v1 and v3, and Dana Kowalski's Oct 8 approval.
Those need A-06-T29's record-mode approval (S29) and a Northwind final TB loaded through the slices
first, so AUD-15, AUD-16, AUD-17 and AUD-20 stay fixture-only. Opt-in (`--slice completion`).
"""

from __future__ import annotations

import csv
import io
from datetime import timedelta
from typing import Final

from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import SETUP_AT
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "completion"
NEEDS: Final = ("people",)
FLAGS: Final = ("reporting.fs_disclosure",)
NAME: Final = "ASC 962 · Defined contribution"
FRAMEWORK: Final = "asc_962_dc"
ITEMS: Final = 142
IMPORTER: Final = "GH"
PUBLISHER: Final = "DR"
_SECTIONS: Final = (
    "General",
    "Statement of net assets",
    "Statement of changes",
    "Investments",
    "Parties in interest",
    "Supplemental schedules",
)


def checklist_csv() -> bytes:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(("key", "section", "text"))
    for n in range(1, ITEMS + 1):
        section = _SECTIONS[(n - 1) * len(_SECTIONS) // ITEMS]
        writer.writerow((f"dc_{n:03d}", section, f"Synthetic checklist item {n}"))
    return out.getvalue().encode()


@register_slice(SLICE)
def completion_events() -> list[Event]:
    events = [
        Event(f"flag:{flag}", SETUP_AT, "platform.flag_set", "system", SLICE, {"flag": flag})
        for flag in FLAGS
    ]
    events.append(
        Event(
            "completion-checklist",
            SETUP_AT + timedelta(seconds=1),
            "methodology.checklist_loaded",
            IMPORTER,
            SLICE,
        )
    )
    return events
