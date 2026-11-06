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
from typing import Any, Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.uow import OutboxEvent, Ref, Target, uow
from abacus.modules.identity.api import AuthContext
from abacus.modules.requests.answer_effect_slots import (
    EffectRequest,
    EffectResult,
    HandlerUnavailable,
    answer_effect_handler,
    rule_fingerprint,
)

JsonMap = Mapping[str, Any]  # Any: rules, conditions and answers are JSON
JsonRow = dict[str, Any]  # Any: an effect row as stored

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
        mapping = cast(Mapping[str, object], value)
        inner = mapping.get("value", mapping.get("answer"))
        return normalise(inner) if inner is not None else ""
    return str(value).strip().lower()


def shown(
    show_when: JsonMap | None,
    parent_value: object,
) -> bool:
    """A follow-up shows when its parent's answer equals `equals` (depth 1)."""
    if not show_when:
        return True
    return normalise(parent_value) == normalise(show_when.get("equals"))


def matching(
    rules: Sequence[JsonMap],
    value: object,
) -> list[JsonMap]:
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
                        "qn.source_template_version_id, qn.template_version_id, qn.created_by "
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
        await _fire(tenant, dict(row), question_id, answer_id, rule, template_version)


async def _fire(
    tenant: TenantContext,
    row: JsonMap,
    question_id: UUID,
    answer_id: UUID,
    rule: JsonMap,
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
        try:
            result = await handler(
                EffectRequest(
                    tenant_id=tenant.tenant_id,
                    questionnaire_id=row["questionnaire_id"],
                    question_id=question_id,
                    answer_id=answer_id,
                    rule_key=str(rule["key"]),
                    template_version_id=template_version,
                    evidence_version_id=await _uploaded_version(tenant, answer_id),
                    owner_user_id=row["created_by"],
                )
            )
        except HandlerUnavailable:
            result = None  # fail closed: pending_handler, the upload stays in the binder
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
                after=Ref(rule=rule_fingerprint(str(rule["key"])), pending=int(result is None)),
            )


async def _uploaded_version(tenant: TenantContext, answer_id: UUID) -> UUID | None:
    """An upload answer's evidence version (`{"evidence_version_id": …}`), if any."""
    async with tenant_session(tenant) as session:
        value = (
            await session.execute(
                text("SELECT value FROM answer_versions WHERE id = :a"), {"a": answer_id}
            )
        ).scalar()
    found = (
        cast(Mapping[str, object], value).get("evidence_version_id")
        if isinstance(value, Mapping)
        else None
    )
    return UUID(str(found)) if found else None


async def fire_staff_edit(
    ctx: AuthContext, questionnaire_id: UUID, fired: Sequence[JsonMap]
) -> None:
    """A staff edit made an existing answer trigger a new rule (T-03 §4.2): the same handlers,
    attributed to the editor, with no answer row. One row per (question, rule): a repeat of the
    same save writes nothing more."""
    tenant = ctx.tenant
    async with tenant_session(tenant) as session:
        head = (
            (
                await session.execute(
                    text(
                        "SELECT id AS questionnaire_id, created_by, "
                        "coalesce(source_template_version_id, template_version_id) AS tv "
                        "FROM questionnaires WHERE id = :q"
                    ),
                    {"q": questionnaire_id},
                )
            )
            .mappings()
            .one()
        )
        questions = {
            r["question_key"]: r["id"]
            for r in (
                await session.execute(
                    text("SELECT id, question_key FROM questions WHERE questionnaire_id = :q"),
                    {"q": questionnaire_id},
                )
            ).mappings()
        }
    for effect in fired:
        question_id = questions.get(str(effect["question_key"]))
        if question_id is None:
            continue
        rule_key, kind = str(effect["rule_key"]), str(effect["kind"])
        async with tenant_session(tenant) as session:
            done = (
                await session.execute(
                    text(
                        "SELECT 1 FROM answer_effects WHERE question_id = :q AND rule_key = :r "
                        "AND answer_id IS NULL"
                    ),
                    {"q": question_id, "r": rule_key},
                )
            ).scalar()
        if done:
            continue
        handler = answer_effect_handler(kind)
        result: EffectResult | None = None
        if handler is not None:
            try:
                result = await handler(
                    EffectRequest(
                        tenant_id=tenant.tenant_id,
                        questionnaire_id=questionnaire_id,
                        question_id=question_id,
                        answer_id=None,
                        rule_key=rule_key,
                        template_version_id=head["tv"],
                        owner_user_id=head["created_by"],
                    )
                )
            except HandlerUnavailable:
                result = None
        async with uow(tenant) as tx:
            await tx.session.execute(
                text(
                    "INSERT INTO answer_effects (tenant_id, question_id, rule_key, effect_kind, "
                    "target_type, target_id, actor_kind, actor_user_id, template_version_id) "
                    "VALUES (:t, :q, :rule, :kind, :tt, :tid, 'human', :by, :tv)"
                ),
                {
                    "t": tenant.tenant_id,
                    "q": question_id,
                    "rule": rule_key,
                    "kind": "pending_handler" if result is None else RESULT_KIND[kind],
                    "tt": None if result is None else result.target_type,
                    "tid": None if result is None else result.target_id,
                    "by": ctx.user_id,
                    "tv": head["tv"],
                },
            )
            tx.record(
                "answer_effect.recorded",
                target=Target("question", question_id),
                after=Ref(rule=rule_fingerprint(rule_key), pending=int(result is None)),
            )


async def effect_log(tenant: TenantContext, questionnaire_id: UUID) -> list[JsonRow]:
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
