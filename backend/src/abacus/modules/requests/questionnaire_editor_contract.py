"""Questionnaires and answer effects, the C5 additive stub (T-03-T02; T-03 §4.3; DEC-2201).
Contract: `docs/contracts/questionnaires.md` §"T-03 additive"; screen BND-03 (a to e) and KNW-01's
"Organizers" category; consumers T-02's POR-05 (unchanged: no field of the v1 routes moves),
N-04 (the effect slot) and T-08 (roll-forward through `questionnaire_from_template`).

Staff edit a binder's organizer (structure, client wording, logic and effect rules) in one atomic
save with If-Match (412 `stale_version`) and a dry run that lists every client-visible change and
every effect it would fire; an answered question keeps its type and is retired, never deleted. A
template is drafted from its current version (one draft at a time), published by its owner for a
tax year with fresh MFA, and never changes after. The client preview is the portal serializer's
DTO, so no firm-internal field (`internal_helper`, effect rules, tags) can reach it.

Every route answers, in order: a client principal 404 (the client answers in POR-05 through T-02's
portal routes); the matrix action at the firm (the service narrows to the binder's engagement or
the template's owner); 404 with `questionnaires.editor` off. Answers are tax return information
(`tri`); wording is the firm's (internal).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from abacus.kernel._flags import QUESTIONNAIRES_EDITOR
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import flag_enabled
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Forbidden,
    Resource,
    allowed_actions,
    authorise,
    current_context,
)

Ctx = Annotated[AuthContext, Depends(current_context)]
IfMatch = Annotated[int, Header(alias="If-Match", ge=1)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
Internal = classified("internal")
Tri = classified("restricted", tri=True)
Name = Annotated[str, classified("confidential")]
OptName = Annotated[str | None, classified("confidential")]  # keeps the tag on an optional field
Key = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,39}(\.[a-z][a-z0-9_]{0,39})?$"), Internal]
OptKey = Annotated[
    str | None, Field(pattern=r"^[a-z][a-z0-9_]{0,39}(\.[a-z][a-z0-9_]{0,39})?$"), Internal
]

EditorQuestionType = Literal["yes_no", "amount", "choice", "date", "text", "upload_if_yes"]
FormFamily = Literal["1040", "1041", "1065", "1120s", "1120", "990", "706"]
VersionStatus = Literal["draft", "published", "superseded", "discarded"]
OwnerKind = Literal["binder", "template_version"]
EffectKind = Literal[
    "request_item_created",
    "review_point_raised",
    "internal_review_flagged",
    "upload_routed_to_notices",
    "pending_handler",
]
RuleKind = Literal[
    "create_request_item", "raise_review_point", "flag_internal_review", "route_upload_to_notices"
]
ChangeKind = Literal["added", "edited", "reordered", "retired", "wording", "required", "logic"]
EditorAction = Literal[
    "questionnaire.edit",
    "questionnaire_template.draft",
    "questionnaire_template.publish",
    "questionnaire_template.assign_owner",
]
Actions = Annotated[list[EditorAction], Internal]


def _frozen() -> ConfigDict:
    return ConfigDict(frozen=True)


def _strict() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


# --- rules ----------------------------------------------------------------------------------


class ShowWhen(BaseModel):
    """Equality on a top-level yes_no or choice parent only; depth 1, no cycles (422
    `logic_invalid`)."""

    model_config = _strict()

    parent_key: Key
    equals: Annotated[str, Field(max_length=120), Internal]


class EffectRule(BaseModel):
    """One deterministic rule ("Yes → create the request 'estimated payment confirmations'").
    Evaluated by code; the agent never fires an effect."""

    model_config = _strict()

    key: Key
    kind: Annotated[RuleKind, Internal]
    when_equals: Annotated[str, Field(max_length=120), Internal]
    title: Annotated[str, Field(min_length=1, max_length=200), Internal]
    detail: Annotated[str | None, Field(max_length=500), Internal] = None


# --- reads ----------------------------------------------------------------------------------


class AnswerSummaryOut(BaseModel):
    """ "Claire Feld · Aug 20: Yes"."""

    model_config = _frozen()

    answer_id: Annotated[UUID, Internal]
    contact_name: Name
    answered_on: Annotated[date, Internal]
    value: Annotated[JsonValue, Tri]
    note: Annotated[str | None, Tri] = (
        None  # "(answered through an issue question; issue resolved)"
    )


class AppliedEffectOut(BaseModel):
    """One `answer_effects` row: the banner "Raised review point '…' · open in TAX-06" and the
    helper "this answer created the open request …"."""

    model_config = _frozen()

    id: Annotated[UUID, Internal]
    rule_key: Key
    kind: Annotated[EffectKind, Internal]
    target_type: Annotated[str | None, Internal] = None
    target_id: Annotated[UUID | None, Internal] = None
    title: Annotated[str, Internal]
    actor_kind: Annotated[Literal["system", "human"], Internal]
    actor_name: OptName = None
    created_at: Annotated[datetime, Internal]


class EditorQuestionOut(BaseModel):
    model_config = _frozen()

    id: Annotated[UUID, Internal]
    key: Key  # "q5", "q5.f2"
    section_key: Key
    parent_key: OptKey = None
    position: Annotated[int, Field(ge=0), Internal]
    type: Annotated[EditorQuestionType, Internal]
    client_wording: Annotated[str, Internal]
    internal_helper: Annotated[str | None, Internal] = None  # never in the client preview
    required: Annotated[bool, Internal]
    show_when: Annotated[ShowWhen | None, Internal] = None
    choices: Annotated[list[str], Internal] = Field(default_factory=list[str])
    amount_parts: Annotated[list[str], Internal] = Field(default_factory=list[str])
    effect_rules: Annotated[list[EffectRule], Internal] = Field(default_factory=list[EffectRule])
    answer: Annotated[AnswerSummaryOut | None, classified("confidential")] = None
    triggered: Annotated[bool | None, Internal] = None  # a follow-up: "Not triggered"
    effects: Annotated[list[AppliedEffectOut], Internal] = Field(
        default_factory=list[AppliedEffectOut]
    )
    answered: Annotated[bool, Internal]  # type locked, retire not delete


class SectionOut(BaseModel):
    model_config = _frozen()

    id: Annotated[UUID, Internal]
    key: Key
    title: Annotated[str, Internal]
    position: Annotated[int, Field(ge=0), Internal]
    question_count: Annotated[int, Internal]


class EditorCountsOut(BaseModel):
    """The rail: "Answered 8 of 9", the Logic band's "4 conditional follow-ups" and the amber
    "1 review point raised"."""

    model_config = _frozen()

    questions: Annotated[int, Internal]
    answered: Annotated[int, Internal]
    conditional_follow_ups: Annotated[int, Internal]
    review_points_raised: Annotated[int, Internal]
    requests_created: Annotated[int, Internal]
    last_answer_on: Annotated[date | None, Internal] = None
    last_answer_by: OptName = None


class OrganizerTemplateRefOut(BaseModel):
    """ "1040 organizer v6"."""

    model_config = _frozen()

    template_id: Annotated[UUID, Internal]
    name: Annotated[str, Internal]
    version: Annotated[int, Internal]
    version_id: Annotated[UUID, Internal]
    applies_to_tax_year: Annotated[int | None, Internal] = None


class QuestionnaireEditorOut(BaseModel):
    model_config = _frozen()

    id: Annotated[UUID, Internal]
    owner_kind: Annotated[OwnerKind, Internal]
    title: Name
    binder_id: Annotated[UUID | None, Internal] = None
    template: Annotated[OrganizerTemplateRefOut | None, classified("internal")] = None
    sections: Annotated[list[SectionOut], Internal]
    questions: Annotated[list[EditorQuestionOut], Tri]
    counts: Annotated[EditorCountsOut, classified("internal")]
    banner: Annotated[str | None, Internal] = None  # template mode: "Editing template … v6 — …"
    row_version: Annotated[int, Internal]
    allowed_actions: Actions


class BinderQuestionnaireOut(BaseModel):
    """BND-02's Questions tab badge and the link into BND-03."""

    model_config = _frozen()

    binder_id: Annotated[UUID, Internal]
    questionnaire_id: Annotated[UUID | None, Internal] = None
    questions: Annotated[int, Internal]
    answered: Annotated[int, Internal]
    template: Annotated[OrganizerTemplateRefOut | None, classified("internal")] = None


