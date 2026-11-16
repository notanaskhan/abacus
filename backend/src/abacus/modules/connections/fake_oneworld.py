"""The fake NetSuite OneWorld connector for synthetic tenants (A-09-T18; DV-1: no live OneWorld
connector yet). Five subsidiaries, each with a balanced trial balance for the current and prior
period; a token marked expired answers `needs_reauth` and is never retried. Read only: it has no
method that writes (CONN-001)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

SUBSIDIARIES: Final = (
    "HP Holdings",
    "HP Operating",
    "HP Manufacturing",
    "HP Distribution",
    "HP Real Estate",
)
PERIODS: Final = ("prior", "current")


class NeedsReauth(Exception):
    code = "needs_reauth"


@dataclass(frozen=True)
class FakeTbLine:
    account: str
    debit: Decimal
    credit: Decimal


@dataclass(frozen=True)
class FakeOneWorld:
    expired: frozenset[str] = frozenset()  # subsidiaries whose token is expired

    def subsidiaries(self) -> tuple[str, ...]:
        return SUBSIDIARIES

    def trial_balance(self, subsidiary: str, period: str) -> tuple[FakeTbLine, ...]:
        if subsidiary not in SUBSIDIARIES or period not in PERIODS:
            raise KeyError(subsidiary)
        if subsidiary in self.expired:
            raise NeedsReauth(subsidiary)
        n = SUBSIDIARIES.index(subsidiary) + 1
        amount = Decimal(1_000_000 * n + (0 if period == "current" else 50_000))
        return (FakeTbLine("1000", amount, Decimal(0)), FakeTbLine("3000", Decimal(0), amount))


def pull_all(connector: FakeOneWorld) -> Mapping[tuple[str, str], str]:
    """Every subsidiary's two periods: `snapshot` or `needs_reauth` (never retried)."""
    out: dict[tuple[str, str], str] = {}
    for sub in connector.subsidiaries():
        for period in PERIODS:
            try:
                connector.trial_balance(sub, period)
            except NeedsReauth:
                out[(sub, period)] = "needs_reauth"
                continue
            out[(sub, period)] = "snapshot"
    return out
