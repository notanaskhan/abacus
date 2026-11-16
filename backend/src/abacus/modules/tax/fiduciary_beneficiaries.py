"""Beneficiaries and the 65-day election (T-07-T23; T-07 §3 F9 to F11; TXT-03; DEC-5317; amber).

- **Allocation by code** (`allocate`): each beneficiary's share of the distributable amounts by
  class, to the cent; the last beneficiary takes the rounding so every class foots to its total
  (160,000 + 80,000 = 240,000).
- **The 65-day election** (`record_election`): the trustee's decision, recorded by a person (a
  Manager with `fiduciary_election.record`; an agent or the system is refused here and by the
  table's CHECK). Each record is a new row, the latest wins; the window ends on the 65th day
  after year-end (§663(b)); an elected amount must be paid inside it (the CHECK too).
- Draft K-1 (1041) packages stay internal: the portal reads only released packages (T-02's
  package service), so nothing here exposes a draft.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.errors import DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import AuthContext, Forbidden, authorise

RECORD: Final = "fiduciary_election.record"
CENT: Final = Decimal("0.01")


class ElectionInvalid(DomainInvalid):
    code = "election_invalid"


@dataclass(frozen=True)
class Allocation:
    beneficiary: str
    by_class: Mapping[str, Decimal]

    @property
    def total(self) -> Decimal:
        return sum(self.by_class.values(), Decimal(0)).quantize(CENT)


def window_end(tax_year: int) -> date:
    """The 65th day after the tax year's end (§663(b))."""
    return date(tax_year, 12, 31) + timedelta(days=65)


def allocate(
    totals: Mapping[str, Decimal], shares: Sequence[tuple[str, Decimal]]
) -> tuple[Allocation, ...]:
    """Each beneficiary's share (fractions summing to 1) of each class; the last takes the
    rounding, so each class foots exactly."""
    if not shares or abs(sum((s for _, s in shares), Decimal(0)) - 1) > Decimal("1e-9"):
        raise ElectionInvalid(facts={"field": "shares"})
    out: list[dict[str, Decimal]] = [{} for _ in shares]
    for klass, total in totals.items():
        given = Decimal(0)
        for i, (_, share) in enumerate(shares):
            part = (
                (Decimal(total) - given).quantize(CENT)
                if i == len(shares) - 1
                else (Decimal(total) * share).quantize(CENT)
            )
            out[i][klass] = part
            given += part
    return tuple(Allocation(name, out[i]) for i, (name, _) in enumerate(shares))


_NEXT: Final = text(
    "SELECT coalesce(max(seq), 0) + 1 FROM sixty_five_day_elections "
    "WHERE client_entity_id = :e AND tax_year = :y"
)
_INSERT: Final = text(
    "INSERT INTO sixty_five_day_elections (tenant_id, client_entity_id, tax_year, seq, status, "
    "amount, paid_on, window_end, decision_owner_contact_id, recorded_by_user_id, "
    "evidence_version_id, actor_kind) VALUES (:t, :e, :y, :n, :s, :a, :p, :w, :o, :u, :ev, "
    "'human') RETURNING id"
)


@dataclass(frozen=True)
class ElectionRecord:
    id: UUID
    seq: int
    status: str
    amount: Decimal | None
    paid_on: date | None
    window_end: date


async def record_election(
    ctx: AuthContext,
    client_entity_id: UUID,
    tax_year: int,
    *,
    status: str,
    amount: Decimal | None,
    paid_on: date | None,
    decision_owner_contact_id: UUID,
    evidence_version_id: UUID | None = None,
) -> ElectionRecord:
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(RECORD, "role")
    from abacus.modules.engagements.api import engagements_of_entity, get_ref

    authorised = False
    for engagement_id in await engagements_of_entity(ctx.tenant, client_entity_id):
        try:
            await authorise(ctx, RECORD, (await get_ref(ctx, engagement_id)).resource())
        except Forbidden:
            continue
        authorised = True
        break
    if not authorised:
        raise NotFound("client_entity")
    end = window_end(tax_year)
    if status == "elected" and (amount is None or amount <= 0 or paid_on is None or paid_on > end):
        raise ElectionInvalid(facts={"field": "paid_on"})
    if status == "not_made" and (amount is not None or paid_on is not None):
        raise ElectionInvalid(facts={"field": "amount"})
    async with uow(ctx.tenant) as tx:
        seq = int(await tx.session.scalar(_NEXT, {"e": client_entity_id, "y": tax_year}) or 1)
        made = cast(
            UUID,
            await tx.session.scalar(
                _INSERT,
                {
                    "t": ctx.tenant_id,
                    "e": client_entity_id,
                    "y": tax_year,
                    "n": seq,
                    "s": status,
                    "a": amount,
                    "p": paid_on,
                    "w": end,
                    "o": decision_owner_contact_id,
                    "u": ctx.user_id,
                    "ev": evidence_version_id,
                },
            ),
        )
        tx.record(
            "fiduciary_election.recorded",
            target=Target("sixty_five_day_election", made),
            after=Ref(tax_year=tax_year, seq=seq),
        )
    return ElectionRecord(made, seq, status, amount, paid_on, end)
