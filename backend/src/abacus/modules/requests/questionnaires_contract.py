"""Questionnaires v1, the stub (T-02-T02; T-02 §4.3; C5 additive v1.x). Contract:
`docs/contracts/questionnaires.md`.

Organizers (from a published template version, prior-year values by code), team questions and
inquiries (A-04 and A-08 create these with an addressee). Templates are database content imported
by the firm. A person sends every question; the client answers in POR-05 (autosave with If-Match),
uploads where a "yes" asks for a file (through the evidence pipeline, fulfilling the linked
request), marks an organizer done, and an inquiry's addressee submits and locks it.

Firm routes answer 404 for a client principal, 403 for a principal the matrix refuses and 404
with `questionnaires.v1` off; they are live since T-02-T16. Portal routes answer 404 to a firm
principal and 404 with the flag off, then 501 until T-02-T22 (the addressee-only check with it).

Classification: an organizer's answers are TRI; question wording is the firm's (internal).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, NoReturn, cast
from uuid import UUID

from fastapi import Depends, Header, Path, Query, Request
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from abacus.kernel._flags import QUESTIONNAIRES_V1
from abacus.kernel._statuses import QuestionnaireStatus
from abacus.kernel.classification import classified
from abacus.kernel.errors import DomainTooLarge, NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Resource,
    authorise,
    current_context,
    current_member,
)
from abacus.modules.requests import questionnaires as svc
from abacus.modules.requests.questionnaire_templates import MAX_BYTES

Ctx = Annotated[AuthContext, Depends(current_context)]
Member = Annotated[AuthContext, Depends(current_member)]
QuestionnaireId = Annotated[UUID, Path()]
QuestionId = Annotated[UUID, Path()]
IfMatch = Annotated[int, Header(alias="If-Match", ge=1)]
Kind = Literal["organizer", "team_questions", "inquiry"]
QuestionType = Literal["yes_no", "amount_group", "upload_if_yes", "long_text", "choice"]


def _frozen() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


class QuestionnaireTemplateOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("internal")]
    current_version: Annotated[int | None, classified("internal")]
    draft_version: Annotated[int | None, classified("internal")]


class TemplateImportOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    template_id: Annotated[UUID | None, classified("internal")]
    version: Annotated[int | None, classified("internal")]
    dry_run: Annotated[bool, classified("internal")]
    problems: Annotated[list[str], classified("internal")]
    # T-02-T16 (additive): the dry run's question keys against the current published version.
    added: Annotated[list[str], classified("internal")] = Field(default_factory=list[str])
    changed: Annotated[list[str], classified("internal")] = Field(default_factory=list[str])
    removed: Annotated[list[str], classified("internal")] = Field(default_factory=list[str])


class QuestionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    section: Annotated[str, classified("internal")]
    type: Annotated[QuestionType, classified("internal")]
    client_wording: Annotated[str, classified("internal")]
    help_text: Annotated[str | None, classified("internal")]
    conditional_on_question_id: Annotated[UUID | None, classified("internal")]
    prior_year_value: Annotated[JsonValue | None, classified("restricted", tri=True)]
    answer: Annotated[JsonValue | None, classified("restricted", tri=True)]
    answer_version: Annotated[int | None, classified("internal")]
    linked_request_item_id: Annotated[UUID | None, classified("internal")]
    sent_at: Annotated[datetime | None, classified("confidential")]


class QuestionnaireOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    kind: Annotated[Kind, classified("internal")]
    title: Annotated[str, classified("confidential")]
    status: Annotated[QuestionnaireStatus, classified("internal")]
    due_on: Annotated[date | None, classified("internal")]
    answered: Annotated[int, classified("internal")]
    total: Annotated[int, classified("internal")]
    addressed_to_contact_id: Annotated[UUID | None, classified("internal")]
    questions: Annotated[list[QuestionOut], classified("restricted", tri=True)]


class AttachOrganizerIn(BaseModel):
    model_config = _frozen()

    template_version_id: Annotated[UUID, classified("internal")]
    due_on: Annotated[date | None, classified("internal")] = None


class QuestionnaireCreateIn(BaseModel):
    model_config = _frozen()

    kind: Annotated[Literal["team_questions", "inquiry"], classified("internal")]
    work_item_id: Annotated[UUID, classified("internal")]
    title: Annotated[str, Field(min_length=1, max_length=200), classified("confidential")]
    addressed_to_contact_id: Annotated[UUID | None, classified("internal")] = None
    due_on: Annotated[date | None, classified("internal")] = None


class QuestionCreateIn(BaseModel):
    model_config = _frozen()

    section: Annotated[str, Field(min_length=1, max_length=80), classified("internal")]
    type: Annotated[QuestionType, classified("internal")]
    client_wording: Annotated[str, Field(min_length=1, max_length=2000), classified("internal")]
    help_text: Annotated[str | None, Field(max_length=2000), classified("internal")] = None
    linked_request_item_id: Annotated[UUID | None, classified("internal")] = None


class AnswerIn(BaseModel):
    model_config = _frozen()

    value: Annotated[JsonValue, classified("restricted", tri=True)]


class AnswerSavedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    saved_at: Annotated[datetime, classified("internal")]
    version: Annotated[int, classified("internal")]


class AttachmentIn(BaseModel):
    model_config = _frozen()

    upload_id: Annotated[UUID, classified("internal")]


questionnaires_router = AbacusRouter(prefix="/v1", tags=["questionnaires"])
portal_questionnaires_router = AbacusRouter(prefix="/v1/portal", tags=["portal"])


async def _gate(ctx: AuthContext, action: str) -> None:
    """Client 404, the action at the firm (403), then the flag (404); the service checks the
    engagement."""
    if ctx.client:
        raise NotFound("questionnaire")
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))
    if not await flag_enabled(ctx.tenant, QUESTIONNAIRES_V1):
        raise NotFound(QUESTIONNAIRES_V1.name)


def _question_out(q: svc.QuestionView) -> QuestionOut:
    return QuestionOut(
        id=q.id,
        section=q.section,
        type=cast(QuestionType, q.type),
        client_wording=q.client_wording,
        help_text=q.help_text,
        conditional_on_question_id=q.conditional_on_question_id,
        prior_year_value=cast(JsonValue, q.prior_year_value),
        answer=cast(JsonValue, q.answer),
        answer_version=q.answer_version,
        linked_request_item_id=q.linked_request_item_id,
        sent_at=q.sent_at,
    )


def _out(v: svc.QuestionnaireView) -> QuestionnaireOut:
    return QuestionnaireOut(
        id=v.id,
        kind=cast(Kind, v.kind),
        title=v.title,
        status=QuestionnaireStatus(v.status),
        due_on=v.due_on,
        answered=v.answered,
        total=v.total,
        addressed_to_contact_id=v.addressed_to_contact_id,
        questions=[_question_out(q) for q in v.questions],
    )


def _template_out(t: svc.TemplateView) -> QuestionnaireTemplateOut:
    return QuestionnaireTemplateOut(
        id=t.id, name=t.name, current_version=t.current_version, draft_version=t.draft_version
    )


async def _body(request: Request) -> bytes:
    data = bytearray()
    async for chunk in request.stream():
        data += chunk
        if len(data) > MAX_BYTES:
            raise DomainTooLarge(facts={"limit": MAX_BYTES})
    return bytes(data)


async def _portal_stub(ctx: AuthContext) -> NoReturn:
    if not ctx.client:
        raise NotFound("questionnaire")
    if not await flag_enabled(ctx.tenant, QUESTIONNAIRES_V1):
        raise NotFound(QUESTIONNAIRES_V1.name)
    raise NotImplementedYet


@questionnaires_router.post(
    "/questionnaire-templates:import",
    action="questionnaire_template.import",
    response_model=TemplateImportOut,
    status_code=201,
    errors=(),
)
async def questionnaire_import_template_route(
    request: Request,
    ctx: Ctx,
    name: Annotated[str, Query(min_length=1, max_length=200)],
    format: Annotated[Literal["csv", "xlsx", "json"], Query()] = "csv",
    dry_run: Annotated[bool, Query()] = True,
) -> TemplateImportOut:
    """A template file as the raw body (no multipart; DEC-1369), parsed in the isolated child.
    The dry run answers problems and the diff and stores nothing (T-02-T16)."""
    await _gate(ctx, "questionnaire_template.import")
    found = await svc.import_template(ctx, name, await _body(request), format, dry_run=dry_run)
    return TemplateImportOut(
        template_id=found.template_id,
        version=found.version,
        dry_run=found.dry_run,
        problems=list(found.problems),
        added=list(found.changes.added) if found.changes else [],
        changed=list(found.changes.changed) if found.changes else [],
        removed=list(found.changes.removed) if found.changes else [],
    )


@questionnaires_router.get(
    "/questionnaire-templates",
    action="questionnaire_template.read",
    response_model=list[QuestionnaireTemplateOut],
    errors=(),
)
async def questionnaire_list_templates_route(ctx: Ctx) -> list[QuestionnaireTemplateOut]:
    await _gate(ctx, "questionnaire_template.read")
    return [_template_out(t) for t in await svc.templates(ctx)]


@questionnaires_router.post(
    "/questionnaire-templates/{template_id}/versions/{version}:publish",
    action="questionnaire_template.publish",
    response_model=QuestionnaireTemplateOut,
    errors=(409,),
)
async def publish_template_route(
    template_id: Annotated[UUID, Path()], version: Annotated[int, Path(ge=1)], ctx: Ctx
) -> QuestionnaireTemplateOut:
    """A person publishes the version (fresh MFA). 409 `version_published`."""
    await _gate(ctx, "questionnaire_template.publish")
    return _template_out(await svc.publish_version(ctx, template_id, version))


@questionnaires_router.post(
    "/request-lists/{request_list_id}/questionnaires",
    action="questionnaire.create",
    response_model=QuestionnaireOut,
    status_code=201,
    errors=(409,),
)
async def attach_organizer_route(
    request_list_id: Annotated[UUID, Path()], body: AttachOrganizerIn, ctx: Ctx
) -> QuestionnaireOut:
    """An organizer from a published version, prior-year values by code. 409
    `version_not_published`."""
    await _gate(ctx, "questionnaire.create")
    found = await svc.attach_organizer(ctx, request_list_id, body.template_version_id, body.due_on)
    return _out(found)


@questionnaires_router.post(
    "/questionnaires",
    action="questionnaire.create",
    response_model=QuestionnaireOut,
    status_code=201,
    errors=(409,),
)
async def create_questionnaire_route(body: QuestionnaireCreateIn, ctx: Ctx) -> QuestionnaireOut:
    """A-04 and A-08's team questions and inquiries (an inquiry names its addressee)."""
    await _gate(ctx, "questionnaire.create")
    found = await svc.create_questionnaire(
        ctx,
        kind=body.kind,
        work_item_id=body.work_item_id,
        title=body.title,
        addressed_to_contact_id=body.addressed_to_contact_id,
        due_on=body.due_on,
    )
    return _out(found)


