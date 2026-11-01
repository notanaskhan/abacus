"""The `review` slice (P-04-T36, TASK-2923; P-04 §2 stories, §3 artboard rows; DEC-1969): the
review-grammar objects whose owners have registered, through the services as the people the
design names, so every row carries its real audit event.

- **Northwind materiality** (SHL-11 a to d; A-04-T12's `planning_materiality`; DF-34's
  timeline): Hannah Leclerc adopts Northwind's PY2025 trial balance at 10:02 AM on Sep 14 (net
  assets 16,812,400, unadjusted) and proposes planning materiality at 10:30 AM; Margaret
  Okonkwo decides 1.5% = $252,200 (PM $189,150, CT $12,610, computed by code) at 11:12 AM with
  her rationale (SHL-11 c keeps 10:02 AM for parity, a deviation). On Tue Oct 6
  Hannah raises the reassessment at final and Margaret records "No change" (v3).
- **Northwind trial balance sign-off and notes** (SHL-12 a to c): Marcus Delaney signs L1 on
  the trial balance of record at 10:20 AM on Sep 14; Hannah (RA!C14) and Margaret (RA!C22) raise
  the two review notes assigned to Marcus, so Hannah's L2 is blocked (b).
- **Ridgeline's 11 open issues** (SHL-12 h, TXP-10): 5 "Waiting on the client" and 6 "Review
  points", verbatim from TXP-10, each blocking final approval, raised by Olivia Brandt (the
  return's preparer) on Sep 10 and 11.
- **Feld checkpoints** (SHL-16 c, d): Kevin Osei's two person saves, Checkpoint 1 "Extension
  estimate (4868)" on Apr 13 and "Before K-1 treatment" on Sep 11.

Not here (DEC-1969): Granite Peak's card (the BH FS groupings carry no pre-tax income line for
the For-profit benchmark), the reassessment's $16,861,000 final (A-06 seeds the 48,600 AJE),
Feld's import and agent checkpoints (T-01's file bridge and P-10's agent runs), field histories
(no `tax_return` field owner until T-04), and the RA workpaper the notes sit on (the notes
anchor its cells on the trial balance until A-04's workpaper seed). Opt-in (`--slice review`).
"""

from __future__ import annotations

from datetime import datetime
from typing import Final, NamedTuple

from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import CT
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import SETUP_AT
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "review"
NEEDS: Final = ("people", "standards", "acceptance", "tax_board")
FLAGS: Final = ("review.checkpoints", "assurance.materiality")  # grammar_api is FLAGS_ON's
NORTHWIND: Final = "Northwind Robotics, Inc."
RIDGELINE: Final = "Ridgeline Property Partners, LP"
FELD: Final = "Jonah & Claire Feld"
NORTHWIND_TB_LABEL: Final = "standard"
# The benchmark, as the BH materiality ranges name it for an EBP (defined contribution) audit.
BENCHMARK_KEY: Final = "net_assets"
RATE_PCT: Final = "1.5"
RATIONALE: Final = (
    "Recurring engagement, stable plan, no prior misstatements above CT. 1.5% of net assets, "
    "consistent with PY2024."
)


class Note(NamedTuple):
    cell: str
    by: str
    body: str


# SHL-12 b, verbatim: the two open notes that block Hannah's L2, both assigned to Marcus
# Delaney, the preparer (the handoff's "Risk Assessment · Version 1" cells).
NOTES: Final = (
    Note("RA!C14", "HL", "Explain why participant loans are not a significant risk"),
    Note("RA!C22", "MO", "Link the presumed fraud risk on contributions to EBP-04 procedures"),
)


class Issue(NamedTuple):
    key: str
    kind: str  # missing_information | review_point | waiting_on_client …
    title: str
    at: datetime


def _at(month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, month, day, hour, minute, tzinfo=CT)


