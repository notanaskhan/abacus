"""The `tax_schedules` slice (T-03-T15; T-03 §5; BND-03, TAX-13; DEC-2328): the T-03 data through
the service and import paths a person uses, never a row written here.

- **Organizer.** The firm's 1040 organizer, imported by Grace Holloway (v1 to v6, the file in
  `files/organizer_1040.csv`), owned and published by Daniel Reyes for TY2025. Kevin Osei attaches
  v6 to the Feld 2025 Binder and adds its two rules; Claire Feld answers 8 of 9.
- **Extensions.** TAX-13 a at Mon Sep 14, 2026: 161 extended (79 open, 82 filed) and 1 of the 2
  likely. The named rows carry the handoff's figures; the rest take the board's rows, no figures.
- **Estimates.** TAX-13 b's 7 schedules for TY2026.

Not here (DEC-2328): Thornbury's 706 likely row (no return); TY2025 and TY2027 reference sets (a
founder's two-person publish), so extensions take the board's dates; TY2025 and TY2026 engine
parameters (a protected file per year), so those years have no targets or annual figures, only the
counts foot; the April timeline's history (acks, Varga's re-file), so rows
carry their state at the demo clock; and DF-34's fixes, which need a loaded review. Opt-in
(`--slice tax_schedules`).
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Final, NamedTuple

from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import SETUP_AT
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.tax_board import BOARD, EXTENDED_TOTAL
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "tax_schedules"
NEEDS: Final = ("people", "tax_board", "portal")
FLAGS: Final = ("questionnaires.editor", "tax.extensions_estimates")
TEMPLATE_NAME: Final = "1040 organizer"
TEMPLATE_KEY: Final = "organizer_1040"
OWNER: Final = "DR"
IMPORTER: Final = "GH"
PREPARER: Final = "KO"
REVIEWER: Final = "SI"
FILE: Final = Path(__file__).parent / "files" / "organizer_1040.csv"
VERSIONS: Final = 6
OPEN_TOTAL: Final = 79
FILED_TOTAL: Final = 82
TAX_YEAR: Final = 2025
ESTIMATE_YEAR: Final = 2026

# Key to Claire Feld's answer. q9 stays open: 8 of the 9 top-level questions are answered.
ANSWERS: Final[dict[str, str]] = {
    "q1": "No",
    "q2": "Yes",
    "q3": "No",
    "q4": "No",
    "q5": "Yes",
    "q6": "Direct deposit",
    "q7": "Yes",
    "q8": "No",
}
RULES: Final[dict[str, tuple[str, str, str]]] = {
    "q2": (
        "q2_yes_residency",
        "raise_review_point",
        "Confirm full-year NYC residency for the IT-201 resident tax",
    ),
    "q5": ("q5_yes_confirmations", "create_request_item", "estimated payment confirmations"),
}


class SeedLine(NamedTuple):
    client: str
    projected: str | None
    held: str | None
    payments: tuple[tuple[str, str, str], ...]  # jurisdiction, form, amount


LINES: Final[tuple[SeedLine, ...]] = (
    SeedLine("Ridgeline Property Partners, LP", None, None,
             (("IL", "IL-1065-V", "28044"), ("CO", "DR-158-N", "17070"),
              ("NY", "IT-370-PF", "18982"))),
    SeedLine("Calloway Family Trust", "46300", "42000", (("US", "7004", "5000"),)),
    SeedLine("Ashford Manufacturing Co.", "1572900", "1560000", (("US", "7004", "12900"),)),
    SeedLine("Jonah & Claire Feld", "122500", "113476",
             (("US", "4868", "10000"), ("NY", "IT-370", "6000"))),
    SeedLine("Meera Shah", "148000", "128000", (("US", "4868", "20000"),)),
    SeedLine("Elena Varga", "3900", "3400", (("US", "4868", "500"),)),
)  # fmt: skip
PTET: Final = "Ridgeline Property Partners, LP"


class Likely(NamedTuple):
    client: str
    form: str
    reason: str
    note: str | None


# TAX-13 c's second row, Thornbury's 706, has no return: its engagement is still a prospect's and
# the board holds only Walter's 1040 (DEC-2328).
LIKELY: Final[tuple[Likely, ...]] = (
    Likely("Lakeshore Literacy Alliance", "8868", "binder_incomplete", None),
)


class SeedEstimate(NamedTuple):
    client: str
    method: str
    prior_year_tax: str | None
    withholding: str | None
    status: str  # Q3's at the demo clock


ESTIMATES: Final[tuple[SeedEstimate, ...]] = (
    SeedEstimate("Jonah & Claire Feld", "prior_year_110", "122500", "0", "paid"),
    SeedEstimate("Meera Shah", "prior_year_110", "148000", "0", "paid"),
    SeedEstimate("Calloway Family Trust", "prior_year_100", "50930", "0", "scheduled"),
    SeedEstimate("Elena Varga", "prior_year_100", "4290", "0", "confirmation_requested"),
    SeedEstimate("Marcus & Dana Whitley", "prior_year_100", "18200", "0",
                 "confirmation_requested"),
    SeedEstimate("Aurelio Santos", "not_required_withholding", None, None, "not_required"),
    SeedEstimate("Estate of Walter Thornbury", "not_required_estate_first_years", None, None,
                 "not_required"),
)  # fmt: skip


def organizer_csv() -> bytes:
    return FILE.read_bytes()


def extended_rows() -> list[str]:
    """The board's extended returns, named rows first. They hold the figures, and sit in Open."""
    named = {line.client for line in LINES}
    rows = [r for r in BOARD if r.extended]
    rows.sort(key=lambda r: (r.client not in named, r.label))
    return [r.label for r in rows]


