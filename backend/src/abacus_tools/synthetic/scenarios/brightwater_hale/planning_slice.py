"""The `planning` slice (A-04-T28, TASK-3233): Northwind PY2025's planning day under the demo
clock, through the services as the people the design names, so every row carries its real audit
event and the register's approval meets G4 at 4:40 PM.

- **Risk register** (AUD-08 a): Hannah Leclerc records R1 to R10 at 10:15 AM on Mon Sep 14
  (RA v1): the presumed management-override risk (significant by rule), the presumed fraud risk on
  contributions (R3, proposed significant) and on investment income (R5, its rebuttal proposed),
  and the seven assertion-level risks, each RMM from BH's `rmm_matrix` v1 (the standards slice).
- **Internal control** (AUD-09 a): at 12:20 PM Hannah opens the internal-control paper (EBP-140)
  and records its seven exceptions verbatim: 1 significant deficiency, 3 deficiencies and 3
  exceptions for resolution (no COSO component; migration 0663).
- **Basis**: Northwind's trial balance of record and materiality ($252,200, decided by Margaret at
  11:12 AM) through the review slice's own handlers, each skipped when that slice already ran.
- **Approval** (AUD-08 b, d): at 12:31 PM Hannah routes the register (one `significant_risk` card
  for R3 and R5's rebuttal); at 4:40 PM Margaret Okonkwo approves it. With the materiality the
  review slice decides at 11:12 AM, G4 is met.
- **RA reviewed** (AUD-05 d; TASK-6407, DEC-2957): Marcus Delaney's Risk Assessment paper
  (RA-100, the completion slice's matrix row) exists from 10:14 AM; he signs L1 at 4:45 PM (a
  made-up time: the handoff draws only the review) and Hannah reviews it at 4:52 PM, so the pill
  reads "Reviewed · HL". Her level is L3, the level AUD-17 draws her on RA-100 (DEC-2428).
- **Materiality v3** (AUD-07 d, AC3.6): on Tue Oct 6 Hannah raises the reassessment at final and
  Margaret records "No change", each skipped when the review slice already wrote it.

Not here (recorded in TASK-3233, TASK-6407): the 9:27 AM materiality v1 (the review slice
proposes at 10:30 AM; the handoff gives no proposer or figures for an earlier version), the agent
runs (9:58 AM IC pack failure, 10:40 AM GAP waiting on two inputs, the 12:40 PM SOC draft), which
need the fake-model registry's artefacts; Sep 22 bridge letter and Sep 29 reliance (both act on
Keystone's SOC report, which only the 12:40 PM soc1 run creates); and Granite Peak's risks and
RCM and ITGC processes (no handoff rows; its 10:12 AM materiality is the completion slice's).
Opt-in (`--slice planning`).
"""

from __future__ import annotations

from datetime import datetime
from typing import Final, NamedTuple

from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import CT
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import SETUP_AT
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "planning"
# Not "review": its Feld checkpoint (Apr 13) precedes the tax board's returns (Sep 1), so it cannot
# load past Apr 13; the planning day carries its own idempotent basis events instead.
NEEDS: Final = ("people", "standards", "acceptance", "sampling")  # sampling: BH rmm_matrix v1
FLAGS: Final = ("assurance.risk_register", "assurance.internal_control")
NORTHWIND: Final = "Northwind Robotics, Inc."
IC_PAPER: Final = ("EBP-140", "Internal control")
RA_PAPER: Final = "RA-100"  # the completion slice's MATRIX_PAPERS row (title, kind, creator)
RA_SIGNS: Final = ((1, "MD", (16, 45)), (3, "HL", (16, 52)))  # (level, signer, (hour, minute))
REASSESS_RATIONALE: Final = "Reassessed at final: no change."  # the review slice's words
APPROVAL_RATIONALE: Final = (
    "R3 stays significant: the late December remittance and the cutoff exception. R5's rebuttal "
    "holds: the income is certified and no fraud factors point to it."
)


class Risk(NamedTuple):
    code: str
    area: str
    level: str  # financial_statement | assertion
    assertions: tuple[str, ...]
    inherent: str  # low | moderate | high
    presumption: str  # none | management_override | revenue_recognition
    proposal: str | None  # significance "proposed" or fraud "rebuttal_proposed"


# AUD-08 a, verbatim: the ten risks in register order (codes are assigned R1, R2… on create).
RISKS: Final = (
    Risk("R1", "Management override of controls", "financial_statement", (), "high",
         "management_override", None),
    Risk("R2", "Contributions — participant & employer", "assertion",
         ("occurrence", "accuracy"), "moderate", "none", None),
    Risk("R3", "Contributions — remittance & cutoff", "assertion", ("completeness", "cutoff"),
         "high", "revenue_recognition", "proposed"),
    Risk("R4", "Investments at fair value (certified)", "assertion", ("existence", "valuation"),
         "low", "none", None),
    Risk("R5", "Investment income (certified)", "assertion", ("occurrence", "accuracy"), "low",
         "revenue_recognition", "rebuttal_proposed"),
    Risk("R6", "Notes receivable from participants", "assertion", ("existence", "valuation"),
         "moderate", "none", None),
    Risk("R7", "Benefit payments", "assertion", ("occurrence", "accuracy"), "moderate", "none",
         None),
    Risk("R8", "Participant accounts — eligibility & deferral data", "assertion",
         ("completeness", "accuracy"), "high", "none", None),
    Risk("R9", "Administrative expenses", "assertion", ("occurrence",), "low", "none", None),
    Risk("R10", "Disclosures — parties in interest, Schedule H line 4a", "assertion",
         ("presentation", "completeness"), "moderate", "none", None),
)  # fmt: skip


