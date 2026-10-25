"""The `compliance` slice (Q-02-T39; Q-02 §5): what the FIL-02 and ADM-06 families need from the
live seed, as events the loader replays through evidence's and platform's services. Synthetic,
Brightwater Hale only; nothing here is platform content.

- **Retention policies** (FIL-02a, its eight rows): the firm's policy per record type, set by
  Felix Andersen (the security admin, `retention_policy.update`). Every firm policy is 7 years,
  from the row's "Clock starts" event; Audit documentation is locked ("Locked · WORM"). The legal
  minimums beside them are **not** seeded: floors are platform reference data published with
  counsel through the two-person import (DEC-71, Q-02-T31), and no floor value may sit in a
  commit. Until a floor set is published, the policies read with no legal minimum. No basis text
  is seeded: FIL-02 gives none. The record-type codes are the seed's (DEC-363).
- **Legal holds** (FIL-02b): Collins · CP2000 · TY2023 placed by Victor Hammond and Meridian ·
  IL-1120 · TY2024 placed by Neil Ashcroft, both partners, each on its client and tax year, then
  taken to Active by the steps `LegalHoldApply` runs. The handoff dates them Aug 12 and Aug 14,
  2026, before the firm's Sep 1 setup on the timeline, so they are placed at the setup instant
  (DEC-363, as DEC-213 did for POR-02b's history); the FIL-02 fixture keeps the canon dates.
- **INC-2026-005** (ADM-06 a, d): "Credential-stuffing attempts against client portal sign-in",
  credential attack, discovered Thu Sep 10, 2026 at 2:14 AM CT, 0 consumers affected, recorded
  by Felix Andersen; on Mon Sep 14 the clock reads day 4 of 30, notify by Sat Oct 10. The
  register numbers a firm's incidents itself (DEC-290), so the loaded reference is the firm's
  first of 2026, not the canon's fifth (TASK-1242 holds the gap).
- **The rollout flags** the services sit behind, `compliance.legal_holds` and
  `compliance.incidents`, turned on for the firm first.

Not seeded yet (DEC-363): the export history (Sep 1 386 GB, Aug 1 371 GB, Jul 1 359 GB) waits
for the `firm_exports` table (Q-02-T43); the agent stages wait for a stage service a loader can
call for a synthetic firm (today's is the owner-role founder command, which refuses `live`
without 50 shadow runs over 14 days). Both stay in apps/web/src/fixtures/seed/compliance.ts.

Opt-in (`--slice compliance`, which brings `people` for Felix's security-admin template and the
partners' level); `build()` keeps its default, so SCENARIO_HASH is unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal

from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import CT
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import SETUP_AT
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "compliance"
NEEDS: Final = ("people",)
QI: Final = "FA"  # Felix Andersen, IT / Security, the firm's Qualified Individual
FLAGS: Final = ("compliance.legal_holds", "compliance.incidents")

ServiceLine = Literal["audit", "tax", "cas", "advisory", "any"]


@dataclass(frozen=True)
class Policy:
    """One FIL-02a row: the record type, the line it applies to, the firm's years, the event its
    clock starts from and whether it is locked."""

    record_type: str
    label: str  # FIL-02a's record-type column, for readers of this file
    service_line: ServiceLine
    firm_years: str
    clock_start_event: str
    lock: bool = False


POLICIES: Final[tuple[Policy, ...]] = (
    Policy(
        "efile_authorization",
        "Signed e-file authorizations (8879 family)",
        "tax",
        "7",
        "due_or_received_later",
    ),
    Policy("return_copy", "Copies of returns prepared", "tax", "7", "filing_date"),
    Policy(
        "tax_source_workpapers", "Tax source documents & workpapers", "tax", "7", "filing_date"
    ),
    Policy("audit_documentation", "Audit documentation", "audit", "7", "report_release", True),
    Policy("cas_workpapers", "CAS workpapers & FS packages", "cas", "7", "period_end"),
    Policy(
        "engagement_letter_consent",
        "Engagement letters & §7216 consents",
        "any",
        "7",
        "relationship_end",
    ),
    Policy("permanent_file", "Permanent file", "any", "7", "client_inactive"),
    Policy("client_messages", "Email & portal messages", "any", "7", "message_date"),
)


@dataclass(frozen=True)
class Hold:
    """One FIL-02b row, held on its client and tax year."""

    label: str
    client: str
    tax_year: int
    reason_code: str
    details: str  # FIL-02b's Reason column, verbatim
    placed_by: str  # initials
    canon_placed_on: str  # the handoff's date; the timeline places it at setup (DEC-363)


HOLDS: Final[tuple[Hold, ...]] = (
    Hold(
        "collins-cp2000-ty2023",
        "Wren & Avery Collins",
        2023,
        "irs_examination",
        "IRS controversy — CP2000 disagreed (N3), awaiting IRS",
        "VH",
        "2026-08-12",
    ),
    Hold(
        "meridian-il1120-ty2024",
        "Meridian Tool & Die, Inc.",
        2024,
        "regulatory_inquiry",
        "State controversy — Illinois DOR notice (N8), response sent Sep 2",
        "NA",
        "2026-08-14",
    ),
)

INCIDENT_LABEL: Final = "INC-2026-005"
INCIDENT_DISCOVERED: Final = datetime(2026, 9, 10, 2, 14, tzinfo=CT)
INCIDENT: Final[dict[str, object]] = {
    "canon_ref": INCIDENT_LABEL,
    "title": "Credential-stuffing attempts against client portal sign-in",
    "event_kind": "credential_attack",
    "discovered_at": INCIDENT_DISCOVERED.isoformat(),
    "consumers_affected": 0,
    "unencrypted": None,
}


@register_slice(SLICE)
def compliance_events() -> list[Event]:
    events = [
        Event(f"flag:{name}", SETUP_AT, "platform.flag_set", "system", SLICE, {"flag": name})
        for name in FLAGS
    ]
    events += [
        Event(
            f"retention-policy:{p.record_type}:{p.service_line}",
            SETUP_AT,
            "evidence.retention_policy_set",
            QI,
            SLICE,
            {
                "record_type": p.record_type,
                "service_line": p.service_line,
                "firm_years": p.firm_years,
                "clock_start_event": p.clock_start_event,
                "lock": p.lock,
            },
        )
        for p in POLICIES
    ]
    events += [
        Event(
            f"legal-hold:{h.label}",
            SETUP_AT,
            "evidence.legal_hold_placed",
            h.placed_by,
            SLICE,
            {
                "client": h.client,
                "tax_year": h.tax_year,
                "reason_code": h.reason_code,
                "details": h.details,
            },
            client=h.client,
        )
        for h in HOLDS
    ]
    events.append(
        Event(
            f"incident:{INCIDENT_LABEL}",
            INCIDENT_DISCOVERED,
            "platform.incident_recorded",
            QI,
            SLICE,
            INCIDENT,
        )
    )
    return events
