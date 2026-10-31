"""The `report_templates` slice (P-11-T13; P-11 §5.4; C11 v1): Brightwater Hale's document
templates, loaded the way a firm loads its own. Each bundle goes through C11's import
(`reporting.api.import_template_bundle`, the `POST /v1/report-templates/import` service) as Grace
Holloway, firm admin, and lands as a draft version; Margaret Okonkwo, practice leader and partner,
publishes it with a fresh second factor (a different person from the importer, AC-3; a partner
for a consent template, T-01-T17). Synthetic wording, Brightwater Hale only: nothing here is
platform content, and no migration or constant in `abacus` carries a template's text (AGENTS 16).

The twelve templates: CAS, audit (EBP) and tax advisory engagement letters; the two §7216
consents, each its own document (use; disclosure to AI service providers); the EBP
representation letter; the AU-C 260 planning letter; the auditor's, review and compilation report
shells; the CP2000 notice response; and the filing instructions letter (TAX-12's packet). Names,
clause titles and the sample data are the handoff's (ENG-04, AUD-21, AUD-22, AUD-23, NOT-03,
TAX-12).

Opt-in (`--slice report_templates`, which brings `people` for Grace's and Margaret's roles).
`docs/guides/template-import.md` is the pilot firm's guide to the same import.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Final

from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import SETUP_AT
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "report_templates"
NEEDS: Final = ("people",)
IMPORTER: Final = "GH"  # Grace Holloway, firm admin (`report_template.import`)
PUBLISHER: Final = "MO"  # Margaret Okonkwo, practice leader and partner (`*.publish`)
FLAG: Final = "reporting.generated_documents"

Json = dict[str, object]
RECIPIENTS: Final = "consent.recipients"


def _t(text: str) -> Json:
    return {"type": "text", "text": text}


def _v(key: str) -> Json:
    return {"type": "var", "key": key}


def _p(*runs: Json | str) -> Json:
    return {"type": "paragraph", "runs": [_t(r) if isinstance(r, str) else r for r in runs]}


def _h(text: str, level: int = 2) -> Json:
    return {"type": "heading", "level": level, "text": text}


def _clause(cid: str) -> Json:
    return {
        "type": "clause",
        "clause_id": cid,
        "enabled": True,
        "non_standard": False,
        "blocks": [],
    }


def _def(cid: str, title: str, *standard: Json, on: bool = True) -> Json:
    return {"clause_id": cid, "title": title, "standard": list(standard), "default_enabled": on}


def _var(key: str, label: str, value_type: str = "text") -> Json:
    return {"key": key, "label": label, "value_type": value_type}


def _sign(*lines: tuple[str, str]) -> Json:
    return {
        "type": "signature_block",
        "signers": [{"label": label, "name": [_v(key)]} for label, key in lines],
    }


_LETTER_VARS: Final = (
    _var("letter.date", "Letter date", "date"),
    _var("client.name", "Client", "name"),
    _var("client.signer", "Client signer", "name"),
    _var("firm.signer", "Firm signer", "name"),
    _var("fee.total", "Fee", "money"),
)
_LETTER_SAMPLE: Final[dict[str, str]] = {
    "letter.date": "September 14, 2026",
    "client.name": "Sample Client, LLC",
    "client.signer": "Sample Signer, Managing Member",
    "firm.signer": "Sample Partner, Partner",
    "fee.total": "$1,000",
}


def _letter(name: str, re_line: str, clauses: list[Json], description: str) -> Json:
    return {
        "family": "engagement_letter",
        "name": name,
        "description": description,
        "layout_key": "letter",
        "body": [
            _p(_v("letter.date")),
            _p(_v("client.name")),
            _h(re_line, 1),
            *(_clause(str(c["clause_id"])) for c in clauses),
            _sign(("BRIGHTWATER HALE LLP", "firm.signer"), ("ACCEPTED", "client.signer")),
        ],
        "clauses": clauses,
        "variables": list(_LETTER_VARS),
        "sample_data": dict(_LETTER_SAMPLE),
    }


_AI_USE: Final = _def(
    "technology-ai",
    "Use of technology and AI",
    _p(
        "We use Accrued, a platform whose AI agents draft work under our supervision. Data stays "
        "in the United States, is not used to train models, and every output is reviewed and "
        "approved by a named Brightwater Hale professional."
    ),
)
_FEES: Final = _def(
    "fees",
    "Fees and billing",
    _p("Our fee for these services is ", _v("fee.total"), ", billed as set out below."),
)

CAS_LETTER: Final = _letter(
    "BH CAS Engagement Letter",
    "Re: Client accounting services",
    [
        _def(
            "scope",
            "Scope of services",
            _p(
                "We will maintain your books, reconcile your accounts each month and prepare "
                "monthly financial statements from the posted ledger."
            ),
        ),
        _def(
            "ssars-route",
            "Reporting on the monthly statements",
            _p(
                "Monthly statements are prepared under AR-C 70 with the legend 'No assurance is "
                "provided' on each page for periods ending before December 15, 2026; from the "
                "December 2026 period, statements prepared within this engagement are outside "
                "AR-C 70 (SSARS 27)."
            ),
        ),
        _def(
            "approver",
            "Approver of record",
            _p("You name an approver of record who approves each month's package."),
        ),
        _FEES,
        _AI_USE,
    ],
    "Client accounting services engagement letter (CAS; AR-C 70 routing)",
)

AUDIT_LETTER: Final = _letter(
    "BH Audit Letter · EBP",
    "Re: Audit of the plan's financial statements",
    [
        _def(
            "objective",
            "Objective and scope",
            _p("We will audit the plan's financial statements."),
        ),
        _def(
            "management",
            "Management's responsibilities",
            _p("Management is responsible for the financial statements and the plan's records."),
        ),
        _def(
            "auditor",
            "Auditor's responsibilities",
            _p("We will conduct the audit under auditing standards generally accepted in the US."),
        ),
        _def("limitations", "Limitations", _p("An audit does not detect every misstatement.")),
        _def("report", "Form of report", _p("We expect to issue a written report on the audit.")),
        _AI_USE,
        _FEES,
    ],
    "Employee benefit plan audit engagement letter (AU-C 210)",
)

TAX_LETTER: Final = _letter(
    "BH Tax Advisory Letter",
    "Re: Tax advisory services",
    [
        _def(
            "scope",
            "Scope of services",
            _p("We will provide the tax advisory services described in this letter."),
        ),
        _def(
            "not-included",
            "Services not included",
            _p("Services not described in this letter are not included."),
        ),
        _def(
            "responsibilities",
            "Your responsibilities",
            _p("The decision to make any election is yours. You will provide what we request."),
        ),
        _FEES,
        _AI_USE,
    ],
    "Tax advisory engagement letter",
)


def _consent(name: str, purpose: str, heading: str, ask: str) -> Json:
    return {
        "family": "consent_7216",
        "name": name,
        "description": f"Section 7216 consent, one purpose per document ({purpose})",
        "layout_key": "consent_7216",
        "body": [
            _h(heading, 1),
            _p("Taxpayer: ", _v("taxpayer.name")),
            _p(ask),
            _p("Recipients: ", _v(RECIPIENTS)),
            _p("Tax years covered: ", _v("consent.tax_years")),
            _sign(("Taxpayer", "taxpayer.name")),
        ],
        "variables": [
            _var("taxpayer.name", "Taxpayer", "name"),
            _var(RECIPIENTS, "Recipients"),
            _var("consent.tax_years", "Tax years"),
        ],
        "sample_data": {"taxpayer.name": "Sample Taxpayer", "consent.tax_years": "2025"},
        "consent": {
            "purpose": purpose,
            "statement_version": "Rev. Proc. 2013-14",
            "counsel_attestation": True,
            "expiry_months": 12,
        },
    }


CONSENT_USE: Final = _consent(
    "BH §7216 Consent to Use",
    "use",
    "Consent to use tax return information",
    "Brightwater Hale may use the tax return information named here for the purpose stated.",
)
CONSENT_AI: Final = _consent(
    "BH §7216 Consent to Disclose — AI sub-processors",
    "ai_disclosure",
    "Consent to disclose tax return information to AI service providers",
    "Brightwater Hale may disclose the tax return information named here to the recipients "
    "listed below, who process it on the firm's behalf.",
)

REP_LETTER: Final[Json] = {
    "family": "representation_letter",
    "name": "BH Representation Letter · EBP",
    "description": "Management representation letter for an EBP audit",
    "layout_key": "letter",
    "body": [
        _p(_v("plan.name")),
        _p(_v("letter.date")),
        _p("Brightwater Hale LLP · 311 West Brannock Street · Chicago, Illinois"),
        _p(
            "We are providing this letter in connection with your audit of the financial "
            "statements of ",
            _v("plan.name"),
            ". We confirm, to the best of our knowledge and belief, the following "
            "representations made to you during the audit.",
        ),
        _h("Financial statements", 3),
        _clause("fs-responsibility"),
        _h("Plan-specific matters", 3),
        _clause("remittances"),
        _sign(("Plan Administrator", "plan.signer")),
    ],
    "clauses": [
        _def(
            "fs-responsibility",
            "Financial statements",
            _p(
                "We have fulfilled our responsibilities, as set out in the engagement letter, for "
                "the preparation and fair presentation of the financial statements."
            ),
        ),
        _def(
            "remittances",
            "Remittances",
            _p("There were no late remittances other than those listed in this letter."),
        ),
    ],
    "variables": [
        _var("plan.name", "Plan", "name"),
        _var("letter.date", "Letter date", "date"),
        _var("plan.signer", "Plan signer", "name"),
    ],
    "sample_data": {
        "plan.name": "Sample 401(k) Plan",
        "letter.date": "October 9, 2026",
        "plan.signer": "Sample Administrator",
    },
}

PLANNING_LETTER: Final[Json] = {
    "family": "governance_letter",
    "name": "BH AU-C 260 Planning Letter",
    "description": "Planning communication with those charged with governance (AU-C 260)",
    "layout_key": "letter",
    "body": [
        _p("Brightwater Hale LLP · 311 West Brannock Street, Chicago, IL"),
        _p(_v("letter.date")),
        _p(_v("governance.addressee")),
        _h("Our planned audit", 2),
        _h("Our responsibilities", 3),
        _p(
            "We will audit the financial statements under auditing standards generally accepted "
            "in the United States of America."
        ),
        _h("Planned scope and timing", 3),
        _p("Fieldwork: ", _v("audit.fieldwork")),
        _h("Significant risks we identified", 3),
        _p("Management override of controls (presumed under auditing standards)."),
        _h("How we use technology", 3),
        _p(
            "Brightwater Hale prepares audit documentation in Accrued. Its agent drafts and tests "
            "documentation; members of our engagement team review and approve every conclusion."
        ),
        _h("Your input", 3),
        _p("Please tell us about any fraud risks you are aware of."),
        _sign(("Engagement Partner", "firm.signer")),
    ],
    "variables": [
        _var("letter.date", "Letter date", "date"),
        _var("governance.addressee", "Addressee"),
        _var("audit.fieldwork", "Fieldwork"),
        _var("firm.signer", "Engagement partner", "name"),
    ],
    "sample_data": {
        "letter.date": "September 17, 2026",
        "governance.addressee": "Members of the Sample Committee",
        "audit.fieldwork": "September 21 \u2013 October 2, 2026",
        "firm.signer": "Sample Partner",
    },
}


def _report(family: str, name: str, title: str, opinion_heading: str, opinion: str) -> Json:
    return {
        "family": family,
        "name": name,
        "description": f"{title} shell",
        "layout_key": "report",
        "body": [
            _p("Brightwater Hale LLP · 311 West Brannock Street, Chicago, IL"),
            _h(title, 1),
            _p(_v("report.addressee")),
            {
                "type": "section",
                "id": "opinion",
                "title": opinion_heading,
                "blocks": [_p(opinion)],
            },
            _p("Chicago, Illinois"),
            _p(_v("report.date")),
        ],
        "variables": [
            _var("report.addressee", "Addressee"),
            _var("report.date", "Report date", "date"),
        ],
        "sample_data": {
            "report.addressee": "To the Sample Board",
            "report.date": "October 9, 2026",
        },
    }


AUDIT_REPORT: Final = _report(
    "audit_report",
    "BH Auditor's Report · EBP §103(a)(3)(C)",
    "Independent Auditor's Report",
    "Opinion",
    "In our opinion, the financial statements are presented fairly, in all material respects.",
)
REVIEW_REPORT: Final = _report(
    "review_report",
    "BH Review Report · AR-C 90",
    "Independent Accountant's Review Report",
    "Conclusion",
    "Based on our review, we are not aware of any material modifications that should be made.",
)
COMPILATION_REPORT: Final = _report(
    "compilation_report",
    "BH Compilation Report · AR-C 80",
    "Accountant's Compilation Report",
    "Compilation",
    "We did not audit or review the financial statements and do not express an opinion.",
)

NOTICE_RESPONSE: Final[Json] = {
    "family": "notice_response",
    "name": "BH Notice Response · CP2000",
    "description": "Taxpayer response to a CP2000 proposed adjustment",
    "layout_key": "notice_response",
    "body": [
        _p(_v("taxpayer.names")),
        _p(_v("letter.date")),
        _p("Internal Revenue Service · address as printed on page 1 of the notice"),
        _p("Re: Notice ", _v("notice.reference")),
        _clause("agree"),
        _p("Please contact us at the address above with any questions."),
        _sign(("Taxpayer", "taxpayer.names")),
        _p("Prepared with the assistance of Brightwater Hale LLP"),
    ],
    "clauses": [
        _def(
            "agree",
            "We agree",
            _p("We have reviewed the proposed changes and agree with them."),
        ),
        _def(
            "disagree",
            "We disagree",
            _p(
                "We have reviewed the proposed changes and disagree with them, as explained below."
            ),
            on=False,
        ),
    ],
    "variables": [
        _var("taxpayer.names", "Taxpayers", "name"),
        _var("letter.date", "Letter date", "date"),
        _var("notice.reference", "Notice"),
    ],
    "sample_data": {
        "taxpayer.names": "Sample Taxpayers",
        "letter.date": "September 14, 2026",
        "notice.reference": "CP2000 · Tax year 2024",
    },
}

DELIVERY_COVER: Final[Json] = {
    "family": "delivery_cover_letter",
    "name": "BH Filing Instructions",
    "description": "Filing instructions letter for a filed return delivered through the portal",
    "layout_key": "letter",
    "body": [
        _p(_v("letter.date")),
        _p(_v("client.name")),
        _p("Your ", _v("return.label"), " is enclosed for your records."),
        _p(_v("payments.summary")),
        _p("Please keep this copy with your tax records."),
        _sign(("Brightwater Hale LLP", "firm.signer")),
        {"type": "enclosures", "items": ["Filed return"]},
    ],
    "variables": [
        _var("letter.date", "Letter date", "date"),
        _var("client.name", "Client", "name"),
        _var("return.label", "Return"),
        _var("payments.summary", "Payment instructions"),
        _var("firm.signer", "Firm signer", "name"),
    ],
    "sample_data": {
        "letter.date": "April 10, 2026",
        "client.name": "Sample Client",
        "return.label": "2025 Form 1040",
        "payments.summary": "No payment is due",
        "firm.signer": "Sample Partner",
    },
}

BUNDLES: Final[tuple[Json, ...]] = (
    CAS_LETTER,
    AUDIT_LETTER,
    TAX_LETTER,
    CONSENT_USE,
    CONSENT_AI,
    REP_LETTER,
    PLANNING_LETTER,
    AUDIT_REPORT,
    REVIEW_REPORT,
    COMPILATION_REPORT,
    NOTICE_RESPONSE,
    DELIVERY_COVER,
)


def bundle(name: str) -> Json:
    return next(b for b in BUNDLES if b["name"] == name)


@register_slice(SLICE)
def report_template_events() -> list[Event]:
    events = [
        Event(f"flag:{FLAG}", SETUP_AT, "platform.flag_set", "system", SLICE, {"flag": FLAG})
    ]
    for n, b in enumerate(BUNDLES):
        name = str(b["name"])
        events.append(
            Event(
                f"report-template-import:{name}",
                SETUP_AT + timedelta(minutes=30, seconds=n),
                "reporting.template_imported",
                IMPORTER,
                SLICE,
                {"name": name},
            )
        )
        events.append(
            Event(
                f"report-template-publish:{name}",
                SETUP_AT + timedelta(minutes=40, seconds=n),
                "reporting.template_published",
                PUBLISHER,
                SLICE,
                {"name": name},
            )
        )
    return events


__all__ = ["BUNDLES", "NEEDS", "SLICE", "bundle"]
