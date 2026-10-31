"""Questionnaires v1, the firm side (T-02-T16; T-02 §3.5, §4.3; DEC-1369). Amber.

- **Templates** (`questionnaire_template.*`): a manager imports a CSV, XLSX or JSON file; it is
  parsed in the isolated child (`questionnaire_templates.parse`, hostile content). A dry run
  answers the problems and the diff against the current published version and stores nothing; a
  real import stores a new unpublished version. Publishing is a person's click (fresh MFA): the
  newest published version is current, the rest superseded (computed).
- **Organizers** (`questionnaire.create` on the engagement): a published version instantiated on
  a request list (binder): its sections and questions, sent as the attach (the attach is the
  person's send); prior-year values copied by code from the client's previous organizer by
  question key (the latest answer there), never by a model. Organizer answers are TRI.
- **Team questions and inquiries** (`questionnaire.create`, then `questionnaire.ask`): A-04 and
  A-08 create them with an addressee (an inquiry must have one); a question is drafted, then sent
  by a person (`sent_at`).
- **Reads** (`questionnaire.read` on the engagement): a binder's questionnaires and one in full,
  each question with its current answer (the highest version) for the engagement team.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Any, Final
from uuid import UUID, uuid4

from sqlalchemy import Row, text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel._statuses import QuestionnaireStatus
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.isolation import IsolationFailed, run_isolated
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.engagements.api import work_item_facts
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    authorise,
    engagement_resource,
)
from abacus.modules.requests.questionnaire_templates import (
    Changes,
    Format,
    Template,
    TemplateInvalid,
    changes_between,
    from_content,
    parse,
)

TextRow = Row[Any]  # a text query's row, read by column name
SUBJECT: Final = "questionnaire"
IMPORT: Final = "questionnaire_template.import"
PUBLISH: Final = "questionnaire_template.publish"
TEMPLATES_READ: Final = "questionnaire_template.read"
CREATE: Final = "questionnaire.create"
ASK: Final = "questionnaire.ask"
READ: Final = "questionnaire.read"


class ImportRefused(DomainInvalid):
    """422: the file is not a template (`facts.problems` counts; the codes come back on the dry
    run)."""

    code = "template_invalid"


class AlreadyPublished(DomainConflict):
    code = "version_published"


class NotPublished(DomainConflict):
    code = "version_not_published"


class AlreadySent(DomainConflict):
    code = "question_sent"


class QuestionnaireClosed(DomainConflict):
    code = "questionnaire_closed"


@dataclass(frozen=True)
class ImportResult:
    template_id: UUID | None
    version: int | None
    dry_run: bool
    problems: tuple[str, ...]
    changes: Changes | None


@dataclass(frozen=True)
class TemplateView:
    id: UUID
    name: str
    current_version: int | None
    draft_version: int | None
    # T-02-T19: the published version a person attaches with "Add organizer…" (TAX-03).
    current_version_id: UUID | None = None


@dataclass(frozen=True)
class QuestionView:
    id: UUID
    section: str
    type: str
    client_wording: str
    help_text: str | None
    conditional_on_question_id: UUID | None
    prior_year_value: object
    answer: object
    answer_version: int | None
    linked_request_item_id: UUID | None
    sent_at: datetime | None


@dataclass(frozen=True)
class QuestionnaireView:
    id: UUID
    kind: str
    title: str
    status: str
    due_on: date | None
    answered: int
    total: int
    addressed_to_contact_id: UUID | None
    questions: tuple[QuestionView, ...]


def _person(ctx: AuthContext, action: str) -> None:
    if ctx.client:
        raise NotFound(SUBJECT)
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(action, "role")


async def _engagement(
    ctx: AuthContext, engagement_id: UUID, work_item_id: UUID, action: str
) -> None:
    base = await engagement_resource(ctx.tenant, engagement_id)
    await authorise(ctx, action, replace(base, work_item_id=work_item_id))


# --- templates --------------------------------------------------------------------------------


async def _parse(content: bytes, fmt: Format) -> Template:
    try:
        return await asyncio.to_thread(run_isolated, parse, content, fmt)
    except IsolationFailed:
        raise TemplateInvalid(["unreadable"]) from None


async def _current(session: AsyncSession, template_id: UUID) -> Template | None:
    content = (
        await session.execute(
            text(
                "SELECT content FROM questionnaire_template_versions WHERE template_id = :t "
                "AND published_at IS NOT NULL ORDER BY version DESC LIMIT 1"
            ),
            {"t": template_id},
        )
    ).scalar_one_or_none()
    return None if content is None else from_content(content)


async def import_template(
    ctx: AuthContext, name: str, content: bytes, fmt: Format, *, dry_run: bool
) -> ImportResult:
    _person(ctx, IMPORT)
    await authorise(ctx, IMPORT, Resource.firm(ctx.tenant_id))
    name = name.strip()
    if not 1 <= len(name) <= 200:
        raise ImportRefused(facts={"field": "name"})
    try:
        template = await _parse(content, fmt)
    except TemplateInvalid as bad:
        if dry_run:
            return ImportResult(None, None, True, tuple(bad.problems), None)
        raise ImportRefused(facts={"problems": len(bad.problems)}) from None
    if dry_run:  # a read: what the import would change, with nothing written
        async with tenant_session(ctx.tenant) as session:
            found = (
                await session.execute(
                    text("SELECT id FROM questionnaire_templates WHERE name = :n"), {"n": name}
                )
            ).scalar_one_or_none()
            before = await _current(session, found) if found else None
        return ImportResult(found, None, True, (), changes_between(before, template))
    async with uow(ctx.tenant) as tx:
        template_id = (
            await tx.session.execute(
                text("SELECT id FROM questionnaire_templates WHERE name = :n"), {"n": name}
            )
        ).scalar_one_or_none()
        before = await _current(tx.session, template_id) if template_id else None
        changes = changes_between(before, template)
        if template_id is None:
            template_id = (
                await tx.session.execute(
                    text(
                        "INSERT INTO questionnaire_templates (tenant_id, name, created_by) "
                        "VALUES (:tenant, :n, :by) RETURNING id"
                    ),
                    {"tenant": ctx.tenant_id, "n": name, "by": ctx.user_id},
                )
            ).scalar_one()
        await tx.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"),
            {"k": f"questionnaire_template:{template_id}"},
        )
        version = (
            await tx.session.execute(
                text(
                    "SELECT coalesce(max(version), 0) + 1 FROM questionnaire_template_versions "
                    "WHERE template_id = :t"
                ),
                {"t": template_id},
            )
        ).scalar_one()
        await tx.session.execute(
            text(
                "INSERT INTO questionnaire_template_versions (tenant_id, template_id, version, "
                "content, source_file_sha256, imported_by) VALUES (:tenant, :t, :v, "
                "CAST(:c AS jsonb), :sha, :by)"
            ),
            {
                "tenant": ctx.tenant_id,
                "t": template_id,
                "v": version,
                "c": json.dumps(template.content()),
                "sha": hashlib.sha256(content).hexdigest(),
                "by": ctx.user_id,
            },
        )
        tx.record(
            "questionnaire_template.imported",
            target=Target("questionnaire_template", template_id),
            after=Ref(
                version=version,
                added=len(changes.added),
                changed=len(changes.changed),
                removed=len(changes.removed),
            ),
        )
    return ImportResult(template_id, int(version), False, (), changes)


async def publish_version(ctx: AuthContext, template_id: UUID, version: int) -> TemplateView:
    """A person publishes (fresh MFA through the matrix); the newest published is current."""
    _person(ctx, PUBLISH)
    await authorise(ctx, PUBLISH, Resource.firm(ctx.tenant_id))
    async with uow(ctx.tenant) as tx:
        found = (
            await tx.session.execute(
                text(
                    "SELECT id, published_at FROM questionnaire_template_versions "
                    "WHERE template_id = :t AND version = :v FOR UPDATE"
                ),
                {"t": template_id, "v": version},
            )
        ).first()
        if found is None:
            raise NotFound("questionnaire_template_version")
        if found.published_at is not None:
            raise AlreadyPublished(facts={"version": version})
        await tx.session.execute(
            text(
                "UPDATE questionnaire_template_versions SET published_by = :by, "
                "published_at = abacus_now() WHERE id = :id"
            ),
            {"by": ctx.user_id, "id": found.id},
        )
        tx.record(
            "questionnaire_template.published",
            target=Target("questionnaire_template", template_id),
            after=Ref(version=version),
        )
    return next(t for t in await templates(ctx) if t.id == template_id)


async def templates(ctx: AuthContext) -> list[TemplateView]:
    if ctx.client:
        raise NotFound(SUBJECT)
    await authorise(ctx, TEMPLATES_READ, Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT t.id, t.name, "
                    "max(v.version) FILTER (WHERE v.published_at IS NOT NULL) AS current, "
                    "max(v.version) FILTER (WHERE v.published_at IS NULL) AS draft, "
                    "(SELECT p.id FROM questionnaire_template_versions p WHERE p.template_id = t.id "
                    "AND p.published_at IS NOT NULL ORDER BY p.version DESC LIMIT 1) AS current_id "
                    "FROM questionnaire_templates t LEFT JOIN questionnaire_template_versions v "
                    "ON v.template_id = t.id GROUP BY t.id, t.name ORDER BY t.name"
                )
            )
        ).all()
    out: list[TemplateView] = []
    for r in rows:
        draft = (
            r.draft if r.draft is not None and (r.current is None or r.draft > r.current) else None
        )
        out.append(TemplateView(r.id, r.name, r.current, draft, r.current_id))
    return out


# --- questionnaires ---------------------------------------------------------------------------


async def _prior_values(
    ctx: AuthContext, session: AsyncSession, work_item_id: UUID
) -> dict[str, object]:
    """The client's previous organizer's latest answers by question key (copied by code)."""
    facts = {f.work_item_id: f for f in await work_item_facts(ctx, "tax_return")}
    mine = facts.get(work_item_id)
    if mine is None:
        return {}
    others = [w for w, f in facts.items() if f.client_id == mine.client_id and w != work_item_id]
    if not others:
        return {}
    rows = (
        await session.execute(
            text(
                "SELECT DISTINCT ON (x.question_key) x.question_key, a.value "
                "FROM questionnaires q JOIN questions x ON x.questionnaire_id = q.id "
                "JOIN answer_versions a ON a.question_id = x.id "
                "WHERE q.kind = 'organizer' AND q.work_item_id = ANY(:others) "
                "AND x.question_key IS NOT NULL "
                "ORDER BY x.question_key, q.created_at DESC, a.version_no DESC"
            ),
            {"others": others},
        )
    ).all()
    return {str(r.question_key): r.value for r in rows}


async def attach_organizer(
    ctx: AuthContext, request_list_id: UUID, template_version_id: UUID, due_on: date | None
) -> QuestionnaireView:
    _person(ctx, CREATE)
    async with tenant_session(ctx.tenant) as session:
        binder = (
            await session.execute(
                text("SELECT engagement_id, work_item_id, name FROM request_lists WHERE id = :id"),
                {"id": request_list_id},
            )
        ).first()
        version = (
            await session.execute(
                text(
                    "SELECT v.content, v.published_at, t.name "
                    "FROM questionnaire_template_versions v JOIN questionnaire_templates t "
                    "ON t.id = v.template_id WHERE v.id = :id"
                ),
                {"id": template_version_id},
            )
        ).first()
    if binder is None:
        raise NotFound("request_list")
    if version is None:
        raise NotFound("questionnaire_template_version")
    await _engagement(ctx, binder.engagement_id, binder.work_item_id, CREATE)
    if version.published_at is None:
        raise NotPublished(facts={"template_version_id": str(template_version_id)})
    template = from_content(version.content)
    async with uow(ctx.tenant) as tx:
        prior = await _prior_values(ctx, tx.session, binder.work_item_id)
        questionnaire_id = (
            await tx.session.execute(
                text(
                    "INSERT INTO questionnaires (tenant_id, engagement_id, work_item_id, "
                    "request_list_id, kind, template_version_id, title, due_on, data_class, "
                    "created_by) VALUES (:tenant, :e, :w, :l, 'organizer', :v, :title, :due, "
                    "'tri', :by) RETURNING id"
                ),
                {
                    "tenant": ctx.tenant_id,
                    "e": binder.engagement_id,
                    "w": binder.work_item_id,
                    "l": request_list_id,
                    "v": template_version_id,
                    "title": str(version.name)[:200],
                    "due": due_on,
                    "by": ctx.user_id,
                },
            )
        ).scalar_one()
        ids: dict[str, UUID] = {}
        position = 0
        for index, section in enumerate(template.sections):
            section_id = uuid4()
            await tx.session.execute(
                text(
                    "INSERT INTO questionnaire_sections (id, tenant_id, questionnaire_id, name, "
                    "icon_key, position) VALUES (:id, :tenant, :q, :n, :icon, :p)"
                ),
                {
                    "id": section_id,
                    "tenant": ctx.tenant_id,
                    "q": questionnaire_id,
                    "n": section.name,
                    "icon": section.icon_key,
                    "p": index,
                },
            )
            for q in section.questions:
                ids[q.key] = uuid4()
                await tx.session.execute(
                    text(
                        "INSERT INTO questions (id, tenant_id, questionnaire_id, section_id, "
                        "question_key, position, type, client_wording, help_text, "
                        "conditional_on_question_id, conditional_value, prior_year_value, "
                        "origin, created_by) VALUES (:id, :tenant, :q, :s, :k, :p, :type, :w, "
                        ":h, :cond, CAST(:cv AS jsonb), CAST(:py AS jsonb), 'template', :by)"
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
                        "cond": ids.get(q.conditional_on) if q.conditional_on else None,
                        "cv": json.dumps(q.conditional_value) if q.conditional_value else None,
                        "py": json.dumps(prior[q.key]) if q.key in prior else None,
                        "by": ctx.user_id,
                    },
                )
                position += 1
        # The attach is the person's send of the organizer's questions.
        await tx.session.execute(
            text(
                "UPDATE questions SET sent_by = :by, sent_at = abacus_now() "
                "WHERE questionnaire_id = :q"
            ),
            {"by": ctx.user_id, "q": questionnaire_id},
        )
        tx.record(
            "questionnaire.created",
            target=Target(SUBJECT, questionnaire_id),
            after=Ref(questions=position, prior_year=len(prior)),  # identifiers and counts only
        )
    return await questionnaire(ctx, questionnaire_id)


async def create_questionnaire(
    ctx: AuthContext,
    *,
    kind: str,
    work_item_id: UUID,
    title: str,
    addressed_to_contact_id: UUID | None,
    due_on: date | None,
) -> QuestionnaireView:
    """A-04 and A-08's team questions and inquiries (an inquiry names its addressee)."""
    _person(ctx, CREATE)
    if kind == "inquiry" and addressed_to_contact_id is None:
        raise DomainInvalid(facts={"field": "addressed_to_contact_id"})
    async with tenant_session(ctx.tenant) as session:
        engagement_id = (
            await session.execute(
                text("SELECT engagement_id FROM request_lists WHERE work_item_id = :w LIMIT 1"),
                {"w": work_item_id},
            )
        ).scalar_one_or_none()
    facts = next(
        (f for f in await work_item_facts(ctx, "tax_return") if f.work_item_id == work_item_id),
        None,
    )
    engagement = facts.engagement_id if facts else engagement_id
    if engagement is None:
        raise NotFound("work_item")
    await _engagement(ctx, engagement, work_item_id, CREATE)
    async with uow(ctx.tenant) as tx:
        questionnaire_id = (
            await tx.session.execute(
                text(
                    "INSERT INTO questionnaires (tenant_id, engagement_id, work_item_id, kind, "
                    "title, due_on, addressed_to_contact_id, created_by) VALUES (:tenant, :e, "
                    ":w, :k, :title, :due, :to, :by) RETURNING id"
                ),
                {
                    "tenant": ctx.tenant_id,
                    "e": engagement,
                    "w": work_item_id,
                    "k": kind,
                    "title": title.strip(),
                    "due": due_on,
                    "to": addressed_to_contact_id,
                    "by": ctx.user_id,
                },
            )
        ).scalar_one()
        tx.record(
            "questionnaire.created",
            target=Target(SUBJECT, questionnaire_id),
            after=Ref(),  # identifiers only: the kind is on the questionnaire row
        )
    return await questionnaire(ctx, questionnaire_id)


