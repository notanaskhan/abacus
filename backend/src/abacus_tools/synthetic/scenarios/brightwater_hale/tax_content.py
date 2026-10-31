"""The `tax_content` slice (T-02-T23; T-02 §5; POR-05, TXP-12, POR-13; DEC-1477): T-02's firm and
client content, loaded the way a firm loads its own, through the import and decision paths.
Synthetic, Brightwater Hale only; nothing here is a constant in the product or a migration.

**K-1 sets** (TXP-12 A, C, D). Each issuing return's engine PDFs arrive through the bridge (`pdfs`,
one per recipient: `2025P_Ridgeline_V2_k1_p01.pdf` …), then its K-1 set through the bridge's
`k1_set` engine import (T-02-T20), a person's upload either way:
- Ridgeline Property Partners, LP (1065, five partners: Ridgeline GP LLC, Meera Shah, Pell Street
  Ventures LLC, Pell Street II LLC, Jonah Feld), drafts, with Jonah Feld's box lines as TXP-12's
  expanded row gives them; Samuel Ito shares Meera's and Jonah's drafts with their 1040s on Sep 10
  (the hand-offs that block those returns' final approval, TAX-03's Ridgeline row);
- Bluestem Analytics, LLC (1120-S, Arjun Mehta 70% and Sunita Rao 30%), the final set, with
  ordinary income, interest, nondeductible expenses and distributions (TXP-12 C);
- Calloway Family Trust (1041, Nora and Theo Calloway), drafts with boxes 1, 2a and 2b (TXP-12 D).
TINs carry their last four only where TXP-12 masks one; elsewhere none (no source gives one).
Each recipient has a contact on the issuing client (a person, or "authorized member" for an
entity, as TXP-12's Delivery column names them), the release's delivery contact.

**Portal people** (POR-13): Nora Calloway and the Pell Street Ventures member are client users
whose contacts are active, so a release gives them their `k1_recipient` grant at once (T-02-T21).

**Questions** (POR-05). The firm's organizer template, imported by Grace Holloway and published by
Daniel Reyes: nine sections, 24 questions (4 + 5 + 2 + 2 + 1 + 2 + 2 + 2 + 4). The six POR-05
writes out are verbatim; the rest are keyed placeholders, as the standards slice keeps checklist
text (ADR-056, DEC-1472). Kevin Osei attaches it to the Feld 2025 Binder and Claire Feld answers
22 of 24 (Retirement's IRA question and Other Activity's foreign-account question stay open);
Kevin's digital-asset team question is sent Sep 11 (POR-05 card 1). Hannah Leclerc's four fraud
inquiries to Dana Kowalski on the Northwind audit (due Sep 18, POR-05 d) and her two analytics
questions to Luis Ferrante on Granite Peak (POR-05 e).

**Not here:** the Sep 15 release itself waits on Ridgeline's final approval being seedable (its
L1 to L3 sign-offs and BH-TAX-02's approve path, owed by DEC-1474), so the release snapshot is
T-02-T21's tests' for now; the "Deliverable ready" (`deliverable_ready`, "View your K-1") version
is the `email_templates` slice's.

Opt-in (`--slice tax_content`, which brings what it names in NEEDS).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final

from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import CT
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import SETUP_AT
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.tax_board import NAMED
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "tax_content"
NEEDS: Final = ("binders", "tax_board", "people", "standards", "email_templates", "portal")
FLAGS: Final = ("tax.k1_release", "questionnaires.v1")
SINK: Final = "example.test"


def _at(month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, month, day, hour, minute, tzinfo=CT)


# --- K-1 sets --------------------------------------------------------------------------------


@dataclass(frozen=True)
class Box:
    code: str
    description: str
    amount: str  # a decimal string, as the engine writes it


@dataclass(frozen=True)
class Recipient:
    ref: str
    name: str
    kind: str  # gp, lp, shareholder, beneficiary
    is_entity: bool
    contact: str  # the delivery contact's display name
    tin_last4: str | None = None
    tin_kind: str | None = None
    states: tuple[str, ...] = ()
    k3: str = "not_required"
    boxes: tuple[Box, ...] = ()


@dataclass(frozen=True)
class K1Set:
    client: str
    form: str  # 1065, 1120s, 1041
    engine_return_id: str  # "2025P:Ridgeline"
    version: int
    is_final: bool
    imported_at: datetime
    recipients: tuple[Recipient, ...]

    def pdf_name(self, recipient: Recipient) -> str:
        prefix = self.engine_return_id.replace(":", "_")
        return f"{prefix}_V{self.version}_k1_{recipient.ref.lower()}.pdf"

    def manifest(self) -> bytes:
        """The bridge's `k1_set` JSON (DEC-1471), as the engine writes it."""
        return json.dumps(
            {
                "engine_return_id": self.engine_return_id,
                "version": self.version,
                "is_final": self.is_final,
                "form": self.form,
                "tax_year": 2025,
                "recipients": [
                    {
                        "ref": r.ref,
                        "name": r.name,
                        "kind": r.kind,
                        "is_entity": r.is_entity,
                        **({"tin_last4": r.tin_last4} if r.tin_last4 else {}),
                        **({"tin_kind": r.tin_kind} if r.tin_kind else {}),
                        "k3": r.k3,
                        "states": list(r.states),
                        "documents": [{"kind": "k1", "file_name": self.pdf_name(r)}],
                        "box_lines": [
                            {
                                "document_kind": "k1",
                                "box_code": b.code,
                                "description": b.description,
                                "amount": b.amount,
                            }
                            for b in r.boxes
                        ],
                    }
                    for r in self.recipients
                ],
            },
            sort_keys=True,
        ).encode()