@questionnaires_router.post(
    "/questionnaires/{questionnaire_id}/questions",
    action="questionnaire.ask",
    response_model=QuestionOut,
    status_code=201,
    errors=(409,),
)
async def draft_question_route(
    questionnaire_id: QuestionnaireId, body: QuestionCreateIn, ctx: Ctx
) -> QuestionOut:
    """A team question drafted in an open questionnaire. 409 `questionnaire_closed`."""
    await _gate(ctx, "questionnaire.ask")
    found = await svc.draft_question(
        ctx,
        questionnaire_id,
        section=body.section,
        type_=body.type,
        client_wording=body.client_wording,
        help_text=body.help_text,
        linked_request_item_id=body.linked_request_item_id,
    )
    return _question_out(found)


@questionnaires_router.post(
    "/questions/{question_id}:send",
    action="questionnaire.ask",
    response_model=QuestionOut,
    errors=(409,),
)
async def send_question_route(question_id: QuestionId, ctx: Ctx) -> QuestionOut:
    """A person sends it (human-only). 409 `question_sent`."""
    await _gate(ctx, "questionnaire.ask")
    return _question_out(await svc.send_question(ctx, question_id))


@questionnaires_router.get(
    "/request-lists/{request_list_id}/questionnaires",
    action="questionnaire.read",
    response_model=list[QuestionnaireOut],
    errors=(),
)
async def list_questionnaires_route(
    request_list_id: Annotated[UUID, Path()], ctx: Ctx
) -> list[QuestionnaireOut]:
    await _gate(ctx, "questionnaire.read")
    return [_out(v) for v in await svc.questionnaires_of_list(ctx, request_list_id)]


