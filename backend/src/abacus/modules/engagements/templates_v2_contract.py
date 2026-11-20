"""TV-1 Templates v2 contract stub, the engagements half (K-03-T08; TASK-8852; SPEC-720 §3.5;
SHL-22; DEC-5849): the engagement's template link, the update dry run and progress, apply, hold and
release, and the evaluated scoping rules. Client 404 → `templates_v2.enabled` off 404 → a write
that is not a live person's 403 → 501 until K-03-T19/T33.
"""

from __future__ import annotations

from datetime import datetime
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
Internal = classified("internal")
Confidential = classified("confidential")
Count = Annotated[int, Field(ge=0), Internal]
LinkState = Literal["current", "update_available", "updated", "held"]
ChangeStatus = Literal["pending", "applied", "kept_signed_off", "kept_team_value", "recorded"]


def _cfg() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


class TemplateLinkOut(BaseModel):
    """SHL-22: "Template update available" / "Updated to FS v6 by Omar Haddad · Oct 1, 10:21"."""

    model_config = _cfg()

    engagement_id: Annotated[UUID, Internal]
    template_id: Annotated[UUID, Internal]
    version_id: Annotated[UUID, Internal]
    version_label: Annotated[str, Field(max_length=40), Internal]
    state: Annotated[LinkState, Internal]
    available_version_id: Annotated[UUID | None, Internal] = None
    available_label: Annotated[str | None, Field(max_length=40), Internal] = None
    held_reason: Annotated[str | None, Field(max_length=500), Confidential] = None
    updated_by: Annotated[str | None, Field(max_length=120), Confidential] = None
    updated_at: Annotated[datetime | None, Internal] = None
    allowed_actions: Annotated[list[str], Internal] = []


class UpdateChangeOut(BaseModel):
    model_config = _cfg()

    change_key: Annotated[str, Field(max_length=120), Internal]
    kind: Annotated[Literal["added", "changed", "removed"], Internal]
    label: Annotated[str, Field(max_length=300), Internal]
    effect_here: Annotated[str, Field(max_length=300), Internal]
    status: Annotated[ChangeStatus, Internal] = "pending"


class TemplateUpdateOut(BaseModel):
    """SHL-22 b (dry run: Added 3 · Changed 5 · Removed 0) and c, d (progress, applied)."""

    model_config = _cfg()

    update_id: Annotated[UUID | None, Internal] = None
    to_version_id: Annotated[UUID, Internal]
    status: Annotated[Literal["dry_run", "applying", "applied", "failed"], Internal]
    changes: Annotated[list[UpdateChangeOut], Internal]
    added: Count
    changed: Count
    removed: Count
    applied: Count = 0
    workflow_id: Annotated[str | None, Field(max_length=200), Internal] = None


class TemplateUpdateIn(BaseModel):
    model_config = _cfg()

    to_version_id: Annotated[UUID, Internal]


class HoldIn(BaseModel):
    model_config = _cfg()

    reason: Annotated[str, Field(min_length=1, max_length=500), Confidential]


class ScopingEvaluationOut(BaseModel):
    model_config = _cfg()

    rule_id: Annotated[UUID, Internal]
    position: Annotated[int, Field(ge=1, le=99), Internal]
    result: Annotated[Literal["shows", "hides", "no_change", "no_answer"], Internal]
    evaluated_at: Annotated[datetime, Internal]


class ScopingEvaluationListOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[ScopingEvaluationOut], Internal]


template_link_router = AbacusRouter(prefix="/v1", tags=["templates v2"])
_E = "/engagements/{engagement_id}"


async def _on(ctx: AuthContext) -> None:
    if ctx.client or not await flag_enabled(ctx.tenant, TEMPLATES_V2_ENABLED):
        raise NotFound(TEMPLATES_V2_ENABLED.name)


async def _human(ctx: AuthContext, action: str) -> None:
    await _on(ctx)
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(action, "role")


@template_link_router.get(
    f"{_E}/template-link",
    action="template_update.read",
    response_model=TemplateLinkOut,
    errors=(501,),
)
async def template_link_route(engagement_id: UUID, ctx: Ctx) -> TemplateLinkOut:
    await _on(ctx)
    raise NotImplementedYet


@template_link_router.get(
    f"{_E}/template-update",
    action="template_update.read",
    response_model=TemplateUpdateOut,
    errors=(501,),
)
async def template_update_dry_run_route(
    engagement_id: UUID, to: UUID, ctx: Ctx
) -> TemplateUpdateOut:
    """The dry run (and its `/changes.csv`): what applying would change here."""
    await _on(ctx)
    raise NotImplementedYet


@template_link_router.get(
    f"{_E}/template-update/{{update_id}}",
    action="template_update.read",
    response_model=TemplateUpdateOut,
    errors=(501,),
)
async def template_update_route(
    engagement_id: UUID, update_id: UUID, ctx: Ctx
) -> TemplateUpdateOut:
    await _on(ctx)
    raise NotImplementedYet


@template_link_router.post(
    f"{_E}/template-update",
    action="template.apply_update",
    response_model=TemplateUpdateOut,
    status_code=202,
    errors=(409, 501),
)
async def template_update_apply_route(
    engagement_id: UUID, body: TemplateUpdateIn, ctx: Ctx, key: IdempotencyKey
) -> TemplateUpdateOut:
    """202 with the workflow id; changes apply in place, nobody is signed out."""
    await _human(ctx, "template.apply_update")
    raise NotImplementedYet


@template_link_router.post(
    f"{_E}/template-hold",
    action="template.apply_update",
    response_model=TemplateLinkOut,
    errors=(409, 501),
)
async def template_hold_route(engagement_id: UUID, body: HoldIn, ctx: Ctx) -> TemplateLinkOut:
    await _human(ctx, "template.apply_update")
    raise NotImplementedYet


@template_link_router.post(
    f"{_E}/template-hold/release",
    action="template.apply_update",
    response_model=TemplateLinkOut,
    errors=(409, 501),
)
async def template_hold_release_route(
    engagement_id: UUID, body: HoldIn, ctx: Ctx
) -> TemplateLinkOut:
    await _human(ctx, "template.apply_update")
    raise NotImplementedYet


@template_link_router.get(
    f"{_E}/scoping", action="scoping.read", response_model=ScopingEvaluationListOut, errors=(501,)
)
async def engagement_scoping_route(engagement_id: UUID, ctx: Ctx) -> ScopingEvaluationListOut:
    await _on(ctx)
    raise NotImplementedYet


__all__ = ["template_link_router"]
