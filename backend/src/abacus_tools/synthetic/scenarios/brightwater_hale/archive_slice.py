"""The `archive` slice (A-07-T41; A-07 §1, F1 to F7, §5.4; DEC-3302): Brightwater Hale's audits
from completion to the locked archive, through the services as the people the design names, on the
demo clock. Synthetic firm only (PF-X1); every name, date and figure is the handoff's.

**Northwind Robotics 401(k) Plan PY2025** (J03 steps 15 to 19):

- **Fri Oct 2.** The firm switches `assurance_release_mode` to `in_app` and turns the four A-07
  flags on (Grace Holloway). At 8:20 AM Hannah Leclerc starts the representation letter; the
  Agent composes v1 from the firm template's trigger rules ("Hannah Leclerc via Agent"). Hannah
  drafts the report: the ERISA supplemental schedules section on (v1), then other information
  off (v2).
- **Mon Oct 5.** Thomas Whitcombe builds the EQR digest (the Agent's code run) and works the EQR
  checklist: 6 of 10 by 11:05 AM with EQR-1 answered and EQR-2 open with Hannah, ten of ten and
  both notes cleared after the 3:30 PM discussion, then concurs at 4:40 PM (G6). Hannah edits the
  letter to v2 and v3; Margaret Okonkwo approves v3 at 5:10 PM.
- **Tue Oct 6.** Hannah sends the letter to Dana Kowalski, dated as of the report date (Oct 9);
  Dana views it at 11:02 AM.
- **Wed Oct 7.** The team closes the review (every outstanding sign-off and note, so G5 reads
  26 of 26); Margaret approves the report at 4:20 PM (L4 on the report version).
- **Thu Oct 8.** Hannah drafts the AU-C 260 completion letter; Margaret approves and sends it to
  the Benefits Committee's governance room.
- **Fri Oct 9.** The bring-down run #4240 at 9:04 AM (no new events); Dana signs at 9:12 AM, so
  G7 reads "October 9, 2026 = report date"; Margaret releases at 10:07 AM (G8): the archive
  opens Assembling, due Dec 8, 2026.
- **Wed Oct 14.** Hannah records the Form 5500 filed with the EFAST2 acknowledgement.
- **Thu Oct 22.** Marcus Delaney runs the archive readiness check (#4302), which builds the
  binder index: AUD-25 reads "Archive in 47 days".
- **Nov 20 / Nov 24.** Hannah drafts the AU-C 265/703 letter; Margaret sends it on Nov 20;
  Victoria Lam acknowledges it for the Benefits Committee on Nov 24 (POR-15).
- **Thu Dec 3.** Marcus requests the lock; Hannah locks the archive at 4:18 PM CST with
  "Assembly is complete" (G9, the seal).
- **Fri Jan 15, 2027.** Hannah adds the PI-02 alternative-procedure memo after lock ("AU-C 585
  omitted procedure"); Margaret approves it ("Addition logged"; the seal unchanged).

**Granite Peak Outdoor Supply FY2026** (J04): Margaret decides "no substantial doubt" on the
going-concern card on Mon Oct 26; its audit committee (Luis Ferrante, chair) gets the AU-C 260
completion letter on Tue Oct 27, and the report releases that morning.

**Lakeshore Literacy Alliance** (AR-C 90): Omar Haddad, its manager, drafts the review report's
choices on Tue Nov 10 (AUD-23 e). The design names Celia Marsh, the partner; the matrix gives
`report.draft` to a manager or senior only, so the manager drafts (DEC-3306).

Not here, or not as designed (DEC-3302): the rep letter's envelope is written as the provider
would have written it (as `signatures` writes SIG-01's), since the C7 send matures through the
outbox and the provider, and G7 then follows from `rep_letters.record_signature`, the
`envelope.completed` consumer's own call; ReleaseWorkflow's and ArchiveLockWorkflow's
activities run in-process in the workflow's order, so the load needs no worker; the digest's six
cards, the 26 workpapers and the 23 run logs are whatever the earlier slices recorded (the
figures A-07-T43's goldens pin). Opt-in (`--slice archive`).
"""

from __future__ import annotations

from datetime import datetime
from typing import Final

from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import CT
from abacus_tools.synthetic.scenarios.brightwater_hale.prng import stable_id
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "archive"
NEEDS: Final = ("completion", "a07_templates", "report_templates", "governance_room")
FLAGS: Final = ("audits.completion", "audits.letters", "audits.report_release", "audits.archive")
RELEASE_MODE: Final = "in_app"