async def head_of(session: AsyncSession, questionnaire_id: UUID) -> TextRow:
    found = (
        await session.execute(
            text(
                "SELECT id, engagement_id, work_item_id, kind, title, status, due_on, "
                "addressed_to_contact_id FROM questionnaires WHERE id = :id"
            ),
            {"id": questionnaire_id},
        )
    ).first()
    if found is None:
        raise NotFound(SUBJECT)
    return found


async def draft_question(
    ctx: AuthContext,
    questionnaire_id: UUID,
    *,
    section: str,
    type_: str,
    client_wording: str,
    help_text: str | None,
    linked_request_item_id: UUID | None,
) -> QuestionView:
    _person(ctx, ASK)
    async with tenant_session(ctx.tenant) as session:
        head = await head_of(session, questionnaire_id)
    await _engagement(ctx, head.engagement_id, head.work_item_id, ASK)
    if head.status != QuestionnaireStatus.OPEN:
        raise QuestionnaireClosed(facts={"status": head.status})
    question_id = uuid4()
    async with uow(ctx.tenant) as tx:
        section_id = (
            await tx.session.execute(
                text(
                    "SELECT id FROM questionnaire_sections "
                    "WHERE questionnaire_id = :q AND name = :n"
                ),
                {"q": questionnaire_id, "n": section.strip()},
            )
        ).scalar_one_or_none()
        if section_id is None:
            section_id = uuid4()
            await tx.session.execute(
                text(
                    "INSERT INTO questionnaire_sections (id, tenant_id, questionnaire_id, name, "
                    "position) SELECT :id, :tenant, :q, :n, coalesce(max(position) + 1, 0) "
                    "FROM questionnaire_sections WHERE questionnaire_id = :q"
                ),
                {
                    "id": section_id,
                    "tenant": ctx.tenant_id,
                    "q": questionnaire_id,
                    "n": section.strip(),
                },
            )
        await tx.session.execute(
            text(
                "INSERT INTO questions (id, tenant_id, questionnaire_id, section_id, position, "
                "type, client_wording, help_text, linked_request_item_id, origin, created_by) "
                "SELECT :id, :tenant, :q, :s, coalesce(max(position) + 1, 0), :type, :w, :h, "
                ":link, 'team', :by FROM questions WHERE questionnaire_id = :q"
            ),
            {
                "id": question_id,
                "tenant": ctx.tenant_id,
                "q": questionnaire_id,
                "s": section_id,
                "type": type_,
                "w": client_wording.strip(),
                "h": help_text,
                "link": linked_request_item_id,
                "by": ctx.user_id,
            },
        )
        tx.record("question.drafted", target=Target("question", question_id))
    return await _question(ctx, question_id)


