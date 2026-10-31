"""P-11-T12's golden render fixtures (TASK-2514; P-11 §9; SPEC-520 AC-6, AC-11, AC-20; ADR-078).

Brightwater Hale snapshots for ENG-04 b, d, e and f, AUD-21 a, AUD-22 a, AUD-23 a, NOT-03 a and
CLS-08's AR-C 70 package, as plain renderer inputs: DocBlocks with `var` runs, the values code
formatted, the clause states and the mode. Wording, names, amounts and dates are the handoff's
(`handoff/screens/<ID>/spec.md`), shortened where a frame shows only part of a section; a frame
that names a clause but shows no body (ENG-04 e's AU-C 210 list) renders its titles only. Test
data, not firm content: nothing here is imported by `abacus` or loaded into a firm (AGENTS 16).

Written from the row and the handoff, not from the renderer (ADR-078): each fixture says what
text its PDF and DOCX must carry, and `p11t12.sha256` records the bytes two fresh containers
agreed on (`make golden-render`, `RECORD_GOLDEN=1` to re-record after an approved engine change).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Final

from abacus.modules.reporting.render.core import Mode, RenderInput

Block = dict[str, object]


def t(text: str) -> Block:
    return {"type": "text", "text": text}


def v(key: str) -> Block:
    return {"type": "var", "key": key}


def p(*runs: Block | str) -> Block:
    return {"type": "paragraph", "runs": [t(r) if isinstance(r, str) else r for r in runs]}


def h(text: str, level: int = 2) -> Block:
    return {"type": "heading", "level": level, "text": text}


def ul(*items: str) -> Block:
    return {"type": "list", "ordered": False, "items": [[t(i)] for i in items]}


def section(sid: str, title: str, *blocks: Block) -> Block:
    return {"type": "section", "id": sid, "title": title, "blocks": list(blocks)}


def clause(cid: str, *blocks: Block, non_standard: bool = False) -> Block:
    return {
        "type": "clause",
        "clause_id": cid,
        "enabled": True,
        "non_standard": non_standard,
        "blocks": list(blocks),
    }


def signers(*lines: tuple[str, str]) -> Block:
    return {
        "type": "signature_block",
        "signers": [{"label": label, "name": [t(name)]} for label, name in lines],
    }


def kv(*rows: tuple[str, str]) -> Block:
    return {"type": "kv", "rows": [{"key": k, "value": [t(val)]} for k, val in rows]}


def table(columns: list[str], *rows: list[str]) -> Block:
    return {"type": "table", "columns": columns, "rows": [list(r) for r in rows]}


@dataclass(frozen=True)
class Fixture:
    name: str
    screen: str
    layout: str
    title: str
    as_of: datetime
    mode: Mode
    blocks: list[Block]
    values: dict[str, str]
    legend: str | None = None

    def input(self) -> RenderInput:
        content = sha256(f"p11t12:{self.name}".encode()).hexdigest()
        return RenderInput(
            layout_key=self.layout,
            blocks=list(self.blocks),
            values=dict(self.values),
            title=self.title,
            as_of=self.as_of,
            mode=self.mode,
            content_hash=content,
        )


def _at(y: int, m: int, d: int, hh: int = 9, mm: int = 0) -> datetime:
    return datetime(y, m, d, hh, mm, tzinfo=UTC)


RIDGELINE_VALUES: Final = {
    "letter.date": "September 14, 2026",
    "letter.addressee": "Ridgeline Property Partners, LP",
    "section_754.due": "September 15, 2026",
    "fee.total": "$18,500",
    "fee.breakdown": "$6,500 for the section 754 work and $12,000 for cost segregation "
    "coordination and Form 3115",
    "billing.installment_1": "$9,250",
    "billing.installment_2": "$9,250",
    "third_party_fee.estimate_1": "$9,800",
    "firm.signer": "Daniel Reyes, Partner",
}

ENG04_B = Fixture(
    name="eng04_b_ridgeline_draft",
    screen="ENG-04 b",
    layout="letter",
    title="Engagement letter · Ridgeline cost segregation and §754 analysis",
    as_of=_at(2026, 9, 14, 13, 35),
    mode="draft",
    values=RIDGELINE_VALUES,
    blocks=[
        p(v("letter.date")),
        p(v("letter.addressee")),
        h("Re: Cost segregation and section 754 analysis", 1),
        section(
            "scope",
            "1. Scope of services",
            clause(
                "scope",
                p(
                    "We will (a) analyze whether the partnership should elect under section "
                    "754 for the June 30, 2025 transfer of a 5% interest from Pell Street "
                    "Ventures LLC to Pell Street II LLC, model the resulting section 743(b) "
                    "adjustment and its section 755 allocation, and give you a written "
                    "recommendation."
                ),
            ),
        ),
        section(
            "timing-754",
            "3. Timing and the section 754 deadline",
            clause(
                "timing-754",
                p(
                    "A section 754 election is made with a statement attached to the "
                    "partnership's timely filed 2025 Form 1065, due ",
                    v("section_754.due"),
                    ".",
                ),
                non_standard=True,
            ),
        ),
        section(
            "fees",
            "6. Fees and billing",
            clause(
                "fees",
                p(
                    "A fixed fee of ",
                    v("fee.total"),
                    " (",
                    v("fee.breakdown"),
                    "), billed ",
                    v("billing.installment_1"),
                    " on signature and ",
                    v("billing.installment_2"),
                    " on delivery of the Form 3115 package. The engineer bills its fee, "
                    "estimated at ",
                    v("third_party_fee.estimate_1"),
                    ", directly.",
                ),
            ),
        ),
        section(
            "signatures",
            "10. Signatures",
            {
                "type": "signature_block",
                "signers": [
                    {
                        "label": "BRIGHTWATER HALE LLP — Daniel Reyes, Partner",
                        "name": [v("firm.signer")],
                    },
                    {
                        "label": "ACCEPTED: Ridgeline Property Partners, LP, by Ridgeline GP "
                        "LLC, its general partner — Owen Calder, Managing Member",
                        "name": [t("Owen Calder")],
                    },
                ],
            },
        ),
    ],
)

ENG04_D = Fixture(
    name="eng04_d_copperleaf_signed",
    screen="ENG-04 d",
    layout="letter",
    title="Engagement letter · Copperleaf 2026 Close",
    as_of=_at(2026, 3, 3, 15, 0),
    mode="final",
    values={"approver": "Ben Ashby, Controller"},
    blocks=[
        h("Engagement letter · Copperleaf Coffee Roasters, Inc. · 2026 Close", 1),
        kv(("Approver of record", "Ben Ashby, Controller")),
        p("Approver of record: ", v("approver")),
        p(
            "Monthly statements: AR-C 70 preparation with the 'No assurance is provided' legend "
            "for periods ending before Dec 15, 2026 (SSARS 27 not early-adopted); from the "
            "December 2026 period, statements prepared within this CAS engagement are outside "
            "AR-C 70 (SSARS 27)."
        ),
        signers(
            ("Signed by Tess Moreno · Mar 2, 2026", "Tess Moreno"),
            ("Countersigned by Priya Raman · Mar 3, 2026", "Priya Raman"),
        ),
    ],
)

ENG04_E = Fixture(
    name="eng04_e_fairhaven_audit",
    screen="ENG-04 e",
    layout="letter",
    title="Engagement letter · Fairhaven Foods 401(k) Plan PY2025",
    as_of=_at(2026, 9, 8, 14, 0),
    mode="draft",
    values={
        "ebp.election": "Plan administrator elects (certification required)",
        "ske.designee": "— (no nonattest services)",
        "fee.total": "$26,500",
    },
    blocks=[
        h("Fairhaven Foods 401(k) Plan PY2025", 1),
        p("§103(a)(3)(C) election: ", v("ebp.election")),
        p("SKE designee: ", v("ske.designee")),
        h("Objective and scope"),
        h("Management's responsibilities"),
        h("Auditor's responsibilities"),
        h("Limitations"),
        h("Form of report"),
        h("Use of technology and AI"),
        h("Fees"),
        p("Fees (", v("fee.total"), ")"),
        h("Signatures"),
    ],
)

ENG04_F = Fixture(
    name="eng04_f_feld_consents",
    screen="ENG-04 f",
    layout="consent_7216",
    title="Consent to disclose tax return information to AI service providers",
    as_of=_at(2026, 2, 2, 15, 0),
    mode="final",
    values={"consent.recipients": "Accrued Agent sub-processors (US)"},
    blocks=[
        h("Consent to disclose tax return information to AI service providers", 1),
        p("BH §7216 Consent to Disclose — AI sub-processors v2 · Rev. Proc. 2013-14 §5.05"),
        p("Recipients: ", v("consent.recipients")),
        signers(("Taxpayer", "Claire Feld"), ("Spouse", "Jonah Feld")),
    ],
)

AUD21_A = Fixture(
    name="aud21_a_northwind_rep_letter",
    screen="AUD-21 a",
    layout="letter",
    title="Representation letter · Northwind Robotics 401(k) Plan",
    as_of=_at(2026, 10, 9, 14, 0),
    mode="draft",
    values={"letter.date": "October 9, 2026"},
    blocks=[
        p("Northwind Robotics 401(k) Plan"),
        p("c/o Northwind Robotics, Inc. · Plan Administrator"),
        p(v("letter.date")),
        p("Brightwater Hale LLP · 311 West Brannock Street · Chicago, Illinois"),
        p(
            "We are providing this letter in connection with your audit of the financial "
            "statements of the Northwind Robotics 401(k) Plan as of December 31, 2025 and 2024 "
            "and for the year ended December 31, 2025. The audit was performed under ERISA "
            "section 103(a)(3)(C), as we elected. We confirm, to the best of our knowledge and "
            "belief, the following representations made to you during the audit."
        ),
        h("Financial statements", 3),
        p(
            "1. We have fulfilled our responsibilities, as set out in the engagement letter, for "
            "the preparation and fair presentation of the financial statements in accordance "
            "with US GAAP."
        ),
        p(
            "3. The effects of the uncorrected misstatements in the attached summary are "
            "immaterial, individually and in aggregate, to the financial statements as a whole."
        ),
        h("Plan-specific matters", 3),
        p(
            "12. Participant contributions of $33,540 withheld from the December 26, 2025 payroll "
            "were remitted on January 9, 2026. Lost earnings of $64.38 were deposited on "
            "September 30, 2026 under the Voluntary Fiduciary Correction Program Self-Correction "
            "Component. There were no other late remittances."
        ),
        p(
            "15. Loans of three terminated participants totaling $14,850 were offset and "
            "reported as distributions."
        ),
        signers(("HR Director and Plan Administrator · Date: October 9, 2026", "Dana Kowalski")),
        {
            "type": "enclosures",
            "items": [
                "Attachment — Summary of uncorrected misstatements "
                "(PAJE-1 35,300 · PAJE-2 (13,050))"
            ],
        },
    ],
)

AUD22_A = Fixture(
    name="aud22_a_northwind_planning_letter",
    screen="AUD-22 a",
    layout="letter",
    title="Planning communication · Northwind Robotics 401(k) Plan",
    as_of=_at(2026, 9, 17, 14, 0),
    mode="draft",
    values={"letter.date": "September 17, 2026"},
    blocks=[
        p("Brightwater Hale LLP · 311 West Brannock Street, Chicago, IL"),
        p(v("letter.date")),
        p("Members of the Benefits Committee · Northwind Robotics 401(k) Plan"),
        h("Our planned audit of the plan's 2025 financial statements", 2),
        h("Planned scope and timing", 3),
        ul(
            "Planning: September 14\u201318, 2026",
            "Fieldwork: September 21 \u2013 October 2, 2026",
            "Report expected: October 9, 2026",
            "Form 5500 due: October 15, 2026 (extended with Form 5558)",
        ),
        h("Significant risks we identified", 3),
        ul(
            "Management override of controls (presumed under auditing standards)",
            "Contributions — completeness, cutoff and timeliness of remittances to the trust",
            "Participant eligibility and automatic enrollment under the plan's QACA provisions",
        ),
        p(
            "We rebutted the presumed risk of fraud in revenue recognition. The plan has no "
            "revenue transactions; contributions follow payroll and the plan's terms."
        ),
        h("Your input", 3),
        p(
            "Please tell us about any fraud risks you are aware of, any late remittances, and "
            "any plan amendments or operational corrections since January 1, 2025."
        ),
        signers(("Engagement Partner", "Margaret Okonkwo")),
    ],
)

AUD23_A = Fixture(
    name="aud23_a_northwind_report",
    screen="AUD-23 a",
    layout="report",
    title="Independent auditor's report · v2",
    as_of=_at(2026, 10, 9, 14, 0),
    mode="draft",
    values={"report.date": "October 9, 2026"},
    blocks=[
        p("Brightwater Hale LLP · 311 West Brannock Street, Chicago, IL"),
        h("Independent Auditor's Report", 1),
        p("To the Plan Administrator and Participants of the Northwind Robotics 401(k) Plan"),
        section(
            "scope",
            "Scope and Nature of the ERISA Section 103(a)(3)(C) Audit",
            p(
                "We have performed an audit of the financial statements of the Northwind "
                "Robotics 401(k) Plan, an employee benefit plan subject to ERISA, as permitted by "
                "ERISA section 103(a)(3)(C)."
            ),
        ),
        section(
            "opinion",
            "Opinion",
            p(
                "In our opinion, based on our audit and on the procedures described in the "
                "Auditor's Responsibilities section: the amounts and disclosures in the "
                "accompanying financial statements, other than those agreed to or derived from "
                "the certified investment information, are presented fairly, in all material "
                "respects, in accordance with accounting principles generally accepted in the "
                "United States of America; and the information in the accompanying financial "
                "statements related to assets held by and certified to by a qualified "
                "institution agrees to, or is derived from, in all material respects, the "
                "information prepared and certified by that institution."
            ),
        ),
        signers(("Chicago, Illinois", "Brightwater Hale LLP")),
        p(v("report.date")),
    ],
)

NOT03_A = Fixture(
    name="not03_a_whitley_cp2000",
    screen="NOT-03 a",
    layout="notice_response",
    title="Response letter · CP2000 · TY2024 · Whitley",
    as_of=_at(2026, 9, 14, 14, 0),
    mode="draft",
    values={"amount.due": "$753.01"},
    blocks=[
        p("Marcus and Dana Whitley · Denver, CO"),
        p("September 14, 2026"),
        p("Internal Revenue Service · address as printed on page 1 of the notice"),
        p("Re: Notice CP2000 dated August 24, 2026 · Tax year 2024 · SSN •••-••-6631"),
        p(
            "We have reviewed the proposed changes to our 2024 tax return and agree with them. "
            "The two Forms 1099-INT listed in the notice — Front Range Bank, $1,870.00, and "
            "Lakeview Credit Union, $1,250.00 — reached us after we filed on March 14, 2025, and "
            "were not included on the return."
        ),
        p(
            "We have signed the enclosed response page and are paying the full amount due of ",
            v("amount.due"),
            " ($686.40 tax and $66.61 interest) through IRS Direct Pay; the payment confirmation "
            "is enclosed.",
        ),
        p("Please contact us at the address above with any questions."),
        signers(("Taxpayer", "Marcus Whitley"), ("Spouse", "Dana Whitley")),
        p("Prepared with the assistance of Brightwater Hale LLP"),
    ],
)

ARC70_LEGEND: Final = "No assurance is provided."

CLS08_PACKAGE = Fixture(
    name="cls08_copperleaf_arc70_package",
    screen="CLS-08 (AR-C 70 package)",
    layout="package",
    title="August 2026 statements · Copperleaf Coffee Roasters, Inc.",
    as_of=_at(2026, 9, 8, 14, 0),
    mode="draft",
    values={"entity.name": "Copperleaf Coffee Roasters, Inc."},
    legend=ARC70_LEGEND,
    blocks=[
        {"type": "legend", "text": ARC70_LEGEND},
        h("Copperleaf Coffee Roasters, Inc.", 1),
        p("Balance Sheet"),
        p("August 31, 2026"),
        table(
            ["Account", "Amount"],
            ["Cash", "$256,990.50"],
            ["Merchant clearing (Square, Shopify)", "3,464.95"],
            ["Accounts receivable", "18,420.00"],
            ["Inventory", "55,460.00"],
            ["Prepaid insurance", "2,800.00"],
            ["Total current assets", "337,135.45"],
            ["Net property and equipment", "212,060.00"],
            ["Total assets", "$549,195.45"],
        ),
        {"type": "page_break"},
        h("Income Statement", 2),
        p("For the months ended August 31 and July 31, 2026"),
        table(
            ["Account", "August 2026", "July 2026"],
            ["Café sales", "$96,400.00", "$92,100.00"],
            ["Online sales", "41,880.00", "39,600.00"],
            ["Wholesale", "61,000.00", "58,300.00"],
            ["Subscription revenue", "15,320.00", "15,300.00"],
            ["Total revenue", "214,600.00", "205,300.00"],
            ["Net income", "$27,795.00", "$31,455.00"],
        ),
        {"type": "page_break"},
        h("Commentary", 2),
        p(
            "Revenue rose 4.5% to $214,600. Payroll rose 12.5% to $68,910: two baristas joined at "
            "the end of July, merit increases took effect Aug 1, and the roastery ran overtime "
            "during the Aug 10\u201314 changeover. Repairs and maintenance of $3,200 was an "
            "electrical repair at the espresso bar. Net income was $27,795 (July $31,455)."
        ),
    ],
)

FIXTURES: Final[tuple[Fixture, ...]] = (
    ENG04_B,
    ENG04_D,
    ENG04_E,
    ENG04_F,
    AUD21_A,
    AUD22_A,
    AUD23_A,
    NOT03_A,
    CLS08_PACKAGE,
)