NORTHWIND: Final = "Northwind Robotics, Inc."
GRANITE: Final = "Granite Peak Outdoor Supply, Inc."
LAKESHORE: Final = "Lakeshore Literacy Alliance"
AUDIT_OF: Final = {NORTHWIND: "A1", GRANITE: "A2", LAKESHORE: "A3"}

# The figures and words the screens show (A-07 §1; the AUD READMEs).
REPORT_DATE: Final = "2026-10-09"
GRANITE_REPORT_DATE: Final = "2026-10-27"
REPORT_CITY: Final = "Chicago, Illinois"
EQR_ITEMS: Final = 10
EQR_DONE_BY_1105: Final = 6
EQR_NOTES: Final = (
    ("EQR-1", "Basis for the service-organisation reliance on Harborline's SOC 1", "HL"),
    ("EQR-2", "Rationale for passing PAJE-1 and PAJE-2 on the SUM", "HL"),
)
LETTER_EDITS: Final = (
    (12, "The plan's late remittance of December 26, 2025 contributions is disclosed in Note 9."),
    (13, "Investment information certified by Harborline Trust Company is complete."),
)
GOVERNANCE_260: Final = "completion_260"
GOVERNANCE_265: Final = "sd_mw_265"
ACKNOWLEDGER: Final = "Victoria Lam"  # the Benefits Committee's chair
FILED_ON: Final = "2026-10-14"
ADDITION_REASON: Final = "au_c_585_omitted_procedure"  # "AU-C 585 omitted procedure"
ADDITION_TITLE: Final = "PI-02 alternative-procedure memo"
ADDITION_DESCRIPTION: Final = (
    "PI-02 alternative procedure: participant deferral rates agreed to payroll elections."
)
GOING_CONCERN_CHOICE: Final = "no_substantial_doubt"
# The EP's rationale (C3 needs one): AUD-19 e's code-computed inputs, in the partner's words.
GOING_CONCERN_RATIONALE: Final = (
    "DSCR of 1.32 against the 1.25 covenant minimum; the Front Range Bank revolver matures in "
    "March 2028."
)
# Granite Peak's TCWG (J04): its audit committee, Luis Ferrante the chair, so the AU-C 260
# completion letter has a room to go to (a governance body is the client's, DEC-93).
GRANITE_BODY: Final = "Audit Committee"
GRANITE_BODY_ID: Final = stable_id("governance-body:granite-audit-committee")
GRANITE_MEMBERS: Final = (("Luis Ferrante", "chair"),)
# The body each audit's governance letters go to, with its members.
BODIES: Final = {
    "A1": None,  # Northwind's Benefits Committee: the governance_room slice's (R-02-T13)
    "A2": (GRANITE_BODY_ID, GRANITE_MEMBERS, GRANITE),
}
# Who does what, by the scenario's seat initials.
PARTNER: Final = "MO"  # Margaret Okonkwo, engagement partner
EQR: Final = "TW"  # Thomas Whitcombe
MANAGER: Final = "HL"  # Hannah Leclerc
SENIOR: Final = "MD"  # Marcus Delaney
ADMIN: Final = "GH"  # Grace Holloway, firm admin
REVIEW_MANAGER: Final = "OH"  # Omar Haddad, Lakeshore's manager (drafts: `report.draft`)


def at(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=CT)