RIDGELINE: Final = "Ridgeline Property Partners, LP"
BLUESTEM: Final = "Bluestem Analytics, LLC"
CALLOWAY: Final = "Calloway Family Trust"
_RIDGELINE_STATES: Final = ("IL", "CO", "NY")

K1_SETS: Final = (
    K1Set(
        RIDGELINE,
        "1065",
        "2025P:Ridgeline",
        2,
        False,
        _at(9, 10, 8),
        (
            Recipient(
                "P01",
                "Ridgeline GP LLC",
                "gp",
                True,
                "Owen Calder",
                "3318",
                "ein",
                _RIDGELINE_STATES,
                "included",
            ),
            Recipient(
                "P02",
                "Meera Shah",
                "lp",
                False,
                "Meera Shah",
                "2290",
                "ssn",
                _RIDGELINE_STATES,
                "included",
            ),
            Recipient(
                "P03",
                "Pell Street Ventures LLC",
                "lp",
                True,
                "Pell Street Ventures LLC · authorized member",
                "7741",
                "ein",
                _RIDGELINE_STATES,
                "included",
            ),
            Recipient(
                "P04",
                "Pell Street II LLC",
                "lp",
                True,
                "Pell Street II LLC · authorized member",
                "5106",
                "ein",
                _RIDGELINE_STATES,
                "included",
            ),
            Recipient(
                "P05",
                "Jonah Feld",
                "lp",
                False,
                "Jonah Feld",
                "4417",
                "ssn",
                _RIDGELINE_STATES,
                "included",
                (
                    Box("2", "Net rental real estate income (loss)", "307900"),
                    Box("5", "Interest income", "4600"),
                    Box("18A", "Tax-exempt interest income", "1550"),
                    Box("19A", "Distributions", "150000"),
                    Box("20A", "Investment income", "4600"),
                ),
            ),
        ),
    ),
    K1Set(
        BLUESTEM,
        "1120s",
        "2025S:Bluestem",
        1,
        True,
        _at(9, 2, 10),
        (
            Recipient(
                "S01",
                "Arjun Mehta",
                "shareholder",
                False,
                "Arjun Mehta",
                states=("NY",),
                boxes=(
                    Box("1", "Ordinary business income (loss)", "602000"),
                    Box("4", "Interest income", "8680"),
                    Box("16C", "Nondeductible expenses", "2940"),
                    Box("16D", "Distributions", "434000"),
                ),
            ),
            Recipient(
                "S02",
                "Sunita Rao",
                "shareholder",
                False,
                "Sunita Rao",
                states=("NY",),
                boxes=(
                    Box("1", "Ordinary business income (loss)", "258000"),
                    Box("4", "Interest income", "3720"),
                    Box("16C", "Nondeductible expenses", "1260"),
                    Box("16D", "Distributions", "186000"),
                ),
            ),
        ),
    ),
    K1Set(
        CALLOWAY,
        "1041",
        "2025F:Calloway",
        1,
        False,
        _at(9, 11, 9),
        (
            Recipient(
                "B01",
                "Nora Calloway",
                "beneficiary",
                False,
                "Nora Calloway",
                boxes=(
                    Box("1", "Interest income", "40000"),
                    Box("2a", "Ordinary dividends", "120000"),
                    Box("2b", "Qualified dividends", "96000"),
                ),
            ),
            Recipient(
                "B02",
                "Theo Calloway",
                "beneficiary",
                False,
                "Theo Calloway",
                boxes=(
                    Box("1", "Interest income", "20000"),
                    Box("2a", "Ordinary dividends", "60000"),
                    Box("2b", "Qualified dividends", "48000"),
                ),
            ),
        ),
    ),
)
# Samuel Ito, Ridgeline's reviewer and its manager on the team (seeded as the tax board seeds its
# teams), shares Meera's and Jonah's drafts with their own 1040s, both of which he reviews (the
# sharer reads both returns, DEC-88; TXP-12 A).
SHARES: Final = (("P02", "Meera Shah"), ("P05", "Jonah & Claire Feld"))
SHARER: Final = "SI"
SHARED_AT: Final = _at(9, 10, 14)
# POR-13's portal people: their contacts are active, so a release grants them at once.
PORTAL_RECIPIENTS: Final = (
    (CALLOWAY, "Nora Calloway"),
    (RIDGELINE, "Pell Street Ventures LLC · authorized member"),
)


