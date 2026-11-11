"""The `tax_workspace` slice (T-04-T28; T-04 §5.3, §8; TAX-05, TAX-06, TAX-07, TXI-01; DEC-3406):
the Feld 2025 Form 1040's worksheets, issues and named checkpoints, through the services as the
people the design names, so `make seed-demo` and fixture mode show the same figures.

- **Worksheets** (TAX-05 d, TAX-06 sheets, TXI-01): "Sch E p2 — Ridgeline" (TSJ T): net rental
  real estate income 307,900, interest income 4,600 (K-1 box 5), distributions 150,000, the
  tax-exempt interest line still empty (TAX-06's ghost 1,550 is the agent's proposal, not a
  value), and the state allocation IL 141,634 + CO 96,989 + NY 69,277 = 307,900; "New York
  IT-201" (TSJ J): line 20 at 0 (TXI-01 b: 0 → 1,550 when the 18A fix is approved) and the
  engine-computed NY and NYC tax lines (read-only, filled by an approved engine import).
- **Issues** (TAX-06; "7 raised Aug 25"): the three open ones the preparer works besides the
  Draft K-1 dependency (raised by the system when the draft K-1 arrived, T-04-T23): box 18A not on
  the worksheet (Missing information, High), the estimated tax confirmations (Missing
  information, Medium) and full-year NYC residency (Review point, Medium); and the three resolved
  ones of TAX-06 f, closed Aug 27 and Aug 28. 4 open = 2 Missing information + 1 Action required
  + 1 Review point.
- **Checkpoints** (TAX-07, SHL-16): "Initial draft" (Kevin Osei, Aug 25), "K-1 box 18A" (Kevin,
  Sep 14) and "Manager review" (Samuel Ito, Sep 15), beside the review slice's two earlier saves.

Deviations, recorded: the issues are raised as Kevin Osei (the handoff says "Created by Accrued
Agent"; an agent-raised issue needs the drafter's run, P-10/T-04-T25's); the 41 documents'
approval timeline, the Ridgeline and Shah K-1 activities, the residency facts and J19's Okafor
and Thornbury rows are not here yet (T-04-T28 partial). Opt-in (`--slice tax_workspace`), after
`tax_board` (the return) and `review` (the earlier checkpoints).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Final

from abacus.modules.tax.api import SeedField, SeedSection, SeedWorksheet
from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import CT
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "tax_workspace"
NEEDS: Final = ("tax_board", "review")
FELD: Final = "Jonah & Claire Feld"
RETURN_LABEL: Final = "jonah-and-claire-feld"
D = Decimal

RIDGELINE_STATE_SHARES: Final = (("il", D("141634")), ("co", D("96989")), ("ny", D("69277")))
RIDGELINE_BOX2: Final = D("307900")  # = 141,634 + 96,989 + 69,277
K1_BOX5: Final = D("4600")
IT201_LINE20: Final = D("0")  # TXI-01 b: 0, then 1,550 once the 18A fix is approved
FIX_AMOUNT: Final = D("1550")

SCH_E_RIDGELINE: Final = SeedWorksheet(
    key="sch_e_p2:ridgeline",
    form_code="1040_sch_e_p2",
    title="Sch E p2 — Ridgeline",
    group_path="Income > Sch E",
    jurisdiction="US",
    default_tsj="T",
    sections=(
        SeedSection(
            "income",
            "Income and Adjustments",
            (
                SeedField("ordinary_business_income", "Ordinary business income", D("0"), tsj="T"),
                SeedField(
                    "net_rental_real_estate",
                    "Net rental real estate income",
                    RIDGELINE_BOX2,
                    line_ref="K-1 2",
                    tsj="T",
                    engine_field_key="sche_p2.ridgeline_l2",
                ),
                SeedField(
                    "interest_income",
                    "Interest income",
                    K1_BOX5,
                    line_ref="K-1 5",
                    tsj="T",
                    engine_field_key="sche_p2.ridgeline_l5",
                ),
                SeedField(
                    "tax_exempt_interest",
                    "Tax-exempt interest (Form 1040 line 2a)",
                    None,
                    line_ref="K-1 18A",
                    tsj="T",
                    engine_field_key="f1040.l2a",
                ),
                SeedField(
                    "distributions", "Distributions", D("150000"), line_ref="K-1 19A", tsj="T"
                ),
            ),
        ),
        SeedSection(
            "state_allocation",
            "State Allocation",
            (
                *(
                    SeedField(f"{state}_amount", f"{state.upper()} amount", amount, tsj="T")
                    for state, amount in RIDGELINE_STATE_SHARES
                ),
                SeedField(
                    "ny_addition_it201_l20",
                    "NY addition — IT-201 line 20",
                    None,
                    tsj="T",
                ),
            ),
        ),
    ),
)
IT201: Final = SeedWorksheet(
    key="it201",
    form_code="it201",
    title="New York IT-201",
    group_path="State > New York",
    jurisdiction="NY",
    default_tsj="J",
    sections=(
        SeedSection(
            "additions",
            "New York additions",
            (
                SeedField(
                    "line20",
                    "Interest income on state and local bonds",
                    IT201_LINE20,
                    line_ref="20",
                    engine_field_key="it201.line20",
                ),
            ),
        ),
        SeedSection(
            "tax",
            "Tax",
            (
                SeedField(
                    "ny_tax",
                    "New York State tax",
                    None,
                    line_ref="39",
                    derivation="engine",
                    engine_field_key="it201.line39",
                ),
                SeedField(
                    "nyc_tax",
                    "New York City resident tax",
                    None,
                    line_ref="47",
                    derivation="engine",
                    engine_field_key="it201.line47",
                ),
            ),
        ),
    ),
)
WORKSHEETS: Final = (SCH_E_RIDGELINE, IT201)

# (key, title, kind, priority, raised, resolved): TAX-06 a, c, d and f, verbatim.
ISSUES: Final[tuple[tuple[str, str, str, str, datetime, datetime | None], ...]] = (
    (
        "box18a",
        "Source K-1 box 18A 'Tax-exempt interest' is not on the worksheet",
        "missing_information",
        "high",
        datetime(2026, 8, 25, 10, 5, tzinfo=CT),
        None,
    ),
    (
        "estimates",
        "Obtain 2025 federal and NY estimated tax payment confirmations",
        "missing_information",
        "medium",
        datetime(2026, 8, 25, 10, 6, tzinfo=CT),
        None,
    ),
    (
        "nyc_residency",
        "Confirm full-year NYC residency for the IT-201 resident tax",
        "review_point",
        "medium",
        datetime(2026, 8, 25, 10, 7, tzinfo=CT),
        None,
    ),
    (
        "digital_assets",
        "Confirm digital asset transactions for Form 1040",
        "missing_information",
        "medium",
        datetime(2026, 8, 25, 10, 8, tzinfo=CT),
        datetime(2026, 8, 27, 11, 0, tzinfo=CT),
    ),
    (
        "nys_refund",
        "2025 Form 1099-G — confirm taxability of the NY refund",
        "review_point",
        "medium",
        datetime(2026, 8, 25, 10, 9, tzinfo=CT),
        datetime(2026, 8, 27, 11, 30, tzinfo=CT),
    ),
    (
        "refund_account",
        "Refund bank account required — paper refund checks ended Sep 30, 2025",
        "missing_information",
        "medium",
        datetime(2026, 8, 25, 10, 10, tzinfo=CT),
        datetime(2026, 8, 28, 9, 15, tzinfo=CT),
    ),
)
OPEN_ISSUES: Final = 4  # the three above plus the system's Draft K-1 dependency
RESOLVED_ISSUES: Final = 3
RAISED_ISSUES: Final = 7

# (seat, name, at): TAX-07's named checkpoints.
CHECKPOINTS: Final = (
    ("KO", "Initial draft", datetime(2026, 8, 25, 10, 30, tzinfo=CT)),
    ("KO", "K-1 box 18A", datetime(2026, 9, 14, 9, 30, tzinfo=CT)),
    ("SI", "Manager review", datetime(2026, 9, 15, 16, 30, tzinfo=CT)),
)
SEEDED_AT: Final = datetime(2026, 8, 25, 10, 0, tzinfo=CT)


@register_slice(SLICE)
def tax_workspace_events() -> list[Event]:
    events = [
        Event(
            "tax-workspace:feld:worksheets",
            SEEDED_AT,
            "tax.workspace_seeded",
            "KO",
            SLICE,
            {"return": RETURN_LABEL},
            client=FELD,
        )
    ]
    for key, title, kind, priority, raised, resolved in ISSUES:
        events.append(
            Event(
                f"tax-workspace:feld:issue:{key}",
                raised,
                "review.feld_issue_created",
                "KO",
                SLICE,
                {"key": key, "title": title, "kind": kind, "priority": priority},
                client=FELD,
            )
        )
        if resolved is not None:
            events.append(
                Event(
                    f"tax-workspace:feld:issue:{key}:resolved",
                    resolved,
                    "review.feld_issue_resolved",
                    "KO",
                    SLICE,
                    {"key": key},
                    client=FELD,
                )
            )
    for seat, name, at in CHECKPOINTS:
        events.append(
            Event(
                f"tax-workspace:feld:checkpoint:{name}",
                at,
                "review.feld_checkpoint_named",
                seat,
                SLICE,
                {"name": name},
                client=FELD,
            )
        )
    return events