def _at(month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return at(2026, month, day, hour, minute)


def _event(key: str, when: datetime, kind: str, actor: str, client: str = NORTHWIND,
           **data: object) -> Event:  # fmt: skip
    return Event(
        f"archive:{AUDIT_OF[client]}:{key}",
        when,
        kind,
        actor,
        SLICE,
        {"audit": AUDIT_OF[client], **data},
        client=client,
    )


def _setup() -> list[Event]:
    events = [
        Event(f"flag:{flag}", _at(10, 2, 8), "platform.flag_set", "system", SLICE, {"flag": flag})
        for flag in FLAGS
    ]
    events.append(
        Event(
            f"governance-body:{GRANITE_BODY_ID}",
            _at(9, 1, 10),
            "assurance.governance_body_seeded",
            PARTNER,
            SLICE,
            {
                "body": GRANITE_BODY,
                "kind": "audit_committee",
                "members": [list(m) for m in GRANITE_MEMBERS],
                "since": "2026-09-01",
                "body_id": GRANITE_BODY_ID,
                "client": GRANITE,
            },
            client=GRANITE,
        )
    )
    events.append(
        Event(
            "archive:release-mode",
            _at(10, 2, 8, 5),
            "archive.release_mode_set",
            ADMIN,
            SLICE,
            {"mode": RELEASE_MODE},
        )
    )
    return events


def _northwind() -> list[Event]:
    e = _event
    return [
        # Fri Oct 2: the letter's v1 (the Agent's compose run) and the report's two drafts.
        e("letter-v1", _at(10, 2, 8, 20), "archive.letter_composed", MANAGER),
        e("report-v1", _at(10, 2, 9), "archive.report_choice", MANAGER,
          field="erisa_supplemental_schedules", value=True),
        e("report-v2", _at(10, 2, 9, 10), "archive.report_choice", MANAGER,
          field="other_information", value=False),
        # Mon Oct 5: the EQR's morning, the 3:30 PM discussion, the concurrence.
        e("eqr-digest", _at(10, 5, 10, 30), "archive.eqr_digest", EQR),
        e("eqr-items-1", _at(10, 5, 10, 45), "archive.eqr_checklist", EQR, done=EQR_DONE_BY_1105),
        e("eqr-note-1", _at(10, 5, 10, 50), "archive.eqr_note_raised", EQR, n=1),
        e("eqr-note-2", _at(10, 5, 10, 55), "archive.eqr_note_raised", EQR, n=2),
        e("eqr-note-1-responded", _at(10, 5, 11), "archive.eqr_note_responded", MANAGER, n=1),
        e("letter-v2", _at(10, 5, 14), "archive.letter_edited", MANAGER, edit=0),
        e("letter-v3", _at(10, 5, 14, 20), "archive.letter_edited", MANAGER, edit=1),
        e("letter-approval", _at(10, 5, 14, 25), "archive.letter_approval_requested", MANAGER),
        e("eqr-note-2-responded", _at(10, 5, 15, 40), "archive.eqr_note_responded", MANAGER, n=2),
        e("eqr-notes-cleared", _at(10, 5, 16, 10), "archive.eqr_notes_cleared", EQR),
        e("eqr-items-2", _at(10, 5, 16, 20), "archive.eqr_checklist", EQR, done=EQR_ITEMS),
        e("eqr-reviewed", _at(10, 5, 16, 30), "archive.eqr_cards_reviewed", EQR),
        e("eqr-concur", _at(10, 5, 16, 40), "archive.eqr_concurred", EQR),
        e("letter-approved", _at(10, 5, 17, 10), "archive.letter_approved", PARTNER),
        # Tue Oct 6: sent, dated as of the report date; Dana views it.
        e("letter-sent", _at(10, 6, 8, 55), "archive.letter_sent", MANAGER,
          report_date=REPORT_DATE, viewed=_at(10, 6, 11, 2).isoformat()),
        # Wed Oct 7: the review closed (G5), the report approved (L4).
        e("review-closed", _at(10, 7, 15), "archive.review_closed", MANAGER),
        e("report-date", _at(10, 7, 16), "archive.report_dated", MANAGER,
          report_date=REPORT_DATE, city=REPORT_CITY),
        e("report-prepared", _at(10, 7, 16, 10), "archive.report_prepared", MANAGER),
        e("report-approved", _at(10, 7, 16, 20), "archive.report_approved", PARTNER),
        # Thu Oct 8: the AU-C 260 completion letter.
        e("letter-260", _at(10, 8, 10), "archive.governance_drafted", MANAGER,
          letter=GOVERNANCE_260),
        e("letter-260-sent", _at(10, 8, 15), "archive.governance_sent", PARTNER,
          letter=GOVERNANCE_260),
        # Fri Oct 9: the bring-down, the signature, the release.
        e("bring-down", _at(10, 9, 9, 4), "archive.bring_down", PARTNER),
        e("letter-signed", _at(10, 9, 9, 12), "archive.letter_signed", "system"),
        # The completion checklist moved with the bring-down and Dana's signature (the projector,
        # under `make dev`'s relay): its sign-offs read Changed, so they are given again before
        # release (P-04's re-sign; a no-op where nothing moved).
        e("review-final", _at(10, 9, 9, 40), "archive.review_closed", MANAGER),
        e("release", _at(10, 9, 10, 7), "archive.released", PARTNER),
        # Wed Oct 14: the Form 5500 filed.
        e("filed", _at(10, 14, 11), "archive.form_5500_filed", MANAGER, filed_on=FILED_ON),
        # Thu Oct 22: the readiness run builds the binder index.
        e("readiness", _at(10, 22, 9, 15), "archive.readiness", SENIOR),
        # Nov 20 / Nov 24: the AU-C 265/703 letter, sent and acknowledged.
        e("letter-265", _at(11, 20, 9), "archive.governance_drafted", MANAGER,
          letter=GOVERNANCE_265),
        e("letter-265-sent", _at(11, 20, 14), "archive.governance_sent", PARTNER,
          letter=GOVERNANCE_265),
        e("letter-265-ack", _at(11, 24, 10), "archive.governance_acknowledged", "system",
          letter=GOVERNANCE_265, member=ACKNOWLEDGER),
        # Thu Dec 3: the index rebuilt, the request, the lock.
        e("readiness-final", _at(12, 3, 15, 50), "archive.readiness", SENIOR),
        e("lock-requested", _at(12, 3, 16), "archive.lock_requested", SENIOR),
        e("locked", _at(12, 3, 16, 18), "archive.locked", MANAGER),
        # Fri Jan 15, 2027: the PI-02 memo, added after lock and approved.
        e("addition", at(2027, 1, 15, 10), "archive.addition_created", MANAGER),
        e("addition-approved", at(2027, 1, 15, 14), "archive.addition_decided", PARTNER),
    ]  # fmt: skip


def _granite() -> list[Event]:
    e = _event
    return [
        # The FS audit's statements (A-06): drafted from the mapped trial balance, then approved
        # by Luis Ferrante, recorded from his signed approval (AUD-24's "FS approved" row).
        e("statements", _at(10, 23, 9), "archive.statements_drafted", MANAGER, GRANITE),
        e("statements-approved", _at(10, 26, 8), "archive.statements_approved", MANAGER,
          GRANITE),
        e("going-concern", _at(10, 26, 9), "archive.going_concern_requested", MANAGER, GRANITE),
        e("going-concern-decided", _at(10, 26, 11), "archive.going_concern_decided", PARTNER,
          GRANITE, choice=GOING_CONCERN_CHOICE, rationale=GOING_CONCERN_RATIONALE),
        e("letter-v1", _at(10, 26, 13), "archive.letter_composed", MANAGER, GRANITE),
        e("letter-approval", _at(10, 26, 13, 30), "archive.letter_approval_requested", MANAGER,
          GRANITE),
        e("letter-approved", _at(10, 26, 15), "archive.letter_approved", PARTNER, GRANITE),
        e("letter-sent", _at(10, 26, 15, 30), "archive.letter_sent", MANAGER, GRANITE,
          report_date=GRANITE_REPORT_DATE, viewed=_at(10, 26, 16, 15).isoformat()),
        e("review-closed", _at(10, 26, 17), "archive.review_closed", MANAGER, GRANITE),
        e("report-date", _at(10, 26, 17, 10), "archive.report_dated", MANAGER, GRANITE,
          report_date=GRANITE_REPORT_DATE, city=REPORT_CITY),
        e("report-prepared", _at(10, 26, 17, 20), "archive.report_prepared", MANAGER, GRANITE),
        e("report-approved", _at(10, 26, 17, 30), "archive.report_approved", PARTNER, GRANITE),
        e("letter-260", _at(10, 27, 8), "archive.governance_drafted", MANAGER, GRANITE,
          letter=GOVERNANCE_260),
        e("letter-260-sent", _at(10, 27, 8, 30), "archive.governance_sent", PARTNER, GRANITE,
          letter=GOVERNANCE_260),
        e("bring-down", _at(10, 27, 9, 4), "archive.bring_down", PARTNER, GRANITE),
        e("letter-signed", _at(10, 27, 9, 20), "archive.letter_signed", "system", GRANITE),
        e("review-final", _at(10, 27, 10, 30), "archive.review_closed", MANAGER, GRANITE),
        e("release", _at(10, 27, 11), "archive.released", PARTNER, GRANITE),
    ]  # fmt: skip


def _lakeshore() -> list[Event]:
    return [
        # `report.draft` needs the drafter's independence on the engagement (the matrix).
        _event("independence:OH", _at(11, 10, 8, 50), "engagements.member_independence_confirmed",
               REVIEW_MANAGER, LAKESHORE),
        _event("report-v1", _at(11, 10, 9), "archive.report_choice", REVIEW_MANAGER, LAKESHORE,
               field="other_information", value=False),
    ]  # fmt: skip


@register_slice(SLICE)
def archive_events() -> list[Event]:
    return [*_setup(), *_northwind(), *_granite(), *_lakeshore()]
