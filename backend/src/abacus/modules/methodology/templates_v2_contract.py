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

from collections.abc import Sequence
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
from abacus.modules.methodology import scoping as engine
from abacus.modules.methodology import skills as sk
from abacus.modules.methodology.template_drafts import ComponentInvalid

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
    when: Annotated[list[dict[str, str]], Internal]  # source, operator, value
    then: Annotated[Literal["show", "hide", "add_requests"], Internal]
    targets: Annotated[list[str], Internal]  # one target per rule (checked by the service)
    # K-03-T18 (DEC-6017), additive: the group's operator, the target's kind (a request group
    # for `add_requests`) and the editor's label.
    group_op: Annotated[Literal["and", "or"], Internal] = "and"
    target_kind: Annotated[
        Literal["step", "sheet", "section", "row", "request_group"] | None, Internal
    ] = None
    label: Annotated[str | None, Field(max_length=200), Confidential] = None


class ScopingRulesOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[ScopingRuleOut], Internal]
    etag: Annotated[int, Field(ge=0), Internal]


class ScopingRulesIn(BaseModel):
    model_config = _cfg()

    items: Annotated[list[ScopingRuleOut], Field(max_length=99), Internal]


class ScopingPreviewIn(BaseModel):
    model_config = _cfg()

    # K-03-T18: no engagement (or `blank`) previews a blank engagement: nothing answered.
    engagement_id: Annotated[UUID | None, Internal] = None
    blank: Annotated[bool, Internal] = False


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
    summary: Annotated[str, Field(max_length=200), Internal] = ""  # code's text (K-03-T18)


class ScopingSourceOut(BaseModel):
    model_config = _cfg()

    key: Annotated[str, Field(max_length=80), Internal]
    label: Annotated[str, Field(max_length=200), Internal]
    kind: Annotated[Literal["planning_form", "risk", "assertion", "engagement_fact"], Internal]
    options: Annotated[list[str], Internal] = []  # the value menu's codes (K-03-T18)


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


class SkillImportIn(BaseModel):
    """K-03-T21 (DEC-6021), additive: the content pack, `{"skills": [{key, name, group,
    versions: [{version, status, body_md, linked_step_keys}]}]}`."""

    model_config = _cfg()

    pack: Annotated[dict[str, object], Internal]


class SkillPinWarningOut(BaseModel):
    """KNW-06c: "Skill BH-SK-430 v2 is a draft" (a warning; it never blocks publish)."""

    model_config = _cfg()

    skill_key: Annotated[str, Field(max_length=60), Internal]
    version: Annotated[int, Field(ge=1), Internal]
    severity: Annotated[Literal["warning"], Internal]
    text: Annotated[str, Field(max_length=200), Internal]


class SkillPinWarningListOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[SkillPinWarningOut], Internal]


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
        # K-03-T17 (DEC-6016): a write may answer 412 on a stale If-Match.
        "errors": (501,) if not write else (409, 412, 501),
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
    """409 `draft_exists` when the template already has a draft (K-03-T17)."""
    await _human(ctx, "template.edit")
    from abacus.modules.methodology import template_drafts as td

    draft = await td.create_draft(ctx, template_id, body.from_version_id)
    return await _version_out(ctx, draft)


@_route("get", "/template-versions", "template.read", EngagementTemplateVersionListOut)
async def versions_route(template_id: UUID, ctx: Ctx) -> EngagementTemplateVersionListOut:
    await _on(ctx)
    raise NotImplementedYet


@_route("get", _V, "template.read", EngagementTemplateVersionOut)
async def version_route(version_id: UUID, ctx: Ctx) -> EngagementTemplateVersionOut:
    await _on(ctx)
    return await _version_out(ctx, version_id)


