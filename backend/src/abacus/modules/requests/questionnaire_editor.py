"""T-03-T05: the organizer editor service (BND-03; T-03 §3 F1; C5 additive; DEC-2241).

- **Read.** A questionnaire's sections and questions in display order with each answer's
  summary, whether it is answered (type locked, retire not delete), its applied effects and the
  rail's counts ("Answered 8 of 9", conditional follow-ups, review points raised).
- **Save.** The whole edited structure in one unit of work against `If-Match` (the
  questionnaire's `row_version`): 412 `stale_version` when it moved. A type change on an answered
  question is 409 `question_answered`; a missing existing question is retired (never deleted, so
  every answer keeps its question). `dry_run` returns the client-visible changes and the effect
  rules that would fire, and writes nothing.
- **Walls and owners (DEC-2370).** A binder's organizer is read and saved against its engagement,
  not the firm; a template's is a template action, and only a draft saves.
- **Client preview.** The portal serializer's projection only (`client_wording`, `help_text`,
  type, choices, amount parts, required): no `internal_helper`, effect rule or tag can reach it.

Editor types map onto the stored types: `amount` is `amount_group`, `text` is `long_text`.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any, Final
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    authorise,
    engagement_resource,
    names_of,
)

READ: Final = "questionnaire.read"
EDIT: Final = "questionnaire.edit"
TEMPLATE_READ: Final = "questionnaire_template.read"
TEMPLATE_DRAFT: Final = "questionnaire_template.draft"
TO_STORED: Final = {"amount": "amount_group", "text": "long_text"}
TO_EDITOR: Final = {v: k for k, v in TO_STORED.items()}
CLIENT_FIELDS: Final = ("key", "type", "client_wording", "help_text", "choices", "amount_parts")


class StaleVersion(DomainConflict):
    """The organizer moved on since If-Match (409 `stale_version`, DEC-2241)."""

    code = "stale_version"


class QuestionAnswered(DomainConflict):
    """An answered question keeps its type (retire it and add a new one)."""

    code = "question_answered"


class LogicInvalid(DomainInvalid):
    """A follow-up names a parent that is not in the organizer."""

    code = "logic_invalid"


class VersionPublished(DomainConflict):
    """A published template version never changes; draft the next one."""

    code = "version_published"


@dataclass(frozen=True)
class TemplateRef:
    template_id: UUID
    name: str
    version: int
    version_id: UUID
    applies_to_tax_year: int | None
    status: str | None
    from_year: int | None  # a draft's banner names the year of the version it came from


@dataclass(frozen=True)
class EditorQuestion:
    id: UUID
    key: str
    section_key: str
    parent_key: str | None
    position: int
    type: str
    client_wording: str
    help_text: str | None
    internal_helper: str | None
    required: bool
    show_when: dict[str, Any] | None  # Any: JSON from the database or the document
    choices: list[str]
    amount_parts: list[str]
    effect_rules: list[dict[str, Any]]  # Any: JSON from the database or the document
    answer_value: Any  # Any: JSON from the database or the document
    answered_on: date | None
    answered_by: UUID | None
    answer_id: UUID | None = None
    answered_by_name: str | None = None
    effects: list[dict[str, Any]] = field(  # Any: JSON from the database
        default_factory=list[dict[str, Any]]  # Any: JSON from the database
    )  # Any: JSON from the database or the document

    @property
    def answered(self) -> bool:
        return self.answer_value is not None


@dataclass(frozen=True)
class Editor:
    id: UUID
    owner_kind: str
    title: str
    work_item_id: UUID | None
    sections: tuple[tuple[UUID, str, str, int], ...]  # id, key, title, position
    questions: tuple[EditorQuestion, ...]
    row_version: int
    binder_id: UUID | None = None
    template: TemplateRef | None = None

    def banner(self) -> str | None:
        """Template mode: "Editing template 1040 organizer v6 — changes apply to TY2026 …"."""
        t = self.template
        if self.owner_kind != "template_version" or t is None:
            return None
        year = t.applies_to_tax_year or t.from_year
        tail = f" — changes apply to TY{year} binders" if year else ""
        return f"Editing template {t.name} v{t.version}{tail}"

    def counts(self) -> dict[str, Any]:  # Any: JSON from the database or the document
        live = self.questions
        answered = [q for q in live if q.answered]
        effects = [e for q in live for e in q.effects]
        last = max(answered, key=lambda q: q.answered_on or date.min, default=None)
        return {
            "questions": len(live),
            "answered": len(answered),
            "conditional_follow_ups": sum(1 for q in live if q.parent_key),
            "review_points_raised": sum(1 for e in effects if e["kind"] == "review_point_raised"),
            "requests_created": sum(1 for e in effects if e["kind"] == "request_item_created"),
            "last_answer_on": last.answered_on if last else None,
            "last_answer_by": last.answered_by if last else None,
        }


async def _template_ref(
    session: AsyncSession, questionnaire_id: UUID, owner_kind: str, version_id: UUID | None
) -> TemplateRef | None:
    """A template's own questionnaire finds its version by owner; a binder's by what it came
    from."""
    own = owner_kind == "template_version"
    if not own and version_id is None:
        return None
    row = (
        await session.execute(
            text(
                "SELECT v.id, v.version, v.status, v.applies_to_tax_year, t.id AS template_id, "
                "t.name, f.applies_to_tax_year AS from_year "
                "FROM questionnaire_template_versions v "
                "JOIN questionnaire_templates t ON t.id = v.template_id "
                "LEFT JOIN questionnaire_template_versions f "
                "ON f.id = v.drafted_from_version_id "
                "WHERE (v.questionnaire_id = :q AND :own) OR (v.id = :v AND NOT :own)"
            ),
            {"q": questionnaire_id, "v": version_id, "own": own},
        )
    ).first()
    if row is None:
        return None
    return TemplateRef(
        row.template_id,
        row.name,
        row.version,
        row.id,
        row.applies_to_tax_year,
        row.status,
        row.from_year,
    )


async def editor(ctx: AuthContext, questionnaire_id: UUID) -> Editor:
    async with tenant_session(ctx.tenant) as session:
        head = (
            (
                await session.execute(
                    text(
                        "SELECT id, owner_kind, title, engagement_id, work_item_id, "
                        "request_list_id, template_version_id, row_version "
                        "FROM questionnaires WHERE id = :q"
                    ),
                    {"q": questionnaire_id},
                )
            )
            .mappings()
            .first()
        )
        if head is None:
            raise NotFound("questionnaire")
        # The wall: a binder's answers are its engagement's, whatever the firm-level gate passed.
        if head["owner_kind"] == "binder":
            base = await engagement_resource(ctx.tenant, head["engagement_id"])
            await authorise(ctx, READ, replace(base, work_item_id=head["work_item_id"]))
        else:
            await authorise(ctx, TEMPLATE_READ, Resource.firm(ctx.tenant_id))
        template = await _template_ref(
            session, questionnaire_id, head["owner_kind"], head["template_version_id"]
        )
        sections = (
            await session.execute(
                text(
                    "SELECT id, coalesce(key, 's' || position::text) AS key, name, position "
                    "FROM questionnaire_sections WHERE questionnaire_id = :q "
                    "AND retired_at IS NULL ORDER BY position"
                ),
                {"q": questionnaire_id},
            )
        ).all()
        rows = (
            (
                await session.execute(
                    text(
                        "SELECT q.*, coalesce(s.key, 's' || s.position::text) AS section_key, "
                        "p.question_key AS parent_key, a.id AS answer_id, "
                        "a.value AS answer_value, "
                        "a.answered_at::date AS answered_on, a.answered_by "
                        "FROM questions q JOIN questionnaire_sections s ON s.id = q.section_id "
                        "LEFT JOIN questions p ON p.id = q.conditional_on_question_id "
                        "LEFT JOIN LATERAL (SELECT id, value, answered_at, answered_by "
                        "FROM answer_versions WHERE question_id = q.id "
                        "ORDER BY version_no DESC LIMIT 1) a ON true "
                        "WHERE q.questionnaire_id = :q AND q.retired_at IS NULL "
                        "ORDER BY s.position, q.position"
                    ),
                    {"q": questionnaire_id},
                )
            )
            .mappings()
            .all()
        )
        effect_rows = (
            (
                await session.execute(
                    text(
                        "SELECT e.id, e.question_id, e.rule_key, e.effect_kind, e.target_type, "
                        "e.target_id, e.actor_kind, e.actor_user_id, e.created_at "
                        "FROM answer_effects e JOIN questions q ON q.id = e.question_id "
                        "WHERE q.questionnaire_id = :q ORDER BY e.created_at"
                    ),
                    {"q": questionnaire_id},
                )
            )
            .mappings()
            .all()
        )
        by_question: dict[
            UUID, list[dict[str, Any]]  # Any: JSON from the database
        ] = {}  # Any: JSON from the database or the document
        for e in effect_rows:
            by_question.setdefault(e["question_id"], []).append(
                {
                    "id": e["id"],
                    "rule_key": e["rule_key"],
                    "kind": e["effect_kind"],
                    "actor_kind": e["actor_kind"],
                    "actor_user_id": e["actor_user_id"],
                    "target_type": e["target_type"],
                    "target_id": e["target_id"],
                    "at": e["created_at"],
                }
            )
        names = await names_of(
            [r["answered_by"] for r in rows if r["answered_by"]]
            + [
                e["actor_user_id"]
                for effects in by_question.values()
                for e in effects
                if e["actor_user_id"]
            ]
        )
        for effects in by_question.values():
            for e in effects:
                e["actor_name"] = names.get(e["actor_user_id"]) if e["actor_user_id"] else None
        questions = tuple(
            EditorQuestion(
                id=r["id"],
                key=r["question_key"],
                section_key=r["section_key"],
                parent_key=r["parent_key"],
                position=r["position"],
                type=str(TO_EDITOR.get(r["type"]) or r["type"]),
                client_wording=r["client_wording"],
                help_text=r["help_text"],
                internal_helper=r["internal_helper"],
                required=r["required"],
                show_when=r["show_when"],
                choices=list(r["choices"] or []),
                amount_parts=list(r["amount_parts"] or []),
                effect_rules=list(r["effect_rules"] or []),
                answer_value=r["answer_value"],
                answered_on=r["answered_on"],
                answered_by=r["answered_by"],
                answer_id=r["answer_id"],
                answered_by_name=names.get(r["answered_by"]) if r["answered_by"] else None,
                effects=by_question.get(r["id"], []),
            )
            for r in rows
        )
    return Editor(
        head["id"],
        head["owner_kind"],
        head["title"],
        head["work_item_id"],
        tuple((s.id, s.key, s.name, s.position) for s in sections),
        questions,
        head["row_version"],
        head["request_list_id"],
        template,
    )


async def for_binder(ctx: AuthContext, binder_id: UUID) -> Editor | None:
    """BND-02's Questions tab: the binder's organizer, against its engagement."""
    async with tenant_session(ctx.tenant) as session:
        binder = (
            await session.execute(
                text("SELECT engagement_id, work_item_id FROM request_lists WHERE id = :b"),
                {"b": binder_id},
            )
        ).first()
        if binder is None:
            raise NotFound("request_list")
        base = await engagement_resource(ctx.tenant, binder.engagement_id)
        await authorise(ctx, READ, replace(base, work_item_id=binder.work_item_id))
        found = (
            await session.execute(
                text(
                    "SELECT id FROM questionnaires WHERE request_list_id = :b "
                    "AND kind = 'organizer' ORDER BY created_at DESC LIMIT 1"
                ),
                {"b": binder_id},
            )
        ).scalar_one_or_none()
    return None if found is None else await editor(ctx, found)


def client_view(
    q: EditorQuestion | dict[str, Any],  # Any: JSON from the database
) -> dict[str, Any]:  # Any: JSON from the database or the document
    """The portal serializer's projection: client fields only (no helper, rule or tag)."""
    src = q if isinstance(q, dict) else vars(q)
    return {k: src.get(k) for k in CLIENT_FIELDS}


