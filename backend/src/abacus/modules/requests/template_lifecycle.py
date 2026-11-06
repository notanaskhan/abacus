"""T-03-T05: the organizer template's lifecycle (T-03 §3 F2; BND-03 d; KNW-01; DEC-2351).

A template's editor version is a template-owned questionnaire (`owner_kind = template_version`,
0655), edited through the same atomic save as a binder's organizer.

- **Draft from current** copies the newest published version's structure; one draft per template
  (409 `draft_exists`). An imported T-02 version is read from its stored content.
- **Discard** hides a draft; a published version never changes (409 `version_published`, and 0655's
  trigger behind it).
- **Publish** is the owner's alone once a template has an owner, with a fresh second factor through
  the matrix and the tax year it applies to. Publishing freezes the version.
- **Owner**: a partner member (409 `owner_not_partner`).
- **Diff** compares two versions' questions by key, the wording and the type.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    allowed_actions,
    authorise,
    member_facts,
    names_of,
)
from abacus.modules.requests.questionnaire_templates import from_content

SUBJECT: Final = "questionnaire_template"
READ: Final = "questionnaire_template.read"
DRAFT: Final = "questionnaire_template.draft"
PUBLISH: Final = "questionnaire_template.publish"
ASSIGN: Final = "questionnaire_template.assign_owner"
_ACTIONS: Final = (DRAFT, PUBLISH, ASSIGN)


class DraftExists(DomainConflict):
    code = "draft_exists"


class VersionPublished(DomainConflict):
    code = "version_published"


class OwnerNotPartner(DomainConflict):
    code = "owner_not_partner"


class NothingPublished(DomainConflict):
    """A draft starts from a published version; import or publish one first."""

    code = "nothing_published"


class TaxYearRequired(DomainInvalid):
    """A published editor version names the tax year it applies to (0655's CHECK)."""

    code = "applies_to_tax_year_required"


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
    key: str
    name: str
    form_family: str | None
    owner_id: UUID | None
    owner_name: str | None
    versions: tuple[VersionView, ...]
    allowed_actions: tuple[str, ...]


@dataclass(frozen=True)
class QuestionDiff:
    question_key: str
    kind: str
    before: str | None
    after: str | None


def _status(row: Mapping[str, Any]) -> str:  # Any: a database row
    """T-02's imported versions have no status: their state is `published_at`."""
    if row["status"] is not None:
        return str(row["status"])
    return "published" if row["published_at"] is not None else "draft"


async def _head(session: AsyncSession, template_id: UUID) -> dict[str, Any]:  # Any: a database row
    found = (
        (
            await session.execute(
                text("SELECT * FROM questionnaire_templates WHERE id = :t"), {"t": template_id}
            )
        )
        .mappings()
        .first()
    )
    if found is None:
        raise NotFound(SUBJECT)
    return dict(found)


async def detail(ctx: AuthContext, template_id: UUID) -> TemplateDetail:
    if ctx.client:
        raise NotFound(SUBJECT)
    await authorise(ctx, READ, Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        head = await _head(session, template_id)
        rows = [
            dict(r)
            for r in (
                await session.execute(
                    text(
                        "SELECT * FROM questionnaire_template_versions WHERE template_id = :t "
                        "AND status IS DISTINCT FROM 'discarded' ORDER BY version DESC"
                    ),
                    {"t": template_id},
                )
            ).mappings()
        ]
    people = {head["owner_id"]} | {
        r[k] for r in rows for k in ("drafted_by", "imported_by", "published_by")
    }
    names = await names_of(sorted((p for p in people if p), key=str))
    allowed = await allowed_actions(ctx, Resource.firm(ctx.tenant_id), _ACTIONS)
    return TemplateDetail(
        id=head["id"],
        key=head["key"] or str(head["id"]).replace("-", ""),
        name=head["name"],
        form_family=head["form_family"],
        owner_id=head["owner_id"],
        owner_name=names.get(head["owner_id"]) if head["owner_id"] else None,
        versions=tuple(
            VersionView(
                id=r["id"],
                version=r["version"],
                status=_status(r),
                applies_to_tax_year=r["applies_to_tax_year"],
                questionnaire_id=r["questionnaire_id"],
                drafted_by_name=names.get(r["drafted_by"] or r["imported_by"], ""),
                published_by_name=names.get(r["published_by"]) if r["published_by"] else None,
                published_at=r["published_at"],
                change_summary=r["change_summary"],
            )
            for r in rows
        ),
        allowed_actions=tuple(a for a in _ACTIONS if a in allowed),
    )


async def assign_owner(ctx: AuthContext, template_id: UUID, owner_id: UUID) -> TemplateDetail:
    await authorise(ctx, ASSIGN, Resource.firm(ctx.tenant_id))
    facts = await member_facts(ctx.tenant, owner_id)
    if facts is None or facts.client or facts.level != "partner":
        raise OwnerNotPartner(facts={"owner_id": str(owner_id)})
    async with uow(ctx.tenant) as tx:
        await _head(tx.session, template_id)
        await tx.session.execute(
            text("UPDATE questionnaire_templates SET owner_id = :o WHERE id = :t"),
            {"o": owner_id, "t": template_id},
        )
        tx.record(
            "questionnaire_template.owner_assigned",
            target=Target(SUBJECT, template_id),
            after=Ref(owner=owner_id),
        )
    return await detail(ctx, template_id)


async def _copy_from_questionnaire(
    tx: UnitOfWork, ctx: AuthContext, source: UUID, into: UUID
) -> int:
    """The source's live sections and questions, new ids, logic rewired. Answers never copy."""
    section_ids: dict[UUID, UUID] = {}
    sections = await tx.session.execute(
        text(
            "SELECT * FROM questionnaire_sections WHERE questionnaire_id = :q "
            "AND retired_at IS NULL ORDER BY position"
        ),
        {"q": source},
    )
    for s in sections.mappings():
        section_ids[s["id"]] = uuid4()
        await tx.session.execute(
            text(
                "INSERT INTO questionnaire_sections (id, tenant_id, questionnaire_id, key, name, "
                "icon_key, position) VALUES (:id, :t, :q, :k, :n, :i, :p)"
            ),
            {
                "id": section_ids[s["id"]],
                "t": ctx.tenant_id,
                "q": into,
                "k": s["key"],
                "n": s["name"],
                "i": s["icon_key"],
                "p": s["position"],
            },
        )
    found = list(
        (
            await tx.session.execute(
                text(
                    "SELECT * FROM questions WHERE questionnaire_id = :q AND retired_at IS NULL "
                    "ORDER BY position"
                ),
                {"q": source},
            )
        ).mappings()
    )
    question_ids = {q["id"]: uuid4() for q in found}
    for q in found:
        await tx.session.execute(
            text(
                "INSERT INTO questions (id, tenant_id, questionnaire_id, section_id, "
                "question_key, "
                "position, type, client_wording, help_text, internal_helper, required, "
                "show_when, "
                "choices, amount_parts, effect_rules, conditional_on_question_id, "
                "conditional_value, origin, origin_template_question_key, created_by) VALUES "
                "(:id, :t, :q, :s, :k, :p, :type, :w, :h, :ih, :req, CAST(:sw AS jsonb), "
                "CAST(:ch AS jsonb), CAST(:ap AS jsonb), CAST(:er AS jsonb), :cond, "
                "CAST(:cv AS jsonb), 'template', :k, :by)"
            ),
            {
                "id": question_ids[q["id"]],
                "t": ctx.tenant_id,
                "q": into,
                "s": section_ids[q["section_id"]],
                "k": q["question_key"],
                "p": q["position"],
                "type": q["type"],
                "w": q["client_wording"],
                "h": q["help_text"],
                "ih": q["internal_helper"],
                "req": q["required"],
                "sw": _json(q["show_when"]),
                "ch": _json(q["choices"]),
                "ap": _json(q["amount_parts"]),
                "er": _json(q["effect_rules"]),
                "cond": question_ids.get(q["conditional_on_question_id"]),
                "cv": _json(q["conditional_value"]),
                "by": ctx.user_id,
            },
        )
    return len(found)


def _json(value: object) -> str | None:
    return None if value is None else json.dumps(value)


async def _copy_from_content(tx: UnitOfWork, ctx: AuthContext, content: object, into: UUID) -> int:
    """An imported version's stored form as the draft's structure."""
    template = from_content(content)
    ids: dict[str, UUID] = {}
    position = 0
    for index, section in enumerate(template.sections):
        section_id = uuid4()
        await tx.session.execute(
            text(
                "INSERT INTO questionnaire_sections (id, tenant_id, questionnaire_id, name, "
                "icon_key, position) VALUES (:id, :t, :q, :n, :i, :p)"
            ),
            {
                "id": section_id,
                "t": ctx.tenant_id,
                "q": into,
                "n": section.name,
                "i": section.icon_key,
                "p": index,
            },
        )
        for q in section.questions:
            ids[q.key] = uuid4()
            await tx.session.execute(
                text(
                    "INSERT INTO questions (id, tenant_id, questionnaire_id, section_id, "
                    "question_key, position, type, client_wording, help_text, "
                    "conditional_on_question_id, conditional_value, origin, "
                    "origin_template_question_key, created_by) VALUES (:id, :t, :q, :s, :k, :p, "
                    ":type, :w, :h, :cond, CAST(:cv AS jsonb), 'template', :k, :by)"
                ),
                {
                    "id": ids[q.key],
                    "t": ctx.tenant_id,
                    "q": into,
                    "s": section_id,
                    "k": q.key,
                    "p": position,
                    "type": q.type,
                    "w": q.client_wording,
                    "h": q.help_text,
                    "cond": ids.get(q.conditional_on) if q.conditional_on else None,
                    "cv": json.dumps(q.conditional_value) if q.conditional_value else None,
                    "by": ctx.user_id,
                },
            )
            position += 1
    return position


async def draft_from_current(
    ctx: AuthContext, template_id: UUID, change_summary: str | None
) -> UUID:
    """The new version's questionnaire is template-owned: no engagement, no client data."""
    await authorise(ctx, DRAFT, Resource.firm(ctx.tenant_id))
    async with uow(ctx.tenant) as tx:
        head = await _head(tx.session, template_id)
        versions = [
            dict(r)
            for r in (
                await tx.session.execute(
                    text(
                        "SELECT * FROM questionnaire_template_versions WHERE template_id = :t "
                        "ORDER BY version DESC FOR UPDATE"
                    ),
                    {"t": template_id},
                )
            ).mappings()
        ]
        if any(r["status"] == "draft" for r in versions):
            raise DraftExists(facts={"template_id": str(template_id)})
        current = next((r for r in versions if r["published_at"] is not None), None)
        if current is None:
            raise NothingPublished(facts={"template_id": str(template_id)})
        questionnaire_id = (
            await tx.session.execute(
                text(
                    "INSERT INTO questionnaires (tenant_id, kind, owner_kind, title, created_by) "
                    "VALUES (:t, 'organizer', 'template_version', :title, :by) RETURNING id"
                ),
                {"t": ctx.tenant_id, "title": str(head["name"])[:200], "by": ctx.user_id},
            )
        ).scalar_one()
        if current["questionnaire_id"] is not None:
            copied = await _copy_from_questionnaire(
                tx, ctx, current["questionnaire_id"], questionnaire_id
            )
        else:
            copied = await _copy_from_content(tx, ctx, current["content"], questionnaire_id)
        version = max(r["version"] for r in versions) + 1
        version_id = (
            await tx.session.execute(
                text(
                    "INSERT INTO questionnaire_template_versions (tenant_id, template_id, "
                    "version, "
                    "imported_by, status, questionnaire_id, drafted_from_version_id, "
                    "change_summary, drafted_by) VALUES (:t, :tpl, :v, :by, 'draft', :q, "
                    ":from, "
                    ":sum, :by) RETURNING id"
                ),
                {
                    "t": ctx.tenant_id,
                    "tpl": template_id,
                    "v": version,
                    "by": ctx.user_id,
                    "q": questionnaire_id,
                    "from": current["id"],
                    "sum": change_summary,
                },
            )
        ).scalar_one()
        tx.record(
            "questionnaire_template.drafted",
            target=Target(SUBJECT, template_id),
            after=Ref(version=version, questions=copied),
        )
    return UUID(str(version_id))


async def discard(ctx: AuthContext, template_id: UUID, version: int) -> UUID:
    await authorise(ctx, DRAFT, Resource.firm(ctx.tenant_id))
    async with uow(ctx.tenant) as tx:
        row = (
            (
                await tx.session.execute(
                    text(
                        "SELECT id, status, published_at FROM questionnaire_template_versions "
                        "WHERE template_id = :t AND version = :v FOR UPDATE"
                    ),
                    {"t": template_id, "v": version},
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise NotFound("questionnaire_template_version")
        if row["published_at"] is not None or row["status"] != "draft":
            raise VersionPublished(facts={"version": version})
        await tx.session.execute(
            text(
                "UPDATE questionnaire_template_versions SET status = 'discarded', "
                "row_version = row_version + 1 WHERE id = :id"
            ),
            {"id": row["id"]},
        )
        tx.record(
            "questionnaire_template.discarded",
            target=Target(SUBJECT, template_id),
            after=Ref(version=version),
        )
    return row["id"]


async def publish_guard(
    tx: UnitOfWork,
    ctx: AuthContext,
    template_id: UUID,
    applies_to_tax_year: int | None,
    row: Any,  # noqa: ANN401 -- a database row
) -> None:
    """The owner alone once there is one (DEC-2200); an editor version names its tax year and is
    frozen by 0655's trigger once `status` reads published. `row`'s `status` is null on a T-02
    import, whose single update stays `published_at`."""
    head = await _head(tx.session, template_id)
    if head["owner_id"] is not None and head["owner_id"] != ctx.user_id:
        raise Forbidden(PUBLISH, "role")
    if row.status is None:
        return
    if applies_to_tax_year is None:
        raise TaxYearRequired
    await tx.session.execute(
        text(
            "UPDATE questionnaire_template_versions SET status = 'published', "
            "applies_to_tax_year = :y, published_actor_kind = 'human', "
            "published_by = :by, published_at = abacus_now(), row_version = row_version + 1 "
            "WHERE id = :id"
        ),
        {"y": applies_to_tax_year, "by": ctx.user_id, "id": row.id},
    )


async def _questions_of(
    session: AsyncSession, version: Mapping[str, Any]
) -> dict[str, tuple[str, str]]:
    if version["questionnaire_id"] is None:
        return {
            k: (q.type, q.client_wording)
            for k, q in from_content(version["content"]).questions().items()
        }
    found = await session.execute(
        text(
            "SELECT question_key, type, client_wording FROM questions WHERE questionnaire_id = :q "
            "AND retired_at IS NULL"
        ),
        {"q": version["questionnaire_id"]},
    )
    return {r.question_key: (r.type, r.client_wording) for r in found}


async def diff(
    ctx: AuthContext, template_id: UUID, version: int, against: int | None
) -> tuple[int, list[QuestionDiff]]:
    """Against the named version, else the one this was drafted from, else the one before it."""
    if ctx.client:
        raise NotFound(SUBJECT)
    await authorise(ctx, READ, Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        rows = {
            r["version"]: dict(r)
            for r in (
                await session.execute(
                    text("SELECT * FROM questionnaire_template_versions WHERE template_id = :t"),
                    {"t": template_id},
                )
            ).mappings()
        }
        if version not in rows:
            raise NotFound("questionnaire_template_version")
        base = against
        if base is None:
            source = rows[version]["drafted_from_version_id"]
            base = next((v for v, r in rows.items() if r["id"] == source), version - 1)
        if base not in rows:
            raise NotFound("questionnaire_template_version")
        new = await _questions_of(session, rows[version])
        old = await _questions_of(session, rows[base])
    out = [QuestionDiff(k, "added", None, new[k][1]) for k in sorted(new.keys() - old.keys())]
    out += [
        QuestionDiff(k, "changed", old[k][1], new[k][1])
        for k in sorted(new.keys() & old.keys())
        if new[k] != old[k]
    ]
    out += [QuestionDiff(k, "removed", old[k][1], None) for k in sorted(old.keys() - new.keys())]
    return base, out


@dataclass(frozen=True)
class BinderQuestionnaire:
    binder_id: UUID
    questionnaire_id: UUID | None
    questions: int
    answered: int
    template_id: UUID | None
    template_name: str | None
    version: int | None
    version_id: UUID | None
    engagement_id: UUID | None
    work_item_id: UUID | None


async def binder_questionnaire(ctx: AuthContext, binder_id: UUID) -> BinderQuestionnaire:
    """BND-02's badge: the binder's newest organizer, its counts and where it came from."""
    async with tenant_session(ctx.tenant) as session:
        row = (
            (
                await session.execute(
                    text(
                        "SELECT q.id, q.engagement_id, q.work_item_id, v.id AS vid, v.version, "
                        "t.id AS tid, "
                        "t.name, (SELECT count(*) FROM questions x "
                        "WHERE x.questionnaire_id = q.id "
                        "AND x.retired_at IS NULL) AS total, (SELECT count(*) FROM questions x "
                        "WHERE x.questionnaire_id = q.id AND x.retired_at IS NULL AND EXISTS "
                        "(SELECT 1 FROM answer_versions a WHERE a.question_id = x.id)) "
                        "AS answered "
                        "FROM questionnaires q LEFT JOIN questionnaire_template_versions v "
                        "ON v.id = coalesce(q.source_template_version_id, "
                        "q.template_version_id) "
                        "LEFT JOIN questionnaire_templates t ON t.id = v.template_id "
                        "WHERE q.request_list_id = :b AND q.kind = 'organizer' "
                        "ORDER BY q.created_at DESC LIMIT 1"
                    ),
                    {"b": binder_id},
                )
            )
            .mappings()
            .first()
        )
    if row is None:
        return BinderQuestionnaire(binder_id, None, 0, 0, None, None, None, None, None, None)
    return BinderQuestionnaire(
        binder_id,
        row["id"],
        int(row["total"]),
        int(row["answered"]),
        row["tid"],
        row["name"],
        row["version"],
        row["vid"],
        row["engagement_id"],
        row["work_item_id"],
    )
