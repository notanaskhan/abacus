"""A person's void of a wrong rule link (R-01 Story 2.2; TASK-1248; portal-pbc contract).

The sort (`drops.py`) links a decisively matched portal drop to its request as a provisional
`rule` fulfilment, which waits for a person (ADR-005). When it is wrong, a person with
`fulfilment.confirm` (the engagement partner, a manager or a senior; the agent is denied) voids it
with `wrong_request`, in one unit of work:

- requests stamps the fulfilment void (`fulfilment.voided`) and returns the request to `requested`
  when nothing else fulfils it;
- the version the link made is retired (`evidence_version_voids`): evidence reads, duplicate
  checks and gates leave it out, and the dropped file waits in the engagement inbox again, for a
  person to assign afresh (`sort_outcome` keeps `rule_linked`: it records what the sort did);
- `fulfilment.voided` and `inbox_file.sorted` go to the outbox (the gates recompute).

Only an unaccepted rule link is voidable: a version a person ever accepted, a link a person or the
agent made, or one already voided answers 409 `not_voidable`. The database refuses the same
(`fulfilments_void_only`, 0159). Here, not in requests, because the void touches the inbox file
too and evidence already depends on requests.
"""

from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from abacus.kernel.errors import DomainConflict
from abacus.kernel.uow import uow
from abacus.modules.engagements.api import get_ref, lock_ref
from abacus.modules.evidence.events import FulfilmentVoided, InboxFileSorted
from abacus.modules.evidence.repository import (
    ever_accepted,
    retire_voided_version,
    return_to_waiting,
)
from abacus.modules.identity.api import AuthContext, Forbidden, authorise, serving_request
from abacus.modules.requests.api import VoidedRuleLink, lock_rule_link, void_rule_link_in

ACTION = "fulfilment.confirm"


class NotVoidable(DomainConflict):
    """Only an unaccepted rule fulfilment is voided (R-01 Story 2.2)."""

    code: ClassVar[str] = "not_voidable"


def _person(ctx: AuthContext) -> None:
    """ADR-005, INV-1: a person, in a request they are making themself, never a support session."""
    if (
        not isinstance(ctx, AuthContext)  # pyright: ignore[reportUnnecessaryIsInstance] -- ADR-005 at runtime too
        or ctx.tenant.actor_kind != "human"
        or ctx.is_support
        or not serving_request()
    ):
        raise Forbidden(ACTION, "role")


async def check_void(ctx: AuthContext, engagement_id: UUID) -> None:
    """Who may void on this engagement, checked before an idempotent replay is answered."""
    _person(ctx)
    engagement = await get_ref(ctx, engagement_id)
    await authorise(ctx, ACTION, engagement.resource())


async def void_rule_link(
    ctx: AuthContext, engagement_id: UUID, fulfilment_id: UUID
) -> VoidedRuleLink:
    await check_void(ctx, engagement_id)
    refused = NotVoidable(facts={"fulfilment_id": str(fulfilment_id)})
    async with uow(ctx.tenant) as tx:
        engagement = await lock_ref(tx, engagement_id)
        await authorise(ctx, ACTION, engagement.resource())
        # The request item is locked first, as an accept locks it (security review).
        version = await lock_rule_link(
            tx, engagement_id=engagement_id, fulfilment_id=fulfilment_id
        )
        if version is None or await ever_accepted(tx.session, [version]):
            raise refused
        voided = await void_rule_link_in(
            tx, engagement_id=engagement_id, fulfilment_id=fulfilment_id, voided_by=ctx.user_id
        )
        if voided is None:
            raise refused
        await retire_voided_version(
            tx.session,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            version_id=voided.evidence_version_id,
            fulfilment_id=fulfilment_id,
            voided_by=ctx.user_id,
        )
        file_id = await return_to_waiting(tx.session, voided.evidence_version_id)
        tx.emit(
            FulfilmentVoided(
                engagement_id=engagement_id,
                fulfilment_id=fulfilment_id,
                request_item_id=voided.request_item_id,
                evidence_version_id=voided.evidence_version_id,
                inbox_file_id=file_id,
            )
        )
        if file_id is not None:
            tx.emit(InboxFileSorted(engagement_id=engagement_id, inbox_file_id=file_id))
    return voided


__all__ = ["NotVoidable", "check_void", "void_rule_link"]
