"""The independence tables (migration 0175, P-07-T41) and the G2 answer they give.

`g2_met` is G2's one source (DEC-428, as DEC-372 is G1's): an engagement with a conclusion row
reads its newest conclusion (Independent or Independent with safeguards: met; Not independent:
unmet); one without reads SPEC-025's `engagement_acceptance` conclusion, only on a row written
before 0175 (`legacy_g2`, DEC-429: the old route can never meet G2 again), until P-07-T59
converts those rows. Either way an open breach (logged, and not yet evaluated, communicated to
those charged with governance and remediated) keeps G2 unmet (SPEC-332 AC-28).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID

from sqlalchemy import Column, FetchedValue, MetaData, Table, func, select
from sqlalchemy.dialects.postgresql import BYTEA
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import BigInteger, Boolean, DateTime, Text

from abacus.modules.engagements.models import EngagementAcceptance
from abacus.modules.engagements.repository import latest_acceptance

_meta = MetaData()
POSITIVE: Final = frozenset({"independent", "independent_with_safeguards"})
BREACH_STEPS: Final = ("evaluated", "tcwg_communicated", "remediated")


def _id() -> Column[UUID]:
    return Column("id", PgUUID(as_uuid=True), primary_key=True, server_default=FetchedValue())


def _uuid(name: str) -> Column[UUID]:
    return Column(name, PgUUID(as_uuid=True))


def _at(name: str) -> Column[datetime]:
    return Column(name, DateTime(timezone=True), server_default=FetchedValue())


conclusions = Table(
    "independence_conclusions",
    _meta,
    _id(),
    _uuid("tenant_id"),
    _uuid("engagement_id"),
    Column("option", Text),
    Column("safeguards_sealed", BYTEA),
    _uuid("concluded_by"),
    _at("concluded_at"),
    Column("mfa_verified_at", DateTime(timezone=True)),
    _uuid("supersedes_id"),
)
nas_rows = Table(
    "nas_evaluations",
    _meta,
    _id(),
    _uuid("tenant_id"),
    _uuid("engagement_id"),
    Column("service_code", Text),
    _uuid("created_by"),
    _at("created_at"),
)
nas_events = Table(
    "nas_evaluation_events",
    _meta,
    _id(),
    Column("seq", BigInteger, server_default=FetchedValue()),
    _uuid("tenant_id"),
    _uuid("nas_id"),
    Column("provided", Boolean),
    Column("status", Text),
    Column("evaluation_sealed", BYTEA),
    Column("safeguards_sealed", BYTEA),
    _uuid("ske_contact_id"),
    _uuid("recorded_by"),
    _at("recorded_at"),
)
breaches = Table(
    "independence_breaches",
    _meta,
    _id(),
    _uuid("tenant_id"),
    _uuid("engagement_id"),
    Column("description_sealed", BYTEA),
    _uuid("user_id"),
    _uuid("logged_by"),
    _at("logged_at"),
)
breach_events = Table(
    "independence_breach_events",
    _meta,
    _id(),
    _uuid("tenant_id"),
    _uuid("breach_id"),
    Column("kind", Text),
    Column("note_sealed", BYTEA),
    _uuid("recorded_by"),
    _at("recorded_at"),
)


@dataclass(frozen=True)
class Concluded:
    id: UUID
    option: str
    concluded_by: UUID
    concluded_at: datetime
    supersedes_id: UUID | None
    safeguards_sealed: bytes | None


async def latest_conclusion(session: AsyncSession, engagement_id: UUID) -> Concluded | None:
    """The engagement's current conclusion: the row no later conclusion supersedes."""
    superseded = select(conclusions.c.supersedes_id).where(
        conclusions.c.engagement_id == engagement_id,
        conclusions.c.supersedes_id.is_not(None),
    )
    row = (
        await session.execute(
            select(conclusions)
            .where(
                conclusions.c.engagement_id == engagement_id,
                conclusions.c.id.not_in(superseded),
            )
            .order_by(conclusions.c.concluded_at.desc(), conclusions.c.id.desc())
            .limit(1)
        )
    ).one_or_none()
    if row is None:
        return None
    return Concluded(
        row.id,
        row.option,
        row.concluded_by,
        row.concluded_at,
        row.supersedes_id,
        row.safeguards_sealed,
    )


async def open_breach_ids(session: AsyncSession, engagement_id: UUID) -> list[UUID]:
    """Breaches logged on the engagement that still lack one of the three closing events."""
    steps = (
        select(func.count(func.distinct(breach_events.c.kind)))
        .where(breach_events.c.breach_id == breaches.c.id)
        .scalar_subquery()
    )
    rows = await session.execute(
        select(breaches.c.id)
        .where(breaches.c.engagement_id == engagement_id, steps < len(BREACH_STEPS))
        .order_by(breaches.c.logged_at, breaches.c.id)
    )
    return list(rows.scalars().all())


async def g2_met(session: AsyncSession, engagement_id: UUID) -> bool:
    """G2 (DEC-428): the newest conclusion is positive (SPEC-025's conclusion where the
    engagement has no conclusion row) and no breach is open."""
    if await open_breach_ids(session, engagement_id):
        return False
    concluded = await latest_conclusion(session, engagement_id)
    if concluded is not None:
        return concluded.option in POSITIVE
    return legacy_concluded(await latest_acceptance(session, engagement_id)) is not None


def legacy_concluded(legacy: EngagementAcceptance | None) -> datetime | None:
    """SPEC-025's conclusion time, on a row written before 0175 only (DEC-429)."""
    if legacy is None or not legacy.legacy_g2:
        return None
    return legacy.independence_concluded_at