def changes(
    current: Editor,
    proposed: Sequence[dict[str, Any]],  # Any: JSON from the database
) -> list[dict[str, Any]]:  # Any: JSON from the database or the document
    """Client-visible changes by question key, in proposed order."""
    by_key = {q.key: q for q in current.questions}
    out: list[dict[str, Any]] = []  # Any: JSON from the database or the document
    seen: set[str] = set()
    for position, q in enumerate(proposed):
        seen.add(q["key"])
        old = by_key.get(q["key"])
        if old is None:
            out.append({"question_key": q["key"], "kind": "added", "after": q["client_wording"]})
            continue
        if old.client_wording != q["client_wording"]:
            out.append(
                {
                    "question_key": q["key"],
                    "kind": "wording",
                    "before": old.client_wording,
                    "after": q["client_wording"],
                }
            )
        if old.required != q.get("required", False):
            out.append({"question_key": q["key"], "kind": "required"})
        if (old.show_when or None) != (q.get("show_when") or None):
            out.append({"question_key": q["key"], "kind": "logic"})
        if old.position != position:
            out.append({"question_key": q["key"], "kind": "reordered"})
    out.extend(
        {"question_key": k, "kind": "retired", "before": by_key[k].client_wording}
        for k in by_key
        if k not in seen
    )
    return out