@questionnaires_router.get(
    "/questionnaires/{questionnaire_id}",
    action="questionnaire.read",
    response_model=QuestionnaireOut,
    errors=(),
)
async def questionnaire_route(questionnaire_id: QuestionnaireId, ctx: Ctx) -> QuestionnaireOut:
    await _gate(ctx, "questionnaire.read")
    return _out(await svc.questionnaire(ctx, questionnaire_id))


@portal_questionnaires_router.get(
    "/questionnaires",
    action="portal_questionnaire.read",
    response_model=list[QuestionnaireOut],
    errors=(501,),
)
async def portal_questionnaires_route(ctx: Member) -> list[QuestionnaireOut]:
    await _portal_stub(ctx)


@portal_questionnaires_router.get(
    "/questionnaires/{questionnaire_id}",
    action="portal_questionnaire.read",
    response_model=QuestionnaireOut,
    errors=(501,),
)
async def portal_questionnaire_route(
    questionnaire_id: QuestionnaireId,
    ctx: Member,
    show: Annotated[Literal["all", "unanswered"] | None, Query(alias="filter")] = None,
    section: Annotated[str | None, Query(max_length=80)] = None,
) -> QuestionnaireOut:
    await _portal_stub(ctx)


@portal_questionnaires_router.put(
    "/questionnaires/{questionnaire_id}/answers/{question_id}",
    action="portal_questionnaire.answer",
    response_model=AnswerSavedOut,
    errors=(409, 501),
)
async def portal_answer_route(
    questionnaire_id: QuestionnaireId,
    question_id: QuestionId,
    body: AnswerIn,
    ctx: Member,
    if_match: IfMatch,
) -> AnswerSavedOut:
    """Autosave (409 `stale_version` when the answer moved)."""
    await _portal_stub(ctx)


@portal_questionnaires_router.post(
    "/questionnaires/{questionnaire_id}/questions/{question_id}/attachments",
    action="portal_questionnaire.answer",
    response_model=AnswerSavedOut,
    status_code=201,
    errors=(501,),
)
async def portal_attachment_route(
    questionnaire_id: QuestionnaireId, question_id: QuestionId, body: AttachmentIn, ctx: Member
) -> AnswerSavedOut:
    await _portal_stub(ctx)


@portal_questionnaires_router.post(
    "/questionnaires/{questionnaire_id}:mark-done",
    action="portal_questionnaire.complete",
    response_model=QuestionnaireOut,
    errors=(409, 501),
)
async def portal_mark_done_route(
    questionnaire_id: QuestionnaireId, ctx: Member
) -> QuestionnaireOut:
    await _portal_stub(ctx)


@portal_questionnaires_router.post(
    "/questionnaires/{questionnaire_id}:submit",
    action="portal_questionnaire.submit",
    response_model=QuestionnaireOut,
    errors=(409, 501),
)
async def portal_submit_route(questionnaire_id: QuestionnaireId, ctx: Member) -> QuestionnaireOut:
    """An inquiry's addressee submits and locks it."""
    await _portal_stub(ctx)
