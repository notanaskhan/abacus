"""The entity returns' slice, part 1 (T-05-T45; TASK-7708; T-05 §5.3; DEC-4711): Ridgeline
Property Partners, LP and Harborview Dental Properties, LP, 2025 Form 1065, through service APIs.

- **Facts** (`tax.entity_seeded`, tax's synthetic-only recorder): profile, the partners, their
  ownership periods and the 6/30/2025 transfer of 5 points from Pell Street Ventures LLC to Pell
  Street II LLC (price 360,000), and the workbook cells Run 2 left: 01's 28 accounts (UTB, AJE,
  RJE, ATB; AJE-1 18,500), 04's two periods of 628,100, 05 Capital (as drafted, Item L 6,860,000),
  06 Schedule K, 07 M-2 (line 9 6,866,200), 09 the five K-1s. Figures are the goldens' and the
  handoff's (TXP-02, TXP-05, TXP-06, TXP-07, TXP-11), never typed fresh.
- **Allocation** (the allocation service and P-04): Harborview's targeted waterfall drafted by
  Daniel Reyes and approved at L3 by Samuel Ito on Aug 28; Ridgeline's straight percentage
  (interim closing, monthly) drafted Sep 8 and approved by Samuel on Sep 9.
- **Runs** (agents' synthetic-only recorder): Run 1 (Sep 8, the import failed, then waiting on an
  answer) and Run 2 (Sep 10, 3:31 → 4:12 PM, succeeded).

Deviations, recorded: Ridgeline's structure is drafted by a person, not adopted from the agreement
reader's proposal (the reader's run and its two bbox clause citations need the LPA and the
assignment's word layers in evidence, T-05-T62); 05's beginning carries the 6/30 transfer (the
server's 05 has no Transfers column; Pell Street Ventures 2,100,000 - 331,405 = 1,768,595, Pell
Street II 331,405); TJE-1 rides 06 line 18a (6,200), not a 02 column. Opt-in (`--slice entity`),
after `tax_board` (the returns).

**Part 2** (T-05-T62; TASK-7942; DEC-4937): the memo drafted (TXP-01's text through tax's
synthetic-only memo recorder) and adopted by Olivia Brandt on Sep 10, approved by Samuel Ito on
Sep 14 at 9:40 AM; the M-2 fix approved by Daniel Reyes at 9:51 (each partner's 18a share into 05
income and ending capital, Item L 6,860,000 → 6,866,200, through the synthetic-only fix recorder,
which turns the approved memo Stale by code); Run 3 at 9:52 (TXP-00 B); the M-2 review point
resolved, so TXP-10's badge reads 10. Named snapshots (`epochs.py`): Sep 8 10:02 AM, Sep 10 4:12
PM, E0 (Sep 14 9:24 AM) and Sep 14 9:52 AM.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Final

from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import CT
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "entity"
NEEDS: Final = ("tax_board",)
RIDGELINE: Final = "ridgeline-property-partners-lp"
HARBORVIEW: Final = "harborview-dental-properties-lp"
D = Decimal
FLAGS: Final = ("tax.entity_workspace", "tax.workbook_run", "tax.entity_agents")
REPLAY_FROM: Final = datetime(2026, 9, 1, 8, 2, tzinfo=CT)
H1, H2 = (date(2025, 1, 1), date(2025, 6, 30)), (date(2025, 7, 1), date(2025, 12, 31))

# (name, kind, entity kind, [(from, to, profit %)], admitted)
RIDGELINE_PARTNERS: Final = (
    ("Ridgeline GP LLC", "gp", "llc", ((*H1, D(2)), (*H2, D(2))), None),
    ("Meera Shah", "lp", "individual", ((*H1, D(38)), (*H2, D(38))), None),
    ("Pell Street Ventures LLC", "lp", "llc", ((*H1, D(35)), (*H2, D(30))), None),
    ("Pell Street II LLC", "lp", "llc", ((*H2, D(5)),), date(2025, 7, 1)),
    ("Jonah Feld", "lp", "individual", ((*H1, D(25)), (*H2, D(25))), None),
)
TRANSFER: Final = (
    date(2025, 6, 30),
    "Pell Street Ventures LLC",
    "Pell Street II LLC",
    D(5),
    D(360000),
)

# 01 Trial Balance (TXP-02 verbatim): account, name, UTB, AJE (RJE 0; ATB = UTB + AJE).
TB: Final = (
    ("1000", "Cash — operating", "693667", "0"),
    ("1100", "Tenant receivables", "96000", "0"),
    ("1200", "Municipal bond fund", "240000", "0"),
    ("1300", "Escrows & other assets", "158000", "0"),
    ("1500", "Land", "3600000", "0"),
    ("1600", "Buildings & improvements", "15752000", "0"),
    ("1650", "Accumulated depreciation", "-2625167", "0"),
    ("2000", "Accounts payable", "-120000", "0"),
    ("2050", "Accrued expenses", "-75500", "-18500"),
    ("2100", "Tenant security deposits", "-121800", "0"),
    ("2500", "Mortgage notes payable (nonrecourse)", "-10712500", "0"),
    ("3000", "Partners' capital — beginning", "-5960000", "0"),
    ("3100", "Partner contributions", "-250000", "0"),
    ("3200", "Partner distributions", "600000", "0"),
    ("4000", "Rental income", "-3776500", "0"),
    ("4100", "Parking & other property income", "-96400", "0"),
    ("4500", "Interest income", "-18400", "0"),
    ("4510", "Tax-exempt interest (book)", "-6200", "0"),
    ("5000", "Repairs & maintenance", "412300", "0"),
    ("5100", "Utilities", "186900", "0"),
    ("5200", "Property management fees", "164000", "0"),
    ("5300", "Real estate taxes", "380000", "18500"),
    ("5400", "Insurance", "121700", "0"),
    ("5500", "Mortgage interest", "512400", "0"),
    ("5600", "Depreciation", "733500", "0"),
    ("5700", "Professional fees", "48000", "0"),
    ("5800", "Other operating expenses", "64000", "0"),
    ("4510-T", "Tax-exempt interest — Sch K 18a (tax only)", "0", "0"),
)

# 05 Capital (TXP-11 verbatim): name, beginning (after the 6/30 transfer), contributions,
# distributions, income, ending as drafted.
CAPITAL: Final = (
    ("Ridgeline GP LLC", "80000", "0", "12000", "25000", "93000"),
    ("Meera Shah", "2280000", "0", "228000", "475000", "2527000"),
    ("Pell Street Ventures LLC", "1768595", "0", "180000", "406250", "1994845"),
    ("Pell Street II LLC", "331405", "0", "30000", "31250", "332655"),
    ("Jonah Feld", "1500000", "250000", "150000", "312500", "1912500"),
)
# 06 Schedule K and 09's K-1 shares (TXP-05 verbatim): line, label, total, five shares.
SCHEDULE_K: Final = (
    ("2", "Net rental real estate income (loss) — Form 8825", "1231600",
     ("24632", "468008", "400270", "30790", "307900")),
    ("5", "Interest income", "18400", ("368", "6992", "5980", "460", "4600")),
    ("18a", "Tax-exempt interest income", "6200", ("124", "2356", "2015", "155", "1550")),
    ("19a", "Distributions of cash and marketable securities", "600000",
     ("12000", "228000", "180000", "30000", "150000")),
    ("20a", "Investment income", "18400", ("368", "6992", "5980", "460", "4600")),
)  # fmt: skip
M2: Final = (("1", "5960000"), ("2", "250000"), ("3", "1256200"), ("4", "0"), ("5", "7466200"),
             ("6", "600000"), ("7", "0"), ("8", "0"), ("9", "6866200"))  # fmt: skip

HARBORVIEW_PARTNERS: Final = (
    ("Harborview Property GP LLC", "gp", "llc", (), None),
    ("Lindqvist Family Holdings LLC", "lp", "llc", (), None),
    ("Bayridge Capital LLC", "lp", "llc", (), None),
)
HARBORVIEW_BEGINNING: Final = ("100000", "2400000", "1500000")  # TXP-06 B (704(b))
HARBORVIEW_RUNGS: Final = (
    ("return_of_capital", None),
    ("preferred_return", "8"),
    ("catch_up", "20"),
    ("promote", "20"),
)


def ridgeline_cells() -> list[tuple[str, str]]:
    cells: list[tuple[str, str]] = []
    for n, (code, name, utb, aje) in enumerate(TB, start=2):
        atb = str(D(utb) + D(aje))
        cells += [(f"01!A{n}", code), (f"01!B{n}", name), (f"01!C{n}", utb),
                  (f"01!D{n}", aje), (f"01!E{n}", "0"), (f"01!F{n}", atb)]  # fmt: skip
    total = len(TB) + 2
    for col, idx in (("C", 2), ("D", 3)):
        cells.append((f"01!{col}{total}", str(sum((D(r[idx]) for r in TB), D(0)))))
    cells += [
        (f"01!E{total}", "0"),
        (f"01!F{total}", str(sum((D(r[2]) + D(r[3]) for r in TB), D(0)))),
    ]
    for n, (key, start, end) in enumerate((("p1", *H1), ("p2", *H2)), start=2):
        cells += [
            (f"04!A{n}", key),
            (f"04!B{n}", start.isoformat()),
            (f"04!C{n}", end.isoformat()),
            (f"04!D{n}", "628100"),
        ]
    for n, row in enumerate(CAPITAL, start=2):
        cells += [(f"05!{c}{n}", v) for c, v in zip("ABCDEF", row, strict=True)]
    for col, (name, *_rest) in zip("BCDEF", RIDGELINE_PARTNERS, strict=True):
        cells.append((f"09!{col}1", name))
    for n, (line, label, total_k, shares) in enumerate(SCHEDULE_K, start=2):
        cells += [(f"06!A{n}", line), (f"06!B{n}", label), (f"06!C{n}", total_k)]
        cells += [(f"09!{c}{n}", s) for c, s in zip("BCDEF", shares, strict=True)]
    cells += [(f"07!B{line}", amount) for line, amount in M2]
    return cells


def harborview_cells() -> list[tuple[str, str]]:
    cells: list[tuple[str, str]] = []
    for n, ((name, *_r), begin) in enumerate(
        zip(HARBORVIEW_PARTNERS, HARBORVIEW_BEGINNING, strict=True), start=2
    ):
        cells += [(f"05!A{n}", name), (f"05!B{n}", begin)]
    return cells


def _replay(events: list[Event]) -> list[Event]:
    out: list[Event] = []
    for i, e in enumerate(sorted(events, key=lambda e: (e.at, e.label))):
        at = max(e.at, REPLAY_FROM + timedelta(seconds=i))
        out.append(Event(e.label, at, e.kind, e.actor, e.slice, {**e.data, "at": e.at.isoformat()},
                         client=e.client))  # fmt: skip
    return out


RUN_1_AT: Final = datetime(2026, 9, 8, 10, 2, tzinfo=CT)
RUN_2_AT: Final = datetime(2026, 9, 10, 15, 31, tzinfo=CT)
# T-05-T62 (part 2, DEC-4937): the memo, its sign-offs, the M-2 fix and Run 3 (DF-34's Sep 14).
MEMO_DRAFTED_AT: Final = datetime(2026, 9, 10, 16, 20, tzinfo=CT)
MEMO_ADOPTED_AT: Final = datetime(2026, 9, 10, 16, 40, tzinfo=CT)
MEMO_APPROVED_AT: Final = datetime(2026, 9, 14, 9, 40, tzinfo=CT)
FIX_APPROVED_AT: Final = datetime(2026, 9, 14, 9, 51, tzinfo=CT)
RUN_3_AT: Final = datetime(2026, 9, 14, 9, 52, tzinfo=CT)
# The M-2 fix (TXP-11 → TXP-00 B): each partner's 18a share of the 6,200 tax-exempt interest
# joins its 05 income and ending capital, so Item L moves 6,860,000 → 6,866,200.
FIX_ADDS: Final = tuple(
    (f"05!{col}{n}", share)
    for n, share in enumerate(next(s for line, *_r, s in SCHEDULE_K if line == "18a"), start=2)
    for col in ("E", "F")
)


@register_slice(SLICE)
def entity_events() -> list[Event]:
    flags = [
        Event(f"flag:{flag}", REPLAY_FROM, "platform.flag_set", "system", SLICE, {"flag": flag})
        for flag in FLAGS
    ]
    events = [
        Event("entity:harborview:seeded", datetime(2026, 8, 20, 9, 0, tzinfo=CT),
              "tax.entity_seeded", "OB", SLICE, {"return": HARBORVIEW}),
        Event("entity:harborview:structure", datetime(2026, 8, 27, 14, 0, tzinfo=CT),
              "tax.allocation_drafted", "DR", SLICE, {"return": HARBORVIEW}),
        Event("entity:harborview:l1", datetime(2026, 8, 27, 14, 5, tzinfo=CT),
              "review.allocation_signed", "DR", SLICE, {"return": HARBORVIEW, "level": 1}),
        Event("entity:harborview:l3", datetime(2026, 8, 28, 11, 0, tzinfo=CT),
              "review.allocation_signed", "SI", SLICE, {"return": HARBORVIEW, "level": 3}),
        Event("entity:ridgeline:seeded", datetime(2026, 9, 8, 9, 0, tzinfo=CT),
              "tax.entity_seeded", "OB", SLICE, {"return": RIDGELINE}),
        Event("entity:ridgeline:run1", RUN_1_AT, "agents.entity_run_recorded", "OB", SLICE,
              {"return": RIDGELINE, "run_number": 1, "state": "waiting_on_inputs"}),
        Event("entity:ridgeline:structure", datetime(2026, 9, 8, 15, 0, tzinfo=CT),
              "tax.allocation_drafted", "DR", SLICE, {"return": RIDGELINE}),
        Event("entity:ridgeline:l1", datetime(2026, 9, 8, 15, 5, tzinfo=CT),
              "review.allocation_signed", "DR", SLICE, {"return": RIDGELINE, "level": 1}),
        Event("entity:ridgeline:l3", datetime(2026, 9, 9, 10, 0, tzinfo=CT),
              "review.allocation_signed", "SI", SLICE, {"return": RIDGELINE, "level": 3}),
        Event("entity:ridgeline:run2", RUN_2_AT, "agents.entity_run_recorded", "OB", SLICE,
              {"return": RIDGELINE, "run_number": 2, "state": "succeeded"}),
        # T-05-T62 (part 2): the memo drafted and adopted Sep 10, approved Sep 14 9:40 AM; the
        # fix approved 9:51; Run 3 at 9:52 (TXP-00 B); the M-2 review point resolved (badge 10).
        Event("entity:ridgeline:memo", MEMO_DRAFTED_AT, "tax.memo_recorded", "OB", SLICE,
              {"return": RIDGELINE}),
        Event("entity:ridgeline:memo-l1", MEMO_ADOPTED_AT, "review.memo_signed", "OB", SLICE,
              {"return": RIDGELINE, "level": 1}),
        Event("entity:ridgeline:memo-l2", MEMO_APPROVED_AT, "review.memo_signed", "SI", SLICE,
              {"return": RIDGELINE, "level": 2}),
        Event("entity:ridgeline:fix", FIX_APPROVED_AT, "tax.fix_recorded", "DR", SLICE,
              {"return": RIDGELINE}),
        Event("entity:ridgeline:run3", RUN_3_AT, "agents.entity_run_recorded", "DR", SLICE,
              {"return": RIDGELINE, "run_number": 3, "state": "succeeded"}),
        Event("entity:ridgeline:m2-resolved", RUN_3_AT + timedelta(seconds=30),
              "review.ridgeline_issue_resolved", "DR", SLICE,
              {"return": RIDGELINE, "issue": "tax-exempt-interest"}),
    ]  # fmt: skip
    return flags + _replay(events)


__all__ = [
    "CAPITAL",
    "FIX_ADDS",
    "FLAGS",
    "HARBORVIEW",
    "HARBORVIEW_RUNGS",
    "NEEDS",
    "RIDGELINE",
    "SCHEDULE_K",
    "SLICE",
    "TB",
    "TRANSFER",
    "entity_events",
    "harborview_cells",
    "ridgeline_cells",
]
