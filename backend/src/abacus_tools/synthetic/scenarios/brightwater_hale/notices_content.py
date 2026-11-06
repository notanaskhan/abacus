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
    respond_by: date | None  # a sent notice has no clock left
    amount: str
    status: str  # the row's status at the demo clock
    assignee: str


# The nine rows of `apps/web/src/fixtures/seed/notices.ts`, the handoff's. N5 and N9 are unassigned
# there; Create notice needs an assignee, so they sit with the filer here (DEC-2335).
NOTICES: Final[tuple[SeedNotice, ...]] = (
    SeedNotice("N1", "Marcus & Dana Whitley", "CP2000", "irs", 2024, date(2026, 8, 24),
               date(2026, 9, 23), "753.01", "analyzing", "KO"),
    SeedNotice("N2", "Harold Stein", "CP2000", "irs", 2024, date(2026, 9, 2),
               date(2026, 9, 30), "4210.00", "analyzing", "GT"),
    SeedNotice("N3", "Wren & Avery Collins", "CP2000", "irs", 2023, date(2026, 7, 18),
               None, "1980.00", "awaiting_irs", "JL"),
    SeedNotice("N4", "Thomas & Irene Kowal", "CP14", "irs", 2024, date(2026, 8, 31),
               date(2026, 9, 21), "3412.18", "response_drafted", "MA"),
    SeedNotice("N5", "Aurelio Santos", "CP14", "irs", 2024, date(2026, 9, 10),
               date(2026, 10, 1), "1106.00", "received", FILER),
    SeedNotice("N6", "Rafael Quintero", "CP501", "irs", 2024, date(2026, 8, 28),
               date(2026, 9, 28), "2240.00", "response_drafted", "LW"),
    SeedNotice("N7", "Copperleaf Coffee Roasters, Inc.", "Notice of deficiency", "state", 2025,
               date(2026, 9, 3),
               date(2026, 10, 3), "640.00", "analyzing", "RM"),
    SeedNotice("N8", "Meridian Tool & Die, Inc.", "Notice of tax due", "state", 2024,
               date(2026, 8, 12),
               None, "5880.00", "awaiting_irs", "YK"),
    SeedNotice("N9", "Priyanka & Sam Iyer", "DTF-160", "state", 2024, date(2026, 9, 11),
               date(2026, 10, 11), "918.00", "received", FILER),
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


# After the clients exist (a client's onboarding can post-date its notice's date) and before the
# demo clock, Mon Sep 14, 2026. A notice's `received` is a field; this is only when it loads.
LOADED_AT: Final = datetime(2026, 9, 14, 8, 0, tzinfo=CT)


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
                LOADED_AT,
                "notices.seed_notice",
                FILER,
                SLICE,
                {
                    "code": row.code,
                    "notice_code": row.notice_code,
                    "agency": row.agency,
                    "tax_year": row.tax_year,
                    "received": row.received.isoformat(),
                    "respond_by": row.respond_by.isoformat() if row.respond_by else None,
                    "amount": row.amount,
                    "status": row.status,
                    "assignee": row.assignee,
                },
                client=row.client,
            )
        )
    return events