# --- the atomic save ------------------------------------------------------------------------


class QuestionIn(BaseModel):
    """A question as the editor sends it. `id` null is a new question; a missing existing id is
    a retire (answered) or a delete (never answered)."""

    model_config = _strict()

    id: Annotated[UUID | None, Internal] = None
    key: Key
    section_key: Key
    parent_key: OptKey = None
    type: Annotated[EditorQuestionType, Internal]
    client_wording: Annotated[str, Field(min_length=1, max_length=2000), Internal]
    internal_helper: Annotated[str | None, Field(max_length=500), Internal] = None
    required: Annotated[bool, Internal] = False
    show_when: Annotated[ShowWhen | None, Internal] = None
    choices: Annotated[list[str], Field(max_length=20), Internal] = Field(
        default_factory=list[str]
    )
    amount_parts: Annotated[list[str], Field(max_length=8), Internal] = Field(
        default_factory=list[str]
    )
    effect_rules: Annotated[list[EffectRule], Field(max_length=10), Internal] = Field(
        default_factory=list[EffectRule]
    )


class SectionIn(BaseModel):
    model_config = _strict()

    id: Annotated[UUID | None, Internal] = None
    key: Key
    title: Annotated[str, Field(min_length=1, max_length=120), Internal]


class QuestionnaireSaveIn(BaseModel):
    """The whole edited structure in display order. 409 `question_answered` (a type change on an
    answered question), 409 `version_published`, 422 `client_wording_required` and
    `logic_invalid`; 412 `stale_version` from If-Match."""

    model_config = _strict()

    sections: Annotated[list[SectionIn], Field(max_length=40), Internal]
    questions: Annotated[list[QuestionIn], Field(max_length=400), Internal]
    change_summary: Annotated[str | None, Field(max_length=500), Internal] = None


