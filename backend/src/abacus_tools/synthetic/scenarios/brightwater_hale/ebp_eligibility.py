"""EBP-03's eligibility test on Northwind PY2025 (TASK-7815; A-05 §3 F2 to F4; DEC-2225, DEC-2328,
DEC-2482, DEC-4813): what the `ebp2` slice records so `GET …/ebp/eligibility/sample` answers the
grid on the Sep 24 seed, through the services as the people the design names.

- **EBP-02's entry rule** (Sep 17): Marcus Delaney starts the provisions review on adoption
  agreement v2, the 2024 amendment and the 2025 SPD. The loader has no model, so the drafter's read
  is refused `ai_drafting_unavailable` and the review stands without it: Marcus keys each
  provision's election and reference from the handoff with a citation note (DV-EBP-03-1, the
  agent-off path), and Hannah Leclerc ticks each value (L1), so `entry_rule_read` is verified
  (21, 3 months, first of month following).
- **The imports** (Sep 23 and 24): Dana Kowalski uploads version 2 of the census and of the HR
  records; Ana Cruz imports the census (keyed W-3 Box 1 + Box 12 D ties) and the HR roster.
- **The test** (Sep 24): Ana creates the `ebp_eligibility` test on the approved Participants
  Version 2 and marks every row: rows 8 and 15 exceptions, row 22 no effect, the rest pass.

**Keys.** The sample's record key is the census row (DEC-1659: "NWC-0215" for Alicia Brennan), so
both files carry it and the column map keys participants by it.

**Figures.** Names, census and HR hire dates, elections, Fatima Qureshi's 21st birthday and the
results are the handoff's (`apps/web/src/fixtures/seed/ebp03.ts`); Kwame Mensah's $41,200 and Yuki
Mori's $52,800 are A-05 §2's; every other compensation is AUD-11's census v2
(`sampling_content.census`). Inferred, and recorded in DEC-4813: the times; the other 24 dates of
birth (masked everywhere; each the first of the hire month 30 years earlier, so hire plus three
months governs as the handoff's entry dates require); and the $18,082.00 the two raised
compensations take off the census's last row, so it still ties to the W-3.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Final, Literal

from openpyxl import Workbook

from abacus_tools.synthetic.documents import pinned_xlsx
from abacus_tools.synthetic.scenarios.brightwater_hale import sampling_content
from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import CT
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import SETUP_AT
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

NORTHWIND: Final = "Northwind Robotics, Inc."
CENSUS_FILE: Final = "Northwind Census PY2025.xlsx"  # the ebp slice's v1; Dana uploads v2
HR_FILE: Final = "Northwind HR records - eligibility sample.xlsx"
REVIEW_FILES: Final = (
    "Northwind 401k - Adoption agreement v2.pdf",
    "Northwind 401k - Amendment 2024-1.pdf",
    "Northwind 401k - Summary Plan Description 2025.pdf",
)
# The designed papers the slice makes when absent (A-05-T09's kinds; EBP-03's title is the
# completion slice's, which makes it when this slice is not loaded).
PROVISIONS_PAPER: Final = ("EBP-02", "Plan provisions review", "ebp_provisions")
ELIGIBILITY_PAPER: Final = ("EBP-03", "Eligibility Testing", "ebp_eligibility")
W3_BOX1: Final = Decimal("13813400.00")
W3_BOX12D: Final = Decimal("746600.00")


Result = Literal["pass", "exception", "no_effect"]


@dataclass(frozen=True)
class Sampled:
    """A designed participant (EBP-03, in A-03's draw order)."""

    name: str
    hire_on: date
    hr_hire_on: date
    election: Decimal | None  # None: no election, the QACA default applies
    result: Result


def _d(text: str) -> date:
    return date.fromisoformat(text)


# The handoff's rows (ebp03.ts ROWS): name, hire, election from the rate label, result in d/e.
SAMPLED: Final[tuple[Sampled, ...]] = (
    Sampled("Alicia Brennan", _d("2025-02-10"), _d("2025-02-10"), Decimal(8), "pass"),
    Sampled("Tomás Ibarra", _d("2021-06-14"), _d("2021-06-14"), Decimal(10), "pass"),
    Sampled("Priyanka Desai", _d("2025-04-07"), _d("2025-04-07"), None, "pass"),
    Sampled("Gordon Whitfield", _d("2012-09-04"), _d("2012-09-04"), Decimal(15), "pass"),
    Sampled("Mei Tanaka", _d("2024-09-16"), _d("2024-09-16"), None, "pass"),
    Sampled("Darnell Hughes", _d("2023-03-06"), _d("2023-03-06"), None, "pass"),
    Sampled("Sofia Marchetti", _d("2025-06-02"), _d("2025-06-02"), Decimal(5), "pass"),
    Sampled("Kwame Mensah", _d("2025-03-17"), _d("2025-03-17"), Decimal(0), "exception"),
    Sampled("Rebecca Lindgren", _d("2019-10-21"), _d("2019-10-21"), Decimal(7), "pass"),
    Sampled("Hiroshi Nakamura", _d("2024-11-04"), _d("2024-11-04"), Decimal(6), "pass"),
    Sampled("Ingrid Solberg", _d("2017-02-13"), _d("2017-02-13"), Decimal(12), "pass"),
    Sampled("Felipe Navarro", _d("2023-08-28"), _d("2023-08-28"), None, "pass"),
    Sampled("Aisha Rahman", _d("2025-07-14"), _d("2025-07-14"), None, "pass"),
    Sampled("Connor Gallagher", _d("2015-05-11"), _d("2015-05-11"), Decimal(9), "pass"),
    Sampled("Yuki Mori", _d("2024-12-02"), _d("2024-12-02"), Decimal(0), "exception"),
    Sampled("Patrick Doyle", _d("2022-01-10"), _d("2022-01-10"), Decimal(10), "pass"),
    Sampled("Leila Farahani", _d("2024-07-08"), _d("2024-07-08"), None, "pass"),
    Sampled("Andre Wilkins", _d("2023-05-15"), _d("2023-05-15"), Decimal(0), "pass"),
    Sampled("Natalie Brooks", _d("2025-05-05"), _d("2025-05-05"), None, "pass"),
    Sampled("Vikram Sethi", _d("2018-08-06"), _d("2018-08-06"), Decimal(6), "pass"),
    Sampled("Chloe Dubois", _d("2016-11-14"), _d("2016-11-14"), Decimal(8), "pass"),
    Sampled("Benjamin Okoro", _d("2024-10-07"), _d("2024-10-14"), None, "no_effect"),
    Sampled("Teresa Romero", _d("2020-12-07"), _d("2020-12-07"), Decimal(4), "pass"),
    Sampled("Ethan Caldwell", _d("2022-06-27"), _d("2022-06-27"), None, "pass"),
    Sampled("Fatima Qureshi", _d("2025-02-03"), _d("2025-02-03"), None, "pass"),
)
# A-05 §2: the two exceptions' compensation (Kwame 2,472 / 1,442; Yuki 3,168 / 1,848).
COMPENSATION: Final = {"Kwame Mensah": Decimal("41200.00"), "Yuki Mori": Decimal("52800.00")}
# The handoff: "6% default (age 21 on 08/19/2025 governs)".
FATIMA_DOB: Final = date(2004, 8, 19)
# The no-effect and exception notes, the handoff's words (EBP-03 copy; the rate label).
NO_EFFECT_NOTE: Final = "No effect: entry 02/01/2025 either way"
EXCEPTION_NOTE: Final = "0% — no opt-out"
ATTRIBUTES: Final = ("hire_date", "entry_date", "deferral_rate", "enrollment")
# Which attribute carries a row's non-pass result: the hire-date difference (row 22) and the
# missed enrollment (rows 8 and 15).
RESULT_ATTRIBUTE: Final = {"no_effect": "hire_date", "exception": "enrollment"}

# EBP-02's provisions, the handoff's (ebp02.ts ROWS): key, election, reference.
PROVISIONS: Final[tuple[tuple[str, str, str], ...]] = (
    ("plan_year", "Jan 1 \u2013 Dec 31", "AA §1.05"),
    ("minimum_age", "21", "AA §2.01(a)"),
    ("service_requirement", "3 months (elapsed time)", "AA §2.01(b)"),
    ("entry_dates", "First of month following", "AA §2.02"),
    ("excluded_classes", "Union employees; nonresident aliens", "AA §2.03"),
    ("long_term_part_time", "2 years with 500+ hours", "AA §2.04"),
    ("compensation", "W-2 wages + pre-tax deferrals; bonuses included", "AA §3.01"),
    ("auto_enrollment", "QACA (§401(k)(13))", "AA §4.01"),
    ("default_deferral_rate", "6%", "AA §4.02"),
    ("auto_escalation", "+1% each Jan 1 after one full plan year, to 15%", "AA §4.03"),
    ("qdia", "KRS Target date fund nearest age 65", "AA §4.05"),
    ("roth_deferrals", "Yes", "AA §4.06"),
    ("catch_up", "Yes, incl. ages 60\u201363", "2024 Amend. §2"),
    ("safe_harbor_match", "100% of first 1% + 50% of next 5%", "AA §5.01"),
    ("match_vesting", "100% after 2 years of service", "AA §6.02"),
    ("forfeitures", "Reduce employer contributions", "AA §6.04"),
    ("loans", "Up to 2 outstanding; $1,000 minimum; payroll repayment", "AA §7.01"),
    ("in_service_withdrawals", "Age 59½", "AA §8.01"),
    ("hardship", "Safe-harbor events; self-certification", "AA §8.02"),
    ("plan_expenses", "Reasonable expenses may be paid from plan", "AA §9.04"),
)
PROVISION_NOTE: Final = "Keyed from the adoption agreement v2 and the 2024 amendment ({ref})"
# The two rows the 2024 amendment governs (EBP-02 b2: absent from a pre-amendment read).
AMENDED: Final = frozenset({"long_term_part_time", "catch_up"})


def held_provisions(*, amended: bool) -> list[tuple[int, tuple[str, str, str]]]:
    """The provisions a review holds with their EBP-02 row (B<row>, C<row>: row 2 first), the
    amendment's two only when it is in force (the registry's `provisions_for`)."""
    return [
        (row, provision)
        for row, provision in enumerate(PROVISIONS, start=2)
        if amended or provision[0] not in AMENDED
    ]


def result_of(person: Sampled, attribute: str) -> tuple[Result, str | None]:
    """Ana's mark on one cell and its note: the row's result on the attribute it concerns, pass on
    the rest."""
    if RESULT_ATTRIBUTE.get(person.result) != attribute:
        return "pass", None
    return person.result, NO_EFFECT_NOTE if person.result == "no_effect" else EXCEPTION_NOTE


def dob_of(person: Sampled) -> date:
    """Fatima's is the handoff's; the rest are inferred (DEC-4813), each before hire plus three
    months, so the service date governs as the handoff's entry dates do."""
    if person.name == "Fatima Qureshi":
        return FATIMA_DOB
    return date(person.hire_on.year - 30, person.hire_on.month, 1)


@dataclass(frozen=True)
class CensusRow:
    row_key: str
    census_id: str
    name: str
    hire_on: date
    dob: date | None
    election: Decimal | None
    compensation: Decimal


def sampled_keys() -> dict[str, str]:
    """Each designed participant's census row (A-03's construction: name → "NWC-0215")."""
    rows = sampling_content.census()
    return {rows[o].name: rows[o].row_key for o in sampling_content.CENSUS_ORDINALS}


def census() -> tuple[CensusRow, ...]:
    """AUD-11's census v2 with the columns EBP-03 reads: the designed rows take the handoff's hire
    dates, elections and dates of birth; Kwame's and Yuki's pay is A-05's, the difference off the
    last row, so the total still ties to the W-3 (14,560,000.00)."""
    designed = {p.name: p for p in SAMPLED}
    base = sampling_content.census()
    raised = sum(
        (COMPENSATION[r.name] - r.compensation for r in base if r.name in COMPENSATION),
        Decimal(0),
    )
    out: list[CensusRow] = []
    for n, r in enumerate(base):
        person = designed.get(r.name)
        pay = COMPENSATION.get(r.name, r.compensation)
        if n == len(base) - 1:
            pay -= raised
        out.append(
            CensusRow(
                r.row_key,
                r.census_id,
                r.name,
                person.hire_on if person else r.hired,
                dob_of(person) if person else None,
                person.election if person else None,
                Decimal(pay).quantize(Decimal("0.01")),
            )
        )
    return tuple(out)


CENSUS_HEADER: Final = (
    "Census row",
    "Participant ID",
    "Name",
    "Hire date",
    "Status",
    "Date of birth",
    "Deferral election %",
    "Compensation",
)
CENSUS_MAP: Final = {
    "participant_key": "Census row",
    "name": "Name",
    "hire_on": "Hire date",
    "status": "Status",
    "dob": "Date of birth",
    "deferral_election_pct": "Deferral election %",
    "compensation": "Compensation",
}
HR_HEADER: Final = ("Census row", "Participant ID", "Name", "Hire date")
HR_MAP: Final = {"participant_key": "Census row", "name": "Name", "hire_on": "Hire date"}


def _sheet(title: str, header: Sequence[str], rows: Sequence[Sequence[object]]) -> bytes:
    book = Workbook()
    sheet = book.active
    if sheet is None:  # pragma: no cover -- openpyxl always opens a sheet
        raise RuntimeError("no sheet")
    sheet.title = title
    sheet.append(list(header))
    for row in rows:
        sheet.append(list(row))
    return pinned_xlsx(book, SETUP_AT)  # the same bytes on every build


def census_xlsx() -> bytes:
    """Version 2 of the census, as Dana uploads it: text cells, ISO dates."""
    return _sheet(
        "Census",
        CENSUS_HEADER,
        [
            (
                r.row_key,
                r.census_id,
                r.name,
                r.hire_on.isoformat(),
                "active",
                "" if r.dob is None else r.dob.isoformat(),
                "" if r.election is None else str(r.election),
                str(r.compensation),
            )
            for r in census()
        ],
    )


def hr_xlsx() -> bytes:
    """Version 2 of the HR records: PayGrid's record for each sampled census row."""
    keys = sampled_keys()
    ids = {name: census_id for name, census_id in sampling_content.PARTICIPANTS}
    return _sheet(
        "HR records",
        HR_HEADER,
        [(keys[p.name], ids[p.name], p.name, p.hr_hire_on.isoformat()) for p in SAMPLED],
    )


# --- the events (DEC-4813: every time inferred; EBP-02 e's L2 is Sep 17, 3:10 PM) -------------


def _at(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 9, day, hour, minute, tzinfo=CT)


PREPARER_ASSIGNED_AT: Final = _at(17, 8, 50)
REVIEW_STARTED_AT: Final = _at(17, 9, 0)
PROVISIONS_KEYED_AT: Final = _at(17, 9, 20)
PROVISIONS_VERIFIED_AT: Final = _at(17, 15, 0)
FILES_UPLOADED_AT: Final = _at(23, 16, 0)
CENSUS_IMPORTED_AT: Final = _at(24, 9, 0)
HR_IMPORTED_AT: Final = _at(24, 9, 5)
TEST_CREATED_AT: Final = _at(24, 9, 10)
RESULTS_MARKED_AT: Final = _at(24, 9, 30)


def events(slice_name: str) -> list[Event]:
    def event(key: str, at: datetime, kind: str, actor: str, **data: object) -> Event:
        return Event(
            f"ebp:northwind:{key}", at, kind, actor, slice_name, dict(data), client=NORTHWIND
        )

    return [
        # Hannah assigns Marcus the preparer function on PY2025 (a cell edit is a preparer's,
        # SHL-09 c), so he can key EBP-02.
        event(
            "preparer",
            PREPARER_ASSIGNED_AT,
            "engagements.ebp_preparer_assigned",
            "HL",
            member="MD",
            function="preparer",
        ),
        event("provisions-review", REVIEW_STARTED_AT, "assurance.ebp_plan_review_started", "MD"),
        event("provisions-keyed", PROVISIONS_KEYED_AT, "assurance.ebp_provisions_keyed", "MD"),
        event(
            "provisions-verified",
            PROVISIONS_VERIFIED_AT,
            "assurance.ebp_provisions_verified",
            "HL",
        ),
        event(
            "eligibility-files",
            FILES_UPLOADED_AT,
            "evidence.ebp_eligibility_files_uploaded",
            "system",
        ),
        event(
            "census-import",
            CENSUS_IMPORTED_AT,
            "assurance.ebp_import_recorded",
            "AC",
            source="census",
        ),
        event(
            "hr-import", HR_IMPORTED_AT, "assurance.ebp_import_recorded", "AC", source="hr_roster"
        ),
        event("eligibility-test", TEST_CREATED_AT, "assurance.ebp_test_created", "AC"),
        event("eligibility-results", RESULTS_MARKED_AT, "assurance.ebp_results_marked", "AC"),
    ]
