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
from typing import Any, Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel._statuses import SixtyFiveDayElectionStatus, TieOutTallyStatus
from abacus.kernel.clock import today as business_today
from abacus.kernel.db import tenant_session
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


# --- TXT-03's read model (T-07-T23 rest; DEC-5331) ---------------------------------------------

_ALLOCATIONS: Final = text(
    "SELECT beneficiary_contact_id, distributions, share, dni_allocated, box_1, box_2a, box_2b "
    "FROM beneficiary_allocations WHERE computation_id = :c ORDER BY beneficiary_contact_id"
)
_PAYMENTS: Final = text(
    "SELECT d.beneficiary_contact_id, v.paid_on, v.amount FROM trust_distributions d JOIN LATERAL "
    "(SELECT * FROM trust_distribution_versions x WHERE x.distribution_id = d.id "
    "ORDER BY x.seq DESC LIMIT 1) v ON true WHERE d.work_item_id = :r ORDER BY v.paid_on, d.id"
)
_ELECTION: Final = text(
    "SELECT status, amount, paid_on, decision_owner_contact_id FROM sixty_five_day_elections "
    "WHERE client_entity_id = :e AND tax_year = :y ORDER BY seq DESC LIMIT 1"
)
READ: Final = "beneficiary_allocation.read"


async def beneficiaries(ctx: AuthContext, return_id: UUID) -> object:
    """TXT-03 (AC-9.1 to AC-11.3): code's allocation from the signed computation, each
    beneficiary's payments and K-1 package, the 65-day card and the 1041 release steps. Before
    a current L2 sign-off on the computation, no rows (TXT-03 e)."""
    from abacus.modules.review.api import sign_off_states
    from abacus.modules.tax import fiduciary_contract as m
    from abacus.modules.tax import fiduciary_service as fs
    from abacus.modules.tax import k1_packages, k1_release

    _, client_entity_id, tax_year = await fs._scope(ctx, return_id, READ)  # pyright: ignore[reportPrivateUsage] -- the module's own scope check
    async with tenant_session(ctx.tenant) as session:
        current = (await session.execute(fs._CURRENT, {"r": return_id})).first()  # pyright: ignore[reportPrivateUsage] -- the module's own read
        payments = (await session.execute(_PAYMENTS, {"r": return_id})).all()
        election = (
            await session.execute(_ELECTION, {"e": client_entity_id, "y": tax_year})
        ).first()
        found_allocations: Sequence[Any] = (  # Any: SQLAlchemy rows, typed just below
            []
            if current is None
            else (await session.execute(_ALLOCATIONS, {"c": current[0]})).all()
        )
    allocations: list[tuple[UUID, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal]] = [
        (
            cast(UUID, a[0]),
            Decimal(a[1]),
            Decimal(a[2]),
            Decimal(a[3]),
            Decimal(a[4]),
            Decimal(a[5]),
            Decimal(a[6]),
        )
        for a in found_allocations
    ]
    signed = False
    if current is not None:
        states = await sign_off_states(
            ctx.tenant, fs.TARGET, [return_id], {return_id: str(current[4])}
        )
        l2 = next((x for x in states.get(return_id, []) if x.level == 2), None)
        signed = l2 is not None and l2.signed_by is not None and not l2.stale
    contacts = sorted({cast(UUID, r[0]) for r in payments} | {a[0] for a in allocations}, key=str)
    names = await fs._contact_names(ctx.tenant, contacts)  # pyright: ignore[reportPrivateUsage] -- the module's own read
    packages = {p.recipient_id: p for p in (await k1_packages.packages_of(ctx, return_id))[0]}
    rows: list[m.BeneficiaryRowOut] = []
    if signed:
        for contact, dist, share, dni, b1, b2a, b2b in allocations:
            package = packages.get(contact)
            rows.append(
                m.BeneficiaryRowOut(
                    contact_id=contact,
                    name=names.get(contact, ""),
                    payments=[
                        m.BeneficiaryPaymentOut(paid_on=on, amount=Decimal(a))
                        for c, on, a in payments
                        if c == contact
                    ],
                    distributions=dist,
                    share=share,
                    dni_allocated=dni,
                    box_1=b1,
                    box_2a=b2a,
                    box_2b=b2b,
                    delivery="firm_1040_client"
                    if package is not None and package.recipient_kind == "client"
                    else "portal_k1_recipient",
                    package_id=None if package is None else package.id,
                    package_status=None if package is None else package.status,  # type: ignore[arg-type] -- T-02's code
                )
            )
    outputs = cast("dict[str, object]", current[3]) if current is not None and signed else {}
    totals = (
        m.BeneficiaryTotalsOut(
            distributions=sum((r.distributions for r in rows), Decimal(0)),
            share=sum((r.share for r in rows), Decimal(0)),
            dni_allocated=sum((r.dni_allocated for r in rows), Decimal(0)),
            box_1=sum((r.box_1 for r in rows), Decimal(0)),
            box_2a=sum((r.box_2a for r in rows), Decimal(0)),
            box_2b=sum((r.box_2b for r in rows), Decimal(0)),
            income_distribution_deduction=Decimal(str(outputs.get("idd", "0"))),
            tie=TieOutTallyStatus.TIE if outputs.get("tie") else TieOutTallyStatus.OFF,
        )
        if rows
        else None
    )
    end = window_end(tax_year)
    start = date(tax_year + 1, 1, 1)
    in_window = sum((Decimal(a) for _, on, a in payments if start <= on <= end), Decimal(0))
    owner = None if election is None else cast("UUID | None", election[3])
    owner_name = None
    if owner is not None:
        owner_name = (await fs._contact_names(ctx.tenant, [owner])).get(owner)  # pyright: ignore[reportPrivateUsage] -- the module's own read
    today = await business_today(ctx.tenant)
    card = m.SixtyFiveDayCardOut(
        tax_year=tax_year,
        window_start=start,
        window_end=end,
        closed=today > end,
        distributions_in_window=in_window if in_window else None,
        decision_owner_name=owner_name,
        status=SixtyFiveDayElectionStatus.NOT_MADE
        if election is None
        else SixtyFiveDayElectionStatus(str(election[0])),
        amount=None if election is None else election[1],
        paid_on=None if election is None else election[2],
        next_tax_year=tax_year + 1,
        next_window_end=window_end(tax_year + 1),
        paragraph=None,
    )
    check = await k1_release.eligibility(ctx, return_id)
    steps = [
        m.ReleaseStepOut(
            key=k1_release.STEP_FINAL_APPROVAL,
            met="not_final_approved" not in check.failing,
            by_name=None,
            at=None,
            superseded_by_change=False,
        ),
        m.ReleaseStepOut(
            key=k1_release.STEP_FORM_8879_F,
            met="form_8879_f" not in check.failing,
            by_name=None,
            at=None,
            superseded_by_change=False,
        ),
    ]
    return m.BeneficiariesOut(
        return_id=return_id,
        computation_id=current[0] if current is not None and signed else None,
        rows=rows,
        totals=totals,
        election=card,
        release_steps=steps,
        release_reason=None if check.eligible else check.failing[0],
        allowed_actions=["fiduciary_election.record", "k1_package.release", "k1_package.resend"],
    )
