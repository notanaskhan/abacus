"""EBP-08: participant accounts summary (A-05-T46; A-05 F7; DF-34). The routes have authorised the
action and the flag.

Figures foot by code (`compute.ebp.accounts`). Vesting covers those who terminated in the
plan year (6 on Northwind, DF-34), not every terminated balance. Forfeitures arising are the
non-vested balances of those people. "Signed off" is P-04's L4 on the `ebp_participant_accounts`
workpaper, so nothing here records it. Names and masked SSNs follow the census's rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.modules.assurance.compute.ebp import accounts as engine
from abacus.modules.assurance.ebp_participants import ssn_mask

_ZERO: Final = Decimal(0)
_ACCOUNTS = text(
    "SELECT participant_key, name, ssn_last4, status, beginning_balance, contributions, earnings, "
    "distributions, fees, transfers, ending_balance FROM ebp_participant_balances "
    "WHERE work_item_id = :item ORDER BY name"
)
_SDBA = text(
    "SELECT security_type, market_value FROM ebp_sdba_holdings WHERE work_item_id = :item"
)
_TRUST = text(
    "SELECT sum(eoy) FROM ebp_trust_report_lines "
    "WHERE work_item_id = :item AND superseded_by IS NULL"
)
_NOTES = text("SELECT sum(ending_balance) FROM ebp_participant_loans WHERE work_item_id = :item")
_VESTING = text(
    "SELECT participant_key, name, ssn_last4, termination_on, years_of_service, vested_pct "
    "FROM ebp_participants WHERE work_item_id = :item AND import_id = ("
    "  SELECT import_id FROM ebp_participants WHERE work_item_id = :item "
    "  ORDER BY created_at DESC LIMIT 1"
    ") AND termination_on BETWEEN :start AND :end ORDER BY name"
)


@dataclass(frozen=True)
class AccountRow:
    participant_key: str
    name: str
    ssn_mask: str | None
    account: engine.ParticipantBalance


@dataclass(frozen=True)
class AccountsView:
    rollforward: engine.Rollforward
    ties: tuple[engine.Tie, ...]
    forfeiture_account: Decimal


@dataclass(frozen=True)
class VestingRow:
    participant_key: str
    name: str
    ssn_mask: str | None
    termination_on: date
    years_of_service: Decimal | None
    vested_pct: Decimal | None
    agrees: bool | None


async def _rows(tenant: TenantContext, work_item_id: UUID) -> list[AccountRow]:
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_ACCOUNTS, {"item": work_item_id})).mappings().all()
    return [
        AccountRow(
            participant_key=r["participant_key"],
            name=r["name"],
            ssn_mask=ssn_mask(r["ssn_last4"]),
            account=engine.ParticipantBalance(
                participant_key=r["participant_key"],
                status=r["status"],
                beginning=r["beginning_balance"],
                contributions=r["contributions"],
                earnings=r["earnings"],
                distributions=r["distributions"],
                fees=r["fees"],
                transfers=r["transfers"],
                ending=r["ending_balance"],
            ),
        )
        for r in rows
    ]


async def accounts(
    tenant: TenantContext,
    work_item_id: UUID,
    *,
    fees_paid: Decimal | None = None,
    contributions_received: Decimal | None = None,
    distributions_paid: Decimal | None = None,
) -> AccountsView:
    """The rollforward and its ties. `ties` compares to EBP-04, EBP-05, EBP-06 and EBP-09; a side
    the caller couldn't read is unknown, never tied."""
    rows = await _rows(tenant, work_item_id)
    if not rows:
        raise NotFound("ebp_participant_balances")
    roll = engine.rollforward([r.account for r in rows])
    async with tenant_session(tenant) as session:
        trust = await session.scalar(_TRUST, {"item": work_item_id})
        notes = await session.scalar(_NOTES, {"item": work_item_id})
    per_trust = None if trust is None else trust + (notes or _ZERO)
    total = roll.total
    ties = (
        engine.tie("net_trust_assets", per_trust, total.ending),
        engine.tie("contributions_allocated", contributions_received, total.contributions),
        engine.tie("distributions", distributions_paid, -total.distributions),
        engine.tie("fees", fees_paid, -total.fees),
    )
    return AccountsView(rollforward=roll, ties=ties, forfeiture_account=_ZERO)


async def group_accounts(
    tenant: TenantContext, work_item_id: UUID, status: str
) -> tuple[AccountRow, ...]:
    """The participant-level drill. An unknown group: 404."""
    rows = [r for r in await _rows(tenant, work_item_id) if r.account.status == status]
    if not rows:
        raise NotFound("participant_group")
    return tuple(rows)


async def sdba(
    tenant: TenantContext, work_item_id: UUID
) -> tuple[dict[str, Decimal], Decimal, Decimal | None]:
    """By security type, the total, and EBP-06's brokerage line (None until it's in the trust
    report under `sdba`)."""
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_SDBA, {"item": work_item_id})).all()
    by_type, total = engine.sdba_by_type([(r[0], r[1]) for r in rows])
    return dict(by_type), total, None


async def vesting(
    tenant: TenantContext, work_item_id: UUID, plan_year: int
) -> tuple[tuple[VestingRow, ...], Decimal]:
    """The plan year's terminations (DF-34) and the forfeitures arising from them. Code's vesting
    against the recordkeeper's stored percent; a person with under 2 years is the exception."""
    params = {
        "item": work_item_id,
        "start": date(plan_year, 1, 1),
        "end": date(plan_year, 12, 31),
    }
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_VESTING, params)).mappings().all()
    out: list[VestingRow] = []
    for r in rows:
        computed = engine.vested_pct(r["years_of_service"])
        recorded = r["vested_pct"]
        out.append(
            VestingRow(
                participant_key=r["participant_key"],
                name=r["name"],
                ssn_mask=ssn_mask(r["ssn_last4"]),
                termination_on=r["termination_on"],
                years_of_service=r["years_of_service"],
                vested_pct=computed,
                agrees=None if computed is None or recorded is None else computed == recorded,
            )
        )
    return tuple(out), _ZERO
