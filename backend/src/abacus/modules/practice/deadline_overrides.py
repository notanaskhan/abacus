"""DF-10 firm overrides on top of the platform rules (T-08-T44; TASK-8919; T-08 AC2.13; FD-1;
HOME-03; KNW-04 section j; DEC-5921; amber).

- **Firm rows** are the firm's published `deadline_overrides` standard (methodology, K-02
  lifecycle: owner-drafted, owner-published, effective-dated, versioned): internal target offsets
  per form, closure days, and the relief notices it tracks. **Platform rows** (due-date rules,
  legal holidays, disaster postponements) stay read-only: no firm row changes a statutory date.
- **Internal targets** (`filing_deadlines.internal_target_on`): the statutory due date less the
  form's offset, moved earlier past a weekend, a legal holiday or a firm closure. HOME-03 keeps
  showing the statutory date; the target is stored and exported (OQ-16).
- **Client relief** (`postponement_applications`, insert-only, human-only, fresh MFA by the
  matrix): a firm admin, manager or partner applies one notice, by its notice id, to one client,
  naming the version it read (the platform's `disaster_postponements` set in effect, or the
  firm's overrides). Only that client's tax dates whose original due date falls in the notice's
  window move, to the notice's date; the row keeps the struck original (`postponed_from`) and the
  application (`postponement_notice_id`). Applying the same notice twice answers the first.
- **Pinning**: every date computed with overrides names the overrides version it read beside the
  platform versions (INV-2), so the same inputs give the same answer and hash.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import AuthContext, Forbidden, Resource, authorise, walled_from

APPLY: Final = "filing_deadline.apply_postponement"
TAX_LINES: Final = frozenset({"tax"})


class PostponementNoticeUnknown(DomainConflict):
    """The named version in effect carries no notice with this id (or the version is not the one
    in effect): nothing is applied."""

    code = "postponement_notice_unknown"


@dataclass(frozen=True)
class Notice:
    notice_id: str
    window_start: date
    window_end: date
    postponed_to: date
    source: Literal["platform", "firm"]
    version_id: UUID


@dataclass(frozen=True)
class Overrides:
    version_id: UUID
    offsets: Mapping[str, int]  # form -> days before the statutory date
    closures: frozenset[date]
    notices: Mapping[str, Notice]  # the firm's own relief notices


@dataclass(frozen=True)
class Application:
    id: UUID
    client_id: UUID
    notice: Notice
    applied_at: datetime


# --- pure ----------------------------------------------------------------------------------------


def internal_target(
    due_on: date, offset_days: int, closures: frozenset[date], holidays: frozenset[date]
) -> date:
    """The statutory date less the offset, moved earlier past a weekend, a legal holiday or a
    firm closure day (a target is a day the firm works)."""
    day = due_on - timedelta(days=offset_days)
    while day.weekday() >= 5 or day in closures or day in holidays:
        day -= timedelta(days=1)
    return day


def postponed(original_due_on: date, due_on: date, notice: Notice) -> date | None:
    """The date a notice moves a due date to: when the original due date falls in its window
    and the notice's date is later; None otherwise (a notice never moves a date earlier)."""
    if (
        notice.window_start <= original_due_on <= notice.window_end
        and notice.postponed_to > due_on
    ):
        return notice.postponed_to
    return None


# --- reads ---------------------------------------------------------------------------------------


async def overrides_in_effect(tenant_id: UUID, as_of: date) -> Overrides | None:
    from abacus.modules.methodology.api import deadline_overrides_in_effect

    found = await deadline_overrides_in_effect(tenant_id, as_of)
    if found is None:
        return None
    policy, payload = found
    return Overrides(
        version_id=policy.version_id,
        offsets={r.form: r.internal_offset_days for r in payload.offsets},
        closures=frozenset(r.date for r in payload.closures),
        notices={
            r.notice_id: Notice(
                r.notice_id, r.window_start, r.window_end, r.postponed_to, "firm",
                policy.version_id,
            )
            for r in payload.postponements
        },
    )  # fmt: skip


async def platform_notices(as_of: date) -> dict[str, Notice]:
    """The platform's `disaster_postponements` in effect, by notice id (each with its version)."""
    from abacus.modules.platform.api import DisasterPostponementsPayload, references_in_effect

    out: dict[str, Notice] = {}
    for found in await references_in_effect("disaster_postponements", as_of):
        for row in cast(DisasterPostponementsPayload, found.payload).rows:
            out[row.notice_id] = Notice(
                row.notice_id, row.window.start, row.window.end, row.postponed_to, "platform",
                found.version_id,
            )  # fmt: skip
    return out


_APPLICATIONS: Final = text(
    "SELECT id, client_id, notice_id, source, reference_set_version_id, applied_at "
    "FROM postponement_applications WHERE (CAST(:client AS uuid) IS NULL OR client_id = :client) "
    "ORDER BY applied_at, id"
)


