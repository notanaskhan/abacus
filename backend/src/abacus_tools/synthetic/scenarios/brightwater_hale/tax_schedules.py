"""The `tax_schedules` slice (T-03-T15; T-03 §5; BND-03, TAX-13; DEC-2371): the T-03 data through
the service and import paths a person uses, never a row written here.

- **Organizer.** The firm's 1040 organizer, imported by Grace Holloway (v1 to v6, the file in
  `files/organizer_1040.csv`), owned and published by Daniel Reyes for TY2025. Kevin Osei attaches
  v6 to the Feld 2025 Binder and adds its two rules; Claire Feld answers 8 of 9.
- **Extensions.** TAX-13 a at Mon Sep 14, 2026: 161 extended (79 open, 82 filed) and 1 of the 2
  likely. The named rows carry the handoff's figures; the rest take the board's rows, no figures.
- **Estimates.** TAX-13 b's 7 schedules for TY2026.

Not here (DEC-2371): Thornbury's 706 likely row (no return); TY2025 and TY2027 reference sets (a
founder's two-person publish), so extensions take the board's dates; TY2025 and TY2026 engine
parameters (a protected file per year), so those years have no targets or annual figures, only the
counts foot; the April timeline's history (acks, Varga's re-file), so rows
carry their state at the demo clock; and DF-34's fixes, which need a loaded review. Opt-in
(`--slice tax_schedules`).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Final, NamedTuple

from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import CT
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import SETUP_AT
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.tax_board import BOARD, EXTENDED_TOTAL
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "tax_schedules"
NEEDS: Final = ("people", "tax_board", "portal")
TEMPLATE_NAME: Final = "1040 organizer"
TEMPLATE_CODE: Final = "organizer_1040"
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
# the board holds only Walter's 1040 (DEC-2371).
LIKELY: Final[tuple[Likely, ...]] = (
    Likely("Lakeshore Literacy Alliance", "8868", "binder_incomplete", None),
)


class SeedEstimate(NamedTuple):
    """One TAX-13 b row (Estimates, Q3 TY2026 at Sep 14), as the handoff draws it (DF-34,
    TASK-3397). `confirmer` is the client person whose upload confirms the quarter, `confirmed`
    the day of that upload; `requested` is when the confirmation request went out."""

    client: str
    form: str
    method: str
    prior_year_tax: str | None
    withholding: str | None
    agi_over: bool | None  # the 110% rule's AGI test (over $150,000)
    label: str | None  # the payment method label
    status: str  # Q3's at the demo clock
    on: date | None = None  # scheduled for, or paid on
    confirmer: str | None = None
    confirmed: datetime | None = None
    requested: datetime | None = None


def _ct(month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, month, day, hour, minute, tzinfo=CT)


# TAX-13 b: Q3 due 5 (Paid 2, Scheduled 1, Awaiting confirmation 2), Not required 2; 7 rows. The
# prior-year figures are the handoff's inputs: Feld's 110% is 135,545 (123,222.73 x 1.1), less
# 55,585 projected withholding. Annual and Q3 amounts need TY2026's parameter file (DEC-2371).
ESTIMATES: Final[tuple[SeedEstimate, ...]] = (
    SeedEstimate("Jonah & Claire Feld", "1040-ES", "prior_year_110", "123222.73", "55585", True,
                 "irs_direct_pay", "scheduled", date(2026, 9, 15), "Claire Feld",
                 _ct(9, 11, 10), _ct(9, 8, 9)),
    SeedEstimate("Meera Shah", "1040-ES", "prior_year_110", "148000", "0", True,
                 "irs_direct_pay", "confirmation_requested", requested=_ct(9, 8, 9, 5)),
    SeedEstimate("Calloway Family Trust", "1041-ES", "prior_year_110", "46300", "0", True,
                 "eftps", "paid", date(2026, 9, 14), "Eleanor Calloway", _ct(9, 14, 8, 30),
                 _ct(9, 8, 9, 10)),
    SeedEstimate("Elena Varga", "1040-ES", "prior_year_100", "3900", "0", False,
                 "irs_direct_pay", "paid", date(2026, 9, 9), "Elena Varga", _ct(9, 9, 11),
                 _ct(9, 8, 9, 15)),
    SeedEstimate("Gloria Mendez", "1040-ES", "prior_year_100", "6200", "0", False,
                 "irs_direct_pay", "not_confirmed"),
    SeedEstimate("Marcus & Dana Whitley", "1040-ES", "not_required_withholding", None, None,
                 None, None, "not_required"),
    SeedEstimate("Estate of Walter Thornbury", "1041-ES", "prospect", None, None, None, None,
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
    # T-03-T18 (DEC-2605): both flags retired; `tax_board` grants the `tax_returns` entitlement.
    events: list[Event] = []
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
    # DF-34 (TASK-3397): each confirmation goes out through the service to the client's own
    # person, and the confirmed ones come back as that person's upload on the day TAX-13 b shows.
    for row in ESTIMATES:
        if row.requested is None:
            continue
        person = row.confirmer or row.client
        events.append(
            Event(f"estimate-contact:{row.client}", tail + 2 * step, "tax.estimate_contact_ready",
                  REVIEWER, SLICE, {"client": row.client, "person": person})
        )  # fmt: skip
        events.append(
            Event(f"estimate-request:{row.client}", row.requested,
                  "tax.estimate_confirmation_requested", PREPARER, SLICE,
                  {"client": row.client, "person": person})
        )  # fmt: skip
        if row.confirmed is not None:
            events.append(
                Event(f"estimate-confirmed:{row.client}", row.confirmed,
                      "tax.estimate_confirmed", PREPARER, SLICE,
                      {"client": row.client, "person": person})
            )  # fmt: skip
    return events