# TXP-10, verbatim: 5 waiting on the client + 6 review points = 11.
ISSUES: Final = (
    Issue(
        "754-election",
        "waiting_on_client",
        "§754 election: partners' decision and support for Pell Street II's $360,000 "
        "purchase price",
        _at(9, 11, 10, 0),
    ),
    Issue(
        "pell-street-transfer",
        "waiting_on_client",
        "Pell Street transfer (6/30/2025): assignment agreement and transfer-date balances",
        _at(9, 11, 10, 5),
    ),
    Issue(
        "elm-street-roof",
        "waiting_on_client",
        "Elm Street roof replacement: contractor invoice and placed-in-service date",
        _at(9, 10, 11, 0),
    ),
    Issue(
        "bergen-street-deposits",
        "waiting_on_client",
        "Bergen Street tenant security deposit ledger supporting 121,800",
        _at(9, 10, 11, 5),
    ),
    Issue(
        "december-re-tax",
        "waiting_on_client",
        "December real estate tax installment: county bill supporting the 18,500 accrual",
        _at(9, 10, 11, 10),
    ),
    Issue(
        "tax-exempt-interest",
        "review_point",
        "Tax-exempt interest 6,200 omitted from the capital rollforward",
        _at(9, 10, 16, 9),
    ),
    Issue(
        "larimer-bonus",
        "review_point",
        "Larimer parking lot: 100% bonus requires acquisition after Jan 19, 2025",
        _at(9, 10, 16, 10),
    ),
    Issue(
        "743b-placeholder",
        "review_point",
        "§743(b) placeholder 28,595 pending the §754 decision",
        _at(9, 10, 16, 11),
    ),
    Issue(
        "apportionment",
        "review_point",
        "Apportionment by property: IL 46.0% · CO 31.5% · NY 22.5%",
        _at(9, 10, 16, 12),
    ),
    Issue(
        "nonrecourse-752",
        "review_point",
        "Nonrecourse mortgage shared by year-end profit percentages under §752",
        _at(9, 10, 16, 13),
    ),
    Issue(
        "k2-k3",
        "review_point",
        "Schedules K-2/K-3 required — domestic filing exception unavailable",
        _at(9, 10, 16, 14),
    ),
)
ISSUE_BLOCKS: Final = ("final_approval",)

# SHL-16: Kevin Osei's person saves on the Feld 1040 (the others are import and agent made).
CHECKPOINTS: Final = (
    ("1", "Extension estimate (4868)", _at(4, 13, 12, 0)),
    ("5", "Before K-1 treatment", _at(9, 11, 16, 40)),
)


def _event(key: str, at: datetime, kind: str, actor: str, client: str, **data: object) -> Event:
    return Event(f"review:{key}", at, kind, actor, SLICE, dict(data), client=client)


@register_slice(SLICE)
def review_events() -> list[Event]:
    events = [
        Event(f"flag:{name}", SETUP_AT, "platform.flag_set", "system", SLICE, {"flag": name})
        for name in FLAGS
    ]
    events += [
        _event("northwind:tb", _at(9, 14, 10, 0), "ledger.northwind_tb_recorded", "HL", NORTHWIND),
        _event(
            "northwind:tb-adopted",
            _at(9, 14, 10, 2),
            "assurance.northwind_tb_adopted",
            "HL",
            NORTHWIND,
        ),
        _event(
            "northwind:tb-l1",
            _at(9, 14, 10, 20),
            "review.northwind_tb_signed",
            "MD",
            NORTHWIND,
            level=1,
        ),
    ]
    events += [
        _event(
            f"northwind:note:{n.cell}",
            _at(9, 14, 10, 21 + i),
            "review.northwind_note_raised",
            n.by,
            NORTHWIND,
            cell=n.cell,
            body=n.body,
        )
        for i, n in enumerate(NOTES)
    ]
    events += [
        _event(
            "northwind:materiality-proposed",
            _at(9, 14, 10, 30),
            "assurance.materiality_proposed",
            "HL",
            NORTHWIND,
            benchmark=BENCHMARK_KEY,
            rate_pct=RATE_PCT,
        ),
        _event(
            "northwind:materiality-decided",
            _at(9, 14, 11, 12),
            "review.materiality_decided",
            "MO",
            NORTHWIND,
            option_key="rate_1_5",
            rationale=RATIONALE,
        ),
        _event(
            "northwind:materiality-reassessed",
            _at(10, 6, 9, 0),
            "assurance.materiality_reassessed",
            "HL",
            NORTHWIND,
        ),
        _event(
            "northwind:materiality-no-change",
            _at(10, 6, 9, 30),
            "review.materiality_decided",
            "MO",
            NORTHWIND,
            option_key="no_change",
            rationale="Reassessed at final: no change.",
        ),
    ]
    events += [
        _event(
            f"ridgeline:issue:{i.key}",
            i.at,
            "review.ridgeline_issue_created",
            "OB",
            RIDGELINE,
            issue=i.key,
        )
        for i in ISSUES
    ]
    events += [
        _event(f"feld:checkpoint:{seq}", at, "review.feld_checkpoint_saved", "KO", FELD, name=name)
        for seq, name, at in CHECKPOINTS
    ]
    return events


__all__ = [
    "CHECKPOINTS",
    "FLAGS",
    "ISSUES",
    "ISSUE_BLOCKS",
    "NEEDS",
    "NORTHWIND_TB_LABEL",
    "NOTES",
    "SLICE",
    "review_events",
]
