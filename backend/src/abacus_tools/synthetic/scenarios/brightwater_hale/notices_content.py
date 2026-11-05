"""The `notices` slice (N-04-T21; N-04 §5; DEC-2316): Brightwater Hale's notices through the
service APIs under the demo clock, the same intake path a person uses: an intake from a stored
file,
the fields entered, Create notice, then the status moves through `notices.service`.

Seed counts: 2 New, 3 Analyzing, 2 Response drafted, 2 Awaiting IRS; 3 CP2000, 2 CP14, 1 CP501,
3 State. Fictional people, and amounts by code from each row. Template variants (agree, partial,
disagree, balance due, generic) are DB content through C11's import and live in
`files/notice_templates.yaml`, never here. Opt-in (`--slice notices`).

Not here (DEC-2316): the per-artboard response versions, envelope, confirmation and sent records,
which need the Whitley letter's render and C7's envelope in a loaded firm; those states are the
fixture scenarios' (N-04-T20).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Final, NamedTuple

from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import CT
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import SETUP_AT
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "notices"
NEEDS: Final = ("people", "tax_board")
FLAGS: Final = ("notices.workspace",)
FILER: Final = "GH"  # Grace Holloway logs a notice on the day it arrives


class SeedNotice(NamedTuple):
    code: str
    client: str
    notice_code: str
    agency: str
    tax_year: int
    received: date
    respond_by: date
    amount: str
    status: str  # the row's status at the demo clock
    assignee: str


NOTICES: Final[tuple[SeedNotice, ...]] = (
    SeedNotice("N1", "Marcus & Dana Whitley", "CP2000", "irs", 2024, date(2026, 8, 26),
               date(2026, 9, 23), "753.01", "response_drafted", "KO"),
    SeedNotice("N2", "Aurelio Santos", "CP14", "irs", 2024, date(2026, 7, 6),
               date(2026, 7, 27), "1982.40", "received", "KO"),
    SeedNotice("N3", "Claire Feld", "CP2000", "irs", 2023, date(2026, 8, 30),
               date(2026, 9, 28), "1204.00", "analyzing", "SI"),
    SeedNotice("N4", "Priya Iyer", "CP2000", "irs", 2024, date(2026, 9, 2),
               date(2026, 10, 2), "420.55", "classified", "KO"),
    SeedNotice("N5", "Tomas Varga", "CP14", "irs", 2024, date(2026, 9, 8),
               date(2026, 10, 1), "310.40", "received", "PS"),
    SeedNotice("N6", "Collins Family Trust", "CP501", "irs", 2023, date(2026, 8, 12),
               date(2026, 9, 11), "96.20", "analyzing", "SI"),
    SeedNotice("N7", "Ridgeline Holdings LP", "CO DR 3904", "state", 2024, date(2026, 8, 18),
               date(2026, 9, 18), "2150.00", "response_drafted", "KO"),
    SeedNotice("N8", "Halvard Group", "IL-1040", "state", 2023, date(2026, 7, 28),
               date(2026, 8, 28), "640.00", "awaiting_irs", "SI"),
    SeedNotice("N9", "Mercer Hill Health", "CA FTB 4600", "state", 2023, date(2026, 7, 2),
               date(2026, 8, 2), "1810.00", "awaiting_irs", "PS"),
)  # fmt: skip


def counts() -> dict[str, int]:
    """The tiles (QN-6) by code, the row's "2 New, 3 Analyzing, 2 Response drafted, 2 Awaiting"."""
    tile = {
        "received": "new",
        "classified": "analyzing",
        "analyzing": "analyzing",
        "response_drafted": "response_drafted",
        "approved": "response_drafted",
        "sent": "awaiting",
        "awaiting_irs": "awaiting",
    }
    found: dict[str, int] = {}
    for row in NOTICES:
        found[tile[row.status]] = found.get(tile[row.status], 0) + 1
    return found


def _at(on: date) -> datetime:
    return datetime(on.year, on.month, on.day, 9, 30, tzinfo=CT)


@register_slice(SLICE)
def notice_events() -> list[Event]:
    events = [
        Event(f"flag:{flag}", SETUP_AT, "platform.flag_set", "system", SLICE, {"flag": flag})
        for flag in FLAGS
    ]
    for row in NOTICES:
        events.append(
            Event(
                f"notice:{row.code}",
                _at(row.received),
                "notices.seed_notice",
                FILER,
                SLICE,
                {
                    "code": row.code,
                    "notice_code": row.notice_code,
                    "agency": row.agency,
                    "tax_year": row.tax_year,
                    "received": row.received.isoformat(),
                    "respond_by": row.respond_by.isoformat(),
                    "amount": row.amount,
                    "status": row.status,
                    "assignee": row.assignee,
                },
                client=row.client,
            )
        )
    return events
