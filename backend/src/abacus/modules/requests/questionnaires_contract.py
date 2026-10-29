"""Questionnaires v1, the stub (T-02-T02; T-02 §4.3; C5 additive v1.x). Contract:
`docs/contracts/questionnaires.md`.

Organizers (from a published template version, prior-year values by code), team questions and
inquiries (A-04 and A-08 create these with an addressee). Templates are database content imported
by the firm. A person sends every question; the client answers in POR-05 (autosave with If-Match),
uploads where a "yes" asks for a file (through the evidence pipeline, fulfilling the linked
request), marks an organizer done, and an inquiry's addressee submits and locks it.

Firm routes answer 404 for a client principal, 403 for a principal the matrix refuses, 404 with
`questionnaires.v1` off and 501 with it on. Portal routes answer 404 to a firm principal and 404
with the flag off, then 501; the addressee-only check comes with the build (T-02-T16).

Classification: an organizer's answers are TRI; question wording is the firm's (internal).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Header, Path, Query
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from abacus.kernel._flags import QUESTIONNAIRES_V1
from abacus.kernel._statuses import QuestionnaireStatus
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Resource,
    authorise,
    current_context,
    current_member,
)

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


class TemplateImportIn(BaseModel):
    model_config = _frozen()

    upload_id: Annotated[UUID, classified("internal")]


class TemplateImportOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    template_id: Annotated[UUID | None, classified("internal")]
    version: Annotated[int | None, classified("internal")]
    dry_run: Annotated[bool, classified("internal")]
    problems: Annotated[list[str], classified("internal")]


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


async def _stub(ctx: AuthContext, action: str) -> NoReturn:
    if ctx.client:
        raise NotFound("questionnaire")
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))
    if not await flag_enabled(ctx.tenant, QUESTIONNAIRES_V1):
        raise NotFound(QUESTIONNAIRES_V1.name)
    raise NotImplementedYet


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
    errors=(501,),
)
async def import_template_route(
    body: TemplateImportIn, ctx: Ctx, dry_run: Annotated[bool, Query()] = True
) -> TemplateImportOut:
    await _stub(ctx, "questionnaire_template.import")


@questionnaires_router.get(
    "/questionnaire-templates",
    action="questionnaire_template.read",
    response_model=list[QuestionnaireTemplateOut],
    errors=(501,),
)
async def list_templates_route(ctx: Ctx) -> list[QuestionnaireTemplateOut]:
    await _stub(ctx, "questionnaire_template.read")


@questionnaires_router.post(
    "/questionnaire-templates/{template_id}/versions/{version}:publish",
    action="questionnaire_template.publish",
    response_model=QuestionnaireTemplateOut,
    errors=(409, 501),
)
async def publish_template_route(
    template_id: Annotated[UUID, Path()], version: Annotated[int, Path(ge=1)], ctx: Ctx
) -> QuestionnaireTemplateOut:
    await _stub(ctx, "questionnaire_template.publish")


@questionnaires_router.post(
    "/request-lists/{request_list_id}/questionnaires",
    action="questionnaire.create",
    response_model=QuestionnaireOut,
    status_code=201,
    errors=(409, 501),
)
async def attach_organizer_route(
    request_list_id: Annotated[UUID, Path()], body: AttachOrganizerIn, ctx: Ctx
) -> QuestionnaireOut:
    await _stub(ctx, "questionnaire.create")


@questionnaires_router.post(
    "/questionnaires",
    action="questionnaire.create",
    response_model=QuestionnaireOut,
    status_code=201,
    errors=(409, 501),
)
async def create_questionnaire_route(body: QuestionnaireCreateIn, ctx: Ctx) -> QuestionnaireOut:
    await _stub(ctx, "questionnaire.create")


@questionnaires_router.post(
    "/questionnaires/{questionnaire_id}/questions",
    action="questionnaire.ask",
    response_model=QuestionOut,
    status_code=201,
    errors=(409, 501),
)
async def draft_question_route(
    questionnaire_id: QuestionnaireId, body: QuestionCreateIn, ctx: Ctx
) -> QuestionOut:
    await _stub(ctx, "questionnaire.ask")


@questionnaires_router.post(
    "/questions/{question_id}:send",
    action="questionnaire.ask",
    response_model=QuestionOut,
    errors=(409, 501),
)
async def send_question_route(question_id: QuestionId, ctx: Ctx) -> QuestionOut:
    """A person sends it (human-only; G3 met except on intake binders)."""
    await _stub(ctx, "questionnaire.ask")


@questionnaires_router.get(
    "/request-lists/{request_list_id}/questionnaires",
    action="questionnaire.read",
    response_model=list[QuestionnaireOut],
    errors=(501,),
)
async def list_questionnaires_route(
    request_list_id: Annotated[UUID, Path()], ctx: Ctx
) -> list[QuestionnaireOut]:
    await _stub(ctx, "questionnaire.read")


@questionnaires_router.get(
    "/questionnaires/{questionnaire_id}",
    action="questionnaire.read",
    response_model=QuestionnaireOut,
    errors=(501,),
)
async def questionnaire_route(questionnaire_id: QuestionnaireId, ctx: Ctx) -> QuestionnaireOut:
    await _stub(ctx, "questionnaire.read")


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
