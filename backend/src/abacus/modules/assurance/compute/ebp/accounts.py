"""Participant accounts (A-05-T46; A-05 §4.4; EBP-08): pure functions over stored rows.

Each group crossfoots (Beginning + Contributions + Earnings + Distributions + Fees + Transfers =
Ending; 11,612,300 + 1,318,300 + 1,716,000 - 104,600 - 29,200 - 871,900 = 13,640,900), the groups
foot to the total (16,812,400) and transfers net to zero. A check that can't be run reads `None`,
never tied. Decimal only; the model never adds.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

ENGINE_NAME: Final = "ebp_accounts"
ENGINE_VERSION: Final = "1"
_ZERO: Final = Decimal(0)
COLUMNS: Final = ("beginning", "contributions", "earnings", "distributions", "fees", "transfers")
QACA_VESTED_YEARS: Final = Decimal(2)


@dataclass(frozen=True)
class ParticipantBalance:
    participant_key: str
    status: str
    beginning: Decimal
    contributions: Decimal
    earnings: Decimal
    distributions: Decimal
    fees: Decimal
    transfers: Decimal
    ending: Decimal


@dataclass(frozen=True)
class Group:
    status: str
    participants: int
    beginning: Decimal
    contributions: Decimal
    earnings: Decimal
    distributions: Decimal
    fees: Decimal
    transfers: Decimal
    ending: Decimal
    crossfoots: bool


@dataclass(frozen=True)
class Rollforward:
    groups: tuple[Group, ...]
    total: Group
    transfers_net_zero: bool
    inputs_hash: str
    engine_version: str = ENGINE_VERSION


@dataclass(frozen=True)
class Tie:
    key: str
    expected: Decimal | None
    actual: Decimal
    ties: bool | None


def _inputs_hash(accounts: Sequence[ParticipantBalance]) -> str:
    canonical = [
        [
            a.participant_key,
            a.status,
            *(str(getattr(a, c)) for c in COLUMNS),
            str(a.ending),
        ]
        for a in sorted(accounts, key=lambda a: a.participant_key)
    ]
    return hashlib.sha256(json.dumps(canonical, separators=(",", ":")).encode()).hexdigest()


def _group(status: str, accounts: Sequence[ParticipantBalance]) -> Group:
    sums = {c: sum((getattr(a, c) for a in accounts), _ZERO) for c in COLUMNS}
    ending = sum((a.ending for a in accounts), _ZERO)
    return Group(
        status=status,
        participants=len(accounts),
        ending=ending,
        crossfoots=sum(sums.values(), _ZERO) == ending,
        **sums,
    )


def rollforward(accounts: Sequence[ParticipantBalance]) -> Rollforward:
    statuses = sorted({a.status for a in accounts})
    groups = tuple(_group(s, [a for a in accounts if a.status == s]) for s in statuses)
    total = _group("total", accounts)
    return Rollforward(
        groups=groups,
        total=total,
        transfers_net_zero=total.transfers == _ZERO,
        inputs_hash=_inputs_hash(accounts),
    )


def tie(key: str, expected: Decimal | None, actual: Decimal) -> Tie:
    """`None` when the other side isn't available yet: unknown, not tied."""
    return Tie(key, expected, actual, None if expected is None else expected == actual)


def sdba_by_type(holdings: Sequence[tuple[str, Decimal]]) -> tuple[Mapping[str, Decimal], Decimal]:
    """Self-directed brokerage by security type, and the total (924,300 + 612,450 + 68,250)."""
    by_type: dict[str, Decimal] = {}
    for security_type, value in holdings:
        by_type[security_type] = by_type.get(security_type, _ZERO) + value
    return by_type, sum(by_type.values(), _ZERO)


def vested_pct(years_of_service: Decimal | None) -> Decimal | None:
    """QACA match: 100% after 2 years, else 0. Unknown service stays unknown."""
    if years_of_service is None:
        return None
    return Decimal(100) if years_of_service >= QACA_VESTED_YEARS else _ZERO
