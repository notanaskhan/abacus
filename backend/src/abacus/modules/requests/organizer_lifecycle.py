"""T-03-T05: the organizer template lifecycle (BND-03 d; T-03 §3 F2; DEC-2326).

A template's versions come in two kinds. T-02's imported versions hold their structure in
`content`. An editor version holds it in a questionnaire of its own (`owner_kind` =
`template_version`). Both read here as `Section` rows, so a draft, a diff and a binder's organizer
treat them the same.

- **Draft.** From the newest published version, or blank when there is none; one at a time
  (409 `draft_exists`).
- **Discard.** A draft only (409 `version_published`), and hidden from lists after.
- **Publish.** The owner, for a tax year (`questionnaires.publish_version`).
- **Binder.** `version_for` finds the version published for a tax year;
  `questionnaires.attach_organizer` instantiates it and records where it came from. A binder
  already started keeps its version: nothing here touches it.

Templates hold no client data (DEC-20), so these reads aren't walled.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.identity.api import AuthContext, Forbidden, names_of, partner_members
from abacus.modules.requests.questionnaire_templates import from_content

SUBJECT: Final = "questionnaire_template"
DRAFT: Final = "questionnaire_template.draft"
ASSIGN: Final = "questionnaire_template.assign_owner"


class DraftExists(DomainConflict):
    """One draft per template: finish or discard it first."""

    code = "draft_exists"


class VersionPublished(DomainConflict):
    """A published version never changes."""

    code = "version_published"


class OwnerNotPartner(DomainConflict):
    """A template's owner is a partner member."""

    code = "owner_not_partner"


@dataclass(frozen=True)
class Question:
    key: str
    type: str
    client_wording: str
    help_text: str | None
    internal_helper: str | None
    required: bool
    parent_key: str | None
    conditional_value: Any  # Any: JSON from the database or the document
    show_when: dict[str, Any] | None  # Any: JSON from the database or the document
    choices: list[str]
    amount_parts: list[str]
    effect_rules: list[dict[str, Any]]  # Any: JSON from the database or the document


@dataclass(frozen=True)
class Section:
    key: str
    name: str
    icon_key: str | None
    questions: tuple[Question, ...]


@dataclass(frozen=True)
class VersionView:
    id: UUID
    version: int
    status: str
    applies_to_tax_year: int | None
    questionnaire_id: UUID | None
    drafted_by_name: str
    published_by_name: str | None
    published_at: datetime | None
    change_summary: str | None


@dataclass(frozen=True)
class TemplateDetail:
    id: UUID
    key: str | None
    name: str
    form_family: str | None
    owner_id: UUID | None
    owner_name: str | None
    versions: tuple[VersionView, ...]


def _person(ctx: AuthContext, action: str) -> None:
    if ctx.client:
        raise NotFound(SUBJECT)
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(action, "role")


def _status(stored: str | None, published_at: datetime | None) -> str:
    """An imported version has no stored status: published or still a draft."""
    if stored is not None:
        return stored
    return "published" if published_at is not None else "draft"


async def structure_of(
    session: AsyncSession, content: object, questionnaire_id: UUID | None
) -> tuple[Section, ...]:
    """A version's sections and questions, from whichever place it holds them."""
    if questionnaire_id is None:
        return tuple(
            Section(
                f"s{index}",
                s.name,
                s.icon_key,
                tuple(
                    Question(
                        q.key,
                        q.type,
                        q.client_wording,
                        q.help_text,
                        None,
                        False,
                        q.conditional_on,
                        q.conditional_value,
                        None,
                        [],
                        [],
                        [],
                    )
                    for q in s.questions
                ),
            )
            for index, s in enumerate(from_content(content).sections)
        )
    sections = (
        await session.execute(
            text(
                "SELECT id, coalesce(key, 's' || position::text) AS key, name, icon_key "
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
                    "SELECT q.*, p.question_key AS parent_key FROM questions q "
                    "LEFT JOIN questions p ON p.id = q.conditional_on_question_id "
                    "WHERE q.questionnaire_id = :q AND q.retired_at IS NULL ORDER BY q.position"
                ),
                {"q": questionnaire_id},
            )
        )
        .mappings()
        .all()
    )
    return tuple(
        Section(
            s.key,
            s.name,
            s.icon_key,
            tuple(
                Question(
                    r["question_key"],
                    r["type"],
                    r["client_wording"],
                    r["help_text"],
                    r["internal_helper"],
                    r["required"],
                    r["parent_key"],
                    r["conditional_value"],
                    r["show_when"],
                    list(r["choices"] or []),
                    list(r["amount_parts"] or []),
                    list(r["effect_rules"] or []),
                )
                for r in rows
                if r["section_id"] == s.id
            ),
        )
        for s in sections
    )


