"""Questionnaires in the portal (T-02-T22; T-02 §3.5; POR-05; DEC-1370). Amber.

- **What a client person sees**: each questionnaire on a work item their grant covers
  (`portal_questionnaire.read`, `scope_only`), only its sent questions; an inquiry only when they
  are its addressee (INV-4: another client user sees neither it nor its answers). Anything else is
  404, never 403.
- **Autosave** (`portal_questionnaire.answer`): one new answer version per save; `If-Match` names
  the version this save makes (the current one plus one), so a second tab's stale write is 409
  `stale_version` and nothing is lost silently. The answer is checked against the question's type
  and stored as given: client content, rendered as text, never as markup (ADR-052). Organizer
  answers are TRI.
- **Mark as done** (organizer and team questions; every sent question answered) and **submit**
  (an inquiry, by its addressee only): a submitted questionnaire's answers are locked by 0467's
  trigger as well as here.
- Attachments for upload-if-yes answers wait on evidence's upload slot (requests may not import
  evidence): the route stays a stub; the notifications and the portal home's to-do source join
  with their owners' slots.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel._statuses import QuestionnaireStatus
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.engagements.api import contact_ids_of_user
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    authorise,
    engagement_resource,
)
from abacus.modules.requests.questionnaires import (
    QuestionnaireView,
    TextRow,
    head_of,
    view_of,
)

SUBJECT: Final = "questionnaire"
READ: Final = "portal_questionnaire.read"
ANSWER: Final = "portal_questionnaire.answer"
COMPLETE: Final = "portal_questionnaire.complete"
SUBMIT: Final = "portal_questionnaire.submit"
MAX_TEXT: Final = 4000
_COMPLETE = text(
    "UPDATE questionnaires SET status = 'complete', completed_by = :by, "
    "completed_at = abacus_now(), row_version = row_version + 1 WHERE id = :q"
)
_SUBMIT = text(
    "UPDATE questionnaires SET status = 'submitted', submitted_by = :by, "
    "submitted_at = abacus_now(), row_version = row_version + 1 WHERE id = :q"
)


class AnswerStale(DomainConflict):
    code = "stale_version"


class QuestionnaireLocked(DomainConflict):
    code = "questionnaire_closed"


class Incomplete(DomainConflict):
    code = "questionnaire_incomplete"


class AnswerInvalid(DomainInvalid):
    code = "answer_invalid"


async def _visible(ctx: AuthContext, head: TextRow, action: str) -> None:
    """The client person's grant covers the work item, and an inquiry is theirs; else 404."""
    if not ctx.client:
        raise NotFound(SUBJECT)
    try:
        base = await engagement_resource(ctx.tenant, head.engagement_id)
        await authorise(ctx, action, replace(base, work_item_id=head.work_item_id))
    except (Forbidden, NotFound):
        raise NotFound(SUBJECT) from None
    if head.kind == "inquiry" and head.addressed_to_contact_id not in await contact_ids_of_user(
        ctx.tenant, ctx.user_id
    ):
        raise NotFound(SUBJECT)


def _client_view(view: QuestionnaireView) -> QuestionnaireView:
    """Only the questions a person has sent."""
    sent = tuple(q for q in view.questions if q.sent_at is not None)
    return replace(
        view,
        questions=sent,
        total=len(sent),
        answered=sum(1 for q in sent if q.answer_version is not None),
    )


async def portal_questionnaires(ctx: AuthContext) -> list[QuestionnaireView]:
    if not ctx.client:
        raise NotFound(SUBJECT)
    async with tenant_session(ctx.tenant) as session:
        heads = (
            await session.execute(
                text(
                    "SELECT id, engagement_id, work_item_id, kind, title, status, due_on, "
                    "addressed_to_contact_id FROM questionnaires ORDER BY created_at"
                )
            )
        ).all()
    out: list[QuestionnaireView] = []
    for head in heads:
        try:
            await _visible(ctx, head, READ)
        except NotFound:
            continue
        async with tenant_session(ctx.tenant) as session:
            view = _client_view(await view_of(session, head))
        if view.total:
            out.append(view)
    return out


async def portal_questionnaire(
    ctx: AuthContext, questionnaire_id: UUID, *, unanswered: bool, section: str | None
) -> QuestionnaireView:
    async with tenant_session(ctx.tenant) as session:
        head = await head_of(session, questionnaire_id)
    await _visible(ctx, head, READ)
    async with tenant_session(ctx.tenant) as session:
        view = _client_view(await view_of(session, head))
    shown = tuple(
        q
        for q in view.questions
        if (not unanswered or q.answer_version is None)
        and (section is None or q.section == section)
    )
    return replace(view, questions=shown)


