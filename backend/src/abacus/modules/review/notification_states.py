"""What review's notification subjects say now (P-04-T26; `kernel.subject_states`; DEC-605).

For the drawer's read-time facts (codes, counts and ids only) and its Approvals tab: a decision
card waits on its reserved person (or, with none named, on whoever reads it in the role) while it
is awaiting the role; a note waits on its assignee while it is open or answered; a sign-off waits
on its signer while it is the newest at its level and stale (the target's hash moved). Reads run
under the reader's own row-level security; the drawer re-checks walls itself.
"""

from __future__ import annotations

from typing import Final
from uuid import UUID

from sqlalchemy import select

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.subject_states import SubjectState, register_subject_state
from abacus.modules.review.models import SignOff
from abacus.modules.review.repository import get_card, get_note
from abacus.modules.review.slots import UnregisteredKind, reviewable_facts

_OPEN_NOTE: Final = frozenset({"open", "responded"})


async def card_state(tenant: TenantContext, user_id: UUID, card_id: UUID) -> SubjectState | None:
    async with tenant_session(tenant) as session:
        card = await get_card(session, card_id)
    if card is None:
        return None
    waiting = card.status == "awaiting_role" and card.reserved_user_id in (None, user_id)
    return SubjectState(
        pending=waiting,
        facts={"card_kind": card.kind, "status": card.status, "version_no": card.version_no},
    )


async def note_state(tenant: TenantContext, user_id: UUID, note_id: UUID) -> SubjectState | None:
    async with tenant_session(tenant) as session:
        note = await get_note(session, note_id)
    if note is None:
        return None
    mine = note.assignee_user_id == user_id or (
        note.assignee_user_id is None and note.raised_by != user_id
    )
    return SubjectState(
        pending=note.status in _OPEN_NOTE and mine,
        facts={"status": note.status, "target_type": note.target_type},
    )


async def sign_off_state(
    tenant: TenantContext, user_id: UUID, sign_off_id: UUID
) -> SubjectState | None:
    async with tenant_session(tenant) as session:
        row = await session.get(SignOff, sign_off_id)
        if row is None:
            return None
        newer = (
            await session.execute(
                select(SignOff.id)
                .where(
                    SignOff.target_type == row.target_type,
                    SignOff.target_id == row.target_id,
                    SignOff.level == row.level,
                    SignOff.created_at > row.created_at,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
    stale = False
    if newer is None and row.signed_by == user_id:
        try:
            facts = await reviewable_facts(tenant, row.target_type, row.target_id)
        except (NotFound, UnregisteredKind):
            facts = None
        stale = facts is not None and facts.content_hash != row.content_hash
    return SubjectState(
        pending=stale,
        facts={"level": row.level, "target_type": row.target_type},
    )


def register_notification_states() -> None:
    register_subject_state("decision_card", card_state)
    register_subject_state("reviewable_note", note_state)
    register_subject_state("sign_off", sign_off_state)
