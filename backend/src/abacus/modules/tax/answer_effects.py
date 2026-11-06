"""T-03-T06: an organizer answer raises a review point or flags internal review (T-03 US-3.2;
DEC-2352). The tax module owns these two effect kinds because it reaches both C5's slot and C3's
issues, which don't import each other. The issue sits on the return; a person resolves it.
"""

from __future__ import annotations

from abacus.kernel.db import TenantContext
from abacus.modules.requests.api import (
    EffectRequest,
    EffectResult,
    effect_rule,
    register_answer_effect,
)
from abacus.modules.review.api import record_rule_issue


async def _issue(
    request: EffectRequest, *, priority: str, blocks: tuple[str, ...]
) -> EffectResult:
    rule = await effect_rule(request)
    issue_id = await record_rule_issue(
        TenantContext(request.tenant_id, "system", "answer_effects"),
        engagement_id=rule.engagement_id,
        work_item_id=rule.work_item_id,
        record_type="tax_return",
        record_id=rule.work_item_id,
        kind="review_point",
        priority=priority,
        title=rule.title,
        source_ref=f"answer_effect:{request.question_id.hex}:{request.rule_key}",
        blocks=blocks,
    )
    return EffectResult("issue", issue_id)


async def raise_review_point(request: EffectRequest) -> EffectResult:
    return await _issue(request, priority="normal", blocks=())


async def flag_internal_review(request: EffectRequest) -> EffectResult:
    """The flag holds final approval until a person clears it."""
    return await _issue(request, priority="high", blocks=("final_approval",))


def register() -> None:
    register_answer_effect("raise_review_point", raise_review_point)
    register_answer_effect("flag_internal_review", flag_internal_review)