class ClientVisibleChangeOut(BaseModel):
    model_config = _frozen()

    question_key: Key
    kind: Annotated[ChangeKind, Internal]
    before: Annotated[str | None, Internal] = None
    after: Annotated[str | None, Internal] = None


class EffectToFireOut(BaseModel):
    model_config = _frozen()

    question_key: Key
    rule_key: Key
    kind: Annotated[RuleKind, Internal]
    title: Annotated[str, Internal]


class QuestionnaireSaveOut(BaseModel):
    """`dry_run=true` returns the lists with `saved` false; the confirm then saves."""

    model_config = _frozen()

    saved: Annotated[bool, Internal]
    client_visible_changes: Annotated[list[ClientVisibleChangeOut], Internal]
    effects_to_fire: Annotated[list[EffectToFireOut], Internal]
    questionnaire: Annotated[QuestionnaireEditorOut | None, classified("confidential")] = None


# --- the client preview ---------------------------------------------------------------------


class PreviewQuestionOut(BaseModel):
    """Exactly the portal question DTO (POR-05's renderer, lifted into packages/ui by T-03-T09):
    wording, type, choices, the "Required" marker and answers. No tag, banner, helper or rule."""

    model_config = _frozen()

    key: Key
    parent_key: OptKey = None
    type: Annotated[EditorQuestionType, Internal]
    client_wording: Annotated[str, Internal]
    required: Annotated[bool, Internal]
    choices: Annotated[list[str], Internal] = Field(default_factory=list[str])
    amount_parts: Annotated[list[str], Internal] = Field(default_factory=list[str])
    visible: Annotated[bool, Internal]
    answer: Annotated[JsonValue | None, Tri] = None


class ClientPreviewOut(BaseModel):
    model_config = _frozen()

    firm_name: Name
    questions: Annotated[list[PreviewQuestionOut], Tri]


