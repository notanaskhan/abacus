"""TV-1 Templates v2 contract stub (K-03-T08; TASK-8852; SPEC-720; ADR-213; C22;
`docs/contracts/templates-v2.md`; DEC-5849). Screens KNW-06, KNW-07, SHT-03 (and SHL-22 through
the engagements half, `engagements/templates_v2_contract.py`).

Every route answers, in order: a client principal 404; `templates_v2.enabled` off 404; a write that
is not a live person's 403 (INV-1); then 501 until its K-03 build task. One matrix action per
route.
Classification (ADR-031): template content and names are `internal` firm content; people are
`confidential`; nothing here is TRI.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Header
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import TEMPLATES_V2_ENABLED
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.modules.identity.api import AbacusRouter, AuthContext, Forbidden, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)]
IfMatch = Annotated[str, Header(alias="If-Match", min_length=1, max_length=40)]
Internal = classified("internal")
Confidential = classified("confidential")
Count = Annotated[int, Field(ge=0), Internal]

VersionStatus = Literal["draft", "published", "deprecated"]
ComponentKind = Literal[
    "program", "sheets", "forms", "request_list", "triggers", "report_templates", "skills",
    "scoping_rules",
]  # fmt: skip
ChangeKind = Literal["added", "changed", "removed"]
ScopingResult = Literal["shows", "hides", "no_change", "no_answer"]
RolloutAction = Literal["update_now", "on_rollover", "hold"]


def _cfg() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


class TemplateAuthorOut(BaseModel):
    model_config = _cfg()

    user_id: Annotated[UUID, Internal]
    name: Annotated[str, Field(max_length=120), Confidential]


class TemplateOut(BaseModel):
    model_config = _cfg()

    template_id: Annotated[UUID, Internal]
    name: Annotated[str, Field(max_length=200), Internal]  # "BH Audit Methodology · FS"
    service_line: Annotated[Literal["audit", "tax", "cas", "advisory"], Internal]
    current_version_id: Annotated[UUID | None, Internal] = None
    draft_version_id: Annotated[UUID | None, Internal] = None
    allowed_actions: Annotated[list[str], Internal] = []


class TemplateListOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[TemplateOut], Internal]
    next_cursor: Annotated[str | None, Internal] = None


class RailCountsOut(BaseModel):
    """KNW-06a's rail: Program 38 (+3 · 1 changed), Sheets 14 (+2), Forms 6, Requests 41 + 6."""

    model_config = _cfg()

    program_steps: Count
    sheets: Count
    forms: Count
    requests: Count
    requests_by_rule: Count
    triggers: Count
    report_templates: Count
    skills: Count
    scoping_rules: Count


class EngagementTemplateVersionOut(BaseModel):
    model_config = _cfg()

    version_id: Annotated[UUID, Internal]
    template_id: Annotated[UUID, Internal]
    seq: Annotated[int, Field(ge=1), Internal]
    label: Annotated[str, Field(max_length=40), Internal]  # "FS v6"
    status: Annotated[VersionStatus, Internal]
    retired: Annotated[bool, Internal] = False  # "Superseded" only when retired
    effective_from: Annotated[date | None, Internal] = None
    methodology_version_id: Annotated[UUID | None, Internal] = None
    based_on_version_id: Annotated[UUID | None, Internal] = None
    rail: Annotated[RailCountsOut, Internal]
    used_by: Count = 0
    draft_etag: Annotated[int | None, Internal] = None
    published_by: Annotated[TemplateAuthorOut | None, Confidential] = None
    published_at: Annotated[datetime | None, Internal] = None
    allowed_actions: Annotated[list[str], Internal] = []


class EngagementTemplateVersionListOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[EngagementTemplateVersionOut], Internal]
    next_cursor: Annotated[str | None, Internal] = None


class NewVersionIn(BaseModel):
    model_config = _cfg()

    from_version_id: Annotated[UUID, Internal]


class ComponentOut(BaseModel):
    model_config = _cfg()

    kind: Annotated[ComponentKind, Internal]
    etag: Annotated[int, Field(ge=0), Internal]
    body: Annotated[dict[str, object], Internal]


class ComponentIn(BaseModel):
    model_config = _cfg()

    body: Annotated[dict[str, object], Internal]