def reviewer_of(client: str) -> str:
    """The return's reviewer on the practice board (TPL-01's team "OB / SI": Samuel Ito), who
    uploads the engine's files and shares in the seed."""
    return NAMED[client].team.split("/")[1].strip()


def set_of(client: str) -> K1Set:
    return next(s for s in K1_SETS if s.client == client)


def contact_email(name: str) -> str:
    local = "".join(c for c in name.lower().split("·")[0] if c.isalnum() or c == " ").strip()
    return f"{local.replace(' ', '.')}@{SINK}"


# --- the organizer and questions ---------------------------------------------------------------


@dataclass(frozen=True)
class Question:
    section: str
    key: str
    type: str
    wording: str
    help: str = ""
    answer: object = None  # None: left open


ORGANIZER_NAME: Final = "2025 Tax Organizer"
_SECTIONS: Final = (
    ("Personal & Household Information", "personal", 4),
    ("Income Sources", "income", 5),
    ("Home & Property", "home", 2),
    ("Health & Medical", "health", 2),
    ("Education & Student", "education", 1),
    ("Retirement", "retirement", 2),
    ("Charitable & Donations", "charity", 2),
    ("Business & Self-Employment", "business", 2),
    ("Other Activity", "other", 4),
)
# POR-05's six written-out questions, by (section key, position); the rest are placeholders.
_WRITTEN: Final[dict[tuple[str, int], Question]] = {
    ("personal", 1): Question(
        "Personal & Household Information",
        "personal-01",
        "yes_no",
        "Did your filing status change in 2025?",
        answer=False,
    ),
    ("home", 1): Question(
        "Home & Property",
        "home-01",
        "yes_no",
        "Did you buy, sell or refinance a home?",
        answer=False,
    ),
    ("retirement", 1): Question(
        "Retirement",
        "retirement-01",
        "amount_group",
        "Did you or Jonah contribute to an IRA, HSA or 529 plan for 2025?",
        "IRA and HSA contributions for 2025 could be made until April 15, 2026. 529 "
        "contributions count for the year you made them.",
    ),
    ("other", 1): Question(
        "Other Activity",
        "other-01",
        "upload_if_yes",
        "Did you make 2025 estimated tax payments?",
        answer=True,
    ),
    ("other", 2): Question(
        "Other Activity",
        "other-02",
        "yes_no",
        "At any time in 2025, did either of you have a financial interest in, or signature "
        "authority over, a bank or brokerage account outside the United States?",
        "If yes, we'll also check whether an FBAR (FinCEN 114) is required.",
    ),
}


