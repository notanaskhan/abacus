"""The confirmations contract's models (A-08-T06; `docs/contracts/confirmations.md`; SPEC-657).

Firm-side shapes for AUD-14 and the respondent shapes for POR-17's public family. Every figure is
code's (ADR-050): differences, unreconciled amounts, coverage and tiles are computed server-side.
Account numbers are last four only. Respondent text is hostile client content (ADR-052) and is
classified confidential; addresses are confidential and never cross into a client response.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._statuses import ConfirmationStatus
from abacus.kernel.classification import classified

Money = Annotated[Decimal, classified("confidential")]
Name = Annotated[str, Field(min_length=1, max_length=200), classified("confidential")]
Text = Annotated[str, Field(min_length=1, max_length=2000), classified("confidential")]
Ids = Annotated[list[UUID], classified("internal")]

ConfirmationType = Literal["bank", "accounts_receivable", "accounts_payable", "other"]
Channel = Literal["accrued_link", "network_recorded", "mail_recorded"]
AddressSource = Literal[
    "client_supplied", "prior_year", "website", "phone", "public_register", "bank_published"
]
ConfirmationAction = Literal[
    "confirmation.verify_address",
    "confirmation.request_authorization",
    "confirmation.send",
    "confirmation.record_response",
    "confirmation.reconcile",
    "confirmation.accept_reconciliation",
    "confirmation.record_alternative",
    "confirmation.close",
    "finding.create",
]
Classification = Literal["factual", "judgmental", "projected"]


# --- firm side (AUD-14) -------------------------------------------------------------------------


class ConfirmationLineOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    position: Annotated[int, classified("internal")]
    description: Name
    account_last4: Annotated[str | None, Field(pattern=r"^\d{4}$"), classified("confidential")]
    book_amount: Money
    confirmed_amount: Money | None
    difference: Money | None  # code's, from the response


class ConfirmationRowOut(BaseModel):
    """One AUD-14 log row: C1…C4, its status and sub-line facts."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    number: Annotated[str, Field(pattern=r"^C\d+$"), classified("internal")]
    type: Annotated[ConfirmationType, classified("internal")]
    respondent_org: Name
    channel: Annotated[Channel, classified("internal")]
    status: Annotated[ConfirmationStatus, classified("internal")]
    book_total: Money
    address_independent: Annotated[bool, classified("internal")]
    authorization_on_file: Annotated[bool, classified("internal")]
    sent_at: Annotated[datetime | None, classified("internal")]
    viewed_at: Annotated[datetime | None, classified("internal")]
    second_request_at: Annotated[datetime | None, classified("internal")]
    responded_at: Annotated[datetime | None, classified("internal")]
    sample_item_ref: Annotated[str | None, classified("internal")]
    allowed_actions: Annotated[list[ConfirmationAction], classified("public")]


class ConfirmationLogOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[ConfirmationRowOut], classified("internal")]
    links_paused: Annotated[bool, classified("public")]  # the confirmation_links control
    allowed_actions: Annotated[
        list[Literal["confirmation.create", "confirmation.export"]], classified("public")
    ]


class StatusTileOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Annotated[ConfirmationStatus, classified("internal")]
    count: Annotated[int, Field(ge=0), classified("internal")]


class ConfirmationCoverageOut(BaseModel):
    """'AR sent for confirmation $897,950.00 of $5,860,000.00 (15.3%) · confirmed … · CT …'."""

    model_config = ConfigDict(frozen=True)

    population_total: Money
    sent_total: Money
    sent_pct: Annotated[Decimal, classified("internal")]  # one decimal place, code's
    confirmed_total: Money
    differences_total: Money
    clearly_trivial: Money


class ConfirmationSummaryOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    tiles: Annotated[list[StatusTileOut], classified("internal")]  # sum to the log's count
    total: Annotated[int, Field(ge=0), classified("internal")]
    coverage: Annotated[ConfirmationCoverageOut | None, classified("internal")]


class AddressVerificationOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    method: Annotated[str, Field(max_length=300), classified("confidential")]
    sources: Annotated[list[AddressSource], classified("internal")]
    independent: Annotated[bool, classified("internal")]  # a non-client source is cited
    citation_ids: Ids
    verified_by_name: Name
    verified_on: Annotated[date, classified("internal")]


class ResponseSummaryOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    agrees: Annotated[bool, classified("confidential")]
    respondent_name: Name
    respondent_title: Annotated[str | None, Field(max_length=200), classified("confidential")]
    via: Annotated[Literal["respondent_page", "recorded"], classified("internal")]
    submitted_at: Annotated[datetime, classified("internal")]
    attested: Annotated[bool, classified("internal")]
    attachment_version_ids: Ids
    explanation: Annotated[str | None, Field(max_length=2000), classified("confidential")]


class ReconciliationItemOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    description: Text
    amount: Money
    item_date: Annotated[date | None, classified("internal")]
    recorded_on: Annotated[date | None, classified("internal")]
    citation_ids: Ids
    proposed_by_agent: Annotated[bool, classified("internal")]  # a suggestion a person adopted


class ReconciliationOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    balance_per_books: Money
    items: Annotated[list[ReconciliationItemOut], classified("internal")]
    balance_per_respondent: Money
    unreconciled: Money  # code's; "tie" at 0.00
    classification: Annotated[Classification | None, classified("internal")]
    below_clearly_trivial: Annotated[bool | None, classified("internal")]
    accepted_by_name: Annotated[str | None, classified("confidential")]
    accepted_at: Annotated[datetime | None, classified("internal")]


class ConfirmationDetailOut(BaseModel):
    """The O2 480 drawer (AUD-14 a): Response, Reconciliation, Classification, Why surfaced."""

    model_config = ConfigDict(frozen=True)

    row: Annotated[ConfirmationRowOut, classified("internal")]
    lines: Annotated[list[ConfirmationLineOut], classified("internal")]
    address_verifications: Annotated[list[AddressVerificationOut], classified("internal")]
    response: Annotated[ResponseSummaryOut | None, classified("internal")]
    reconciliation: Annotated[ReconciliationOut | None, classified("internal")]
    why_surfaced_suggestion_id: Annotated[UUID | None, classified("internal")]
    finding_id: Annotated[UUID | None, classified("internal")]
    misstatement_id: Annotated[UUID | None, classified("internal")]


class ConfirmationCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: ConfirmationType
    respondent_name: Name
    respondent_org: Name
    channel: Channel
    address_value: Annotated[str, Field(min_length=3, max_length=320), classified("confidential")]
    sample_item_ref: Annotated[str | None, Field(max_length=100), classified("internal")] = None
    tb_account_refs: Annotated[list[str], Field(max_length=50), classified("internal")] = []


class AddressVerificationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: Annotated[str, Field(min_length=1, max_length=300), classified("confidential")]
    sources: Annotated[list[AddressSource], Field(min_length=1)]
    citation_ids: Annotated[list[UUID], Field(min_length=1)]


class AuthorizationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmation_ids: Annotated[list[UUID], Field(min_length=1, max_length=200)]
    signer_contact_id: UUID


class AuthorizationOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    envelope_id: Annotated[UUID, classified("internal")]
    confirmation_ids: Ids


class RecordedResponseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agrees: bool
    confirmed_amounts: Annotated[list[Decimal], Field(max_length=50)]
    evidence_version_ids: Annotated[list[UUID], Field(min_length=1)]
    received_on: date


class ReconciliationItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: Text
    amount: Decimal
    item_date: date | None = None
    recorded_on: date | None = None
    citation_ids: Annotated[list[UUID], Field(min_length=1)]
    suggestion_id: UUID | None = None


class ReconciliationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: Annotated[list[ReconciliationItemIn], Field(max_length=50)]
    classification: Classification | None = None


class SeenHashIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seen_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class AlternativeProcedureIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: Text
    amount: Decimal | None = None
    citation_ids: Annotated[list[UUID], Field(min_length=1)]