async def send_question(ctx: AuthContext, question_id: UUID) -> QuestionView:
    """A person sends a drafted question (human only; never the agent)."""
    _person(ctx, ASK)
    async with tenant_session(ctx.tenant) as session:
        found = (
            await session.execute(
                text("SELECT questionnaire_id, sent_at FROM questions WHERE id = :id"),
                {"id": question_id},
            )
        ).first()
        if found is None:
            raise NotFound("question")
        head = await head_of(session, found.questionnaire_id)
    await _engagement(ctx, head.engagement_id, head.work_item_id, ASK)
    if found.sent_at is not None:
        raise AlreadySent(facts={"question_id": str(question_id)})
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "UPDATE questions SET sent_by = :by, sent_at = abacus_now() "
                "WHERE id = :id AND sent_at IS NULL"
            ),
            {"by": ctx.user_id, "id": question_id},
        )
        tx.record("question.sent", target=Target("question", question_id))
    return await _question(ctx, question_id)


# --- reads ------------------------------------------------------------------------------------

_QUESTIONS = text(
    "SELECT x.id, s.name AS section, x.type, x.client_wording, x.help_text, "
    "x.conditional_on_question_id, x.prior_year_value, x.linked_request_item_id, x.sent_at, "
    "a.value AS answer, a.version_no AS answer_version FROM questions x "
    "JOIN questionnaire_sections s ON s.id = x.section_id "
    "LEFT JOIN LATERAL (SELECT value, version_no FROM answer_versions v "
    "WHERE v.question_id = x.id "
    "ORDER BY version_no DESC LIMIT 1) a ON true "
    "WHERE x.questionnaire_id = :q ORDER BY s.position, x.position"
)