class TemplateCheckOut(BaseModel):
    """KNW-06c: 2 errors · 1 warning; checks are code (ADR-050)."""

    model_config = _cfg()

    code: Annotated[str, Field(max_length=60), Internal]
    severity: Annotated[Literal["error", "warning"], Internal]
    component: Annotated[ComponentKind, Internal]
    item_ref: Annotated[str | None, Field(max_length=120), Internal] = None
    fix_link: Annotated[str | None, Field(max_length=200), Internal] = None


class TemplateCheckListOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[TemplateCheckOut], Internal]
    errors: Count
    warnings: Count


class ChangeOut(BaseModel):
    """Added 3 · Changed 5 · Removed 0 (KNW-07b, SHL-22b)."""

    model_config = _cfg()

    change_key: Annotated[str, Field(max_length=120), Internal]
    kind: Annotated[ChangeKind, Internal]
    component: Annotated[ComponentKind, Internal]
    item_ref: Annotated[str, Field(max_length=200), Internal]
    label: Annotated[str, Field(max_length=300), Internal]


class ChangeListOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[ChangeOut], Internal]
    added: Count
    changed: Count
    removed: Count


class TemplatePreviewIn(BaseModel):
    model_config = _cfg()

    answers: Annotated[dict[str, str] | None, Internal] = None
    engagement_id: Annotated[UUID | None, Internal] = None
    blank: Annotated[bool, Internal] = False


class TemplateVersionPreviewOut(BaseModel):
    """KNW-06b's dock: 38 steps · 14 sheets · 47 requests · 2 triggers · 3 report templates ·
    5 skills."""

    model_config = _cfg()

    rail: Annotated[RailCountsOut, Internal]
    skipped_steps: Count = 0  # DEC-43: no "hidden" field names in any schema


class ScopingRuleOut(BaseModel):
    model_config = _cfg()

    rule_id: Annotated[UUID, Internal]
    position: Annotated[int, Field(ge=1, le=99), Internal]
    when: Annotated[list[dict[str, str]], Internal]  # source, operator, value (AND)
    then: Annotated[Literal["show", "hide", "add_requests"], Internal]
    targets: Annotated[list[str], Internal]


class ScopingRulesOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[ScopingRuleOut], Internal]
    etag: Annotated[int, Field(ge=0), Internal]


class ScopingRulesIn(BaseModel):
    model_config = _cfg()

    items: Annotated[list[ScopingRuleOut], Field(max_length=99), Internal]


class ScopingPreviewIn(BaseModel):
    model_config = _cfg()

    engagement_id: Annotated[UUID, Internal]


class ScopingPreviewRowOut(BaseModel):
    model_config = _cfg()

    rule_id: Annotated[UUID, Internal]
    result: Annotated[ScopingResult, Internal]


class ScopingPreviewOut(BaseModel):
    """SHT-03a: Shows 3 steps · 2 sheets · hides 1 · adds 6 requests."""

    model_config = _cfg()

    rows: Annotated[list[ScopingPreviewRowOut], Internal]
    shows_steps: Count
    shows_sheets: Count
    hides: Count
    adds_requests: Count


class ScopingSourceOut(BaseModel):
    model_config = _cfg()

    key: Annotated[str, Field(max_length=80), Internal]
    label: Annotated[str, Field(max_length=200), Internal]
    kind: Annotated[Literal["planning_form", "risk", "assertion", "engagement_fact"], Internal]


class ScopingSourceListOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[ScopingSourceOut], Internal]


class TemplatePublishIn(BaseModel):
    model_config = _cfg()

    effective_from: Annotated[date, Internal]
    previous: Annotated[Literal["deprecate_for_new"], Internal] = "deprecate_for_new"


class UsedByOut(BaseModel):
    model_config = _cfg()

    engagement_id: Annotated[UUID, Internal]
    label: Annotated[str, Field(max_length=200), Internal]  # "A28 Harlow & Pike"
    phase: Annotated[str, Field(max_length=40), Internal]


class UsedByListOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[UsedByOut], Internal]
    total: Count


class RolloutRowOut(BaseModel):
    model_config = _cfg()

    engagement_id: Annotated[UUID, Internal]
    label: Annotated[str, Field(max_length=200), Internal]
    suggested_action: Annotated[RolloutAction | None, Internal] = None
    action: Annotated[RolloutAction | None, Internal] = None
    reason: Annotated[str | None, Field(max_length=500), Confidential] = None
    eligible: Annotated[bool, Internal] = True


