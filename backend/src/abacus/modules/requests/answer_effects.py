"""T-03-T06: the answer-effects engine (T-03 §3 F3; BND-03; DEC-2242).

Code evaluates every rule, never a model: a question's `show_when` and each effect rule's
`when_equals` compare the answer's normalised value with equality. `on_answered` hears C5's
`questionnaire.answered` (outbox, at-least-once) and, for each matching rule, writes one
`answer_effects` row first (unique per answer and rule: a replay writes nothing more) and then
calls the kind's handler through `register_answer_effect`'s slot. A kind with no handler is
recorded `pending_handler`, and the upload or answer stays where it is (fail closed). Effects are
the system's, attributed to the rule and the template version that published it; never the
agent's. `effect_log` is BND-03's read model (counts, banners, helpers).

Built-in handler: `create_request_item` (P-06's request lifecycle, created by the system with the
rule's provenance). N-04 registers `route_upload_to_notices`; C3 registers the review-point and
internal-review kinds.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.uow import OutboxEvent, Ref, Target, uow
from abacus.modules.requests.answer_effect_slots import (
    EffectRequest,
    EffectResult,
    answer_effect_handler,
)

_SYSTEM_ACTOR: Final = "answer_effects"
RESULT_KIND: Final = {
    "create_request_item": "request_item_created",
    "raise_review_point": "review_point_raised",
    "flag_internal_review": "internal_review_flagged",
    "route_upload_to_notices": "upload_routed_to_notices",
}


def normalise(value: object) -> str:
    """An answer as compared by rules: booleans as yes/no, everything else as trimmed text."""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, Mapping):
        inner = value.get("value", value.get("answer"))
        return normalise(inner) if inner is not None else ""
    return str(value).strip().lower()


def shown(show_when: Mapping[str, Any] | None, parent_value: object) -> bool:
    """A follow-up shows when its parent's answer equals `equals` (depth 1)."""
    if not show_when:
        return True
    return normalise(parent_value) == normalise(show_when.get("equals"))


def matching(rules: Sequence[Mapping[str, Any]], value: object) -> list[Mapping[str, Any]]:
    answer = normalise(value)
    return [r for r in rules if normalise(r.get("when_equals")) == answer]


async def on_answered(event: OutboxEvent) -> None:
    """`questionnaire.answered`: fire each matching rule once per answer (idempotent)."""
    tenant = TenantContext(event.tenant_id, "system", _SYSTEM_ACTOR)
    question_id = UUID(str(event.payload["question_id"]))
    answer_id = UUID(str(event.payload["answer_id"]))
    async with tenant_session(tenant) as session:
        row = (
            (
                await session.execute(
                    text(
                        "SELECT q.effect_rules, q.questionnaire_id, a.value, qn.engagement_id, "
                        "qn.source_template_version_id, qn.template_version_id "
                        "FROM questions q JOIN answer_versions a ON a.id = :a "
                        "JOIN questionnaires qn ON qn.id = q.questionnaire_id WHERE q.id = :q"
                    ),
                    {"a": answer_id, "q": question_id},
                )
            )
            .mappings()
            .first()
        )
    if row is None or not row["effect_rules"]:
        return
    template_version = row["source_template_version_id"] or row["template_version_id"]
    for rule in matching(row["effect_rules"], row["value"]):
        await _fire(tenant, row, question_id, answer_id, rule, template_version)


async def _fire(
    tenant: TenantContext,
    row: Mapping[str, Any],
    question_id: UUID,
    answer_id: UUID,
    rule: Mapping[str, Any],
    template_version: UUID | None,
) -> None:
    """One rule for one answer: skipped when already recorded (a replay); otherwise the handler
    runs (it is idempotent on the answer and rule) and one insert-only row records the effect
    with its target, or `pending_handler` when no module owns the kind."""
    kind = str(rule["kind"])
    async with tenant_session(tenant) as session:
        done = (
            await session.execute(
                text("SELECT 1 FROM answer_effects WHERE answer_id = :a AND rule_key = :rule"),
                {"a": answer_id, "rule": rule["key"]},
            )
        ).scalar()
    if done:
        return
    handler = answer_effect_handler(kind)
    result: EffectResult | None = None
    if handler is not None:
        result = await handler(
            EffectRequest(
                tenant_id=tenant.tenant_id,
                questionnaire_id=row["questionnaire_id"],
                question_id=question_id,
                answer_id=answer_id,
                rule_key=str(rule["key"]),
                template_version_id=template_version,
            )
        )
    async with uow(tenant) as tx:
        inserted = (
            await tx.session.execute(
                text(
                    "INSERT INTO answer_effects (tenant_id, answer_id, question_id, rule_key, "
                    "effect_kind, target_type, target_id, actor_kind, template_version_id) "
                    "VALUES (:t, :a, :q, :rule, :kind, :tt, :tid, 'system', :tv) "
                    "ON CONFLICT DO NOTHING RETURNING id"
                ),
                {
                    "t": tenant.tenant_id,
                    "a": answer_id,
                    "q": question_id,
                    "rule": rule["key"],
                    "kind": "pending_handler" if result is None else RESULT_KIND[kind],
                    "tt": None if result is None else result.target_type,
                    "tid": None if result is None else result.target_id,
                    "tv": template_version,
                },
            )
        ).scalar()
        if inserted is not None:
            tx.record(
                "answer_effect.recorded",
                target=Target("question", question_id),
                after=Ref(rule=str(rule["key"]), pending=int(result is None)),
            )


async def effect_log(tenant: TenantContext, questionnaire_id: UUID) -> list[dict[str, Any]]:
    """BND-03's effect log, oldest first (counts, banners and helpers read it)."""
    async with tenant_session(tenant) as session:
        return [
            dict(r)
            for r in (
                await session.execute(
                    text(
                        "SELECT e.id, e.question_id, e.rule_key, e.effect_kind, e.target_type, "
                        "e.target_id, e.actor_kind, e.created_at FROM answer_effects e "
                        "JOIN questions q ON q.id = e.question_id WHERE q.questionnaire_id = :q "
                        "ORDER BY e.created_at, e.id"
                    ),
                    {"q": questionnaire_id},
                )
            ).mappings()
        ]


SUBSCRIPTIONS = {"questionnaire.answered": on_answered}