async def insert_structure(
    tx: UnitOfWork,
    ctx: AuthContext,
    questionnaire_id: UUID,
    sections: tuple[Section, ...],
    *,
    prior: dict[str, Any],  # Any: JSON from the database or the document
) -> int:
    """A version's structure into a new questionnaire; the question count."""
    ids: dict[str, UUID] = {}
    position = 0
    for index, section in enumerate(sections):
        section_id = uuid4()
        await tx.session.execute(
            text(
                "INSERT INTO questionnaire_sections (id, tenant_id, questionnaire_id, name, "
                "icon_key, position, key) VALUES (:id, :tenant, :q, :n, :icon, :p, :k)"
            ),
            {
                "id": section_id,
                "tenant": ctx.tenant_id,
                "q": questionnaire_id,
                "n": section.name,
                "icon": section.icon_key,
                "p": index,
                "k": section.key,
            },
        )
        for q in section.questions:
            ids[q.key] = uuid4()
            await tx.session.execute(
                text(
                    "INSERT INTO questions (id, tenant_id, questionnaire_id, section_id, "
                    "question_key, position, type, client_wording, help_text, internal_helper, "
                    "required, conditional_on_question_id, conditional_value, show_when, choices, "
                    "amount_parts, effect_rules, prior_year_value, origin, "
                    "origin_template_question_key, created_by) VALUES (:id, :tenant, :q, :s, :k, "
                    ":p, :type, :w, :h, :helper, :required, :cond, CAST(:cv AS jsonb), "
                    "CAST(:show AS jsonb), CAST(:choices AS jsonb), CAST(:parts AS jsonb), "
                    "CAST(:rules AS jsonb), CAST(:py AS jsonb), 'template', :k, :by)"
                ),
                {
                    "id": ids[q.key],
                    "tenant": ctx.tenant_id,
                    "q": questionnaire_id,
                    "s": section_id,
                    "k": q.key,
                    "p": position,
                    "type": q.type,
                    "w": q.client_wording,
                    "h": q.help_text,
                    "helper": q.internal_helper,
                    "required": q.required,
                    "cond": ids.get(q.parent_key) if q.parent_key else None,
                    "cv": json.dumps(q.conditional_value) if q.conditional_value else None,
                    "show": json.dumps(q.show_when) if q.show_when else None,
                    "choices": json.dumps(q.choices),
                    "parts": json.dumps(q.amount_parts),
                    "rules": json.dumps(q.effect_rules),
                    "py": json.dumps(prior[q.key]) if q.key in prior else None,
                    "by": ctx.user_id,
                },
            )
            position += 1
    return position