class RolloutOut(BaseModel):
    """KNW-07a: 6 live · 3 Update now · 0 On rollover · 3 Hold · 0 Updated."""

    model_config = _cfg()

    status: Annotated[Literal["not_started", "in_progress", "complete"], Internal]
    rows: Annotated[list[RolloutRowOut], Internal]
    live: Count
    update_now: Count
    on_rollover: Count
    hold: Count
    updated: Count


class RolloutActionIn(BaseModel):
    model_config = _cfg()

    action: Annotated[RolloutAction, Internal]
    reason: Annotated[str | None, Field(max_length=500), Confidential] = None


class SkillOut(BaseModel):
    model_config = _cfg()

    skill_id: Annotated[UUID, Internal]
    key: Annotated[str, Field(max_length=40), Internal]  # "BH-SK-430"
    version_id: Annotated[UUID, Internal]
    version: Annotated[int, Field(ge=1), Internal]
    status: Annotated[Literal["draft", "published"], Internal]


class SkillListOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[SkillOut], Internal]


templates_v2_router = AbacusRouter(prefix="/v1", tags=["templates v2"])
_V = "/template-versions/{version_id}"


async def _on(ctx: AuthContext) -> None:
    if ctx.client or not await flag_enabled(ctx.tenant, TEMPLATES_V2_ENABLED):
        raise NotFound(TEMPLATES_V2_ENABLED.name)


async def _human(ctx: AuthContext, action: str) -> None:
    await _on(ctx)
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(action, "role")


def _route(  # noqa: ANN202 -- the router's own decorator type
    method: str,
    path: str,
    action: str,
    model: type[BaseModel] | None,
    *,
    code: int = 200,
    write: bool = False,
):
    register = getattr(templates_v2_router, method)
    kwargs: dict[str, object] = {
        "action": action,
        "response_model": model,
        "errors": (501,) if not write else (409, 501),
    }
    if code != 200:
        kwargs["status_code"] = code
    return register(path, **kwargs)


@_route("get", "/engagement-templates", "template.read", TemplateListOut)
async def templates_route(ctx: Ctx) -> TemplateListOut:
    await _on(ctx)
    raise NotImplementedYet


@_route("get", "/engagement-templates/{template_id}", "template.read", TemplateOut)
async def template_route(template_id: UUID, ctx: Ctx) -> TemplateOut:
    await _on(ctx)
    raise NotImplementedYet


@_route(
    "post",
    "/engagement-templates/{template_id}/versions",
    "template.edit",
    EngagementTemplateVersionOut,
    code=201,
    write=True,
)
async def new_version_route(
    template_id: UUID, body: NewVersionIn, ctx: Ctx
) -> EngagementTemplateVersionOut:
    """409 `draft_exists` when the template already has a draft."""
    await _human(ctx, "template.edit")
    raise NotImplementedYet


@_route("get", "/template-versions", "template.read", EngagementTemplateVersionListOut)
async def versions_route(template_id: UUID, ctx: Ctx) -> EngagementTemplateVersionListOut:
    await _on(ctx)
    raise NotImplementedYet


@_route("get", _V, "template.read", EngagementTemplateVersionOut)
async def version_route(version_id: UUID, ctx: Ctx) -> EngagementTemplateVersionOut:
    await _on(ctx)
    raise NotImplementedYet


@_route("get", f"{_V}/components/{{kind}}", "template.read", ComponentOut)
async def component_route(version_id: UUID, kind: ComponentKind, ctx: Ctx) -> ComponentOut:
    await _on(ctx)
    raise NotImplementedYet


@_route("put", f"{_V}/components/{{kind}}", "template.edit", ComponentOut, write=True)
async def component_put_route(
    version_id: UUID, kind: ComponentKind, body: ComponentIn, ctx: Ctx, if_match: IfMatch
) -> ComponentOut:
    """ETag autosave: 412 on a stale ETag; 409 `not_draft` on a published version."""
    await _human(ctx, "template.edit")
    raise NotImplementedYet


@_route("get", f"{_V}/checks", "template.read", TemplateCheckListOut)
async def checks_route(version_id: UUID, ctx: Ctx) -> TemplateCheckListOut:
    await _on(ctx)
    raise NotImplementedYet


@_route("get", f"{_V}/changes", "template.read", ChangeListOut)
async def changes_route(version_id: UUID, ctx: Ctx, against: UUID | None = None) -> ChangeListOut:
    await _on(ctx)
    raise NotImplementedYet