async def applications(
    tenant: TenantContext, as_of: date, client_id: UUID | None = None
) -> dict[UUID, list[Application]]:
    """Every client's applications whose notice is still in effect, by client."""
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_APPLICATIONS, {"client": client_id})).all()
    if not rows:
        return {}
    platform = await platform_notices(as_of)
    firm = await overrides_in_effect(tenant.tenant_id, as_of)
    out: dict[UUID, list[Application]] = {}
    for r in rows:
        pool = platform if r.source == "platform" else ({} if firm is None else firm.notices)
        notice = pool.get(str(r.notice_id))
        if notice is None:
            continue  # the notice was withdrawn from the version in effect: nothing moves
        out.setdefault(cast(UUID, r.client_id), []).append(
            Application(cast(UUID, r.id), cast(UUID, r.client_id), notice, r.applied_at)
        )
    return out


# --- the person's act ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Applied:
    application_id: UUID
    client_id: UUID
    moved: int
    applied_at: datetime


_INSERT: Final = text(
    "INSERT INTO postponement_applications (tenant_id, client_id, notice_id, source, "
    "reference_set_version_id, applied_by) VALUES (:t, :c, :n, :s, :v, :by) "
    "ON CONFLICT (tenant_id, client_id, notice_id) DO NOTHING RETURNING id, applied_at"
)
_EXISTING: Final = text(
    "SELECT id, applied_at FROM postponement_applications WHERE client_id = :c AND notice_id = :n"
)


class _Nothing(Exception):
    """Leave the unit of work without a commit (nothing changed)."""


async def apply_postponement(
    ctx: AuthContext, client_id: UUID, notice_id: str, reference_set_version_id: UUID
) -> Applied:
    """A person applies a notice to one client (module docstring); answers how many of that
    client's deadline rows moved. A walled or unknown client is 404."""
    from abacus.kernel.clock import today
    from abacus.modules.organisations.api import client_exists

    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(APPLY, "role")
    await authorise(ctx, APPLY, Resource.client(ctx.tenant_id, client_id))
    if client_id in await walled_from(ctx.tenant, ctx.user_id) or not await client_exists(
        ctx.tenant, client_id
    ):
        raise NotFound("client")
    as_of = await today(ctx.tenant)
    platform = await platform_notices(as_of)
    firm = await overrides_in_effect(ctx.tenant_id, as_of)
    notice = platform.get(notice_id)
    if notice is None or notice.version_id != reference_set_version_id:
        notice = None if firm is None else firm.notices.get(notice_id)
    if notice is None or notice.version_id != reference_set_version_id:
        raise PostponementNoticeUnknown(facts={"notice_id": notice_id})
    row = None
    try:
        async with uow(ctx.tenant) as tx:
            row = (
                await tx.session.execute(
                    _INSERT,
                    {"t": ctx.tenant_id, "c": client_id, "n": notice_id, "s": notice.source,
                     "v": reference_set_version_id, "by": ctx.user_id},
                )
            ).first()  # fmt: skip
            if row is None:
                raise _Nothing  # applied before: no write, no event
            tx.record(
                "postponement.applied",
                target=Target("client", client_id),
                after=Ref(application=cast(UUID, row.id), version=reference_set_version_id),
            )
    except _Nothing:
        row = None
    if row is None:  # applied before: answer the first
        async with tenant_session(ctx.tenant) as session:
            row = (await session.execute(_EXISTING, {"c": client_id, "n": notice_id})).first()
        if row is None:
            raise NotFound("postponement_application")
    from abacus.modules.practice.deadlines_service import recompute

    moved = await recompute(ctx.tenant_id, client_id=client_id)
    return Applied(cast(UUID, row.id), client_id, moved, row.applied_at)


def apply_overrides(
    facts: Sequence[object],
    overrides: Overrides | None,
    client_applications: Mapping[UUID, Sequence[Application]],
    holidays: frozenset[date],
) -> list[tuple[object, date | None, Application | None, date | None]]:
    """For each `FilingDeadlineFact`: (fact, internal target, the application that moved it, the
    moved date). Pure: the recompute writes what this answers."""
    from abacus.modules.platform.api import FilingDeadlineFact

    out: list[tuple[object, date | None, Application | None, date | None]] = []
    for raw in facts:
        fact = cast(FilingDeadlineFact, raw)
        moved_by: Application | None = None
        moved_to: date | None = None
        if fact.service_line in TAX_LINES and fact.client_id is not None:
            for app in client_applications.get(fact.client_id, ()):
                to = postponed(fact.original_due_on, fact.due_on, app.notice)
                if to is not None and (moved_to is None or to > moved_to):
                    moved_by, moved_to = app, to
        target: date | None = None
        if overrides is not None and fact.source_kind == "tax_return" and fact.rule_key:
            offset = overrides.offsets.get(fact.rule_key)
            if offset is not None:
                due = moved_to or fact.due_on
                target = internal_target(due, offset, overrides.closures, holidays)
        out.append((fact, target, moved_by, moved_to))
    return out


__all__ = [
    "APPLY",
    "Application",
    "Applied",
    "Notice",
    "Overrides",
    "PostponementNoticeUnknown",
    "applications",
    "apply_overrides",
    "apply_postponement",
    "internal_target",
    "overrides_in_effect",
    "platform_notices",
    "postponed",
]