async def detail(ctx: AuthContext, template_id: UUID) -> TemplateDetail:
    """The template and its versions, newest first; a discarded draft isn't listed."""
    async with tenant_session(ctx.tenant) as session:
        head = (
            await session.execute(
                text(
                    "SELECT id, key, name, form_family, owner_id FROM questionnaire_templates "
                    "WHERE id = :t"
                ),
                {"t": template_id},
            )
        ).first()
        if head is None:
            raise NotFound(SUBJECT)
        rows = (
            await session.execute(
                text(
                    "SELECT id, version, status, applies_to_tax_year, questionnaire_id, "
                    "coalesce(drafted_by, imported_by) AS drafted_by, published_by, published_at, "
                    "change_summary FROM questionnaire_template_versions WHERE template_id = :t "
                    "AND status IS DISTINCT FROM 'discarded' ORDER BY version DESC"
                ),
                {"t": template_id},
            )
        ).all()
    people = {r.drafted_by for r in rows} | {r.published_by for r in rows if r.published_by}
    if head.owner_id is not None:
        people.add(head.owner_id)
    names = await names_of(list(people))
    return TemplateDetail(
        head.id,
        head.key,
        head.name,
        head.form_family,
        head.owner_id,
        names.get(head.owner_id) if head.owner_id else None,
        tuple(
            VersionView(
                r.id,
                r.version,
                _status(r.status, r.published_at),
                r.applies_to_tax_year,
                r.questionnaire_id,
                names.get(r.drafted_by, ""),
                names.get(r.published_by) if r.published_by else None,
                r.published_at,
                r.change_summary,
            )
            for r in rows
        ),
    )


async def assign_owner(ctx: AuthContext, template_id: UUID, owner_id: UUID) -> TemplateDetail:
    _person(ctx, ASSIGN)
    if owner_id not in await partner_members(ctx.tenant_id):
        raise OwnerNotPartner
    async with uow(ctx.tenant) as tx:
        found = (
            await tx.session.execute(
                text(
                    "UPDATE questionnaire_templates SET owner_id = :o WHERE id = :t RETURNING id"
                ),
                {"o": owner_id, "t": template_id},
            )
        ).first()
        if found is None:
            raise NotFound(SUBJECT)
        tx.record(
            "questionnaire_template.owner_assigned",
            target=Target(SUBJECT, template_id),
            after=Ref(owner_id=owner_id),
        )
    return await detail(ctx, template_id)


async def new_draft(
    ctx: AuthContext, template_id: UUID, change_summary: str | None
) -> TemplateDetail:
    """The next version as a draft, its structure copied from the newest published one."""
    _person(ctx, DRAFT)
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"),
            {"k": f"{SUBJECT}:{template_id}"},
        )
        head = (
            await tx.session.execute(
                text("SELECT name FROM questionnaire_templates WHERE id = :t"), {"t": template_id}
            )
        ).first()
        if head is None:
            raise NotFound(SUBJECT)
        versions = (
            await tx.session.execute(
                text(
                    "SELECT id, version, status, content, questionnaire_id, published_at "
                    "FROM questionnaire_template_versions WHERE template_id = :t "
                    "ORDER BY version DESC"
                ),
                {"t": template_id},
            )
        ).all()
        if any(_status(v.status, v.published_at) == "draft" for v in versions):
            raise DraftExists
        source = next((v for v in versions if v.published_at is not None), None)
        questionnaire_id = (
            await tx.session.execute(
                text(
                    "INSERT INTO questionnaires (tenant_id, kind, title, owner_kind, created_by) "
                    "VALUES (:tenant, 'organizer', :title, 'template_version', :by) RETURNING id"
                ),
                {"tenant": ctx.tenant_id, "title": str(head.name)[:200], "by": ctx.user_id},
            )
        ).scalar_one()
        sections = (
            await structure_of(tx.session, source.content, source.questionnaire_id)
            if source is not None
            else ()
        )
        questions = await insert_structure(tx, ctx, questionnaire_id, sections, prior={})
        version = max((v.version for v in versions), default=0) + 1
        await tx.session.execute(
            text(
                "INSERT INTO questionnaire_template_versions (tenant_id, template_id, version, "
                "status, questionnaire_id, drafted_from_version_id, change_summary, drafted_by, "
                "imported_by) VALUES (:tenant, :t, :v, 'draft', :q, :src, :summary, :by, :by)"
            ),
            {
                "tenant": ctx.tenant_id,
                "t": template_id,
                "v": version,
                "q": questionnaire_id,
                "src": source.id if source is not None else None,
                "summary": change_summary,
                "by": ctx.user_id,
            },
        )
        tx.record(
            "questionnaire_template.drafted",
            target=Target(SUBJECT, template_id),
            after=Ref(version=version, questions=questions),
        )
    return await detail(ctx, template_id)


