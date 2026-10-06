"""Synthetic client data model (SPEC-001 §7). Frozen dataclasses; amounts are Decimal to 0.01."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

CENT = Decimal("0.01")
ZERO = Decimal("0.00")

AccountType = Literal["asset", "liability", "equity", "revenue", "expense"]
Tier = Literal["A", "B", "C", "D", "E"]


def money(value: Decimal | int) -> Decimal:
    """Quantise to cents. Ints are cents."""
    if isinstance(value, int):
        return (Decimal(value) / 100).quantize(CENT)
    return value.quantize(CENT)


@dataclass(frozen=True)
class Account:
    code: str
    name: str
    type: AccountType


@dataclass(frozen=True)
class JournalLine:
    account_code: str
    debit: Decimal
    credit: Decimal
    description: str
    counterparty: str | None


@dataclass(frozen=True)
class JournalEntry:
    id: str
    date: date
    memo: str
    lines: tuple[JournalLine, ...]


@dataclass(frozen=True)
class TrialBalanceLine:
    account_code: str
    account_name: str
    debit: Decimal
    credit: Decimal


@dataclass(frozen=True)
class TrialBalance:
    as_of: date
    lines: tuple[TrialBalanceLine, ...]

    @property
    def total_debits(self) -> Decimal:
        return sum((line.debit for line in self.lines), ZERO)

    @property
    def total_credits(self) -> Decimal:
        return sum((line.credit for line in self.lines), ZERO)


@dataclass(frozen=True)
class BankAccount:
    name: str
    routing_number: str
    account_number: str
    gl_account_code: str


@dataclass(frozen=True)
class BankLine:
    date: date
    description: str
    amount: Decimal
    balance: Decimal


@dataclass(frozen=True)
class ReconcilingItem:
    kind: Literal["outstanding_cheque", "deposit_in_transit"]
    description: str
    amount: Decimal


@dataclass(frozen=True)
class BankStatement:
    account_number: str
    period_start: date
    period_end: date
    currency: str
    opening_balance: Decimal
    closing_balance: Decimal
    lines: tuple[BankLine, ...]
    reconciling_items: tuple[ReconcilingItem, ...]


@dataclass(frozen=True)
class AgingLine:
    counterparty: str
    current: Decimal
    days_1_30: Decimal
    days_31_60: Decimal
    days_61_90: Decimal
    over_90: Decimal
    total: Decimal  # stated total; equals the bucket sum unless the aging is flawed (`altered`)


@dataclass(frozen=True)
class Aging:
    kind: Literal["ar", "ap"]
    as_of: date
    control_account_code: str
    lines: tuple[AgingLine, ...]

    @property
    def total(self) -> Decimal:
        return sum((line.total for line in self.lines), ZERO)


@dataclass(frozen=True)
class ClientEntity:
    name: str
    ein: str
    currency: str
    period_start: date
    period_end: date
    accounts: tuple[Account, ...]
    journal_entries: tuple[JournalEntry, ...]
    trial_balances: tuple[TrialBalance, ...]
    bank_accounts: tuple[BankAccount, ...]
    bank_statements: tuple[BankStatement, ...]
    ar_aging: Aging
    ap_aging: Aging


@dataclass(frozen=True)
class RequestItem:
    id: str
    description: str
    audit_area: str
    retrievability_tier: Tier
    artefact: str | None


@dataclass(frozen=True)
class RequestList:
    items: tuple[RequestItem, ...]


@dataclass(frozen=True)
class Flaw:
    category: str
    artefact: str
    client_entity: str
    location: str
    detection: Literal["mechanical", "ai"]


@dataclass(frozen=True)
class AdversarialPayload:
    category: str
    artefact: str
    field: str
    location: str
    payload: str


@dataclass(frozen=True)
class Manifest:
    flaws: tuple[Flaw, ...]
    adversarial: tuple[AdversarialPayload, ...]


@dataclass(frozen=True)
class SyntheticClient:
    seed: int
    generator_version: str
    name: str
    client_entities: tuple[ClientEntity, ...]
    request_list: RequestList
    manifest: Manifest
