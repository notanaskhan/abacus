"""Access events: who read which client content (Q-02-T20; AC-23, AC-25). PROTECTED.

`record_reads` writes one identifier-only row per subject in one statement, committed on its own:
a read changes no state, so it needs no unit of work or audit event. The read's caller writes the
rows before handing the content over, and an error propagates, so content that can't be recorded
is never served. Rows hold no file name, quote or value. A kind is registered once
(`register_access_kind`) with the classification flags its content always carries; any other kind
is refused.

Public as `abacus.kernel.access`.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Final
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import TenantContext, platform_transaction, tenant_connection

FLAGS: Final = frozenset(
    {"tri", "phi", "pii_tin", "pii_bank", "pii_ip_pin", "pii_dob", "restricted"}
)
_KIND: Final = re.compile(r"[a-z_]+\.[a-z_]+")
_SUBJECT_TYPE: Final = re.compile(r"[a-z][a-z_]{0,39}")
_KINDS: dict[str, frozenset[str]] = {}


@dataclass(frozen=True)
class AccessSubject:
    """What was read, by identifiers only."""

    subject_type: str
    subject_id: UUID
    client_id: UUID | None = None
    engagement_id: UUID | None = None
    work_item_id: UUID | None = None
    taxpayer_contact_id: UUID | None = None
    tax_year: int | None = None


class UnknownAccessKind(ValueError):
    """`record_reads` was asked for a kind nobody registered."""


def register_access_kind(kind: str, flags: Iterable[str] = ()) -> None:
    """A kind of read and the flags its content always carries; registering twice must agree."""
    wanted = frozenset(flags)
    if not _KIND.fullmatch(kind) or not wanted <= FLAGS:
        raise ValueError(f"access kind {kind!r} or its flags are not valid")
    if kind in _KINDS and _KINDS[kind] != wanted:
        raise ValueError(f"access kind {kind!r} is already registered with other flags")
    _KINDS[kind] = wanted


def _actor_id(ctx: TenantContext) -> UUID | None:
    try:
        return UUID(ctx.actor_id)
    except ValueError:
        return None  # an agent or system principal named by text (`agent:<run>`)


_INSERT = text(
    "INSERT INTO access_events (tenant_id, actor_kind, actor_id, on_behalf_of_user_id, run_id, "
    "kind, subject_type, subject_id, client_id, engagement_id, work_item_id, "
    "taxpayer_contact_id, tax_year, flags, request_id) VALUES (:tenant, :actor_kind, :actor, "
    ":on_behalf, :run, :kind, :subject_type, :subject_id, :client, :engagement, :work_item, "
    ":taxpayer, :tax_year, :flags, :request)"
)


async def record_reads(
    ctx: TenantContext,
    kind: str,
    subjects: Sequence[AccessSubject],
    *,
    run_id: UUID | None = None,
    request_id: UUID | None = None,
    flags: Iterable[str] = (),
) -> int:
    """Record that `ctx` read each subject; returns how many rows were written."""
    if kind not in _KINDS:
        raise UnknownAccessKind(kind)
    extra = frozenset(flags)
    if not extra <= FLAGS:
        raise ValueError("unknown access flags")
    if not subjects:
        return 0
    for subject in subjects:
        if not _SUBJECT_TYPE.fullmatch(subject.subject_type):
            raise ValueError(f"subject type {subject.subject_type!r} is not an identifier")
    marked = sorted(_KINDS[kind] | extra)
    rows = [
        {
            "tenant": ctx.tenant_id,
            "actor_kind": ctx.actor_kind,
            "actor": _actor_id(ctx),
            "on_behalf": ctx.on_behalf_of_user_id,
            "run": run_id,
            "kind": kind,
            "subject_type": s.subject_type,
            "subject_id": s.subject_id,
            "client": s.client_id,
            "engagement": s.engagement_id,
            "work_item": s.work_item_id,
            "taxpayer": s.taxpayer_contact_id,
            "tax_year": s.tax_year,
            "flags": marked,
            "request": request_id,
        }
        for s in subjects
    ]
    async with tenant_connection(ctx) as conn:
        await conn.execute(_INSERT, rows)
        await conn.commit()
    return len(rows)


_RUN_READS = text(
    "SELECT run_id, occurred_at, on_behalf_of_user_id FROM access_events "
    "WHERE kind = :kind AND subject_type = :subject_type AND subject_id = :subject_id "
    "AND run_id IS NOT NULL AND occurred_at >= :since ORDER BY occurred_at DESC LIMIT :limit"
)


@dataclass(frozen=True)
class RunRead:
    """One agent run's read of a subject: the run, when, and on whose behalf."""

    run_id: UUID
    occurred_at: datetime
    on_behalf_of_user_id: UUID | None


async def run_reads(
    session: AsyncSession,
    kind: str,
    subject_type: str,
    subject_id: UUID,
    since: datetime,
    limit: int = 200,
) -> list[RunRead]:
    """The active tenant's agent-run reads of one subject since `since`, newest first (T-01-T16:
    ADM-05's consent drawer). The caller has authorised the read of the subject."""
    rows = await session.execute(
        _RUN_READS,
        {
            "kind": kind,
            "subject_type": subject_type,
            "subject_id": subject_id,
            "since": since,
            "limit": limit,
        },
    )
    return [RunRead(r.run_id, r.occurred_at, r.on_behalf_of_user_id) for r in rows.all()]


async def ensure_partitions(today: date, months_ahead: int = 2) -> list[str]:
    """This month's and the next `months_ahead` months' partitions, created if missing through the
    reviewed definer. Monthly maintenance runs it; 0105 created October 2026 to March 2027."""
    first = today.replace(day=1)
    names: list[str] = []
    async with platform_transaction("access_events:partitions") as conn:
        for n in range(months_ahead + 1):
            month = date(
                first.year + (first.month - 1 + n) // 12, (first.month - 1 + n) % 12 + 1, 1
            )
            names.append(
                str(
                    (
                        await conn.execute(
                            text("SELECT access_events_partition(:month)"), {"month": month}
                        )
                    ).scalar_one()
                )
            )
    return names


__all__ = [
    "FLAGS",
    "AccessSubject",
    "UnknownAccessKind",
    "ensure_partitions",
    "record_reads",
    "register_access_kind",
]
