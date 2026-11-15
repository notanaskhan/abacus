"""Closes data access (F-03-T22; C-01-T14): the `closes` subtype rows and the facts the close
record computes from the module's own tables (plans, procedures, reconciliations, schedules)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Final
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_INSERT = text(
    "INSERT INTO closes (tenant_id, work_item_id, engagement_id, period, client_entity_id, "
    "requests_publish_on, due_on) "
    "VALUES (:tenant_id, :work_item_id, :engagement_id, :period, :client_entity_id, "
    ":requests_publish_on, :due_on)"
)


async def insert_closes(session: AsyncSession, values: Mapping[str, object]) -> None:
    await session.execute(
        _INSERT,
        {"client_entity_id": None, "requests_publish_on": None, "due_on": None, **dict(values)},
    )


@dataclass(frozen=True)
class CloseRow:
    work_item_id: UUID
    engagement_id: UUID
    client_entity_id: UUID | None
    period: str
    status: str
    on_hold: bool
    on_hold_reason: str | None
    close_plan_version_id: UUID | None
    plan_pinned_at: datetime | None
    requests_publish_on: date | None
    due_on: date | None
    run_no: int
    locked_at: datetime | None
    row_version: int


_COLUMNS: Final = (
    "work_item_id, engagement_id, client_entity_id, period, status, on_hold, on_hold_reason, "
    "close_plan_version_id, plan_pinned_at, requests_publish_on, due_on, run_no, locked_at, "
    "row_version"
)
_BY_IDS = text(f"SELECT {_COLUMNS} FROM closes WHERE work_item_id = ANY(:ids)")  # noqa: S608
_ONE = text(f"SELECT {_COLUMNS} FROM closes WHERE work_item_id = :id")  # noqa: S608
_LOCK = text(f"SELECT {_COLUMNS} FROM closes WHERE work_item_id = :id FOR UPDATE")  # noqa: S608
_OF_ENGAGEMENT = text("SELECT period FROM closes WHERE engagement_id = :e")
_NEIGHBOURS = text(
    "SELECT period, work_item_id FROM closes WHERE engagement_id = :e AND period = ANY(:p)"
)


def _row(r: Sequence[object]) -> CloseRow:
    return CloseRow(*r)  # type: ignore[arg-type]


async def closes_by_ids(session: AsyncSession, ids: Sequence[UUID]) -> list[CloseRow]:
    if not ids:
        return []
    return [_row(r) for r in (await session.execute(_BY_IDS, {"ids": list(ids)})).all()]


async def close_row(
    session: AsyncSession, close_id: UUID, *, lock: bool = False
) -> CloseRow | None:
    found = (await session.execute(_LOCK if lock else _ONE, {"id": close_id})).first()
    return None if found is None else _row(found)


async def periods_of(session: AsyncSession, engagement_id: UUID) -> frozenset[str]:
    return frozenset(await session.scalars(_OF_ENGAGEMENT, {"e": engagement_id}))


async def neighbours(
    session: AsyncSession, engagement_id: UUID, periods: Sequence[str]
) -> dict[str, UUID]:
    rows = await session.execute(_NEIGHBOURS, {"e": engagement_id, "p": list(periods)})
    return {period: item for period, item in rows.all()}


_STATUS = text(
    "UPDATE closes SET status = :status, on_hold = :on_hold, on_hold_reason = :reason, "
    "locked_at = CASE WHEN :status = 'locked' THEN abacus_now() ELSE locked_at END, "
    "row_version = row_version + 1 "
    "WHERE work_item_id = :id AND row_version = :seen RETURNING row_version"
)


async def update_status(
    session: AsyncSession,
    close_id: UUID,
    *,
    status: str,
    on_hold: bool,
    reason: str | None,
    seen: int,
) -> int | None:
    """The new row version, or None when `seen` is stale."""
    return await session.scalar(
        _STATUS,
        {"id": close_id, "status": status, "on_hold": on_hold, "reason": reason, "seen": seen},
    )


_BUMP = text(
    "UPDATE closes SET row_version = row_version + 1 "
    "WHERE work_item_id = :id AND row_version = :seen RETURNING row_version"
)


async def bump(session: AsyncSession, close_id: UUID, seen: int) -> int | None:
    return await session.scalar(_BUMP, {"id": close_id, "seen": seen})


_START = text(
    "UPDATE closes SET status = 'in_progress', row_version = row_version + 1 "
    "WHERE work_item_id = :id AND status = 'not_started' RETURNING work_item_id"
)


async def start(session: AsyncSession, close_id: UUID) -> bool:
    """Not started → In progress (a system transition): False when already past it."""
    return await session.scalar(_START, {"id": close_id}) is not None


# --- plans --------------------------------------------------------------------------------------

_PLAN_VERSIONS = text("SELECT v.id, v.version FROM close_plan_versions v WHERE v.id = ANY(:ids)")
# The current published version of each entity's plan: the newest whose effective month has
# begun by the close's period (a close not yet pinned reads the version it would pin, QC-2).
_EFFECTIVE = text(
    "SELECT DISTINCT ON (p.client_entity_id) p.client_entity_id, v.id, v.version "
    "FROM close_plans p JOIN close_plan_versions v ON v.plan_id = p.id "
    "WHERE p.client_entity_id = ANY(:entities) AND v.status = 'published' "
    "AND v.effective_from <= :period "
    "ORDER BY p.client_entity_id, v.effective_from DESC, v.version DESC"
)
# Balance-sheet accounts: the income-statement procedures (recategorize, flux) are not accounts.
_PLAN_ACCOUNTS = text(
    "SELECT version_id, id, account_external_id, account_name, procedure, review_level "
    "FROM close_plan_rows WHERE version_id = ANY(:ids) "
    "AND procedure NOT IN ('recategorize', 'flux') ORDER BY version_id, position"
)


@dataclass(frozen=True)
class PlanAccount:
    row_id: UUID
    account_external_id: str | None
    account_name: str
    procedure: str
    review_level: str


async def plan_versions(session: AsyncSession, ids: Sequence[UUID]) -> dict[UUID, int]:
    if not ids:
        return {}
    rows = await session.execute(_PLAN_VERSIONS, {"ids": list(ids)})
    return {vid: int(version) for vid, version in rows.all()}


async def effective_versions(
    session: AsyncSession, entities: Sequence[UUID], period: str
) -> dict[UUID, tuple[UUID, int]]:
    if not entities:
        return {}
    rows = await session.execute(_EFFECTIVE, {"entities": list(entities), "period": period})
    return {entity: (vid, int(version)) for entity, vid, version in rows.all()}


async def plan_accounts(
    session: AsyncSession, version_ids: Sequence[UUID]
) -> dict[UUID, list[PlanAccount]]:
    out: dict[UUID, list[PlanAccount]] = {vid: [] for vid in version_ids}
    if not version_ids:
        return out
    for vid, row_id, ext, name, procedure, review in (
        await session.execute(_PLAN_ACCOUNTS, {"ids": list(version_ids)})
    ).all():
        out[vid].append(PlanAccount(row_id, ext, name, procedure, review))
    return out


# --- what has been computed for each account ----------------------------------------------------

# The newest version of each account's reconciliation (a recompute is a new version, ADR-004).
_LATEST_RECS = text(
    "SELECT DISTINCT ON (close_id, account_external_id) close_id, account_external_id, id, "
    "tally, content_hash FROM reconciliations WHERE close_id = ANY(:ids) "
    "ORDER BY close_id, account_external_id, version DESC"
)
_ITEM_ISSUES = text(
    "SELECT reconciliation_id, issue_id FROM reconciling_items "
    "WHERE reconciliation_id = ANY(:ids) AND issue_id IS NOT NULL"
)
_LATEST_SCHEDULES = text(
    "SELECT DISTINCT ON (r.close_id, a.account_external_id) r.close_id, a.account_external_id, "
    "r.tie FROM close_schedule_results r JOIN arrangements a ON a.id = r.arrangement_id "
    "WHERE r.close_id = ANY(:ids) ORDER BY r.close_id, a.account_external_id, r.computed_at DESC"
)
_LATEST_PROCEDURES = text(
    "SELECT DISTINCT ON (close_id, plan_row_id) close_id, plan_row_id, status, open_count "
    "FROM close_procedures WHERE close_id = ANY(:ids) AND plan_row_id IS NOT NULL "
    "ORDER BY close_id, plan_row_id, started_at DESC NULLS LAST"
)
_RUNNING = text(
    "SELECT DISTINCT close_id FROM close_procedures "
    "WHERE close_id = ANY(:ids) AND status IN ('queued', 'running')"
)


@dataclass(frozen=True)
class LatestReconciliation:
    reconciliation_id: UUID
    tally: str
    content_hash: str


@dataclass(frozen=True)
class Computed:
    reconciliations: dict[tuple[UUID, str], LatestReconciliation]
    item_issues: dict[UUID, list[UUID]]
    schedules: dict[tuple[UUID, str], str]
    procedures: dict[tuple[UUID, UUID], tuple[str, int]]
    running: frozenset[UUID]


async def computed(session: AsyncSession, close_ids: Sequence[UUID]) -> Computed:
    ids = {"ids": list(close_ids)}
    recs = {
        (close, account): LatestReconciliation(rid, tally, content_hash)
        for close, account, rid, tally, content_hash in (
            await session.execute(_LATEST_RECS, ids)
        ).all()
    }
    issues: dict[UUID, list[UUID]] = {}
    rec_ids = [r.reconciliation_id for r in recs.values()]
    if rec_ids:
        for rid, issue in (await session.execute(_ITEM_ISSUES, {"ids": rec_ids})).all():
            issues.setdefault(rid, []).append(issue)
    schedules = {
        (close, account): tie
        for close, account, tie in (await session.execute(_LATEST_SCHEDULES, ids)).all()
    }
    procedures = {
        (close, row): (status, int(open_count))
        for close, row, status, open_count in (
            await session.execute(_LATEST_PROCEDURES, ids)
        ).all()
    }
    running = frozenset(await session.scalars(_RUNNING, ids))
    return Computed(recs, issues, schedules, procedures, running)


_RUNNING_RUNS = text(
    "SELECT DISTINCT ON (close_id) close_id, run_id, "
    "count(*) FILTER (WHERE status IN ('done', 'needs_attention')) "
    "OVER (PARTITION BY close_id, run_id), count(*) OVER (PARTITION BY close_id, run_id), "
    "min(started_at) OVER (PARTITION BY close_id, run_id) "
    "FROM close_procedures p WHERE close_id = ANY(:ids) "
    "AND EXISTS (SELECT 1 FROM close_procedures q WHERE q.close_id = p.close_id "
    "AND q.run_id = p.run_id AND q.status IN ('queued', 'running')) "
    "ORDER BY close_id, started_at DESC NULLS LAST"
)


@dataclass(frozen=True)
class RunningRun:
    close_id: UUID
    run_id: UUID
    done: int
    total: int
    started_at: datetime


async def running_runs(session: AsyncSession, close_ids: Sequence[UUID]) -> list[RunningRun]:
    """Each close's newest run that still has a procedure queued or running."""
    if not close_ids:
        return []
    rows = await session.execute(_RUNNING_RUNS, {"ids": list(close_ids)})
    return [RunningRun(c, r, int(d), int(t), s) for c, r, d, t, s in rows.all()]
