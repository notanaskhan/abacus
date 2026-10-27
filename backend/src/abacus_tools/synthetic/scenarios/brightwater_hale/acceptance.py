"""The `acceptance` slice (P-07-T40; P-07 §5): scenario content wave 2 for CLI-04, CLI-06h,
CLI-07, CLI-08 and ENG-05, as events the loader replays through engagements' and organisations'
services as the people the handoff names. Synthetic, Brightwater Hale only. Text is verbatim
from the CLI-06, CLI-07 and CLI-08 handoff specs and the ENG-05 and CLI-04 fixtures.

- **Questionnaire templates** (CLI-07): "Tax engagements v2" (the nine CLI-07 rail sections) and
  "Audit & assurance v3" (inferred, DEC-412: the same rail plus R2's "Client responsiveness"
  for continuance). No service writes templates (firm content through an admin screen that does
  not exist yet), so the loader inserts the insert-only rows as the firm admin.
- **Contacts** (CLI-04): Northwind's contacts through `create_contact`, Sam Ortiz excepted (the
  portal slice owns him); Harborline Trust Company also as Calloway Family Trust's custodian,
  the counterparty the conflict searches find. Delegations and invited / active states need
  `invite` and an accepted invitation: not seeded (DEC-412).
- **Northwind team and EQR** (ENG-05): budget hours, Thomas Whitcombe moved from the team to
  EQR (Jun 1; his EBP audits as partner pass the competence check, so no eligibility approval is
  needed, and Celia Marsh does not hold `quality_partner` to give one), Margaret Okonkwo's team
  approval (Jun 1), then Kira Ross proposed by Hannah Leclerc (Sep 11).
- **Independence** (CLI-08a): MO, TW, HL and MD confirm (Aug 3 and 4); Ana Cruz stays pending,
  so the five read "4 of 5". NAS and rotation have no service yet (P-07-T41 stubs): not seeded
  (DEC-412).
- **Conflict checks**: CLI-08c's seven names over Northwind, Harborline cleared "Not adverse"
  by Hannah Leclerc; CLI-06h's "Harborline Trust Company" over the Thornbury client, run and
  cleared by Samuel Ito (a check on a draft is its creator's alone, and Grace may not clear).
- **Acceptance records** (CLI-07): Thornbury's new-engagement record, started by Grace Holloway
  from her intake (CLI-06; a manager may not create engagements, so the record's starter reads
  as its preparer), answered and flagged by Samuel Ito (three human-authored flags, Moderate,
  Grace Holloway's manual fee check), sent to Daniel
  Reyes, who accepts with conditions at Sep 14, 9:46 AM (after E0); Meridian's FY2026 continuance
  opened by Margaret Okonkwo on the archived FY2025 audit.

Acts the handoff dates before the firm's Sep 1 setup are replayed on Sep 2, in their own order,
and keep the canon date in their data (DEC-363's rule). Opt-in (`--slice acceptance`, which
brings `people` for the partners' level and the managers' firm roles); SCENARIO_HASH is unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final

from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import CT
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "acceptance"
NEEDS: Final = ("people",)
FLAGS: Final = ("engagements.acceptance_v2", "contacts.v2", "engagements.v2")
NORTHWIND: Final = "Northwind Robotics, Inc."
CALLOWAY: Final = "Calloway Family Trust"
THORNBURY: Final = "Estate of Walter Thornbury"
MERIDIAN: Final = "Meridian Tool & Die, Inc."
# Pre-setup acts, replayed from Sep 2 at 8:00 CT, ten minutes apart in canon order.
REPLAY_FROM: Final = datetime(2026, 9, 2, 8, 0, tzinfo=CT)


@dataclass(frozen=True)
class Section:
    code: str
    title: str


TAX_SECTIONS: Final[tuple[Section, ...]] = (
    Section("engagement_profile", "Engagement profile"),
    Section("integrity_screening", "Executor integrity screening"),
    Section("authority_documents", "Authority & documents"),
    Section("scope_complexity", "Scope & complexity"),
    Section("client_identification", "Client identification & conflicts"),
    Section("prior_year_history", "Prior-year history"),
    Section("fees_collectability", "Fees & collectability"),
    Section("competence_capacity", "Competence & capacity"),
    Section("conclusion", "Conclusion"),
)
AUDIT_SECTIONS: Final[tuple[Section, ...]] = (
    Section("engagement_profile", "Engagement profile"),
    Section("integrity_screening", "Integrity screening"),
    Section("authority_documents", "Authority & documents"),
    Section("scope_complexity", "Scope & complexity"),
    Section("client_identification", "Client identification & conflicts"),
    Section("prior_year_history", "Prior-year history"),
    Section("client_responsiveness", "Client responsiveness"),
    Section("fees_collectability", "Fees & collectability"),
    Section("competence_capacity", "Competence & capacity"),
    Section("conclusion", "Conclusion"),
)
TEMPLATES: Final[tuple[tuple[str, str, tuple[Section, ...]], ...]] = (
    ("Tax engagements v2", "tax", TAX_SECTIONS),
    ("Audit & assurance v3", "audit_assurance", AUDIT_SECTIONS),
)


@dataclass(frozen=True)
class Contact:
    client: str
    slug: str
    name: str
    party_kind: str
    email: str | None
    role: str | None
    title: str | None


CONTACTS: Final[tuple[Contact, ...]] = (
    Contact(
        CALLOWAY,
        "harborline-trust-company",
        "Harborline Trust Company",
        "organisation",
        "certifications@harborlinetrust.com",
        "custodian",
        "Directed trustee / custodian",
    ),
    Contact(
        NORTHWIND,
        "dana-kowalski",
        "Dana Kowalski",
        "person",
        "dana.kowalski@northwindrobotics.com",
        "plan_sponsor_officer",
        "HR Director",
    ),
    Contact(
        NORTHWIND, "benefits-committee", "Northwind benefits committee", "group", None, None, None
    ),
    Contact(
        NORTHWIND,
        "summit-plan-administrators",
        "Summit Plan Administrators",
        "organisation",
        None,
        "tpa",
        "TPA · prepares Form 5500",
    ),
    Contact(
        NORTHWIND,
        "harborline-trust-company",
        "Harborline Trust Company",
        "organisation",
        "certifications@harborlinetrust.com",
        "custodian",
        "Directed trustee / custodian",
    ),
    Contact(
        NORTHWIND,
        "paygrid-payroll",
        "PayGrid Payroll",
        "organisation",
        None,
        "payroll_provider",
        "Payroll provider",
    ),
)

# ENG-05 (team-roles.ts): budget hours of the people already on A1; TW's 6.0 as EQR has no
# service (DEC-412).
HOURS: Final[tuple[tuple[str, str], ...]] = (
    ("MO", "10.0"),
    ("HL", "37.0"),
    ("MD", "61.0"),
    ("AC", "40.0"),
)
# CLI-08a: who confirms, and the canon date (A1 is in planning, so audit_core confirms nobody;
# AC stays pending).
CONFIRMATIONS: Final[tuple[tuple[str, str], ...]] = (
    ("MO", "2026-08-03"),
    ("TW", "2026-08-04"),
    ("HL", "2026-08-03"),
    ("MD", "2026-08-03"),
)
# CLI-08c, in its row order.
NORTHWIND_NAMES: Final = (
    "Northwind Robotics, Inc.",
    "Northwind Robotics 401(k) Plan",
    "Keystone Retirement Services",
    "Harborline Trust Company",
    "PayGrid Payroll",
    "Summit Plan Administrators",
    "Dana Kowalski",
)
HARBORLINE: Final = "Harborline Trust Company"
NORTHWIND_CLEARANCE: Final = "Custodian for Calloway Family Trust (tax client)"
INTAKE_CLEARANCE: Final = "Counterparty · custodian for Calloway Family Trust — review"

# CLI-07 (handoff spec, frames a, b, d).
THORNBURY_DRAFT: Final[dict[str, object]] = {
    "type_code": "forms_706_709",
    "name": "Estate returns — final 1040 · 1041 · 706",
    "fiscal_period_start": "2026-01-01",
    "fiscal_period_end": "2027-01-31",
    "team": [("DR", "engagement_partner"), ("SI", "manager")],
    "owner": "GH",  # CLI-06: Grace runs the intake (`engagement.create` is not a manager's)
}
THORNBURY_ANSWERS: Final[tuple[tuple[str, str], ...]] = (
    (
        "engagement_profile",
        "Form 706, estate Form 1041, final Form 1040 and Form 56 · tax services only, no attest "
        "relationship (independence not applicable) · §7216 use and AI-disclosure consents "
        "(2 documents) to be signed by the executor",
    ),
    (
        "integrity_screening",
        "OFAC SDN and adverse media on Paul Thornbury and the estate — no matches (Sep 11)",
    ),
    ("authority_documents", "1 flag · letters of office missing"),
    ("scope_complexity", "1 flag · Form 706 required"),
    ("client_identification", "1 flag · executor is also a beneficiary"),
    (
        "prior_year_history",
        "Walter Thornbury's TY2024 Form 1040 filed on time; no open notices; TY2025 Form 1040 in "
        "Gathering (BN / YK)",
    ),
    (
        "fees_collectability",
        "CCH Axcess Practice shows no unpaid invoices on the Walter Thornbury account; the estate "
        "has no billing account there yet, so Grace Holloway confirmed it manually (Sep 11)",
    ),
    (
        "competence_capacity",
        "estate and trust returns in the current year — Calloway Family Trust (1041), Estate of "
        "Eugene Barlow (1041); DR and SI have estate-tax experience",
    ),
)
THORNBURY_FLAGS: Final[tuple[tuple[str, str, str], ...]] = (
    (
        "medium",
        "Form 706 is required",
        "The executor's asset summary puts the gross estate at about $16.4M, above the 2026 "
        "basic exclusion amount of $15,000,000. The return is due Nov 2, 2026 (9 months after "
        "the Feb 2, 2026 date of death). Form 4768 gives an automatic 6-month extension to "
        "file, to May 3, 2027; extending time to pay needs a separate request. Valuations for "
        "non-marketable assets may need a qualified appraiser.",
    ),
    (
        "medium",
        "Executor authority is not yet evidenced",
        "No letters of office from the Circuit Court of Cook County are in Files. The intake "
        "answer says letters are pending. Without them we cannot confirm Paul Thornbury can "
        "engage us or sign for the estate. (Walter's 2025 Form 1040 letter, signed Apr 14, relied "
        "on Paul as the executor named in the will; the estate engagement needs the court's "
        "appointment.)",
    ),
    (
        "low",
        "Client identification — the estate, not the beneficiaries",
        "Paul Thornbury is the executor and also a beneficiary. Our client is the estate acting "
        "through him. Other beneficiaries are not clients, and their interests may differ "
        "(Circular 230 §10.29). The engagement letter should say so.",
    ),
)
THORNBURY_CONDITIONS: Final = (
    "Letters of office on file before the letter is signed.",
    "Letter names the client as the estate, acting through the executor.",
    "Form 56 filed with the IRS.",
)
THORNBURY_RATIONALE: Final = (
    "Risk is moderate and every flag can be resolved by a condition. The firm has current "
    "estate-return capacity, and the 706 deadline leaves 49 days, or longer with Form 4768."
)
MERIDIAN_DRAFT: Final[dict[str, object]] = {
    "type_code": "fs_audit",
    "name": "FY2026 FS Audit",
    "fiscal_period_start": "2026-01-01",
    "fiscal_period_end": "2026-12-31",
    "team": [("MO", "engagement_partner")],
    "prior_audit": "A20",
    "owner": "MO",
}


def _replayed(n: int) -> datetime:
    return REPLAY_FROM + timedelta(minutes=10 * n)


def _at(day: int, hour: int, minute: int) -> datetime:
    return datetime(2026, 9, day, hour, minute, tzinfo=CT)


@register_slice(SLICE)
def acceptance_events() -> list[Event]:
    def event(
        label: str, at: datetime, kind: str, actor: str, data: dict[str, object], **kw: str
    ) -> Event:
        return Event(label, at, kind, actor, SLICE, data, **kw)

    n = iter(range(100))
    events = [
        event(f"flag:{name}", REPLAY_FROM, "platform.flag_set", "system", {"flag": name})
        for name in FLAGS
    ]
    events += [
        event(
            f"questionnaire:{family}",
            REPLAY_FROM,
            "engagements.questionnaire_template_added",
            "GH",
            {"name": name, "family": family, "sections": [[s.code, s.title] for s in sections]},
        )
        for name, family, sections in TEMPLATES
    ]
    # Calloway's custodian first: the Northwind search on Aug 3 finds it.
    events.append(
        event(
            "contact:calloway:harborline-trust-company",
            _replayed(next(n)),
            "organisations.contact_created",
            "DR",
            {"index": 0},
            client=CALLOWAY,
        )
    )
    # ENG-05 history (Jun 1): hours, the EQR, the team approval.
    events += [
        event(
            f"team-hours:A1:{initials}",
            _replayed(next(n)),
            "engagements.member_hours_set",
            "HL",
            {"audit": "A1", "member": initials, "hours": hours, "canon_on": "2026-06-01"},
            client=NORTHWIND,
        )
        for initials, hours in HOURS
    ]
    events += [
        event(
            "team-left:A1:TW",
            _replayed(next(n)),
            "engagements.member_removed",
            "HL",
            {"audit": "A1", "member": "TW", "canon_on": "2026-06-01"},
            client=NORTHWIND,
        ),
        event(
            "eqr:A1:TW",
            _replayed(next(n)),
            "engagements.eqr_assigned",
            "MO",
            {"audit": "A1", "eqr": "TW", "canon_on": "2026-06-01"},
            client=NORTHWIND,
        ),
        event(
            "team-approval:A1",
            _replayed(next(n)),
            "engagements.team_approved",
            "MO",
            {"audit": "A1", "canon_at": "2026-06-01T15:00:00Z"},
            client=NORTHWIND,
        ),
    ]
    # CLI-08c (Aug 3, 10:12 AM): the seven names, Harborline cleared by Hannah Leclerc.
    events.append(
        event(
            "conflict-check:northwind",
            _replayed(next(n)),
            "organisations.conflict_check_run",
            "HL",
            {
                "subject": "client",
                "names": list(NORTHWIND_NAMES),
                "clear": HARBORLINE,
                "reason": NORTHWIND_CLEARANCE,
                "canon_at": "2026-08-03T10:12:00-05:00",
            },
            client=NORTHWIND,
        )
    )
    events += [
        event(
            f"independence:A1:{initials}",
            _replayed(next(n)),
            "engagements.member_independence_confirmed",
            initials,
            {"audit": "A1", "canon_on": on},
            client=NORTHWIND,
        )
        for initials, on in CONFIRMATIONS
    ]
    events += [
        event(
            f"contact:northwind:{c.slug}",
            _replayed(next(n)),
            "organisations.contact_created",
            "MO",
            {"index": i},
            client=c.client,
        )
        for i, c in enumerate(CONTACTS)
        if c.client == NORTHWIND
    ]
    # CLI-06h and CLI-07 a, b, d: Thornbury's draft (on the estate entity audit_core loads with
    # its client, TASK-393), the Harborline hit and the record.
    events += [
        event(
            "draft:thornbury",
            _at(8, 14, 0),
            "engagements.draft_created",
            "GH",
            {"draft": "thornbury"},
            client=THORNBURY,
        ),
        event(
            "conflict-check:thornbury:harborline",
            _at(8, 14, 9),
            "organisations.conflict_check_run",
            "SI",
            {
                "subject": "client",
                "names": [HARBORLINE],
                "clear": HARBORLINE,
                "reason": INTAKE_CLEARANCE,
            },
            client=THORNBURY,
        ),
        event(
            "acceptance-started:thornbury",
            _at(8, 14, 12),
            "engagements.acceptance_started",
            "GH",
            {"draft": "thornbury"},
            client=THORNBURY,
        ),
        event(
            "acceptance-prepared:thornbury",
            _at(11, 15, 30),
            "engagements.acceptance_prepared",
            "SI",
            {"draft": "thornbury", "risk_rating": "moderate"},
            client=THORNBURY,
        ),
        event(
            "acceptance-sent:thornbury",
            _at(11, 16, 1),
            "engagements.acceptance_sent",
            "SI",
            {"draft": "thornbury"},
            client=THORNBURY,
        ),
        event(
            "acceptance-decided:thornbury",
            _at(14, 9, 46),
            "engagements.acceptance_decided",
            "DR",
            {
                "draft": "thornbury",
                "option": "accept_with_conditions",
                "rationale": THORNBURY_RATIONALE,
                "conditions": list(THORNBURY_CONDITIONS),
                "assignee": "SI",
            },
            client=THORNBURY,
        ),
        # CLI-07f: Meridian's continuance, opened before Monday's 10:05 frame.
        event(
            "draft:meridian",
            _at(11, 14, 0),
            "engagements.draft_created",
            "MO",
            {"draft": "meridian"},
            client=MERIDIAN,
        ),
        event(
            "acceptance-started:meridian",
            _at(11, 14, 5),
            "engagements.acceptance_started",
            "MO",
            {"draft": "meridian"},
            client=MERIDIAN,
        ),
        # ENG-05: Kira Ross proposed by Hannah Leclerc, Sep 11, 2026 14:20 UTC.
        event(
            "team-added:A1:KR",
            _at(11, 9, 20),
            "engagements.member_proposed",
            "HL",
            {"audit": "A1", "member": "KR", "role": "staff", "hours": "18.0"},
            client=NORTHWIND,
        ),
    ]
    return events


DRAFTS: Final[dict[str, tuple[str, dict[str, object]]]] = {
    "thornbury": (THORNBURY, THORNBURY_DRAFT),
    "meridian": (MERIDIAN, MERIDIAN_DRAFT),
}
