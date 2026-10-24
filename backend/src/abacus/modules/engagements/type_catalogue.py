"""ENG-03's engagement-type catalogue (P-07-T16; P-07 Story 6.3; DEC-143, DEC-225).

A code catalogue, not firm content: the 18 types the wizard offers (Tax 8, Audit & assurance 8,
CAS & Advisory 2), each with its C1 engagement type, the work-item kind it creates, its copy
(the copy registry's words, OQ-15, held with the code), the entitlement it needs and the step
fields the wizard asks for. Single audit is out of scope (D10, DEC-19): no code here, and a draft
or create naming it is 422 `unknown_engagement_type` like any unknown code. The ENG-03 "Coming
soon" tile is static frontend copy.

Cardinality (chapter 03 §3.1): an assurance type is the engagement's one assurance work item; a
tax form is one return per form (Forms 706 / 709 are two); a monthly close is the period's first
close; an advisory project is one project; a notice response creates its notice when the notice's
code and received date are recorded (they are not wizard fields yet, DEC-225).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

Family = Literal["tax", "audit_assurance", "cas_advisory"]
Entitlement = Literal["attest", "group_audit"]
WizardStep = Literal[
    "client_type",
    "standards_methodology",
    "period_deadlines",
    "team_independence",
    "binder_portal",
    "letter_review",
]


@dataclass(frozen=True)
class CatalogueEntry:
    code: str
    engagement_type: str  # C1's `EngagementType`
    family: Family
    work_item_kind: str
    label: str
    standard_line: str
    entitlement: Entitlement | None = None
    group_audit_allowed: bool = False
    forms: tuple[str, ...] = ()  # tax_return forms, one work item each


# Fields every type's steps ask for; a type adds its own (standards for attest, forms for tax).
_COMMON: Final[dict[WizardStep, tuple[str, ...]]] = {
    "client_type": ("client_id", "client_entity_id", "type_code"),
    "standards_methodology": ("methodology_version_id",),
    "period_deadlines": ("name", "fiscal_period_start", "fiscal_period_end", "period_label"),
    "team_independence": ("team",),
    "binder_portal": ("portal_contact_ids",),
    "letter_review": (),
}
_ATTEST_EXTRA: Final[dict[WizardStep, tuple[str, ...]]] = {
    "standards_methodology": ("standards_code", "scope_code"),
    "team_independence": ("eqr_user_id",),
}

_TAX = "tax_compliance"
CATALOGUE: Final[tuple[CatalogueEntry, ...]] = (
    CatalogueEntry(
        "form_1040", _TAX, "tax", "tax_return", "Form 1040", "Individual", forms=("1040",)
    ),
    CatalogueEntry(
        "form_1041", _TAX, "tax", "tax_return", "Form 1041", "Trust or estate", forms=("1041",)
    ),
    CatalogueEntry(
        "form_1065", _TAX, "tax", "tax_return", "Form 1065", "Partnership", forms=("1065",)
    ),
    CatalogueEntry(
        "form_1120s", _TAX, "tax", "tax_return", "Form 1120-S", "S corporation", forms=("1120s",)
    ),
    CatalogueEntry(
        "form_1120", _TAX, "tax", "tax_return", "Form 1120", "C corporation", forms=("1120",)
    ),
    CatalogueEntry(
        "form_990", _TAX, "tax", "tax_return", "Form 990", "Exempt organization", forms=("990",)
    ),
    CatalogueEntry(
        "forms_706_709",
        _TAX,
        "tax",
        "tax_return",
        "Forms 706 / 709",
        "Estate & gift",
        forms=("706", "709"),
    ),
    CatalogueEntry(
        "notice_response",
        "notice_response",
        "tax",
        "notice",
        "Notice response",
        "IRS or state notice",
    ),
    CatalogueEntry(
        "ebp_audit", "ebp_audit", "audit_assurance", "assurance", "EBP audit", "AU-C 703 · ERISA"
    ),
    CatalogueEntry(
        "fs_audit",
        "fs_audit",
        "audit_assurance",
        "assurance",
        "FS audit",
        "GAAS nonissuer",
        group_audit_allowed=True,
    ),
    CatalogueEntry("review", "review", "audit_assurance", "assurance", "Review", "AR-C 90"),
    CatalogueEntry(
        "compilation", "compilation", "audit_assurance", "assurance", "Compilation", "AR-C 80"
    ),
    CatalogueEntry(
        "preparation", "preparation", "audit_assurance", "assurance", "Preparation", "AR-C 70"
    ),
    CatalogueEntry(
        "agreed_upon_procedures",
        "agreed_upon_procedures",
        "audit_assurance",
        "assurance",
        "Agreed-upon procedures",
        "AT-C 215",
    ),
    CatalogueEntry(
        "soc1", "soc1", "audit_assurance", "assurance", "SOC 1", "AT-C 320", entitlement="attest"
    ),
    CatalogueEntry(
        "soc2", "soc2", "audit_assurance", "assurance", "SOC 2", "AT-C 205", entitlement="attest"
    ),
    CatalogueEntry(
        "cas_monthly_close",
        "cas_monthly_close",
        "cas_advisory",
        "close",
        "Monthly close",
        "Client accounting services",
    ),
    CatalogueEntry(
        "advisory",
        "advisory",
        "cas_advisory",
        "advisory_project",
        "Advisory project",
        "Scoped project",
    ),
)
BY_CODE: Final[dict[str, CatalogueEntry]] = {e.code: e for e in CATALOGUE}


def steps_of(entry: CatalogueEntry) -> list[tuple[WizardStep, tuple[str, ...]]]:
    """Each step and the payload fields it asks for, in wizard order."""
    extra = _ATTEST_EXTRA if entry.family == "audit_assurance" else {}
    return [(step, fields + extra.get(step, ())) for step, fields in _COMMON.items()]


def entry_of(code: str | None) -> CatalogueEntry | None:
    return None if code is None else BY_CODE.get(code)