async def _version_out(ctx: AuthContext, version_id: UUID) -> EngagementTemplateVersionOut:
    """KNW-06a's version header and rail counts (code's counts of the version's rows)."""
    from sqlalchemy import text

    from abacus.kernel.db import tenant_session
    from abacus.modules.identity.api import Resource, authorise

    await authorise(ctx, "template.read", Resource.firm(ctx.tenant_id))
    sql = text(
        "SELECT v.id, v.template_id, v.seq, v.label, v.status, v.retired_at, v.effective_from, "
        "v.methodology_version_id, v.based_on_version_id, v.draft_etag, v.published_at, "
        "(SELECT count(*) FROM template_sheet_definitions c "
        "WHERE c.template_version_id = v.id) AS sheets, "
        "(SELECT count(*) FROM template_forms c "
        "WHERE c.template_version_id = v.id) AS forms, "
        "(SELECT count(*) FROM template_requests c "
        "WHERE c.template_version_id = v.id) AS requests, "
        "(SELECT count(*) FROM template_requests r WHERE r.template_version_id = v.id "
        "AND r.shown_by_rule_id IS NOT NULL) AS requests_by_rule, "
        "(SELECT count(*) FROM template_trigger_defaults c "
        "WHERE c.template_version_id = v.id) AS triggers, "
        "(SELECT count(*) FROM template_report_template_refs c "
        "WHERE c.template_version_id = v.id) AS report_templates, "
        "(SELECT count(*) FROM template_skill_pins c "
        "WHERE c.template_version_id = v.id) AS skills, "
        "(SELECT count(*) FROM scoping_rules c "
        "WHERE c.template_version_id = v.id) AS scoping_rules "
        "FROM template_versions v WHERE v.id = :v"
    )
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(sql, {"v": version_id})).mappings().first()
    if row is None:
        raise NotFound("template_version")
    return EngagementTemplateVersionOut(
        version_id=row["id"], template_id=row["template_id"], seq=row["seq"],
        label=row["label"], status=row["status"], retired=row["retired_at"] is not None,
        effective_from=row["effective_from"],
        methodology_version_id=row["methodology_version_id"],
        based_on_version_id=row["based_on_version_id"],
        rail=RailCountsOut(
            program_steps=0, sheets=row["sheets"], forms=row["forms"],
            requests=row["requests"], requests_by_rule=row["requests_by_rule"],
            triggers=row["triggers"], report_templates=row["report_templates"],
            skills=row["skills"], scoping_rules=row["scoping_rules"],
        ),
        draft_etag=row["draft_etag"] if row["status"] == "draft" else None,
        published_at=row["published_at"],
    )  # fmt: skip


@_route("get", f"{_V}/components/{{kind}}", "template.read", ComponentOut)
async def component_route(version_id: UUID, kind: ComponentKind, ctx: Ctx) -> ComponentOut:
    await _on(ctx)
    from abacus.modules.methodology import template_drafts as td

    etag, found = await td.component(ctx, version_id, kind)
    return ComponentOut(kind=kind, etag=etag, body=found)


@_route("put", f"{_V}/components/{{kind}}", "template.edit", ComponentOut, write=True)
async def component_put_route(
    version_id: UUID, kind: ComponentKind, body: ComponentIn, ctx: Ctx, if_match: IfMatch
) -> ComponentOut:
    """ETag autosave: 412 on a stale ETag; 409 `not_draft` on a published version."""
    await _human(ctx, "template.edit")
    from abacus.modules.methodology import template_drafts as td

    etag, found = await td.save_component(ctx, version_id, kind, body.body, if_match)
    return ComponentOut(kind=kind, etag=etag, body=found)


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


def _rule_in(item: ScopingRuleOut) -> tuple[engine.Rule, str | None]:
    if len(item.targets) != 1 or not item.when:
        raise ComponentInvalid(facts={"table": "scoping_rules", "rule": item.position})
    conditions: list[engine.Condition] = []
    for c in item.when:
        operator = c.get("operator", "")
        if operator not in engine.OPERATORS or not c.get("source"):
            raise ComponentInvalid(facts={"table": "scoping_rules", "rule": item.position})
        conditions.append(engine.Condition(c["source"], operator, c.get("value")))
    kind = "request_group" if item.then == "add_requests" else (item.target_kind or "step")
    rule = engine.Rule(
        str(item.rule_id), item.position, item.group_op, tuple(conditions),
        "hide" if item.then == "hide" else "show", kind, item.targets[0],
    )  # fmt: skip
    return rule, item.label


def _rules_out(etag: int, found: Sequence[tuple[engine.Rule, str | None]]) -> ScopingRulesOut:
    items = [
        ScopingRuleOut(
            rule_id=UUID(r.key), position=r.position,
            when=[{"source": c.source, "operator": c.operator}
                  | ({} if c.value is None else {"value": c.value}) for c in r.conditions],
            then="add_requests" if r.target_kind == "request_group" and r.effect == "show"
            else r.effect,
            targets=[r.target_ref], group_op=r.group_op, target_kind=r.target_kind, label=label,
        )
        for r, label in found
    ]  # fmt: skip
    return ScopingRulesOut(items=items, etag=etag)


