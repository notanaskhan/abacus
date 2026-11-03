"""AUD-17's re-review request and the work-item note bands (A-06-T14; A-06 §3 F7; DEC-2214).

- `request_re_review`: on a **stale** sign-off only (409 `not_stale` otherwise), a person asks
  its signer to look again. The request is audited and announced (`sign_off.re_review_requested`,
  C16 `sign_off_re_review` to the signer); the sign-off itself never changes (ADR-160 clause 3:
  staleness stays computed, a re-sign is a new row).
- `note_bands`: a work item's review notes in Open, Responded and Cleared bands (Northwind:
  2 + 1 + 11 = 14), under the same `visible()` rule as C3's note list.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.engagements.api import get_ref
from abacus.modules.identity.api import AuthContext, authorise
from abacus.modules.review.events import SignOffReReviewRequested
from abacus.modules.review.models import SignOff
from abacus.modules.review.slots import reviewable_facts

ACTION = "sign_off.request_re_review"


class NotStale(DomainConflict):
    """Only a stale sign-off can be sent back for re-review."""

    code = "not_stale"


async def request_re_review(ctx: AuthContext, sign_off_id: UUID) -> UUID:
    async with tenant_session(ctx.tenant) as session:
        row = await session.scalar(select(SignOff).where(SignOff.id == sign_off_id))
    if row is None:
        raise NotFound("sign_off")
    ref = await get_ref(ctx, row.engagement_id)
    await authorise(ctx, ACTION, ref.resource())
    facts = await reviewable_facts(ctx.tenant, row.target_type, row.target_id)
    if facts.content_hash == row.content_hash:
        raise NotStale(facts={"level": row.level})
    async with uow(ctx.tenant) as tx:
        tx.record(
            "sign_off.re_review_requested",
            target=Target("sign_off", sign_off_id),
            after=Ref(level=row.level),
        )
        tx.emit(
            SignOffReReviewRequested(
                sign_off_id=sign_off_id,
                engagement_id=row.engagement_id,
                target_type=row.target_type,
                target_id=row.target_id,
                level=row.level,
                signed_by=row.signed_by,
                requested_by=ctx.user_id,
            )
        )
    return sign_off_id


@dataclass(frozen=True)
class NoteBands:
    open: int
    responded: int
    cleared: int

    @property
    def total(self) -> int:
        return self.open + self.responded + self.cleared


def bands_of(counts: dict[str, int]) -> NoteBands:
    """C3 note counts by status as AUD-17's three bands (withdrawn notes are not shown)."""
    return NoteBands(
        open=counts.get("open", 0),
        responded=counts.get("responded", 0),
        cleared=counts.get("cleared", 0),
    )
