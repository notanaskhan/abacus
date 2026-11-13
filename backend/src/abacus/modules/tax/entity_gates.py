"""The entity return's gate kinds and the facts its guards read (T-05-T52; TASK-7903; T-05 F10,
F12; TXP-00, TXP-10; DEC-4905). Amber. Code only: every check reads stored state, never a model.

Five gate kinds (P-04's `register_gate_kind`, engagement-level: each holds when it holds for every
entity return on the engagement, i.e. every return whose form has a workbook; an engagement with
no entity return meets them):

- `tax_mapping_complete`: no account of the newest trial balance is unmapped (C9's mapped TB).
- `tax_allocation_approved`: the newest allocation structure version is approved (an L3 sign-off,
  T-05-T41).
- `tax_fix_settled`: no workbook fix proposal awaits a person's decision (T-05-T50).
- `tax_memo_approved`: the preparer memo's newest event is `approved` (L2) and the memo is not
  stale since (T-05-T54 writes the events).
- `tax_run_questions_answered`: no run question is open on the return's live runs (the §706(d)
  convention, consent).

The same facts feed the final-approval guards (T-05-T53) per return.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.tax.workbook_service import sheets_of

MAPPING: Final = "tax_mapping_complete"
ALLOCATION: Final = "tax_allocation_approved"
FIX: Final = "tax_fix_settled"
MEMO: Final = "tax_memo_approved"
RUN_QUESTION: Final = "tax_run_questions_answered"
GATE_KINDS: Final = (MAPPING, ALLOCATION, FIX, MEMO, RUN_QUESTION)

_RETURNS: Final = text("SELECT work_item_id, form FROM tax_returns WHERE engagement_id = :e")
_MEMO_EVENT: Final = text(
    "SELECT e.event FROM preparer_memo_events e JOIN preparer_memos m ON m.id = e.memo_id "
    "WHERE m.work_item_id = :r AND e.event IN ('drafted', 'regenerated', 'section_edited', "
    "'adopted', 'approved', 'went_stale') ORDER BY e.created_at DESC, e.id DESC LIMIT 1"
)


async def entity_returns(tenant: TenantContext, engagement_id: UUID) -> list[UUID]:
    """The engagement's returns whose form has a workbook."""
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_RETURNS, {"e": engagement_id})).all()
    return [UUID(str(r.work_item_id)) for r in rows if sheets_of(str(r.form))]


async def engagement_of_return(tenant: TenantContext, return_id: UUID) -> UUID | None:
    async with tenant_session(tenant) as session:
        found = await session.scalar(
            text("SELECT engagement_id FROM tax_returns WHERE work_item_id = :r"), {"r": return_id}
        )
    return None if found is None else UUID(str(found))


# --- facts, per return -------------------------------------------------------------------------


async def unmapped_accounts(tenant: TenantContext, engagement_id: UUID) -> int | None:
    """Accounts of the newest trial balance without a form line; None with no trial balance."""
    from abacus.modules.ledger.api import engagement_trial_balances, mapped_trial_balance

    balances = await engagement_trial_balances(tenant, engagement_id)
    if not balances:
        return None
    newest = max(balances, key=lambda b: (b.period_end, b.current_version_no))
    mapped = await mapped_trial_balance(tenant, engagement_id, newest.id)
    return None if mapped is None else int(mapped.unmapped)


async def allocation_approved(tenant: TenantContext, return_id: UUID) -> bool:
    from abacus.modules.tax.allocation_structure import versions

    found = await versions(tenant, return_id)
    return bool(found) and found[0].status == "approved"


async def memo_status(tenant: TenantContext, return_id: UUID) -> str | None:
    """The memo's newest lifecycle event (`approved`, `went_stale`, …) or None without a memo."""
    async with tenant_session(tenant) as session:
        found = await session.scalar(_MEMO_EVENT, {"r": return_id})
    return None if found is None else str(found)


async def open_questions(tenant: TenantContext, return_id: UUID) -> int:
    from abacus.modules.agents.api import open_question_count

    return await open_question_count(tenant, f"tax_return:{return_id}")


async def pending_fixes(tenant: TenantContext, engagement_id: UUID) -> int:
    from abacus.modules.agents.api import pending_proposal_count
    from abacus.modules.tax.workbook_fix import KIND

    return await pending_proposal_count(tenant, engagement_id, KIND)


# --- the gate checks (engagement-level) ---------------------------------------------------------


def _every(
    check: Callable[[TenantContext, UUID], Awaitable[bool]],
) -> Callable[[TenantContext, UUID], Awaitable[bool]]:
    async def gate(tenant: TenantContext, engagement_id: UUID) -> bool:
        for return_id in await entity_returns(tenant, engagement_id):
            if not await check(tenant, return_id):
                return False
        return True

    gate.__qualname__ = f"gate_{check.__name__}"
    return gate


async def mapping_complete(tenant: TenantContext, engagement_id: UUID) -> bool:
    if not await entity_returns(tenant, engagement_id):
        return True
    return await unmapped_accounts(tenant, engagement_id) == 0


async def fix_settled(tenant: TenantContext, engagement_id: UUID) -> bool:
    if not await entity_returns(tenant, engagement_id):
        return True
    return await pending_fixes(tenant, engagement_id) == 0


async def _memo_approved(tenant: TenantContext, return_id: UUID) -> bool:
    return await memo_status(tenant, return_id) == "approved"


async def _questions_answered(tenant: TenantContext, return_id: UUID) -> bool:
    return await open_questions(tenant, return_id) == 0


allocation_gate: Final = _every(allocation_approved)
memo_gate: Final = _every(_memo_approved)
run_question_gate: Final = _every(_questions_answered)


def register() -> None:
    """At the tax api's import."""
    from abacus.modules.review.api import register_gate_kind

    register_gate_kind(MAPPING, mapping_complete)
    register_gate_kind(ALLOCATION, allocation_gate)
    register_gate_kind(FIX, fix_settled)
    register_gate_kind(MEMO, memo_gate)
    register_gate_kind(RUN_QUESTION, run_question_gate)


__all__ = [
    "ALLOCATION",
    "FIX",
    "GATE_KINDS",
    "MAPPING",
    "MEMO",
    "RUN_QUESTION",
    "allocation_approved",
    "allocation_gate",
    "engagement_of_return",
    "entity_returns",
    "fix_settled",
    "mapping_complete",
    "memo_gate",
    "memo_status",
    "open_questions",
    "pending_fixes",
    "register",
    "run_question_gate",
    "unmapped_accounts",
]