def _organizer() -> tuple[Question, ...]:
    out: list[Question] = []
    for name, key, count in _SECTIONS:
        for n in range(1, count + 1):
            written = _WRITTEN.get((key, n))
            out.append(
                written
                if written is not None
                else Question(
                    name, f"{key}-{n:02d}", "yes_no", f"{name} question {n}", answer=False
                )
            )
    return tuple(out)


ORGANIZER: Final = _organizer()
ANSWERED_BY: Final = "Claire Feld"
ANSWERED_AT: Final = _at(9, 10, 18)  # POR-05's "Answered Aug 20" predates the firm's setup


def organizer_csv() -> bytes:
    """The template in the import format's CSV (T-02-T16), as Grace uploads it."""
    lines = ["section,icon_key,key,type,client_wording,help_text,conditional_on,conditional_value"]
    icons = {name: key for name, key, _ in _SECTIONS}

    def cell(text: str) -> str:
        return '"' + text.replace('"', '""') + '"'

    for q in ORGANIZER:
        lines.append(
            ",".join(
                (
                    cell(q.section),
                    icons[q.section],
                    q.key,
                    q.type,
                    cell(q.wording),
                    cell(q.help),
                    "",
                    "",
                )
            )
        )
    return ("\r\n".join(lines) + "\r\n").encode()


@dataclass(frozen=True)
class Ask:
    """Questions a person sends: a team question, or an inquiry to its addressee."""

    label: str
    actor: str
    client: str
    work: str  # "return" (the client's 2025 return) or "audit" (its audit)
    kind: str  # team_questions, inquiry
    title: str
    addressee: str | None
    due: str | None
    sent_at: datetime
    questions: tuple[tuple[str, str], ...]  # (wording, help)


ASKS: Final = (
    Ask(
        "feld-digital-asset",
        "KO",
        "Jonah & Claire Feld",
        "return",
        "team_questions",
        "Questions from your team",
        None,
        None,
        _at(9, 11, 10),
        (
            (
                "Did either of you sell, exchange or receive any digital assets (such as "
                "cryptocurrency) in 2025?",
                "Your 2024 return answered Yes to this question. Exchanges send Form 1099-DA for "
                "the first time for 2025.",
            ),
        ),
    ),
    Ask(
        "northwind-fraud-inquiries",
        "HL",
        "Northwind Robotics, Inc.",
        "audit",
        "inquiry",
        "PY2025 audit — fraud risk inquiries",
        "Dana Kowalski",
        "2026-09-18",
        _at(9, 11, 15),
        (
            (
                "Are you aware of any actual, suspected or alleged fraud affecting the Northwind "
                "Robotics 401(k) Plan since January 1, 2025?",
                "",
            ),
            (
                "How do you identify and respond to risks such as unauthorized distributions, "
                "loans or changes to participant data?",
                "",
            ),
            (
                "Were any participant contributions sent to the trust late in 2025 or 2026, or "
                "corrected through the DOL's Voluntary Fiduciary Correction Program?",
                "",
            ),
            (
                "Have you told the people who handle plan transactions what's expected of them on "
                "ethics and conduct, and how?",
                "",
            ),
        ),
    ),
    Ask(
        "granite-peak-analytics",
        "HL",
        "Granite Peak Outdoor Supply, Inc.",
        "audit",
        "team_questions",
        "FY2026 audit — questions",
        None,
        None,
        _at(9, 12, 11),
        (
            (
                "Inventory rose $2,240,000 (24.4%) to $11,420,000 at June 30, 2026. What drove "
                "the increase, and how much relates to products discontinued during the year?",
                "",
            ),
            (
                "Gross margin fell from 41.0% to 40.0%. Which cost changes (freight, product mix, "
                "markdowns) explain it?",
                "",
            ),
        ),
    ),
)


