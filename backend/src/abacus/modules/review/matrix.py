"""The sign-off matrix and the review gate, G5 (P-04; SPEC-313; TASK-331).

For every registered reviewable on an engagement: its five levels (who signed, stale or not),
its open notes, and a status computed by code. G5 is met when there is at least one reviewable
and every one has its required levels signed on its current content and no open notes; the
blockers say what's missing. Code states; people decide.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.modules.engagements.api import GateFact, get_ref
from abacus.modules.identity.api import AuthContext, authorise, engagement_team
from abacus.modules.review.notes import open_note_counts
from abacus.modules.review.service import LevelState, sign_off_states
from abacus.modules.review.slots import REQUIRED_LEVELS, Reviewable, reviewables_of

RowStatus = Literal[
    "not_started", "needs_sign_off", "changed_after_signoff", "open_notes", "complete"
]


@dataclass(frozen=True)
class MatrixLevel:
    level: int
    name: str
    signed_by_name: str | None
    stale: bool
    required: bool


@dataclass(frozen=True)
class MatrixRow:
    target_type: str
    target_id: UUID
    code: str
    title: str
    levels: list[MatrixLevel]
    open_notes: int
    status: RowStatus
    missing: list[int]  # required levels not signed on the current content


@dataclass(frozen=True)
class Matrix:
    rows: list[MatrixRow]
    gate_met: bool
    blockers: list[str]


def row_status(r: Reviewable, states: list[LevelState], notes: int) -> tuple[RowStatus, list[int]]:
    current = {s.level for s in states if s.signed_by is not None and not s.stale}
    missing = [lv for lv in REQUIRED_LEVELS if lv not in current]
    if notes:
        return "open_notes", missing
    if any(s.stale for s in states):
        return "changed_after_signoff", missing
    if missing:
        return ("needs_sign_off" if r.has_content else "not_started"), missing
    return "complete", missing


async def _rows(
    tenant: TenantContext, engagement_id: UUID
) -> list[tuple[Reviewable, list[LevelState], int]]:
    found = await reviewables_of(tenant, engagement_id)
    notes = await open_note_counts(tenant, engagement_id)
    out: list[tuple[Reviewable, list[LevelState], int]] = []
    for target_type in sorted({r.target_type for r in found}):
        mine = [r for r in found if r.target_type == target_type]
        states = await sign_off_states(
            tenant,
            target_type,
            [r.target_id for r in mine],
            {r.target_id: r.content_hash for r in mine},
        )
        out.extend((r, states[r.target_id], notes.get(r.target_id, 0)) for r in mine)
    return out


def blockers_of(rows: list[tuple[Reviewable, list[LevelState], int]]) -> list[str]:
    if not rows:
        return ["nothing_to_review"]
    blockers: list[str] = []
    for r, states, notes in rows:
        _, missing = row_status(r, states, notes)
        if notes:
            blockers.append(f"open_notes:{r.code}:{notes}")
        if any(s.stale for s in states):
            blockers.append(f"changed_after_signoff:{r.code}")
        blockers.extend(f"unsigned:{r.code}:L{lv}" for lv in missing)
    return blockers


async def review_gate(tenant: TenantContext, engagement_id: UUID) -> GateFact:
    """G5: review complete (registered with engagements in api.py)."""
    try:
        blockers = blockers_of(await _rows(tenant, engagement_id))
    except Exception:  # a provider that fails leaves the gate unmet, never met
        return GateFact(met=False, blockers=("review_unavailable",))
    return GateFact(met=not blockers, blockers=tuple(blockers))


async def matrix_for(ctx: AuthContext, engagement_id: UUID) -> Matrix:
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "workpaper.read", ref.resource())
    rows = await _rows(ctx.tenant, engagement_id)
    names = {m.user_id: m.display_name for m in await engagement_team(ctx, engagement_id)}
    out: list[MatrixRow] = []
    for r, states, notes in rows:
        status, missing = row_status(r, states, notes)
        out.append(
            MatrixRow(
                r.target_type,
                r.target_id,
                r.code,
                r.title,
                [
                    MatrixLevel(
                        s.level,
                        s.name,
                        names.get(s.signed_by, "Former member") if s.signed_by else None,
                        s.stale,
                        s.level in REQUIRED_LEVELS,
                    )
                    for s in states
                ],
                notes,
                status,
                missing,
            )
        )
    blockers = blockers_of(rows)
    return Matrix(out, not blockers, blockers)