# --- templates ------------------------------------------------------------------------------


class OrganizerTemplateVersionOut(BaseModel):
    model_config = _frozen()

    id: Annotated[UUID, Internal]
    version: Annotated[int, Field(ge=1), Internal]
    status: Annotated[VersionStatus, Internal]
    applies_to_tax_year: Annotated[int | None, Internal] = None
    questionnaire_id: Annotated[UUID | None, Internal] = None  # an imported version has none
    drafted_by_name: Name
    published_by_name: OptName = None
    published_at: Annotated[datetime | None, Internal] = None
    change_summary: Annotated[str | None, Internal] = None


class TemplateDetailOut(BaseModel):
    """KNW-01's "Organizers" rows and BND-03 d's header."""

    model_config = _frozen()

    id: Annotated[UUID, Internal]
    key: OptKey = None  # a T-02 import has neither until the firm sets them
    name: Annotated[str, Internal]
    form_family: Annotated[FormFamily | None, Internal] = None
    owner_id: Annotated[UUID | None, Internal] = None
    owner_name: OptName = None
    versions: Annotated[list[OrganizerTemplateVersionOut], Internal]
    allowed_actions: Actions


class TemplateOwnerIn(BaseModel):
    model_config = _strict()

    owner_id: Annotated[UUID, Internal]  # a partner member (`owner_of_target`)


class TemplateDraftIn(BaseModel):
    model_config = _strict()

    change_summary: Annotated[str | None, Field(max_length=500), Internal] = None


class QuestionDiffOut(BaseModel):
    model_config = _frozen()

    question_key: Key
    kind: Annotated[Literal["added", "removed", "changed"], Internal]
    before: Annotated[str | None, Internal] = None
    after: Annotated[str | None, Internal] = None


class TemplateDiffOut(BaseModel):
    model_config = _frozen()

    version: Annotated[int, Internal]
    against: Annotated[int, Internal]
    changes: Annotated[list[QuestionDiffOut], Internal]


# --- gate -----------------------------------------------------------------------------------


async def _gate(ctx: AuthContext, action: str) -> None:
    if ctx.client:
        raise NotFound("questionnaire")
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))
    if not await flag_enabled(ctx.tenant, QUESTIONNAIRES_EDITOR):
        raise NotFound(QUESTIONNAIRES_EDITOR.name)


async def _gate_either(ctx: AuthContext, binder_action: str, template_action: str) -> None:
    """A questionnaire route serves a binder's organizer and a template's. Either action passes
    this firm-level gate; the service then checks the exact one for what the id turns out to be
    (a firm admin drafts templates and holds no engagement role, DEC-20)."""
    if ctx.client:
        raise NotFound("questionnaire")
    try:
        await authorise(ctx, binder_action, Resource.firm(ctx.tenant_id))
    except Forbidden:
        await authorise(ctx, template_action, Resource.firm(ctx.tenant_id))
    if not await flag_enabled(ctx.tenant, QUESTIONNAIRES_EDITOR):
        raise NotFound(QUESTIONNAIRES_EDITOR.name)


def _template_ref_out(found: object) -> OrganizerTemplateRefOut | None:
    from abacus.modules.requests.questionnaire_editor import TemplateRef

    if found is None:
        return None
    t = cast(TemplateRef, found)
    return OrganizerTemplateRefOut(
        template_id=t.template_id,
        name=t.name,
        version=t.version,
        version_id=t.version_id,
        applies_to_tax_year=t.applies_to_tax_year or t.from_year,
    )


async def _editor_actions(ctx: AuthContext, found: object) -> list[EditorAction]:
    """What this person may do here: the editor's Save and, on a template, Publish… for its owner
    alone (T-03 US-2.2). The route still checks each act."""
    from abacus.modules.requests.organizer_lifecycle import detail
    from abacus.modules.requests.questionnaire_editor import Editor

    e = cast(Editor, found)
    if e.owner_kind == "binder":
        return ["questionnaire.edit"]
    if e.template is None or e.template.status != "draft":
        return []
    actions: list[EditorAction] = ["questionnaire_template.draft"]
    owner = (await detail(ctx, e.template.template_id)).owner_id
    if owner == ctx.user_id:
        actions.append("questionnaire_template.publish")
    return actions