def _checked(kind: str, value: object) -> object:
    """The answer as the question's type takes it (code, never a model's reading)."""
    if value is None:
        return None
    if kind in ("yes_no", "upload_if_yes"):
        if isinstance(value, bool):
            return value
    elif kind in ("long_text", "choice"):
        if isinstance(value, str) and len(value) <= MAX_TEXT:
            return value
    elif kind == "amount_group" and isinstance(value, dict):
        amounts = cast(dict[str, object], value)
        try:
            if len(amounts) <= 50 and all(
                len(k) <= 80 and Decimal(str(v)).is_finite() for k, v in amounts.items()
            ):
                return {k: str(v) for k, v in amounts.items()}
        except InvalidOperation:
            pass
    raise AnswerInvalid(facts={"field": "value"})


async def save_answer(
    ctx: AuthContext,
    questionnaire_id: UUID,
    question_id: UUID,
    value: object,
    if_match: int,
) -> tuple[datetime, int]:
    async with tenant_session(ctx.tenant) as session:
        head = await head_of(session, questionnaire_id)
    await _visible(ctx, head, ANSWER)
    async with uow(ctx.tenant) as tx:
        locked = (
            await tx.session.execute(
                text("SELECT status FROM questionnaires WHERE id = :q FOR UPDATE"),
                {"q": questionnaire_id},
            )
        ).scalar_one()
        if locked == QuestionnaireStatus.SUBMITTED or (
            locked == QuestionnaireStatus.COMPLETE and head.kind != "organizer"
        ):
            raise QuestionnaireLocked(facts={"status": str(locked)})
        question = (
            await tx.session.execute(
                text(
                    "SELECT type, sent_at FROM questions WHERE id = :id AND questionnaire_id = :q"
                ),
                {"id": question_id, "q": questionnaire_id},
            )
        ).first()
        if question is None or question.sent_at is None:
            raise NotFound("question")
        current = (
            await tx.session.execute(
                text(
                    "SELECT coalesce(max(version_no), 0) FROM answer_versions "
                    "WHERE question_id = :id"
                ),
                {"id": question_id},
            )
        ).scalar_one()
        if if_match != current + 1:
            raise AnswerStale(facts={"question_id": str(question_id)})
        saved = (
            await tx.session.execute(
                text(
                    "INSERT INTO answer_versions (tenant_id, question_id, value, version_no, "
                    "answered_by) VALUES (:tenant, :id, CAST(:v AS jsonb), :n, :by) "
                    "RETURNING answered_at"
                ),
                {
                    "tenant": ctx.tenant_id,
                    "id": question_id,
                    "v": json.dumps(_checked(question.type, value)),
                    "n": current + 1,
                    "by": ctx.user_id,
                },
            )
        ).scalar_one()
        tx.record(
            "questionnaire.answered",
            target=Target("question", question_id),
            after=Ref(questionnaire=questionnaire_id, version=current + 1),
        )
    return saved, int(current) + 1


async def _close(ctx: AuthContext, questionnaire_id: UUID, action: str) -> QuestionnaireView:
    async with tenant_session(ctx.tenant) as session:
        head = await head_of(session, questionnaire_id)
    await _visible(ctx, head, action)
    submitting = action == SUBMIT
    if submitting != (head.kind == "inquiry"):
        raise QuestionnaireLocked(facts={"kind": str(head.kind)})
    async with uow(ctx.tenant) as tx:
        status = (
            await tx.session.execute(
                text("SELECT status FROM questionnaires WHERE id = :q FOR UPDATE"),
                {"q": questionnaire_id},
            )
        ).scalar_one()
        if status != QuestionnaireStatus.OPEN:
            raise QuestionnaireLocked(facts={"status": str(status)})
        open_questions = (
            await tx.session.execute(
                text(
                    "SELECT count(*) FROM questions x WHERE x.questionnaire_id = :q "
                    "AND x.sent_at IS NOT NULL AND NOT EXISTS (SELECT 1 FROM answer_versions a "
                    "WHERE a.question_id = x.id)"
                ),
                {"q": questionnaire_id},
            )
        ).scalar_one()
        if open_questions and not submitting:
            raise Incomplete(facts={"unanswered": int(open_questions)})
        await tx.session.execute(
            _SUBMIT if submitting else _COMPLETE, {"by": ctx.user_id, "q": questionnaire_id}
        )
        tx.record(
            f"questionnaire.{'submitted' if submitting else 'completed'}",
            target=Target(SUBJECT, questionnaire_id),
        )
    return await portal_questionnaire(ctx, questionnaire_id, unanswered=False, section=None)


async def mark_done(ctx: AuthContext, questionnaire_id: UUID) -> QuestionnaireView:
    return await _close(ctx, questionnaire_id, COMPLETE)


async def submit(ctx: AuthContext, questionnaire_id: UUID) -> QuestionnaireView:
    return await _close(ctx, questionnaire_id, SUBMIT)


__all__ = [
    "AnswerInvalid",
    "AnswerStale",
    "Incomplete",
    "QuestionnaireLocked",
    "mark_done",
    "portal_questionnaire",
    "portal_questionnaires",
    "save_answer",
    "submit",
]