@_route("post", f"{_V}/preview", "template.read", TemplateVersionPreviewOut)
async def preview_route(
    version_id: UUID, body: TemplatePreviewIn, ctx: Ctx
) -> TemplateVersionPreviewOut:
    """The same rule engine as engagements; no model is called (INV-1)."""
    await _on(ctx)
    raise NotImplementedYet


@_route("get", f"{_V}/scoping-rules", "template.read", ScopingRulesOut)
async def scoping_rules_route(version_id: UUID, ctx: Ctx) -> ScopingRulesOut:
    await _on(ctx)
    raise NotImplementedYet


@_route("put", f"{_V}/scoping-rules", "scoping_rule.edit", ScopingRulesOut, write=True)
async def scoping_rules_put_route(
    version_id: UUID, body: ScopingRulesIn, ctx: Ctx, if_match: IfMatch
) -> ScopingRulesOut:
    """422 `rule_conflict`, `unknown_source`."""
    await _human(ctx, "scoping_rule.edit")
    raise NotImplementedYet


@_route("post", f"{_V}/scoping-rules/preview", "template.read", ScopingPreviewOut)
async def scoping_preview_route(
    version_id: UUID, body: ScopingPreviewIn, ctx: Ctx
) -> ScopingPreviewOut:
    await _on(ctx)
    raise NotImplementedYet


@_route("get", f"{_V}/scoping-sources", "template.read", ScopingSourceListOut)
async def scoping_sources_route(version_id: UUID, ctx: Ctx) -> ScopingSourceListOut:
    await _on(ctx)
    raise NotImplementedYet


@_route("post", f"{_V}/publish", "template.publish", EngagementTemplateVersionOut, write=True)
async def publish_route(
    version_id: UUID, body: TemplatePublishIn, ctx: Ctx, key: IdempotencyKey
) -> EngagementTemplateVersionOut:
    """Fresh MFA; 409 `checks_failing`, `skill_not_published`."""
    await _human(ctx, "template.publish")
    raise NotImplementedYet


@_route("post", f"{_V}/deprecate", "template.publish", EngagementTemplateVersionOut, write=True)
async def deprecate_route(
    version_id: UUID, ctx: Ctx, key: IdempotencyKey
) -> EngagementTemplateVersionOut:
    await _human(ctx, "template.publish")
    raise NotImplementedYet


@_route("get", f"{_V}/used-by", "template.read", UsedByListOut)
async def used_by_route(version_id: UUID, ctx: Ctx) -> UsedByListOut:
    """Counted over `visible()`; walled engagements are absent."""
    await _on(ctx)
    raise NotImplementedYet


@_route("get", f"{_V}/rollout", "template.rollout", RolloutOut)
async def rollout_route(version_id: UUID, ctx: Ctx) -> RolloutOut:
    await _on(ctx)
    raise NotImplementedYet


@_route(
    "put", f"{_V}/rollout/actions/{{engagement_id}}", "template.rollout", RolloutRowOut, write=True
)
async def rollout_action_route(
    version_id: UUID, engagement_id: UUID, body: RolloutActionIn, ctx: Ctx
) -> RolloutRowOut:
    """409 `missing_reason` for On rollover or Hold without a reason."""
    await _human(ctx, "template.rollout")
    raise NotImplementedYet


@_route("post", f"{_V}/rollout/start", "template.rollout", RolloutOut, write=True)
async def rollout_start_route(version_id: UUID, ctx: Ctx, key: IdempotencyKey) -> RolloutOut:
    await _human(ctx, "template.rollout")
    raise NotImplementedYet


@_route("post", "/skills/import", "skill.import", SkillListOut, code=201, write=True)
async def skills_import_route(ctx: Ctx, key: IdempotencyKey) -> SkillListOut:
    """Content import (fresh MFA); the body is the content pack."""
    await _human(ctx, "skill.import")
    raise NotImplementedYet


@_route("get", "/skills", "knowledge.read", SkillListOut)
async def skills_route(ctx: Ctx) -> SkillListOut:
    await _on(ctx)
    raise NotImplementedYet


@_route("get", "/skill-versions/{skill_version_id}", "knowledge.read", SkillOut)
async def skill_version_route(skill_version_id: UUID, ctx: Ctx) -> SkillOut:
    await _on(ctx)
    raise NotImplementedYet


__all__ = ["templates_v2_router"]