def effects_to_fire(
    current: Editor,
    proposed: Sequence[dict[str, Any]],  # Any: JSON from the database
) -> list[dict[str, Any]]:  # Any: JSON from the database or the document
    """Rules new on an already-answered question fire on save (attributed to the editor)."""
    by_key = {q.key: q for q in current.questions}
    out: list[dict[str, Any]] = []  # Any: JSON from the database or the document
    for q in proposed:
        old = by_key.get(q["key"])
        if old is None or not old.answered:
            continue
        known = {r.get("key") for r in old.effect_rules}
        out.extend(
            {
                "question_key": q["key"],
                "rule_key": r["key"],
                "kind": r["kind"],
                "title": r["title"],
            }
            for r in q.get("effect_rules", [])
            if r.get("key") not in known
        )
    return out


async def _may_edit(ctx: AuthContext, current: Editor) -> None:
    """A person's act: on a binder, `questionnaire.edit` on its engagement; on a template, a draft
    with `questionnaire_template.draft`. A published version is frozen."""
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(EDIT, "role")
    if current.owner_kind == "template_version":
        await authorise(ctx, TEMPLATE_DRAFT, Resource.firm(ctx.tenant_id))
        if current.template is None or current.template.status != "draft":
            raise VersionPublished
        return
    async with tenant_session(ctx.tenant) as session:
        row = (
            await session.execute(
                text("SELECT engagement_id, work_item_id FROM questionnaires WHERE id = :q"),
                {"q": current.id},
            )
        ).one()
    base = await engagement_resource(ctx.tenant, row.engagement_id)
    await authorise(ctx, EDIT, replace(base, work_item_id=row.work_item_id))