def state_of(index: int) -> str:
    """The first 79 are open, the other 82 filed."""
    return "open" if index < OPEN_TOTAL else "filed"


def counts() -> dict[str, int]:
    labels = extended_rows()
    states = [state_of(i) for i in range(len(labels))]
    return {
        "extended": EXTENDED_TOTAL,
        "open": states.count("open"),
        "filed": states.count("filed"),
        "likely": len(LIKELY),
    }


# A return's federal extension form (the Code's, not the firm's; the board's labels, DEC-76).
_FEDERAL_FORM: Final[dict[str, str]] = {
    "1040": "4868",
    "1040-X": "4868",
    "1041": "7004",
    "1065": "7004",
    "1120": "7004",
    "1120-S": "7004",
    "990": "8868",
    "990-PF": "8868",
    "706": "4768",
    "709": "8892",
}


def federal_form(return_form: str) -> str:
    return _FEDERAL_FORM.get(return_form, "7004")


def money(value: str | None) -> Decimal | None:
    return None if value is None else Decimal(value)


@register_slice(SLICE)
def tax_schedules_events() -> list[Event]:
    at = SETUP_AT
    step = timedelta(seconds=1)
    events = [
        Event(f"flag:{flag}", at, "platform.flag_set", "system", SLICE, {"flag": flag})
        for flag in FLAGS
    ]
    events.append(Event("organizer-loaded", at + step, "tax.organizer_v6_loaded", IMPORTER, SLICE))
    events.append(Event("organizer-feld", at + 2 * step, "tax.organizer_feld", PREPARER, SLICE))
    for index, label in enumerate(extended_rows()):
        events.append(
            Event(
                f"extension:{label}",
                at + (3 + index) * step,
                "tax.extension_seeded",
                REVIEWER,
                SLICE,
                {"label": label, "state": state_of(index)},
            )
        )
    tail = at + (3 + EXTENDED_TOTAL) * step
    for row in LIKELY:
        events.append(
            Event(f"likely:{row.client}", tail, "tax.likely_seeded", REVIEWER, SLICE,
                  {"client": row.client})
        )  # fmt: skip
    for row in ESTIMATES:
        events.append(
            Event(f"estimate:{row.client}", tail + step, "tax.estimate_seeded", REVIEWER, SLICE,
                  {"client": row.client})
        )  # fmt: skip
    return events