def _version_out(v: object) -> OrganizerTemplateVersionOut:
    from abacus.modules.requests.organizer_lifecycle import VersionView

    found = cast(VersionView, v)
    return OrganizerTemplateVersionOut(
        id=found.id,
        version=found.version,
        status=cast(VersionStatus, found.status),
        applies_to_tax_year=found.applies_to_tax_year,
        questionnaire_id=found.questionnaire_id,
        drafted_by_name=found.drafted_by_name,
        published_by_name=found.published_by_name,
        published_at=found.published_at,
        change_summary=found.change_summary,
    )


async def _detail_out(ctx: AuthContext, found: object) -> TemplateDetailOut:
    from abacus.modules.requests.organizer_lifecycle import TemplateDetail

    t = cast(TemplateDetail, found)
    resource = Resource.firm(ctx.tenant_id)
    actions = set(
        await allowed_actions(
            ctx,
            resource,
            ("questionnaire_template.draft", "questionnaire_template.assign_owner"),
        )
    )
    if t.owner_id == ctx.user_id and any(v.status == "draft" for v in t.versions):
        actions.add("questionnaire_template.publish")
    return TemplateDetailOut(
        id=t.id,
        key=t.key,
        name=t.name,
        form_family=cast(FormFamily | None, t.form_family),
        owner_id=t.owner_id,
        owner_name=t.owner_name,
        versions=[_version_out(v) for v in t.versions],
        allowed_actions=cast(list[EditorAction], sorted(actions)),
    )


def _answer_out(q: object) -> AnswerSummaryOut | None:
    from abacus.modules.requests.questionnaire_editor import EditorQuestion

    found = cast(EditorQuestion, q)
    if found.answer_id is None or found.answered_on is None:
        return None
    return AnswerSummaryOut(
        answer_id=found.answer_id,
        contact_name=found.answered_by_name or "",
        answered_on=found.answered_on,
        value=found.answer_value,
    )


def _editor_out(found: object, actions: list[EditorAction]) -> QuestionnaireEditorOut:
    from abacus.modules.requests.questionnaire_editor import Editor

    e = cast(Editor, found)
    counts = e.counts()
    return QuestionnaireEditorOut(
        id=e.id,
        owner_kind=cast(OwnerKind, e.owner_kind),
        title=e.title,
        binder_id=e.binder_id,
        template=_template_ref_out(e.template),
        sections=[
            SectionOut(
                id=sid,
                key=key,
                title=title,
                position=pos,
                question_count=sum(1 for q in e.questions if q.section_key == key),
            )
            for sid, key, title, pos in e.sections
        ],
        questions=[
            EditorQuestionOut(
                id=q.id,
                key=q.key,
                section_key=q.section_key,
                parent_key=q.parent_key,
                position=q.position,
                type=cast(EditorQuestionType, q.type),
                client_wording=q.client_wording,
                internal_helper=q.internal_helper,
                required=q.required,
                show_when=ShowWhen.model_validate(q.show_when) if q.show_when else None,
                choices=q.choices,
                amount_parts=q.amount_parts,
                effect_rules=[EffectRule.model_validate(r) for r in q.effect_rules],
                answer=_answer_out(q),
                triggered=None,
                effects=[
                    AppliedEffectOut(
                        id=effect["id"],
                        rule_key=effect["rule_key"],
                        kind=effect["kind"],
                        target_type=effect["target_type"],
                        target_id=effect["target_id"],
                        title=next(
                            (
                                str(r.get("title"))
                                for r in q.effect_rules
                                if r.get("key") == effect["rule_key"]
                            ),
                            effect["rule_key"],
                        ),
                        actor_kind=effect["actor_kind"],
                        actor_name=effect["actor_name"],
                        created_at=effect["at"],
                    )
                    for effect in q.effects
                ],
                answered=q.answered,
            )
            for q in e.questions
        ],
        counts=EditorCountsOut(
            questions=counts["questions"],
            answered=counts["answered"],
            conditional_follow_ups=counts["conditional_follow_ups"],
            review_points_raised=counts["review_points_raised"],
            requests_created=counts["requests_created"],
            last_answer_on=counts["last_answer_on"],
            last_answer_by=next(
                (
                    q.answered_by_name
                    for q in e.questions
                    if q.answered_by == counts["last_answer_by"] and q.answered_by_name
                ),
                None,
            ),
        ),
        banner=e.banner(),
        row_version=e.row_version,
        allowed_actions=actions,
    )


