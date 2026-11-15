"""POR-17's synthetic fixtures for the confirmations stub (A-08-T06; SPEC-657 AC-0.6, AC-7.1).

Six respondent pages, one per artboard (a link opened, b submitted, c does not agree, d expired,
e already answered, f the bank variant), with the handoff's figures (POR-17 spec.md). Served only
in local and test environments (the fixture tenant's stub mode), never from a database row and
never to a firm. The tokens are fixture constants, not secrets: real links carry 256-bit random
tokens stored hashed (A-08-T15). Every figure here foots in code (`foots`), never by hand.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Final

from abacus.modules.assurance.confirmations_contract_models import (
    RespondentAccountOut,
    RespondentInvoiceOut,
    RespondentReceiptOut,
    RespondentRequestOut,
    RespondentViewOut,
)

FIRM: Final = "Brightwater Hale LLP"
CLIENT: Final = "Granite Peak Outdoor Supply, Inc."
AS_OF: Final = date(2026, 6, 30)
AUTHORIZATION: Final = (
    "Our auditors, Brightwater Hale LLP, are auditing our financial statements for the year ended "
    "June 30, 2026. Please confirm directly to them the balance you owed us at that date. This is "
    "not a request for payment."
)
AUTHORIZED_BY: Final = "Luis Ferrante, Chief Financial Officer, Granite Peak Outdoor Supply, Inc."
AUTHORIZED_ON: Final = date(2026, 9, 18)
# The fixture code a test or a fixture-mode page types to verify the email (stub only).
FIXTURE_CODE: Final = "246810"

TOKENS: Final = {
    "a": "fixture-por17-summit-trail",
    "b": "fixture-por17-summit-trail-submitted",
    "c": "fixture-por17-alpine-ridge",
    "d": "fixture-por17-canyon-basecamp",
    "e": "fixture-por17-summit-trail-answered",
    "f": "fixture-por17-front-range-bank",
}

_SUMMIT_INVOICES: Final = (
    ("INV-26-1841", date(2026, 5, 28), Decimal("138200.00")),
    ("INV-26-1907", date(2026, 6, 12), Decimal("151750.00")),
    ("INV-26-1966", date(2026, 6, 26), Decimal("122650.00")),
)


def foots(invoices: tuple[tuple[str, date, Decimal], ...]) -> Decimal:
    """The balance the invoices add to (code, never typed)."""
    return sum((amount for _, _, amount in invoices), Decimal("0.00"))


def _request(
    reference: str,
    respondent: str,
    kind: str,
    balance: Decimal | None,
    invoices: tuple[tuple[str, date, Decimal], ...] = (),
    accounts: tuple[tuple[str, Decimal], ...] = (),
) -> RespondentRequestOut:
    return RespondentRequestOut(
        reference=reference,
        type=kind,  # pyright: ignore[reportArgumentType] -- one of the four literals below
        firm_name=FIRM,
        client_name=CLIENT,
        respondent_org=respondent,
        as_of=AS_OF,
        authorization_text=AUTHORIZATION,
        authorized_by=AUTHORIZED_BY,
        authorized_on=AUTHORIZED_ON,
        balance_per_client=balance,
        invoices=[
            RespondentInvoiceOut(number=n, invoice_date=d, amount=a) for n, d, a in invoices
        ],
        client_accounts=[
            RespondentAccountOut(description=desc, balance_per_client=amount)
            for desc, amount in accounts
        ],
        list_every_account=kind == "bank",
    )


_SUMMIT = _request(
    "C2",
    "Summit Trail Outfitters",
    "accounts_receivable",
    foots(_SUMMIT_INVOICES),
    _SUMMIT_INVOICES,
)
_ALPINE = _request("C3", "Alpine Ridge Sports", "accounts_receivable", Decimal("286900.00"))
_BANK = _request(
    "C1",
    "Front Range Bank",
    "bank",
    None,
    accounts=(
        ("Revolving line of credit", Decimal("6500000.00")),
        ("Term loan", Decimal("3200000.00")),
    ),
)

_SUBMITTED_AT: Final = datetime(2026, 9, 25, 16, 12, tzinfo=UTC)  # 10:12 AM MT
RECEIPT: Final = RespondentReceiptOut(
    receipt_id="C2-R1",
    reference="C2",
    agrees=True,
    respondent_balance=Decimal("412600.00"),
    difference=Decimal("0.00"),
    submitted_at=_SUBMITTED_AT,
    verified_email="r.imholt@example.com",
)

EXPIRED: Final = RespondentViewOut(state="expired")


def view(token: str) -> RespondentViewOut | None:
    """The fixture page a token names, or None for any other token (the caller answers the
    uniform expired view either way)."""
    if token == TOKENS["a"]:
        return RespondentViewOut(state="open", request=_SUMMIT)
    if token == TOKENS["b"]:
        return RespondentViewOut(
            state="answered", receipt=RECEIPT, answered_on=_SUBMITTED_AT.date()
        )
    if token == TOKENS["c"]:
        return RespondentViewOut(state="open", request=_ALPINE)
    if token == TOKENS["d"]:
        return EXPIRED
    if token == TOKENS["e"]:
        return RespondentViewOut(state="answered", answered_on=_SUBMITTED_AT.date())
    if token == TOKENS["f"]:
        return RespondentViewOut(state="open", request=_BANK)
    return None