async def save(
    ctx: AuthContext,
    questionnaire_id: UUID,
    if_match: int,
    *,
    sections: Sequence[dict[str, Any]],  # Any: JSON from the database or the document
    questions: Sequence[dict[str, Any]],  # Any: JSON from the database or the document
    dry_run: bool,
    change_summary: str | None = None,
) -> tuple[
    bool, list[dict[str, Any]], list[dict[str, Any]]  # Any: JSON from the database
]:  # Any: JSON from the database or the document
    """One atomic save, or a dry run that writes nothing."""
    current = await editor(ctx, questionnaire_id)
    await _may_edit(ctx, current)
    if current.row_version != if_match:
        raise StaleVersion(facts={"current": current.row_version})
    keys = {q["key"] for q in questions}
    if any(q.get("parent_key") and q["parent_key"] not in keys for q in questions):
        raise LogicInvalid
    by_key = {q.key: q for q in current.questions}
    for q in questions:
        old = by_key.get(q["key"])
        if old is not None and old.answered and old.type != q["type"]:
            raise QuestionAnswered(facts={"question_key": q["key"]})
    listed = changes(current, questions)
    fired = effects_to_fire(current, questions)
    if dry_run:
        return False, listed, fired
    async with uow(ctx.tenant) as tx:
        section_ids: dict[str, UUID] = {}
        for position, s in enumerate(sections):
            found = next((sid for sid, key, _, _ in current.sections if key == s["key"]), None)
            if found is None:
                found = (
                    await tx.session.execute(
                        text(
                            "INSERT INTO questionnaire_sections (tenant_id, questionnaire_id, "
                            "name, position, key) VALUES (:t, :q, :n, :p, :k) RETURNING id"
                        ),
                        {
                            "t": ctx.tenant_id,
                            "q": questionnaire_id,
                            "n": s["title"],
                            "p": position,
                            "k": s["key"],
                        },
                    )
                ).scalar_one()
            else:
                await tx.session.execute(
                    text(
                        "UPDATE questionnaire_sections SET name = :n, position = :p WHERE id = :id"
                    ),
                    {"n": s["title"], "p": position, "id": found},
                )
            section_ids[s["key"]] = found
        ids: dict[str, UUID] = {q.key: q.id for q in current.questions}
        for position, q in enumerate(questions):
            values = {
                "section": section_ids[q["section_key"]],
                "position": position,
                "type": TO_STORED.get(q["type"], q["type"]),
                "wording": q["client_wording"],
                "helper": q.get("internal_helper"),
                "required": q.get("required", False),
                "show_when": json.dumps(q.get("show_when")) if q.get("show_when") else None,
                "choices": json.dumps(q.get("choices") or []),
                "parts": json.dumps(q.get("amount_parts") or []),
                "rules": json.dumps(q.get("effect_rules") or []),
            }
            if q["key"] in ids:
                await tx.session.execute(
                    text(
                        "UPDATE questions SET section_id = :section, position = :position, "
                        "type = :type, client_wording = :wording, internal_helper = :helper, "
                        "required = :required, show_when = CAST(:show_when AS jsonb), "
                        "choices = CAST(:choices AS jsonb), amount_parts = CAST(:parts AS jsonb), "
                        "effect_rules = CAST(:rules AS jsonb) WHERE id = :id"
                    ),
                    {**values, "id": ids[q["key"]]},
                )
            else:
                ids[q["key"]] = (
                    await tx.session.execute(
                        text(
                            "INSERT INTO questions (tenant_id, questionnaire_id, section_id, "
                            "question_key, position, type, client_wording, internal_helper, "
                            "required, show_when, choices, amount_parts, effect_rules, origin, "
                            "created_by) VALUES (:t, :q, :section, :key, :position, :type, "
                            ":wording, :helper, :required, CAST(:show_when AS jsonb), "
                            "CAST(:choices AS jsonb), CAST(:parts AS jsonb), "
                            "CAST(:rules AS jsonb), 'team', :by) RETURNING id"
                        ),
                        {
                            **values,
                            "t": ctx.tenant_id,
                            "q": questionnaire_id,
                            "key": q["key"],
                            "by": ctx.user_id,
                        },
                    )
                ).scalar_one()
        for q in questions:
            if q.get("parent_key"):
                await tx.session.execute(
                    text("UPDATE questions SET conditional_on_question_id = :p WHERE id = :id"),
                    {"p": ids[q["parent_key"]], "id": ids[q["key"]]},
                )
        retired = [ids[k] for k in by_key if k not in keys]
        if retired:
            await tx.session.execute(
                text("UPDATE questions SET retired_at = clock_timestamp() WHERE id = ANY(:ids)"),
                {"ids": retired},
            )
        await tx.session.execute(
            text("UPDATE questionnaires SET row_version = row_version + 1 WHERE id = :q"),
            {"q": questionnaire_id},
        )
        if change_summary is not None and current.template and current.owner_kind != "binder":
            await tx.session.execute(
                text(
                    "UPDATE questionnaire_template_versions SET change_summary = :s, "
                    "row_version = row_version + 1 WHERE id = :v"
                ),
                {"s": change_summary, "v": current.template.version_id},
            )
        tx.record(
            "questionnaire.edited",
            target=Target("questionnaire", questionnaire_id),
            after=Ref(changes=len(listed), retired=len(retired), effects=len(fired)),
        )
    return True, listed, fired