class ControlFinding(NamedTuple):
    row: int
    matter: str
    description: str
    severity: str | None  # deficiency | significant_deficiency; None: exception for resolution
    coso: str | None


# AUD-09 a, verbatim (rows 2 to 8): 1 significant deficiency, 3 deficiencies, 3 for resolution.
EXCEPTIONS: Final = (
    ControlFinding(
        2,
        "Remittance of deferrals not monitored",
        "The Dec 26, 2025 payroll deferrals and match ($48,600) reached Harborline on Jan 9, "
        "2026; no sponsor control compares pay dates to deposit dates.",
        "significant_deficiency",
        "control_activities",
    ),
    ControlFinding(
        3,
        "Year-end contribution cutoff not recorded",
        "The Dec 26, 2025 payroll ($48,600) is not recorded as contributions receivable at "
        "December 31, 2025.",
        None,
        None,
    ),
    ControlFinding(
        4,
        "Service organization reports not reviewed",
        "Northwind does not review Keystone's SOC 1 report; its period ends Sep 30, 2025 and no "
        "bridge letter covers Oct 1 \u2013 Dec 31, 2025.",  # the handoff's en dash
        "deficiency",
        "monitoring",
    ),
    ControlFinding(
        5,
        "Complementary user entity controls unsupported",
        "Evidence exists for 2 of the 6 CUECs in Keystone's SOC 1 report.",
        "deficiency",
        "control_activities",
    ),
    ControlFinding(
        6,
        "Auto-enrolled participants with no deferrals",
        "4 auto-enrolled employees have no deferrals and no opt-out election on file.",
        None,
        None,
    ),
    ControlFinding(
        7,
        "Loan offsets for terminated participants",
        "3 terminated participants' loans ($14,850) were offset at distribution; confirm they "
        "are reported as distributions on Schedule H.",
        None,
        None,
    ),
    ControlFinding(
        8,
        "Census changes not reviewed",
        "No documented review of hires, terminations and pay changes sent to Keystone.",
        "deficiency",
        "information_communication",
    ),
)


def _at(month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, month, day, hour, minute, tzinfo=CT)


def _event(key: str, at: datetime, kind: str, actor: str, **data: object) -> Event:
    return Event(f"planning:{key}", at, kind, actor, SLICE, {"client": NORTHWIND, **data})


@register_slice(SLICE)
def planning_events() -> list[Event]:
    events = [
        Event(f"flag:{name}", SETUP_AT, "platform.flag_set", "system", SLICE, {"flag": name})
        for name in FLAGS
    ]
    # The basis the register needs (the review slice's 10:00, 10:02, 10:30 and 11:12 events, each
    # skipped when that slice already wrote it): the trial balance of record and materiality.
    events += [
        _event("northwind:tb-basis", _at(9, 14, 10, 2), "assurance.northwind_tb_basis", "HL"),
        _event(
            "northwind:materiality-basis",
            _at(9, 14, 10, 30),
            "assurance.northwind_materiality_basis",
            "HL",
        ),
        _event(
            "northwind:materiality-decided",
            _at(9, 14, 11, 12),
            "review.northwind_materiality_basis_decided",
            "MO",
        ),
    ]
    events += [
        _event("northwind:risks-recorded", _at(9, 14, 10, 15), "assurance.northwind_risks", "HL"),
        _event("northwind:ic-exceptions", _at(9, 14, 12, 20), "assurance.northwind_ic", "HL"),
        _event(
            "northwind:risks-routed", _at(9, 14, 12, 31), "assurance.northwind_risks_routed", "HL"
        ),
        _event(
            "northwind:risks-approved",
            _at(9, 14, 16, 40),
            "review.northwind_risks_approved",
            "MO",
            rationale=APPROVAL_RATIONALE,
        ),
    ]
    events.append(
        _event("northwind:ra-paper", _at(9, 14, 10, 14), "assurance.northwind_ra_paper", "MD")
    )
    events += [
        _event(
            f"northwind:ra-signed:{level}",
            _at(9, 14, hour, minute),
            "review.northwind_ra_signed",
            who,
            paper=RA_PAPER,
            level=level,
        )
        for level, who, (hour, minute) in RA_SIGNS
    ]
    events += [
        _event(
            "northwind:materiality-reassessed",
            _at(10, 6, 9, 0),
            "assurance.northwind_materiality_reassessed",
            "HL",
        ),
        _event(
            "northwind:materiality-no-change",
            _at(10, 6, 9, 30),
            "review.northwind_materiality_no_change",
            "MO",
            rationale=REASSESS_RATIONALE,
        ),
    ]
    return events


__all__ = [
    "EXCEPTIONS",
    "FLAGS",
    "IC_PAPER",
    "NEEDS",
    "RA_PAPER",
    "RISKS",
    "SLICE",
    "planning_events",
]