def ask_of(label: str) -> Ask:
    return next(a for a in ASKS if a.label == label)


# --- the timeline ------------------------------------------------------------------------------


@register_slice(SLICE)
def tax_content_events() -> list[Event]:
    events = [
        Event(f"flag:{name}", SETUP_AT, "platform.flag_set", "system", SLICE, {"flag": name})
        for name in FLAGS
    ]
    contacts_at = SETUP_AT + timedelta(hours=3)
    n = 0
    for k1_set in K1_SETS:
        for r in k1_set.recipients:
            events.append(
                Event(
                    f"k1-contact:{k1_set.client}:{r.ref}",
                    contacts_at + timedelta(seconds=n),
                    "tax.k1_contact_created",
                    "GH",
                    SLICE,
                    {"client": k1_set.client, "ref": r.ref},
                    client=k1_set.client,
                )
            )
            n += 1
    for client, name in PORTAL_RECIPIENTS:
        events.append(
            Event(
                f"k1-portal-person:{name}",
                contacts_at + timedelta(minutes=5),
                "tax.k1_portal_person_added",
                "GH",
                SLICE,
                {"client": client, "contact": name},
                client=client,
            )
        )
    for k1_set in K1_SETS:
        for i, r in enumerate(k1_set.recipients):
            events.append(
                Event(
                    f"k1-pdf:{k1_set.client}:{r.ref}",
                    k1_set.imported_at + timedelta(seconds=i),
                    "tax.engine_pdf_imported",
                    reviewer_of(k1_set.client),
                    SLICE,
                    {"client": k1_set.client, "ref": r.ref},
                    client=k1_set.client,
                )
            )
        events.append(
            Event(
                f"k1-set:{k1_set.client}:v{k1_set.version}",
                k1_set.imported_at + timedelta(minutes=5),
                "tax.k1_set_imported",
                reviewer_of(k1_set.client),
                SLICE,
                {"client": k1_set.client},
                client=k1_set.client,
            )
        )
    for ref, target in SHARES:
        events.append(
            Event(
                f"k1-share:{ref}:{target}",
                SHARED_AT,
                "tax.k1_shared",
                SHARER,
                SLICE,
                {"client": RIDGELINE, "ref": ref, "target": target},
                client=RIDGELINE,
            )
        )
    template_at = SETUP_AT + timedelta(hours=4)
    events += [
        Event("organizer-import", template_at, "requests.organizer_imported", "GH", SLICE, {}),
        Event(
            "organizer-publish",
            template_at + timedelta(minutes=10),
            "requests.organizer_published",
            "DR",
            SLICE,
            {},
        ),
        Event(
            "organizer-attach:feld",
            template_at + timedelta(minutes=20),
            "requests.organizer_attached",
            "KO",
            SLICE,
            {"client": "Jonah & Claire Feld"},
            client="Jonah & Claire Feld",
        ),
    ]
    answered = [q for q in ORGANIZER if q.answer is not None]
    for i, q in enumerate(answered):
        events.append(
            Event(
                f"organizer-answer:{q.key}",
                ANSWERED_AT + timedelta(seconds=i),
                "requests.organizer_answered",
                "system",
                SLICE,
                {"key": q.key, "person": ANSWERED_BY},
                client="Jonah & Claire Feld",
            )
        )
    for ask in ASKS:
        events.append(
            Event(
                f"ask:{ask.label}",
                ask.sent_at,
                "requests.questions_sent",
                ask.actor,
                SLICE,
                {"label": ask.label},
                client=ask.client,
            )
        )
    return events


__all__ = [
    "ASKS",
    "FLAGS",
    "K1_SETS",
    "NEEDS",
    "ORGANIZER",
    "ORGANIZER_NAME",
    "PORTAL_RECIPIENTS",
    "SHARES",
    "SLICE",
    "Ask",
    "K1Set",
    "Recipient",
    "ask_of",
    "contact_email",
    "organizer_csv",
    "reviewer_of",
    "set_of",
    "tax_content_events",
]