def _question_view(r: TextRow) -> QuestionView:
    return QuestionView(
        r.id,
        r.section,
        r.type,
        r.client_wording,
        r.help_text,
        r.conditional_on_question_id,
        r.prior_year_value,
        r.answer,
        r.answer_version,
        r.linked_request_item_id,
        r.sent_at,
    )


async def view_of(session: AsyncSession, head: TextRow) -> QuestionnaireView:
    rows = (await session.execute(_QUESTIONS, {"q": head.id})).all()
    questions = tuple(_question_view(r) for r in rows)
    return QuestionnaireView(
        head.id,
        head.kind,
        head.title,
        head.status,
        head.due_on,
        sum(1 for q in questions if q.answer_version is not None),
        len(questions),
        head.addressed_to_contact_id,
        questions,
    )


async def questionnaire(ctx: AuthContext, questionnaire_id: UUID) -> QuestionnaireView:
    if ctx.client:
        raise NotFound(SUBJECT)
    async with tenant_session(ctx.tenant) as session:
        head = await head_of(session, questionnaire_id)
    await _engagement(ctx, head.engagement_id, head.work_item_id, READ)
    async with tenant_session(ctx.tenant) as session:
        return await view_of(session, head)


async def _question(ctx: AuthContext, question_id: UUID) -> QuestionView:
    async with tenant_session(ctx.tenant) as session:
        q = (
            await session.execute(
                text("SELECT questionnaire_id FROM questions WHERE id = :id"), {"id": question_id}
            )
        ).scalar_one()
        view = await view_of(session, await head_of(session, q))
    return next(x for x in view.questions if x.id == question_id)


