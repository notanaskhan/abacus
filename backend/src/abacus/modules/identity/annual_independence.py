"""Annual independence confirmation (G-01-T13; G-01 §3.6, AC6.1 to AC6.3; DEC-91, DEC-381).

Once a year every staff member confirms (or declines, with a note) the firm's independence
statement, for themself only. The statement is firm content: a firm admin publishes it, each
publication a new version, and a person confirms the version they read (409 `stale_version` when
a newer one was published since; 409 `independence_statement_missing` before the first). Rows are
insert-only; the newest per person and year wins, so a decline can later become a confirmation.

- **Who confirms:** the person themself (`independence.annual_confirm` through `authorise_own`):
  a live, signed-in staff member; never support, a client user, an agent or the platform
  (INV-1, and the table's `actor_kind = 'human'` CHECK). There is no user id in the request, so
  nobody confirms for someone else (AC6.3, structural).
- **Who reads the list:** `independence.annual_read` (firm admins, quality partners, partners);
  anyone else gets a 404 (ADR-024). Each active staff member reads Confirmed with its date, Not
  yet, or Declined with its note, and the counts foot to the seat holders.
- **The year** is the firm's current business year in its time zone (`kernel.clock`).
- `has_current_annual_confirmation` is what P-07's G2 and team picker read (P-07-T41).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Final, Literal, cast
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel import clock
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.authz import Forbidden, Resource, authorise, authorise_own
from abacus.modules.identity.context import AuthContext
from abacus.modules.identity.events import IndependenceAnnualRecorded
from abacus.modules.identity.repository import time_zone_of

Decision = Literal["confirmed", "declined"]
Status = Literal["confirmed", "not_yet", "declined"]
STATUSES: Final[tuple[Status, ...]] = ("confirmed", "not_yet", "declined")


class StatementMissing(DomainConflict):
    """The firm has not published its independence statement yet, so there is nothing to
    confirm."""

    code = "independence_statement_missing"


# The statement changed since it was read: read it again. No docstring: the error catalogue keeps
# the shared `stale_version` summary.
class StaleStatement(DomainConflict):
    code = "stale_version"


class AnnualConfirmationInvalid(DomainInvalid):
    """Only the current year can be confirmed, and a decline needs a note."""

    code = "annual_confirmation_invalid"


@dataclass(frozen=True)
class Statement:
    version: int
    body: str


@dataclass(frozen=True)
class AnnualRow:
    user_id: UUID
    status: Status
    decided_at: datetime | None
    note: str | None


@dataclass(frozen=True)
class AnnualView:
    year: int
    rows: list[AnnualRow]
    counts: dict[str, int]


@dataclass(frozen=True)
class MyAnnual:
    year: int
    status: Status
    decided_at: datetime | None
    statement: Statement | None


@dataclass(frozen=True)
class Recorded:
    year: int
    decision: Decision
    decided_at: datetime


async def _zone(session: AsyncSession) -> ZoneInfo:
    try:
        return ZoneInfo(await time_zone_of(session))
    except (ZoneInfoNotFoundError, ValueError):
        return clock.FIRM_ZONE


async def business_today(tenant: TenantContext) -> date:
    """The firm's business date in its own time zone."""
    async with tenant_session(tenant) as session:
        zone = await _zone(session)
    return await clock.today(tenant, zone)


_LATEST = text(
    "SELECT DISTINCT ON (user_id) user_id, decision, note, decided_at, statement_version "
    "FROM independence_annual_confirmations WHERE year = :year "
    "AND (CAST(:user AS uuid) IS NULL OR user_id = :user) ORDER BY user_id, seq DESC"
)
_STATEMENT = text(
    "SELECT version, body FROM independence_statements ORDER BY version DESC LIMIT 1"
)


async def _latest(
    session: AsyncSession, year: int, user_id: UUID | None = None
) -> dict[UUID, RowMapping]:
    rows = await session.execute(_LATEST, {"year": year, "user": user_id})
    return {cast(UUID, r["user_id"]): r for r in rows.mappings()}


def _status(row: RowMapping | None, current: int | None) -> Status:
    """The newest answer, where a confirmation counts only for the statement as now published:
    a new version needs a new confirmation (DEC-383). A decline stands until answered again."""
    if row is None:
        return "not_yet"
    if row["decision"] == "confirmed" and row["statement_version"] != current:
        return "not_yet"
    return cast(Status, row["decision"])


async def _current_version(session: AsyncSession) -> int | None:
    found = await _statement(session)
    return None if found is None else found.version


async def _statement(session: AsyncSession) -> Statement | None:
    row = (await session.execute(_STATEMENT)).first()
    return None if row is None else Statement(int(row[0]), str(row[1]))


# --- reads ---------------------------------------------------------------------------------------


async def annual(ctx: AuthContext, year: int) -> AnnualView:
    """AC6.3 (ADM-02g): every active staff member's status for the year, in the order the firm
    added them, with counts that foot to them."""
    try:
        await authorise(ctx, "independence.annual_read", Resource.firm(ctx.tenant_id))
    except Forbidden:
        raise NotFound("annual_independence") from None
    async with tenant_session(ctx.tenant) as session:
        members = (
            await session.execute(
                text(
                    "SELECT user_id FROM memberships WHERE kind = 'staff' AND status = 'active' "
                    "ORDER BY created_at, user_id"
                )
            )
        ).scalars()
        people = [cast(UUID, m) for m in members]
        latest = await _latest(session, year)
        current = await _current_version(session)
    rows: list[AnnualRow] = []
    for user in people:
        status = _status(latest.get(user), current)
        answered = latest.get(user) if status != "not_yet" else None
        rows.append(
            AnnualRow(
                user,
                status,
                cast(datetime | None, answered["decided_at"]) if answered is not None else None,
                cast(str | None, answered["note"]) if answered is not None else None,
            )
        )
    counts = {status: sum(1 for r in rows if r.status == status) for status in STATUSES}
    return AnnualView(year, rows, counts)


