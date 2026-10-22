"""`/v1/me` v3 and the person's own preferences (P-01-T04; SHL-03; migration 0091).

The firm facts each membership shows (region, time zone, seats, sandbox) and, for the active
tenant, the person's initials, job title, the firm's offices and their default office filter.
Offices filter lists only and never restrict access (DEC-30). The default office is the person's
own row, written through the unit of work and audited as `user_preference.updated`.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainInvalid
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.authz import AuthContext
from abacus.modules.identity.slots import firm_offices


class OfficeNotInFirm(DomainInvalid):
    """The default office must be one of the active firm's offices."""

    code = "office_not_in_firm"


@dataclass(frozen=True)
class Office:
    id: UUID
    name: str


@dataclass(frozen=True)
class FirmFacts:
    region: str
    time_zone: str
    seats_total: int | None  # None for a sandbox: it holds no seats of its own
    is_sandbox: bool
    sandbox_of: UUID | None


@dataclass(frozen=True)
class MeDetails:
    initials: str | None
    job_title: str | None
    default_office_id: UUID | None
    offices: tuple[Office, ...]


_FIRM = text(
    "SELECT f.region, f.time_zone, f.sandbox_of_firm_id, "
    "(SELECT count(*) FROM memberships m WHERE m.status = 'active' AND m.kind = 'staff') AS seats "
    "FROM firms f"
)
_ME = text(
    "SELECT initials, job_title, default_office_filter_id FROM memberships "
    "WHERE user_id = :user_id AND status = 'active'"
)
_SET_DEFAULT_OFFICE = text(
    "UPDATE memberships SET default_office_filter_id = :office_id "
    "WHERE user_id = :user_id AND status = 'active'"
)


async def firm_facts(tenant: TenantContext) -> FirmFacts | None:
    """The firm row under its own tenant (row-level security), or None if it can't be read."""
    async with tenant_session(tenant) as session:
        row = (await session.execute(_FIRM)).one_or_none()
    if row is None:
        return None
    sandbox_of: UUID | None = row.sandbox_of_firm_id
    return FirmFacts(
        region=str(row.region),
        time_zone=str(row.time_zone),
        seats_total=None if sandbox_of is not None else int(row.seats),
        is_sandbox=sandbox_of is not None,
        sandbox_of=sandbox_of,
    )


async def me_details(tenant: TenantContext, user_id: UUID) -> MeDetails:
    async with tenant_session(tenant) as session:
        me = (await session.execute(_ME, {"user_id": user_id})).one_or_none()
    return MeDetails(
        initials=me.initials if me is not None else None,
        job_title=me.job_title if me is not None else None,
        default_office_id=me.default_office_filter_id if me is not None else None,
        offices=tuple(Office(i, name) for i, name in await firm_offices(tenant)),
    )


async def set_default_office(ctx: AuthContext, office_id: UUID | None) -> MeDetails:
    """AC 2.1.3: store the person's own default office filter (or clear it); audited."""
    if office_id is not None and office_id not in {i for i, _ in await firm_offices(ctx.tenant)}:
        raise OfficeNotInFirm
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            _SET_DEFAULT_OFFICE, {"office_id": office_id, "user_id": ctx.user_id}
        )
        tx.record(
            "user_preference.updated",
            target=Target("user", ctx.user_id),
            after=Ref(preference="default_office"),
        )
    return await me_details(ctx.tenant, ctx.user_id)