questionnaire_editor_router = AbacusRouter(prefix="/v1", tags=["questionnaires"])
_Q = "/questionnaires/{questionnaire_id}"
_T = "/questionnaire-templates/{template_id}"


@questionnaire_editor_router.get(
    "/binders/{binder_id}/questionnaire",
    action="questionnaire.read",
    response_model=BinderQuestionnaireOut,
    errors=(501,),
)
async def binder_questionnaire_route(binder_id: UUID, ctx: Ctx) -> BinderQuestionnaireOut:
    await _gate(ctx, "questionnaire.read")
    from abacus.modules.requests import questionnaire_editor

    found = await questionnaire_editor.for_binder(ctx, binder_id)
    if found is None:
        return BinderQuestionnaireOut(binder_id=binder_id, questions=0, answered=0)
    counts = found.counts()
    return BinderQuestionnaireOut(
        binder_id=binder_id,
        questionnaire_id=found.id,
        questions=counts["questions"],
        answered=counts["answered"],
        template=_template_ref_out(found.template),
    )


@questionnaire_editor_router.get(
    f"{_Q}/editor",
    action="questionnaire.read",
    response_model=QuestionnaireEditorOut,
    errors=(501,),
)
async def questionnaire_editor_route(questionnaire_id: UUID, ctx: Ctx) -> QuestionnaireEditorOut:
    """Sections, questions, follow-ups, logic, effect rules, answers, the effect log and counts.
    T-02's `GET /v1/questionnaires/{id}` keeps its v1 shape for POR-05's consumers (DEC-2201)."""
    await _gate_either(ctx, "questionnaire.read", "questionnaire_template.read")
    from abacus.modules.requests import questionnaire_editor

    found = await questionnaire_editor.editor(ctx, questionnaire_id)
    return _editor_out(found, await _editor_actions(ctx, found))


@questionnaire_editor_router.put(
    _Q, action="questionnaire.edit", response_model=QuestionnaireSaveOut, errors=(409, 501)
)
async def questionnaire_save_route(
    questionnaire_id: UUID,
    body: QuestionnaireSaveIn,
    ctx: Ctx,
    if_match: IfMatch,
    dry_run: Annotated[bool, Query()] = False,
) -> QuestionnaireSaveOut:
    """`questionnaire.edit` on a binder's organizer; a template draft's questionnaire needs
    `questionnaire_template.draft` (the service checks the owner kind)."""
    await _gate_either(ctx, "questionnaire.edit", "questionnaire_template.draft")
    from abacus.modules.requests import questionnaire_editor

    saved, listed, fired = await questionnaire_editor.save(
        ctx,
        questionnaire_id,
        if_match,
        sections=[sec.model_dump() for sec in body.sections],
        questions=[q.model_dump(mode="json") for q in body.questions],
        dry_run=dry_run,
        change_summary=body.change_summary,
    )
    latest = await questionnaire_editor.editor(ctx, questionnaire_id) if saved else None
    return QuestionnaireSaveOut(
        saved=saved,
        client_visible_changes=[ClientVisibleChangeOut.model_validate(c) for c in listed],
        effects_to_fire=[EffectToFireOut.model_validate(f) for f in fired],
        questionnaire=_editor_out(latest, await _editor_actions(ctx, latest))
        if latest is not None
        else None,
    )