async def _own_member(ctx: AuthContext) -> None:
    """A signed-in staff member of this firm reading their own status (`OWN`)."""
    if ctx.client or ctx.is_support or ctx.tenant.actor_kind != "human":
        raise NotFound("annual_independence")
    async with tenant_session(ctx.tenant) as session:
        found = await session.scalar(
            text(
                "SELECT 1 FROM memberships WHERE user_id = :u AND kind = 'staff' "
                "AND status = 'active'"
            ),
            {"u": ctx.user_id},
        )
    if found is None:
        raise NotFound("annual_independence")


async def mine(ctx: AuthContext, year: int | None = None) -> MyAnnual:
    """AC6.1: the person's own status for the year and the statement to confirm."""
    await _own_member(ctx)
    year = year or (await business_today(ctx.tenant)).year
    async with tenant_session(ctx.tenant) as session:
        latest = (await _latest(session, year, ctx.user_id)).get(ctx.user_id)
        statement = await _statement(session)
    status = _status(latest, None if statement is None else statement.version)
    return MyAnnual(
        year,
        status,
        cast(datetime | None, latest["decided_at"])
        if latest is not None and status != "not_yet"
        else None,
        statement,
    )


async def status_of(tenant: TenantContext, user_id: UUID, year: int) -> Status:
    """A person's status for the year, for a caller that already authorised reading the person
    (ADM-02d's drawer)."""
    async with tenant_session(tenant) as session:
        latest = (await _latest(session, year, user_id)).get(user_id)
        return _status(latest, await _current_version(session))


async def has_current_annual_confirmation(
    tenant: TenantContext, user_id: UUID, at: date | datetime | None = None
) -> bool:
    """AC6.2 (P-07-T41): whether the person's newest answer for `at`'s year (the firm's current
    business year by default) confirms the statement as now published (DEC-383). A decline, no
    answer, or a confirmation of an earlier version is False."""
    year = (await business_today(tenant)).year if at is None else at.year
    return await status_of(tenant, user_id, year) == "confirmed"


# --- writes --------------------------------------------------------------------------------------


async def record(
    ctx: AuthContext,
    *,
    year: int,
    decision: Decision,
    statement_version: int,
    note: str | None,
) -> Recorded:
    """AC6.1: the person's own confirmation or decline for the current year, of the statement
    version they read."""
    await authorise_own(ctx, "independence.annual_confirm")
    if year != (await business_today(ctx.tenant)).year:
        raise AnnualConfirmationInvalid(facts={"field": "year"})
    if decision == "declined" and not (note and note.strip()):
        raise AnnualConfirmationInvalid(facts={"field": "note"})
    async with uow(ctx.tenant) as tx:
        current = await _statement(tx.session)
        if current is None:
            raise StatementMissing
        if current.version != statement_version:
            raise StaleStatement(facts={"version": current.version})
        decided_at = cast(
            datetime,
            await tx.session.scalar(
                text(
                    "INSERT INTO independence_annual_confirmations (tenant_id, user_id, year, "
                    "decision, note, statement_version) VALUES (:tenant, :user, :year, "
                    ":decision, :note, :version) RETURNING decided_at"
                ),
                {
                    "tenant": ctx.tenant_id,
                    "user": ctx.user_id,
                    "year": year,
                    "decision": decision,
                    "note": note.strip() if note and note.strip() else None,
                    "version": statement_version,
                },
            ),
        )
        tx.record(
            f"independence.annual_{decision}",
            target=Target("user", ctx.user_id),
            after=Ref(year=year, statement_version=statement_version),
        )
        tx.emit(IndependenceAnnualRecorded(user_id=ctx.user_id, year=year))
    return Recorded(year, decision, decided_at)


def _human(ctx: AuthContext) -> None:
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden("firm.manage_settings", "role")


async def publish_statement(ctx: AuthContext, body: str) -> Statement:
    """The firm's statement as a new version (firm admin, fresh MFA; firm content, DEC-381).
    Everyone's next confirmation is of this version."""
    await authorise(ctx, "firm.manage_settings", Resource.firm(ctx.tenant_id))
    _human(ctx)
    text_ = body.strip()
    if not text_:
        raise AnnualConfirmationInvalid(facts={"field": "body"})
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext('independence_statements' || :t))"),
            {"t": str(ctx.tenant_id)},
        )
        current = await _statement(tx.session)
        version = 1 if current is None else current.version + 1
        await tx.session.execute(
            text(
                "INSERT INTO independence_statements (tenant_id, version, body, created_by) "
                "VALUES (:tenant, :version, :body, :by)"
            ),
            {"tenant": ctx.tenant_id, "version": version, "body": text_, "by": ctx.user_id},
        )
        tx.record(
            "independence.statement_published",
            target=Target("firm", ctx.tenant_id),
            after=Ref(version=version),
        )
    return Statement(version, text_)


async def statement(ctx: AuthContext) -> Statement | None:
    """The firm's current statement, for a settings reader (ADM-01's admins)."""
    try:
        await authorise(ctx, "firm.read_settings", Resource.firm(ctx.tenant_id))
    except Forbidden:
        raise NotFound("independence_statement") from None
    async with tenant_session(ctx.tenant) as session:
        return await _statement(session)
