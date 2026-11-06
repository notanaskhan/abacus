"""T-03-T06: the requests module's own answer-effect handler (DEC-2242).

`create_request_item` adds a request item to the binder's engagement through P-06's request
lifecycle, created by the system with the rule's provenance (the template version's publisher is
the named creator, never the agent). The engine calls it once per (answer, rule): it records the
effect row right after, and skips a pair already recorded.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.requests.answer_effect_slots import (
    EffectRequest,
    EffectResult,
    HandlerUnavailable,
    register_answer_effect,
    rule_fingerprint,
)
from abacus.modules.requests.repository import request_list_for
from abacus.modules.requests.service import (
    _insert_item,  # pyright: ignore[reportPrivateUsage] -- the sibling module's own helper
)


@dataclass(frozen=True)
class EffectRule:
    """What another module's handler needs of the rule it acts on (T-03-T06)."""

    engagement_id: UUID
    work_item_id: UUID
    title: str


async def effect_rule(request: EffectRequest) -> EffectRule:
    tenant = TenantContext(request.tenant_id, "system", "answer_effects")
    async with tenant_session(tenant) as session:
        row = (
            (
                await session.execute(
                    text(
                        "SELECT qn.engagement_id, qn.work_item_id, q.effect_rules "
                        "FROM questions q "
                        "JOIN questionnaires qn ON qn.id = q.questionnaire_id WHERE q.id = :q"
                    ),
                    {"q": request.question_id},
                )
            )
            .mappings()
            .one()
        )
    if row["engagement_id"] is None or row["work_item_id"] is None:
        raise HandlerUnavailable  # a template-owned question has no return to raise it on
    rule = next(r for r in row["effect_rules"] if r["key"] == request.rule_key)
    return EffectRule(row["engagement_id"], row["work_item_id"], str(rule["title"])[:500])


async def create_request_item(request: EffectRequest) -> EffectResult:
    tenant = TenantContext(request.tenant_id, "system", "answer_effects")
    async with tenant_session(tenant) as session:
        row = (
            (
                await session.execute(
                    text(
                        "SELECT qn.engagement_id, q.effect_rules, coalesce(tv.published_by, "
                        "qn.created_by) AS creator FROM questions q "
                        "JOIN questionnaires qn ON qn.id = q.questionnaire_id "
                        "LEFT JOIN questionnaire_template_versions tv "
                        "ON tv.id = coalesce(qn.source_template_version_id, "
                        "qn.template_version_id) "
                        "WHERE q.id = :q"
                    ),
                    {"q": request.question_id},
                )
            )
            .mappings()
            .one()
        )
    rule = next(r for r in row["effect_rules"] if r["key"] == request.rule_key)
    async with uow(tenant) as tx:
        list_id, _ = await request_list_for(tx.session, request.tenant_id, row["engagement_id"])
        item = await _insert_item(
            tx,
            item_id=uuid4(),
            tenant_id=request.tenant_id,
            engagement_id=row["engagement_id"],
            request_list_id=list_id,
            description=str(rule["title"])[:2000],
            audit_area="organizer",
            created_by=row["creator"],
        )
        tx.record(
            "request_item.created_by_answer_effect",
            target=Target("request_item", item.id),
            after=Ref(rule=rule_fingerprint(request.rule_key)),
        )
    return EffectResult("request_item", item.id)


def register() -> None:
    register_answer_effect("create_request_item", create_request_item)