@questionnaire_editor_router.get(
    f"{_Q}/client-preview",
    action="questionnaire.read",
    response_model=ClientPreviewOut,
    errors=(501,),
)
async def questionnaire_preview_route(
    questionnaire_id: UUID,
    ctx: Ctx,
    question: Annotated[str | None, Query(max_length=81)] = None,
    contact: Annotated[UUID | None, Query()] = None,
) -> ClientPreviewOut:
    """The portal serializer's DTO for one question or the whole organizer."""
    await _gate_either(ctx, "questionnaire.read", "questionnaire_template.read")
    from abacus.modules.requests import questionnaire_editor

    e = await questionnaire_editor.editor(ctx, questionnaire_id)
    shown = [q for q in e.questions if question is None or q.key == question]
    return ClientPreviewOut(
        firm_name="",
        questions=[
            PreviewQuestionOut(
                key=q.key,
                parent_key=q.parent_key,
                type=cast(EditorQuestionType, q.type),
                client_wording=q.client_wording,
                required=q.required,
                choices=q.choices,
                amount_parts=q.amount_parts,
                visible=q.parent_key is None,
                answer=q.answer_value,
            )
            for q in shown
        ],
    )


@questionnaire_editor_router.get(
    _T, action="questionnaire_template.read", response_model=TemplateDetailOut, errors=(501,)
)
async def template_detail_route(template_id: UUID, ctx: Ctx) -> TemplateDetailOut:
    await _gate(ctx, "questionnaire_template.read")
    from abacus.modules.requests import organizer_lifecycle

    return await _detail_out(ctx, await organizer_lifecycle.detail(ctx, template_id))


@questionnaire_editor_router.put(
    f"{_T}/owner",
    action="questionnaire_template.assign_owner",
    response_model=TemplateDetailOut,
    errors=(409, 501),
)
async def template_owner_route(
    template_id: UUID, body: TemplateOwnerIn, ctx: Ctx
) -> TemplateDetailOut:
    """409 `owner_not_partner` unless the owner is a partner member."""
    await _gate(ctx, "questionnaire_template.assign_owner")
    from abacus.modules.requests import organizer_lifecycle

    return await _detail_out(
        ctx, await organizer_lifecycle.assign_owner(ctx, template_id, body.owner_id)
    )


@questionnaire_editor_router.post(
    f"{_T}/versions",
    status_code=201,
    action="questionnaire_template.draft",
    response_model=OrganizerTemplateVersionOut,
    errors=(409, 501),
)
async def template_draft_route(
    template_id: UUID, body: TemplateDraftIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> OrganizerTemplateVersionOut:
    """A draft from the current published version; 409 `draft_exists`."""
    await _gate(ctx, "questionnaire_template.draft")
    from abacus.modules.requests import organizer_lifecycle

    found = await organizer_lifecycle.new_draft(ctx, template_id, body.change_summary)
    return _version_out(found.versions[0])


@questionnaire_editor_router.delete(
    f"{_T}/versions/{{version}}",
    action="questionnaire_template.draft",
    response_model=OrganizerTemplateVersionOut,
    errors=(409, 501),
)
async def template_discard_route(
    template_id: UUID, version: int, ctx: Ctx
) -> OrganizerTemplateVersionOut:
    """Discards a draft (hidden from lists); 409 `version_published` for a published one."""
    await _gate(ctx, "questionnaire_template.draft")
    from abacus.modules.requests import organizer_lifecycle

    return _version_out(await organizer_lifecycle.discard(ctx, template_id, version))


@questionnaire_editor_router.get(
    f"{_T}/versions/{{version}}/diff",
    action="questionnaire_template.read",
    response_model=TemplateDiffOut,
    errors=(501,),
)
async def template_diff_route(
    template_id: UUID,
    version: int,
    ctx: Ctx,
    against: Annotated[int | None, Query(ge=1)] = None,
) -> TemplateDiffOut:
    await _gate(ctx, "questionnaire_template.read")
    from abacus.modules.requests import organizer_lifecycle

    base, changes = await organizer_lifecycle.version_changes(ctx, template_id, version, against)
    return TemplateDiffOut(
        version=version,
        against=base,
        changes=[QuestionDiffOut.model_validate(c) for c in changes],
    )
