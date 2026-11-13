"""The entity return's rail facts and its partners (S41 leftovers, TASK-7733; T-05-T46 §9.5;
DEC-4737). Green: reads only, over this module's own tables and `organisations.api`.

- **General information** (`GET …/general-information`): the client entity's name, the form and
  year, the EIN's last four (the masked form only, never the sealed EIN; the route masks it again
  for an offshore reader), the profile's accounting method, and the people the return's ladder
  names: preparer, the first reviewer named (detail, first-level, then manager) and the signer.
- **Partners** (`GET …/partners`): the partners in their order with the TIN's last four, the
  ownership periods (each period's profit shares by partner id, exact decimals) and the interest
  transfers with their first clause citation. `version` is 1: ownership is written once, by the
  synthetic recorder (T-05-T45) and the agreement reader's adoption, until `PUT …/ownership` has
  a row (it stays 501, DEC-4737).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session

PartnerKind = Literal["general", "limited", "llc_member"]

# The entity workspace serves 1065s (DEC-4520): a partner is a GP, an LP or an LLC member.
KINDS: Final[dict[str, PartnerKind]] = {"gp": "general", "lp": "limited", "member": "llc_member"}

# The ladder's functions as `overview` reads them (T-04's rungs): the first reviewer named wins.
REVIEWERS: Final = ("detail_reviewer", "first_level_reviewer", "manager_reviewer")

_PROFILE: Final = text(
    "SELECT accounting_method FROM entity_return_profiles WHERE work_item_id = :r"
)
_PARTNERS: Final = text(
    "SELECT id, kind, display_name, tin_last4 FROM partners WHERE work_item_id = :r "
    "ORDER BY ord, display_name"
)
_PERIODS: Final = text(
    "SELECT partner_id, period_from, period_to, profit_pct FROM ownership_periods "
    "WHERE work_item_id = :r ORDER BY period_from, period_to, partner_id"
)
_TRANSFERS: Final = text(
    "SELECT transfer_date, from_partner_id, to_partner_id, points, citation_ids "
    "FROM interest_transfers WHERE work_item_id = :r ORDER BY transfer_date, id"
)


@dataclass(frozen=True)
class Partner:
    id: UUID
    name: str
    tin_last4: str | None
    kind: PartnerKind


@dataclass(frozen=True)
class Period:
    starts_on: date
    ends_on: date
    shares: dict[str, Decimal]


@dataclass(frozen=True)
class Transfer:
    on: date
    from_partner_id: UUID
    to_partner_id: UUID
    percentage: Decimal
    citation_id: UUID | None


@dataclass(frozen=True)
class Ownership:
    version: int
    partners: tuple[Partner, ...]
    periods: tuple[Period, ...]
    transfers: tuple[Transfer, ...]


async def accounting_method(tenant: TenantContext, return_id: UUID) -> str | None:
    async with tenant_session(tenant) as session:
        found = (await session.execute(_PROFILE, {"r": return_id})).scalar()
    return None if found is None else str(found)


def ladder_people(
    assignees: Mapping[str, tuple[UUID, ...]],
) -> tuple[UUID | None, UUID | None, UUID | None]:
    """(preparer, reviewer, signer) from the return's assignees by function."""

    def first(*functions: str) -> UUID | None:
        return next((u for f in functions for u in assignees.get(f, ())), None)

    return first("preparer"), first(*REVIEWERS), first("signer")


def periods_of(rows: list[tuple[UUID, date, date, Decimal]]) -> list[Period]:
    """Rows (partner, from, to, profit %) grouped into periods, in date order."""
    grouped: dict[tuple[date, date], dict[str, Decimal]] = defaultdict(dict)
    for partner_id, starts, ends, pct in rows:
        grouped[(starts, ends)][str(partner_id)] = pct
    return [Period(s, e, shares) for (s, e), shares in sorted(grouped.items())]


async def ownership(tenant: TenantContext, return_id: UUID) -> Ownership:
    """The return's partners, ownership periods and transfers (the caller authorised the read)."""
    async with tenant_session(tenant) as session:
        partners = (await session.execute(_PARTNERS, {"r": return_id})).mappings().all()
        periods = (await session.execute(_PERIODS, {"r": return_id})).all()
        transfers = (await session.execute(_TRANSFERS, {"r": return_id})).mappings().all()
    return Ownership(
        version=1,
        partners=tuple(
            Partner(
                id=cast(UUID, p["id"]),
                name=str(p["display_name"]),
                tin_last4=None if p["tin_last4"] is None else str(p["tin_last4"]),
                kind=KINDS[str(p["kind"])],
            )
            for p in partners
            if str(p["kind"]) in KINDS
        ),
        periods=tuple(
            periods_of(
                [
                    (cast(UUID, r[0]), cast(date, r[1]), cast(date, r[2]), Decimal(r[3]))
                    for r in periods
                ]
            )
        ),
        transfers=tuple(
            Transfer(
                on=cast(date, t["transfer_date"]),
                from_partner_id=cast(UUID, t["from_partner_id"]),
                to_partner_id=cast(UUID, t["to_partner_id"]),
                percentage=Decimal(t["points"]),
                citation_id=next(iter(cast(list[UUID], t["citation_ids"] or [])), None),
            )
            for t in transfers
        ),
    )


__all__ = [
    "KINDS",
    "REVIEWERS",
    "Ownership",
    "Partner",
    "Period",
    "Transfer",
    "accounting_method",
    "ladder_people",
    "ownership",
    "periods_of",
]