async def questionnaires_of_list(
    ctx: AuthContext, request_list_id: UUID
) -> list[QuestionnaireView]:
    if ctx.client:
        raise NotFound(SUBJECT)
    async with tenant_session(ctx.tenant) as session:
        binder = (
            await session.execute(
                text("SELECT engagement_id, work_item_id FROM request_lists WHERE id = :id"),
                {"id": request_list_id},
            )
        ).first()
        if binder is None:
            raise NotFound("request_list")
    await _engagement(ctx, binder.engagement_id, binder.work_item_id, READ)
    async with tenant_session(ctx.tenant) as session:
        heads: Sequence[TextRow] = (
            await session.execute(
                text(
                    "SELECT id, engagement_id, work_item_id, kind, title, status, due_on, "
                    "addressed_to_contact_id FROM questionnaires WHERE request_list_id = :l "
                    "ORDER BY created_at"
                ),
                {"l": request_list_id},
            )
        ).all()
        return [await view_of(session, h) for h in heads]


@dataclass(frozen=True)
class QuestionnaireSummary:
    """TAX-03's Questions band (T-02-T18): counts and the submission, never the answers."""

    id: UUID
    kind: str
    title: str
    status: str
    answered: int
    total: int
    submitted_at: datetime | None
    submitted_by: UUID | None