async def discard(ctx: AuthContext, template_id: UUID, version: int) -> VersionView:
    _person(ctx, DRAFT)
    async with uow(ctx.tenant) as tx:
        row = (
            await tx.session.execute(
                text(
                    "SELECT id, status, published_at FROM questionnaire_template_versions "
                    "WHERE template_id = :t AND version = :v FOR UPDATE"
                ),
                {"t": template_id, "v": version},
            )
        ).first()
        if row is None or row.status == "discarded":
            raise NotFound("questionnaire_template_version")
        if row.published_at is not None:
            raise VersionPublished(facts={"version": version})
        await tx.session.execute(
            text(
                "UPDATE questionnaire_template_versions SET status = 'discarded', "
                "row_version = row_version + 1 WHERE id = :id"
            ),
            {"id": row.id},
        )
        tx.record(
            "questionnaire_template.discarded",
            target=Target(SUBJECT, template_id),
            after=Ref(version=version),
        )
    names = await names_of([ctx.user_id])
    return VersionView(
        row.id, version, "discarded", None, None, names.get(ctx.user_id, ""), None, None, None
    )


def _flat(sections: tuple[Section, ...]) -> dict[str, Question]:
    return {q.key: q for s in sections for q in s.questions}


def diff_of(
    before: tuple[Section, ...], after: tuple[Section, ...]
) -> list[dict[str, str | None]]:
    """Questions by key in key order: added, removed, and changed in any field."""
    old, new = _flat(before), _flat(after)
    out: list[dict[str, str | None]] = []
    for key in sorted(old.keys() | new.keys()):
        was, now = old.get(key), new.get(key)
        if was == now:
            continue
        kind = "added" if was is None else "removed" if now is None else "changed"
        out.append(
            {
                "question_key": key,
                "kind": kind,
                "before": was.client_wording if was else None,
                "after": now.client_wording if now else None,
            }
        )
    return out


async def diff(
    ctx: AuthContext, template_id: UUID, version: int, against: int | None
) -> tuple[int, list[dict[str, str | None]]]:
    """`version` against `against`, by default the version it was drafted from, else the one
    before it."""
    async with tenant_session(ctx.tenant) as session:
        rows = {
            r.version: r
            for r in (
                await session.execute(
                    text(
                        "SELECT id, version, content, questionnaire_id, drafted_from_version_id "
                        "FROM questionnaire_template_versions WHERE template_id = :t"
                    ),
                    {"t": template_id},
                )
            ).all()
        }
        current = rows.get(version)
        if current is None:
            raise NotFound("questionnaire_template_version")
        if against is None:
            drafted_from = next(
                (v for v, r in rows.items() if r.id == current.drafted_from_version_id), None
            )
            against = drafted_from if drafted_from is not None else version - 1
        other = rows.get(against)
        if other is None:
            raise NotFound("questionnaire_template_version")
        return against, diff_of(
            await structure_of(session, other.content, other.questionnaire_id),
            await structure_of(session, current.content, current.questionnaire_id),
        )


async def version_for(ctx: AuthContext, template_key: str, tax_year: int) -> UUID:
    """The newest version published for this tax year (T-03 §4.4)."""
    async with tenant_session(ctx.tenant) as session:
        found = (
            await session.execute(
                text(
                    "SELECT v.id FROM questionnaire_template_versions v "
                    "JOIN questionnaire_templates t ON t.id = v.template_id "
                    "WHERE t.key = :k AND v.applies_to_tax_year = :y "
                    "AND v.published_at IS NOT NULL ORDER BY v.version DESC LIMIT 1"
                ),
                {"k": template_key, "y": tax_year},
            )
        ).scalar_one_or_none()
    if found is None:
        raise NotFound("questionnaire_template_version")
    return found


__all__ = [
    "DraftExists",
    "OwnerNotPartner",
    "Question",
    "Section",
    "TemplateDetail",
    "VersionPublished",
    "VersionView",
    "assign_owner",
    "detail",
    "diff",
    "diff_of",
    "discard",
    "insert_structure",
    "new_draft",
    "structure_of",
    "version_for",
]
