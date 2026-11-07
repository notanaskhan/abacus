"""The `completion` slice (A-06-T28; A-06 §5; AUD-15, AUD-16, AUD-17, AUD-20; DEC-2373): Northwind
PY2025's completion through the services as the people the design names, and Brightwater Hale's
ASC 962 Defined contribution checklist, 142 synthetic firm-worded items through the import route
and published by a person. The checklist's wording is keyed placeholders, as the standards slice
keeps checklist text (ADR-056), and is never licensed text.

- **Findings** (AUD-15 a): F-01 to F-04 from control exceptions, F-05 to F-09 as misstatements.
  F-02 is concluded a deficiency on Sep 25 and F-01 a significant deficiency on Sep 28, each by
  Margaret Okonkwo on her card.
- **Entries** (AUD-16): AJE-1 and RJE-1 client approved and PAJE-1/2 declined by Dana Kowalski on
  Sep 25, recorded from her email; Margaret passes PAJE-1/2 on the SUM. F-09 is below CT by code
  (BCT-1). F-07's 35,300 is code's projection of 2,140 over the Participants sample.
- **SUM**: PY-1, the six factors, a frozen snapshot, and Margaret's conclusion on Oct 2.
- **Notes and sign-offs** (AUD-17 a): 14 notes (11 cleared, 2 open, 1 responded) and the named
  workpapers' sign-offs, Marcus Delaney's L2 on EBP-04 going stale when Ana Cruz changes the paper.
- **Statements** (AUD-20): v1 before RJE-1 is recorded, then v2, v3, and Dana's Oct 8 approval.
  The firm's 11 note headings and wording import and publish as firm content (DEC-2389).

Not here, or not as designed (DEC-2373): findings raised by a person, so no agent run; Ana's change
and response are a person's, not "via Agent"; RJE-1 is in v1 from its
approval, so v1's 14,850 difference isn't shown; the checklist's answers are Ana's, reviewed by
Hannah, not the agent's adopted (nothing writes a suggested answer yet); Granite Peak's entry reads
AJE-1, not AJE-3 (see below). Opt-in
(`--slice completion`).
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta
from typing import Final, NamedTuple

from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import CT
from abacus_tools.synthetic.scenarios.brightwater_hale.review_slice import NORTHWIND
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import SETUP_AT
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "completion"
NEEDS: Final = ("people", "standards", "acceptance", "sampling", "tax_board", "review")
FLAGS: Final = ("reporting.fs_disclosure",)
NAME: Final = "ASC 962 · Defined contribution"
FRAMEWORK: Final = "asc_962_dc"
ITEMS: Final = 142
ANSWERED_YES: Final = 97  # AUD-20: Yes 97 · N/A 45 · No 0
NA_REASON: Final = "Not applicable to this plan"
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


# The firm's notes for the plan set (AUD-20 f): the titles and Note 9's words are the design's; a
# figure is `{{fs_line_key}}`, filled at draft from the version's own line. The design's other note
# bodies aren't in the handoff, so those notes are headings (DEC-2389).
NOTES_NAME: Final = "BH plan notes"
NOTES_FRAMEWORK: Final = "us_gaap"
_NOTES: Final = (
    (1, "Description of the Plan", "", ""),
    (2, "Significant Accounting Policies", "", ""),
    (3, "Fair Value Measurements", "Total investments at fair value {{investments}}",
     "investments"),
    (4, "Information Certified by Harborline", "", ""),
    (5, "Notes Receivable from Participants", "", "notes_receivable"),
    (6, "Party-in-Interest Transactions", "", ""),
    (7, "Tax Status", "", ""),
    (8, "Reconciliation to Form 5500",
     "Net assets per the financial statements {{net_assets}}. "
     "Less contributions receivable ({{contributions_receivable}}).",
     "net_assets;contributions_receivable"),
    (9, "Delinquent Participant Contributions",
     "Participant contributions of $33,540 withheld from the December 26, 2025 payroll were "
     "remitted on January 9, 2026. The plan sponsor deposited lost earnings of $64.38 on "
     "September 30, 2026 under the Department of Labor's Voluntary Fiduciary Correction Program "
     "Self-Correction Component.", ""),
    (10, "Plan Termination", "", ""),
    (11, "Subsequent Events", "", ""),
)  # fmt: skip


def notes_csv() -> bytes:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(("number", "title", "body", "line_keys"))
    writer.writerows(_NOTES)
    return out.getvalue().encode()


def checklist_csv() -> bytes:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(("key", "section", "text"))
    for n in range(1, ITEMS + 1):
        section = _SECTIONS[(n - 1) * len(_SECTIONS) // ITEMS]
        writer.writerow((f"dc_{n:03d}", section, f"Synthetic checklist item {n}"))
    return out.getvalue().encode()


class Paper(NamedTuple):
    code: str
    title: str
    kind: str


class SeedException(NamedTuple):
    row: int
    title: str
    coso: str | None
    severity: str | None


class SeedFinding(NamedTuple):
    ref: str
    title: str
    type_: str
    amount: str | None
    nature: str
    effect: dict[str, str]
    sample_error: str | None = None


class SeedEntry(NamedTuple):
    finding: str
    kind: str
    description: str
    lines: tuple[tuple[str, str, str], ...]
    decision: str
    reason: str | None
    note: str | None = None


# AUD-17 a's named papers. The handoff's footer counts 26; it doesn't name the other 13.
PAPERS: Final = (
    Paper("EBP-03", "Eligibility Testing", "ebp_eligibility"),
    Paper("EBP-04", "Contributions & Remittance", "ebp_contributions"),
    Paper("EBP-05", "Distributions & Loans", "ebp_distributions_loans"),
    Paper("EBP-07", "Form 5500 Tie-Out", "ebp_form5500"),
)
# Verbatim from AUD-15. F-01 and F-02's severities are the partner's, on their cards.
EXCEPTIONS: Final = (
    SeedException(
        2,
        "December 26, 2025 payroll deposited January 9, 2026 — 9 business days after payday",
        "control_activities",
        "significant_deficiency",
    ),
    SeedException(
        3,
        "Keystone SOC 1 covers Oct 1, 2024 – Sep 30, 2025; Oct–Dec 2025 gap "  # noqa: RUF001
        "not monitored until the Sep 21, 2026 bridge letter",
        "monitoring",
        "deficiency",
    ),
    SeedException(
        4,
        "Opt-out elections missing for 4 auto-enrolled participants with no deferrals",
        "control_activities",
        "deficiency",
    ),
    SeedException(
        5,
        "Evidence for 4 of 6 complementary user entity controls (Keystone SOC 1) not provided",
        None,
        None,
    ),
)
FINDINGS: Final = (
    SeedFinding(
        "F-05",
        "Contributions receivable not recorded for the December 26, 2025 payroll — $48,600",
        "factual",
        "48600.00",
        "misstatement",
        {"description": "Contributions receivable"},
    ),
    SeedFinding(
        "F-06",
        "Loan offsets of 3 terminated participants ($14,850) presented as deemed distributions",
        "factual",
        "14850.00",
        "reclassification",
        {"description": "Loan offsets to benefits paid"},
    ),
    SeedFinding(
        "F-07",
        "Safe-harbor match not computed on bonus pay; the plan's compensation definition "
        "includes bonuses",
        "projected",
        None,
        "misstatement",
        {
            "description": "Employer safe-harbor match on bonus pay (projected)",
            "workpaper_ref": "EBP-04",
            "assets": "35300.00",
            "net_assets": "35300.00",
            "change_in_net_assets": "35300.00",
        },
        "2140.00",
    ),
    SeedFinding(
        "F-08",
        "Q4 2025 recordkeeping, TPA and audit fees not accrued — auditor estimate $13,050",
        "judgmental",
        "13050.00",
        "misstatement",
        {
            "description": "Accrued administrative expenses — Q4 recordkeeping 6,150 · TPA 2,400 "
            "· audit fee 4,500",
            "workpaper_ref": "EBP-09",
            "liabilities": "13050.00",
            "net_assets": "-13050.00",
            "change_in_net_assets": "-1150.00",
        },
    ),
    SeedFinding(
        "F-09",
        "Rollover received Dec 31, 2025, recorded Jan 2, 2026 — $4,210",
        "factual",
        "4210.00",
        "misstatement",
        {"description": "Rollover recorded late"},
    ),
)
# AJE-1's codes are the handoff's. It gives no codes for the others (aud16.ts), and Northwind's
# trial balance has no such accounts, so these are the design's account names, by key.
ENTRIES: Final = (
    SeedEntry(
        "F-05",
        "aje",
        "Contributions receivable — December 26, 2025 payroll",
        (("1250", "48600.00", "0"), ("4100", "0", "33540.00"), ("4200", "0", "15060.00")),
        "client_accepted",
        None,
    ),
    SeedEntry(
        "F-06",
        "rje",
        "Loan offsets to benefits paid",
        (("5100", "14850.00", "0"), ("5110", "0", "14850.00")),
        "client_accepted",
        None,
    ),
    SeedEntry(
        "F-07",
        "paje",
        "Employer safe-harbor match on bonus pay (projected)",
        (("1250", "35300.00", "0"), ("4200", "0", "35300.00")),
        "client_declined",
        "sponsor will correct under EPCRS in 2026",
        "Declined by Dana Kowalski · Sep 25 — sponsor will correct under EPCRS in 2026",
    ),
    SeedEntry(
        "F-08",
        "paje",
        "Accrued administrative expenses",
        (("5300", "13050.00", "0"), ("2100", "0", "13050.00")),
        "client_declined",
        "recorded when invoiced",
        "Declined by Dana Kowalski · Sep 25 — recorded when invoiced",
    ),
)
PY_EFFECT: Final = {
    "description": "Accrued administrative expenses at 12/31/2024 — reversed in 2025",
    "liabilities": "11900.00",
    "net_assets": "-11900.00",
    "change_in_net_assets": "-11900.00",
}
FACTORS: Final = (
    ("participant_balances", "Yes · 412 census records (PAJE-1)"),
    ("plan_terms", "Yes · AU-C 703 reportable finding"),
    ("trend", "No"),
    ("fraud", "No"),
    ("comparatives", "No · PY effect reverses"),
    ("approaches_pm", "No"),
)
# (raised by, paper, anchor, body, state) AUD-17's three live notes are verbatim; the handoff gives
# the 11 cleared ones no words, so theirs are keyed placeholders.
LIVE_NOTES: Final = (
    ("MO", "EBP-04", "EBP-04!F31",
     "Show the Dec 26 lag is not a pattern — compare all 26 biweekly remittances", "open"),
    ("MO", "EBP-04", "EBP-04!K18", "Show how the $35,300 projection was computed", "responded"),
    ("HL", "EBP-04", "AUD-21 §3",
     "Rep letter: add the specific representation on correcting the 4 missed deferrals", "open"),
)  # fmt: skip
CLEARED_NOTES: Final = 11
RN13_RESPONSE: Final = "Addressed in v3: added the projection table at EBP-04!K18:K24."
# AUD-17 a's matrix, level to signer; EBP-04's L2 is the one that goes stale.
SIGN_OFFS: Final = (
    ("EBP-03", ((1, "AC"), (2, "MD"), (3, "HL"), (4, "MO"))),
    ("EBP-04", ((1, "AC"), (2, "MD"))),
    ("EBP-05", ((1, "AC"), (2, "MD"), (3, "HL"))),
    ("EBP-07", ((1, "AC"), (2, "MD"), (3, "HL"))),
)
# The plan's statement of net assets as firm content (the firm's other set is commercial: PP&E,
# inventory). Same import grammar as `sampling_content.grouping_set_csv`; synthetic wording.
EBP_GROUPING_KEY: Final = "bh-ebp-groupings"
EBP_GROUPING_NAME: Final = "BH EBP groupings"
_EBP_GROUPINGS: Final = (
    ("investments", "Investments", "assets", "investments", "Investments, at fair value",
     "debit", 1000, 1199),
    ("notes_receivable", "Notes receivable", "assets", "notes_receivable",
     "Notes receivable from participants", "debit", 1200, 1249),
    ("contributions_receivable", "Contributions receivable", "assets",
     "contributions_receivable", "Contributions receivable", "debit", 1250, 1299),
    ("accrued_expenses", "Accrued expenses", "liabilities", "accrued_expenses",
     "Accrued administrative expenses", "credit", 2000, 2999),
    ("net_assets", "Net assets", "equity", "net_assets", "Net assets available for benefits",
     "credit", 3000, 3999),
    ("additions", "Additions", "revenue", "contributions", "Contributions", "credit", 4000, 4999),
    ("deductions", "Deductions", "expenses", "benefits_paid", "Benefits paid", "debit",
     5000, 5999),
)  # fmt: skip


def ebp_grouping_csv() -> str:
    head = (
        "grouping_key,grouping_label,class,fs_line_key,fs_line_label,normal_balance,"
        "account_from,account_to"
    )
    rows = [
        ",".join((key, f'"{label}"', klass, line_key, f'"{line}"', side, str(low), str(high)))
        for key, label, klass, line_key, line, side, low, high in _EBP_GROUPINGS
    ]
    return "\n".join((head, *rows)) + "\n"


CONCLUSION_RATIONALE: Final = "Immaterial individually and in aggregate; PY effect reverses."


def _at(month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, month, day, hour, minute, tzinfo=CT)


def _event(key: str, at: datetime, kind: str, actor: str, **data: object) -> Event:
    return Event(f"completion:{key}", at, kind, actor, SLICE, dict(data), client=NORTHWIND)


# Granite Peak FY2026 (J22 step 8): 5% of pre-tax income 3,100,000 decided Sep 14, 10:12 AM, then
# the SURL's Front Range Freight invoice, 68,400, declined by Luis Ferrante on Oct 5 and passed on
# SUM below PM 116,250. The design calls it AJE-3 but names no AJE-1 or AJE-2, so it reads AJE-1
# here: the number is the service's, and inventing two entries to reach 3 would be worse.
GRANITE: Final = "Granite Peak Outdoor Supply, Inc."
GRANITE_PAPER: Final = ("SURL", "Search for unrecorded liabilities")
GRANITE_FINDING: Final = "Improperly excluded: Front Range Freight Co., invoice FRF-30418"
GRANITE_AMOUNT: Final = "68400.00"
GRANITE_RATE_OPTION: Final = "rate_5_0"  # 5% of pre-tax income, code's option
GRANITE_ENTRY: Final = "June inbound freight recorded in July"
GRANITE_LINES: Final = (("5010", "68400.00", "0"), ("2010", "0", "68400.00"))
GRANITE_DECLINED: Final = "The client declines to book it"
GRANITE_PASSED: Final = "Below PM 116,250"


def _granite(key: str, at: datetime, kind: str, actor: str, **data: object) -> Event:
    return Event(f"completion:granite:{key}", at, kind, actor, SLICE, dict(data), client=GRANITE)


def _granite_events() -> list[Event]:
    return [
        # The design's manager on Granite Peak (J22), joining before independence is concluded.
        _granite(
            "team-added:HL",
            _at(9, 10, 9, 5),
            "engagements.member_proposed",
            "MO",
            audit="A2",
            member="HL",
            role="manager",
            hours="40.0",
        ),
        Event(
            "completion:granite:independence:HL",
            _at(9, 10, 9, 40),
            "engagements.member_independence_confirmed",
            "HL",
            SLICE,
            {"audit": "A2"},
            client=GRANITE,
        ),
        _granite("materiality", _at(9, 14, 10), "completion.granite_materiality_proposed", "HL"),
        _granite(
            "materiality-decided",
            _at(9, 14, 10, 12),
            "completion.granite_materiality_decided",
            "MO",
        ),
        _granite("finding", _at(10, 5, 9), "completion.granite_finding", "HL"),
        _granite("sent", _at(10, 5, 9, 30), "completion.granite_sent", "HL"),
        _granite("declined", _at(10, 5, 11), "completion.granite_declined", "HL"),
        _granite("passed", _at(10, 5, 14), "completion.granite_passed", "MO"),
    ]


def _northwind_events() -> list[Event]:
    events = [_event("papers", _at(9, 20, 9), "completion.papers", "HL")]
    events.append(_event("exceptions", _at(9, 24, 10, 10), "completion.exceptions", "HL"))
    at = _at(9, 24, 10, 20)
    for n, finding in enumerate(FINDINGS):
        events.append(
            _event(
                f"finding:{finding.ref}",
                at + timedelta(minutes=n),
                "completion.finding",
                "HL",
                ref=finding.ref,
            )
        )
    for n, entry in enumerate(ENTRIES):
        events.append(
            _event(
                f"entry:{entry.finding}",
                _at(9, 24, 14) + timedelta(minutes=n),
                "completion.entry",
                "HL",
                finding=entry.finding,
            )
        )
    events.append(_event("send", _at(9, 24, 16), "completion.send", "HL"))
    # After Granite Peak's run, which takes the firm's newest published set (sampling, 10:19).
    events.append(_event("groupings", _at(9, 24, 17), "completion.ebp_groupings", "MO"))
    events.append(_event("mapping", _at(9, 24, 17, 10), "completion.mapping", "HL"))
    decided = {"F-05": _at(9, 25, 10), "F-06": _at(9, 25, 11), "F-07": _at(9, 25, 11, 5),
               "F-08": _at(9, 25, 11, 10)}  # fmt: skip
    for entry in ENTRIES:
        events.append(
            _event(
                f"decision:{entry.finding}",
                decided[entry.finding],
                "completion.client_decision",
                "HL",
                finding=entry.finding,
            )
        )
    events += [
        _event("fs:1", _at(9, 25, 10, 30), "completion.statement_drafted", "HL", version=1),
        _event("fs:2", _at(9, 28, 9), "completion.statement_drafted", "HL", version=2),
        _event("sev:F-02", _at(9, 25, 13), "completion.severity_requested", "HL", finding="F-02"),
        _event("sev:F-02:decide", _at(9, 25, 15), "completion.severity_decided", "MO",
               finding="F-02", option="deficiency", rationale="Monitoring gap, since bridged."),
        _event("sev:F-01", _at(9, 28, 10, 15), "completion.severity_requested", "HL",
               finding="F-01"),
        _event("sev:F-01:decide", _at(9, 28, 16, 12), "completion.severity_decided", "MO",
               finding="F-01", option="significant_deficiency",
               rationale="No backup approver; the late deposit is a design gap."),
        _event("pass:F-07", _at(9, 28, 11), "completion.pass", "MO", finding="F-07",
               reason="Below PM; sponsor will correct under EPCRS in 2026."),
        _event("pass:F-08", _at(9, 28, 11, 5), "completion.pass", "MO", finding="F-08",
               reason="Below PM; recorded when invoiced."),
        _event("py", _at(9, 28, 11, 30), "completion.prior_year", "HL"),
        _event("factors", _at(9, 28, 12), "completion.factors", "HL"),
    ]  # fmt: skip
    for code, signs in SIGN_OFFS:
        for level, who in signs:
            events.append(
                _event(
                    f"sign:{code}:{level}",
                    _at(9, 29, 9) + timedelta(minutes=10 * level),
                    "completion.signed",
                    who,
                    paper=code,
                    level=level,
                )
            )
    for n in range(CLEARED_NOTES):
        events.append(
            _event(f"note:cleared:{n + 1}", _at(9, 29, 13) + timedelta(minutes=n),
                   "completion.note_cleared", "HL", n=n + 1)
        )  # fmt: skip
    for n, (who, paper, anchor, body, state) in enumerate(LIVE_NOTES):
        events.append(
            _event(f"note:live:{n + 1}", _at(9, 30, 16, 5) + timedelta(minutes=n),
                   "completion.note_raised", who, paper=paper, anchor=anchor, body=body,
                   state=state)
        )  # fmt: skip
    events += [
        # Ana changes the paper for RN-13: Marcus's L2 reads stale (AUD-17 a).
        _event(
            "rn13:change", _at(10, 2, 13, 58), "completion.paper_changed", "AC", paper="EBP-04"
        ),
        _event(
            "sign:EBP-04:v3", _at(10, 2, 14, 4), "completion.signed", "AC", paper="EBP-04", level=1
        ),
        _event("snapshot", _at(10, 2, 14, 30), "completion.sum_snapshot", "HL"),
        _event("conclude", _at(10, 2, 16, 30), "completion.sum_concluded", "MO"),
        _event("fs:3", _at(10, 6, 9), "completion.statement_drafted", "HL", version=3),
        _event("fs:tie", _at(10, 6, 9, 30), "completion.statement_tied", "HL"),
        _event("checklist:picked", _at(10, 6, 9, 40), "completion.checklist_picked", "HL"),
        _event("checklist:answered", _at(10, 6, 9, 50), "completion.checklist_answered", "AC"),
        _event("checklist:reviewed", _at(10, 6, 10, 20), "completion.checklist_reviewed", "HL"),
        _event("fs:approved", _at(10, 8, 10), "completion.statement_approved", "HL"),
    ]
    return events


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
    events.append(
        Event(
            "completion-notes",
            SETUP_AT + timedelta(seconds=2),
            "methodology.statement_notes_loaded",
            IMPORTER,
            SLICE,
        )
    )
    return events + _northwind_events() + _granite_events()