@_route("get", f"{_V}/scoping-rules", "template.read", ScopingRulesOut)
async def scoping_rules_route(version_id: UUID, ctx: Ctx) -> ScopingRulesOut:
    await _on(ctx)
    from abacus.modules.methodology import scoping_rules as sr

    return _rules_out(*await sr.rules(ctx, version_id))


@_route("put", f"{_V}/scoping-rules", "scoping_rule.edit", ScopingRulesOut, write=True)
async def scoping_rules_put_route(
    version_id: UUID, body: ScopingRulesIn, ctx: Ctx, if_match: IfMatch
) -> ScopingRulesOut:
    """422 `rule_conflict`, `unknown_source`; 412 on a stale If-Match; 409 `not_draft`."""
    await _human(ctx, "scoping_rule.edit")
    from abacus.modules.methodology import scoping_rules as sr

    items = [_rule_in(i) for i in body.items]
    return _rules_out(*await sr.save_rules(ctx, version_id, items, if_match))


@_route("post", f"{_V}/scoping-rules/preview", "template.read", ScopingPreviewOut)
async def scoping_preview_route(
    version_id: UUID, body: ScopingPreviewIn, ctx: Ctx
) -> ScopingPreviewOut:
    """Code evaluates every rule (ADR-050); the agent never does. Nothing is written."""
    await _on(ctx)
    from abacus.modules.methodology import scoping_rules as sr

    found = await sr.preview(ctx, version_id, None if body.blank else body.engagement_id)
    return ScopingPreviewOut(
        rows=[ScopingPreviewRowOut(rule_id=UUID(r.key), result=res) for r, res in found.results],
        shows_steps=found.shows_steps, shows_sheets=found.shows_sheets, hides=found.hides,
        adds_requests=found.adds_requests, summary=found.summary,
    )  # fmt: skip


@_route("get", f"{_V}/scoping-sources", "template.read", ScopingSourceListOut)
async def scoping_sources_route(version_id: UUID, ctx: Ctx) -> ScopingSourceListOut:
    await _on(ctx)
    from abacus.modules.methodology import scoping_rules as sr

    return ScopingSourceListOut(
        items=[
            ScopingSourceOut(key=s.key, label=s.label, kind=s.kind, options=list(s.options))
            for s in await sr.sources(ctx, version_id)
        ]
    )


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


def _skill_out(found: sk.SkillVersionView) -> SkillOut:
    return SkillOut(
        skill_id=found.skill_id, key=found.key[:40], version_id=found.version_id,
        version=found.version, status=found.status,
    )  # fmt: skip


@_route("post", "/skills/import", "skill.import", SkillListOut, code=201, write=True)
async def skills_import_route(ctx: Ctx, key: IdempotencyKey, body: SkillImportIn) -> SkillListOut:
    """Content import (fresh MFA); 422 `skill_markdown_unsafe`; answers the new versions."""
    await _human(ctx, "skill.import")
    del key  # idempotent by content: an identical re-import adds nothing
    added = set(await sk.import_skills(ctx, body.pack))
    return SkillListOut(
        items=[_skill_out(v) for v in await sk.skills(ctx) if v.version_id in added]
    )


@_route("get", "/skills", "knowledge.read", SkillListOut)
async def skills_route(ctx: Ctx) -> SkillListOut:
    await _on(ctx)
    return SkillListOut(items=[_skill_out(v) for v in await sk.skills(ctx)])


@_route("get", "/skill-versions/{skill_version_id}", "knowledge.read", SkillOut)
async def skill_version_route(skill_version_id: UUID, ctx: Ctx) -> SkillOut:
    await _on(ctx)
    return _skill_out(await sk.skill_version(ctx, skill_version_id))


@_route("get", f"{_V}/skill-pin-warnings", "template.read", SkillPinWarningListOut)
async def skill_pin_warnings_route(version_id: UUID, ctx: Ctx) -> SkillPinWarningListOut:
    """K-03-T21 (KNW-06c): pins to draft skill versions, as warnings that never block publish."""
    await _on(ctx)
    from abacus.modules.identity.api import Resource, authorise

    await authorise(ctx, "template.read", Resource.firm(ctx.tenant_id))
    found = await sk.pin_warnings(ctx.tenant, version_id)
    return SkillPinWarningListOut(
        items=[SkillPinWarningOut(skill_key=w.skill_key, version=w.version, severity=w.severity,
                                  text=w.text) for w in found]
    )  # fmt: skip


__all__ = ["templates_v2_router"]
