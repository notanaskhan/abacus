"""Sign-offs, the review grammar's first engine (P-04; ADR-136; SPEC-308; TASK-319).

Levels: L1 preparer, L2 reviewer, L3 manager, L4 partner, L5 EQR. Each level is its own matrix
action, so who may sign at which level lives in the permission matrix. A sign-off records the
content hash it approved; when the target's content changes, the sign-off is stale (shown, never
deleted). L2 and above need a current L1, and the L1 signer can't sign L2 (segregation).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid
from abacus.kernel.uow import Ref, Target, UnitOfWork
from abacus.modules.identity.api import AuthContext, Resource, authorise
from abacus.modules.review.models import SignOff
from abacus.modules.review.repository import (
    insert_sign_off,
    note_events_of,
    notes_of_target,
    sign_offs_of,
    stale_sign_offs,
)

LEVELS: Final = {1: "preparer", 2: "reviewer", 3: "manager", 4: "partner", 5: "eqr"}
_ACTIONS: Final = {
    1: "sign_off.prepare",
    2: "sign_off.review",
    3: "sign_off.manager",
    4: "sign_off.partner",
    5: "sign_off.eqr",
}


class SignOffInvalid(DomainInvalid):
    code = "sign_off_invalid"


class NotPrepared(DomainConflict):
    """L2 and above need a current preparer sign-off."""

    code = "not_prepared"


class PreparerCannotReview(DomainConflict):
    code = "preparer_cannot_review"


class NotesOpen(DomainConflict):
    """A reviewer signs (L2 and above) only when the target's notes are cleared."""

    code = "review_notes_open"


class AlreadySigned(DomainConflict):
    """The same level is already signed on this exact content."""

    code = "already_signed"


@dataclass(frozen=True)
class LevelState:
    level: int
    name: str
    signed_by: UUID | None
    signed_at: datetime | None
    stale: bool


def states_of(rows: Sequence[SignOff], current_hash: str) -> list[LevelState]:
    """Per level, the newest sign-off and whether the content has changed since (by code)."""
    out: list[LevelState] = []
    for level, name in LEVELS.items():
        newest = next((r for r in rows if r.level == level), None)
        out.append(
            LevelState(
                level,
                name,
                newest.signed_by if newest else None,
                newest.created_at if newest else None,
                newest is not None and newest.content_hash != current_hash,
            )
        )
    return out


async def sign_off_states(
    tenant: TenantContext, target_type: str, target_ids: Sequence[UUID], hashes: dict[UUID, str]
) -> dict[UUID, list[LevelState]]:
    """For callers authorised on the targets' engagement."""
    async with tenant_session(tenant) as session:
        rows = await sign_offs_of(session, target_type, target_ids)
    return {
        tid: states_of([r for r in rows if r.target_id == tid], hashes[tid]) for tid in target_ids
    }


@dataclass(frozen=True)
class StaleSignOff:
    """A sign-off whose target changed since (P-04-T14): shown struck, never updated."""

    target_id: UUID
    level: int
    signed_by: UUID
    signed_at: datetime
    signed_hash: str
    current_hash: str


async def stale_of(
    tenant: TenantContext, target_type: str, hashes: dict[UUID, str]
) -> list[StaleSignOff]:
    """The computed staleness query: each target's newest sign-off per level that no longer
    matches the target's current hash. For callers authorised on the targets' engagement."""
    async with tenant_session(tenant) as session:
        rows = await stale_sign_offs(session, target_type, hashes)
    return [
        StaleSignOff(
            r.target_id, r.level, r.signed_by, r.created_at, r.content_hash, hashes[r.target_id]
        )
        for r in rows
    ]


async def _open_notes(tx: UnitOfWork, target_id: UUID) -> bool:
    notes = await notes_of_target(tx.session, target_id)
    events = await note_events_of(tx.session, [n.id for n in notes])
    for n in notes:
        mine = [e for e in events if e.note_id == n.id]
        if not mine or mine[-1].kind != "cleared":
            return True
    return False


async def record_sign_off(
    tx: UnitOfWork,
    ctx: AuthContext,
    resource: Resource,
    engagement_id: UUID,
    target_type: str,
    target_id: UUID,
    level: int,
    content_hash: str,
) -> None:
    """Inside the owner's unit of work (the owner has locked the target and computed the hash)."""
    if level not in LEVELS:
        raise SignOffInvalid("level")
    await authorise(ctx, _ACTIONS[level], resource)
    current = states_of(await sign_offs_of(tx.session, target_type, [target_id]), content_hash)
    mine = current[level - 1]
    if mine.signed_by is not None and not mine.stale and mine.signed_by == ctx.user_id:
        raise AlreadySigned(str(level))
    if level > 1 and await _open_notes(tx, target_id):
        raise NotesOpen(str(target_id))
    if level > 1:
        preparer = current[0]
        if preparer.signed_by is None or preparer.stale:
            raise NotPrepared(str(target_id))
        if level == 2 and preparer.signed_by == ctx.user_id:
            raise PreparerCannotReview(str(target_id))
    await insert_sign_off(
        tx.session,
        tenant_id=ctx.tenant_id,
        engagement_id=engagement_id,
        target_type=target_type,
        target_id=target_id,
        level=level,
        content_hash=content_hash,
        signed_by=ctx.user_id,
    )
    tx.record(
        "sign_off.recorded",
        target=Target(target_type, target_id),
        after=Ref(level=level, content_hash=content_hash),
    )