async def work_item_questionnaires(
    ctx: AuthContext, engagement_id: UUID, work_item_id: UUID
) -> list[QuestionnaireSummary]:
    """The work item's questionnaires for a firm reader (`questionnaire.read` on it)."""
    if ctx.client:
        raise NotFound(SUBJECT)
    await _engagement(ctx, engagement_id, work_item_id, READ)
    async with tenant_session(ctx.tenant) as session:
        heads = (
            await session.execute(
                text(
                    "SELECT id, engagement_id, work_item_id, kind, title, status, due_on, "
                    "addressed_to_contact_id, submitted_at, submitted_by FROM questionnaires "
                    "WHERE work_item_id = :w ORDER BY created_at, id"
                ),
                {"w": work_item_id},
            )
        ).all()
        out: list[QuestionnaireSummary] = []
        for h in heads:
            view = await view_of(session, h)
            out.append(
                QuestionnaireSummary(
                    h.id,
                    h.kind,
                    h.title,
                    h.status,
                    view.answered,
                    view.total,
                    h.submitted_at,
                    h.submitted_by,
                )
            )
    return out


__all__ = [
    "AlreadyPublished",
    "AlreadySent",
    "ImportRefused",
    "ImportResult",
    "NotPublished",
    "QuestionView",
    "QuestionnaireClosed",
    "QuestionnaireSummary",
    "QuestionnaireView",
    "TemplateView",
    "TextRow",
    "attach_organizer",
    "create_questionnaire",
    "draft_question",
    "head_of",
    "import_template",
    "publish_version",
    "questionnaire",
    "questionnaires_of_list",
    "send_question",
    "templates",
    "view_of",
    "work_item_questionnaires",
]