class ExceptionPrefillOut(BaseModel):
    """SHL-15's prefill; a person submits it through `assurance.api.record_finding` (or, below
    clearly trivial, `record_misstatement`)."""

    model_config = ConfigDict(frozen=True)

    confirmation_id: Annotated[UUID, classified("internal")]
    difference: Money
    below_clearly_trivial: Annotated[bool, classified("internal")]
    route: Annotated[Literal["finding", "misstatement"], classified("internal")]


# --- the public family (POR-17) -----------------------------------------------------------------


class RespondentInvoiceOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    number: Annotated[str, Field(max_length=60), classified("confidential")]
    invoice_date: Annotated[date, classified("confidential")]
    amount: Money


class RespondentAccountOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    description: Name
    balance_per_client: Money


class RespondentRequestOut(BaseModel):
    """One confirmation's render data, and nothing else (AC-7.1, INV-4): no engagement, no other
    customer, no portal link, no staff."""

    model_config = ConfigDict(frozen=True)

    reference: Annotated[str, Field(pattern=r"^C\d+$"), classified("internal")]
    type: Annotated[ConfirmationType, classified("internal")]
    firm_name: Annotated[str, classified("public")]
    client_name: Name
    respondent_org: Name
    as_of: Annotated[date, classified("confidential")]
    authorization_text: Annotated[str, Field(max_length=2000), classified("confidential")]
    authorized_by: Name
    authorized_on: Annotated[date, classified("confidential")]
    balance_per_client: Money | None
    invoices: Annotated[list[RespondentInvoiceOut], classified("confidential")]
    client_accounts: Annotated[list[RespondentAccountOut], classified("confidential")]
    list_every_account: Annotated[bool, classified("public")]  # the bank variant (f)


class RespondentReceiptOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    receipt_id: Annotated[str, Field(max_length=40), classified("internal")]
    reference: Annotated[str, classified("internal")]
    agrees: Annotated[bool, classified("confidential")]
    respondent_balance: Money | None
    difference: Money  # the server's, never the page's
    submitted_at: Annotated[datetime, classified("internal")]
    verified_email: Annotated[str, Field(max_length=320), classified("confidential")]


class RespondentViewOut(BaseModel):
    """`open` with the request, `answered` (with the receipt right after a submission), or
    `expired`: the one answer for unknown, revoked, expired and paused links (DV-7)."""

    model_config = ConfigDict(frozen=True)

    state: Annotated[Literal["open", "expired", "answered"], classified("public")]
    request: Annotated[RespondentRequestOut | None, classified("confidential")] = None
    receipt: Annotated[RespondentReceiptOut | None, classified("confidential")] = None
    answered_on: Annotated[date | None, classified("internal")] = None


class CodeRequestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: Annotated[str, Field(min_length=3, max_length=320), classified("confidential")]


class CodeVerifyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Annotated[str, Field(pattern=r"^\d{6}$"), classified("restricted")]


class AcceptedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    accepted: Annotated[bool, classified("public")] = True


class VerifiedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    verified: Annotated[bool, classified("public")]


class RespondentBalanceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: Annotated[Decimal, Field(max_digits=20, decimal_places=2)]


class RespondentAccountIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: Name
    account_last4: Annotated[str | None, Field(pattern=r"^\d{4}$")] = None
    balance: Annotated[Decimal, Field(max_digits=20, decimal_places=2)]


class RespondentResponseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agrees: bool
    balances: Annotated[list[RespondentBalanceIn], Field(max_length=20)] = []
    accounts: Annotated[list[RespondentAccountIn], Field(max_length=50)] = []
    explanation: Annotated[str | None, Field(max_length=2000)] = None
    attachment_ids: Annotated[list[UUID], Field(max_length=10)] = []
    respondent_name: Name
    respondent_title: Annotated[str | None, Field(max_length=200)] = None
    respondent_company: Name
    attestation: Literal[True]


class AttachmentOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    attachment_id: Annotated[UUID, classified("internal")]
    file_name: Annotated[str, Field(max_length=255), classified("confidential")]
    size_bytes: Annotated[int, classified("internal")]
