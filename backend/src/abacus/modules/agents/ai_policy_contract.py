"""The AI-policy contract, v1: ADM-04's family (G-02-T15 stub; SPEC-349 AC-31 to AC-44, AC-48;
ADR-186, ADR-187; DEC-50, DEC-53, DEC-87, DEC-532). Contract: `docs/contracts/ai-policy.md`.

Behind `ai_policy.v1`: off, every route here answers 404; on, live since G-02-T24
(`ai_policy_service.py`; tables, compiled defaults and validator from G-02-T23). Each route
declares exactly one matrix action, and the matrix answers before the flag is read (security
review L1): a client principal gets 404 (INV-4); the agent, the system, a person without the
action and a stale second factor get 403.

Rules the shapes carry (ADR-186, ADR-187):

- **Versions are insert-only.** `awaiting_approval` -> `published` | `declined` | `withdrawn`;
  "Superseded" is derived (`superseded`), never stored. A carried-over v1 names no people.
- **Stricter-only.** A draft that loosens a locked or default-strict cell answers 422
  `policy_loosening_refused` with `facts.field` (the cell's path); no control offers it. The
  policy principal and every gate's policy acceptance are stored off and locked (ADR-187).
- **Two partners.** The QM owner requests publication with fresh MFA; a different partner
  approves with fresh MFA (409 `approver_must_differ` for the requester, AC-37).
- **Immediate controls are not policy cells**: the client-data opt-in (SPEC-036), each agent's
  stage (read-only here) and "Pause all agents" keep their own routes.
- **Sub-processors and the model family come from the provider-terms register** (DF-16, DEC-87):
  never typed in, and the model family is a model, not a processor.
- Rows carry codes and facts; the SPA composes the words ("BH AI policy v3 · published Jan 14,
  2026 by Margaret Okonkwo").
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import Depends, Header, Path, Query
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.kernel.listing import ListPage
from abacus.modules.agents import ai_policy_service as svc
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    current_context,
)

Ctx = Annotated[AuthContext, Depends(current_context)]
IfMatch = Annotated[int, Header(alias="If-Match", ge=0)]

VersionState = Literal["awaiting_approval", "published", "declined", "withdrawn"]
# C1 engagement type keys the Auto mode defaults are stored under (ADR-186 item 6).
EngagementTypeKey = Literal[
    "ebp_audit",
    "fs_audit",
    "review_compilation",
    "preparation",
    "tax_return",
    "monthly_close",
    "notice",
    "advisory",
]
InstallRole = Literal["manager_plus", "partner_only"]
PublishApprover = Literal["methodology_owner"]
AgentStage = Literal["shadow", "live"]
# The attest column of fieldset A ("Never", "Never; held for client approval", "Posting
# disabled").
AttestRule = Literal["never", "never_held_for_client", "posting_disabled"]
# Why a cell is locked, as a code the SPA words.
LockReason = Literal[
    "policy_principal_dormant",  # ADR-187: policy acceptance stays off
    "platform_floor",  # §7216 consent on, trace retention 7 years, client drafts off
    "real_firm_season_1",  # "Auto mode isn't available for client data yet"
    "not_a_partner",  # "Only partners can change the AI policy." (AC-33)
    "client_data_only",  # security_admin edits fieldset D only (AC-40)
]
SECTION_KEYS: tuple[str, ...] = (
    "autonomy",
    "gates",
    "policy_principal",
    "auto_mode_defaults",
    "client_data",
    "governance",
)


class PolicyPersonOut(BaseModel):
    """A person named on the policy; the id links to the ADM-02 user drawer."""

    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    display_name: Annotated[str, classified("confidential")]


# --- sections (A to E), as stored and as a draft carries them ------------------------------------


class AutonomySection(BaseModel):
    """The firm's autonomy level (0 advise, 1 routine; Season 1 caps it at 1, ADR-186)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    level: Annotated[int, Field(ge=0, le=3), classified("internal")]


class GateOverride(BaseModel):
    """Fieldset A: what a firm may change on a gate row (stricter-only; today only policy
    acceptance, stored off and locked under ADR-187)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    action_key: Annotated[str, Field(min_length=3, max_length=80), classified("internal")]
    policy_acceptance_on: Annotated[bool, classified("internal")] = False


class PolicyPrincipalSection(BaseModel):
    """Fieldset B: the dormant policy principal (ADR-187): `on` is false and locked."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    on: Annotated[bool, classified("internal")] = False


class AutoModeDefaults(BaseModel):
    """Fieldset C: Auto mode per engagement type (a standing plan approval). Stored; forced off
    on every real firm until runtime v2 (ADR-186 item 6)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ebp_audit: Annotated[bool, classified("internal")] = False
    fs_audit: Annotated[bool, classified("internal")] = False
    review_compilation: Annotated[bool, classified("internal")] = False
    preparation: Annotated[bool, classified("internal")] = False
    tax_return: Annotated[bool, classified("internal")] = False
    monthly_close: Annotated[bool, classified("internal")] = False
    notice: Annotated[bool, classified("internal")] = False
    advisory: Annotated[bool, classified("internal")] = False


class ClientDataSection(BaseModel):
    """Fieldset D: §7216 consent (locked on), the consent template, AI-use disclosure in
    engagement letters, model-drafted client text (locked off, ADR P-25)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    require_7216_consent: Annotated[bool, classified("internal")] = True
    consent_template_ref: Annotated[UUID | None, classified("internal")] = None
    disclosure_in_letters: Annotated[bool, classified("internal")] = True
    client_drafts_enabled: Annotated[bool, classified("internal")] = False


class GovernanceSection(BaseModel):
    """Fieldset E: who installs agents, who approves a publish, the override tolerance, the
    monthly accuracy sample and run-trace retention (never under 7 years)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    install_role: Annotated[InstallRole, classified("internal")] = "manager_plus"
    publish_approver: Annotated[PublishApprover, classified("internal")] = "methodology_owner"
    override_tolerance_pct: Annotated[int, Field(ge=0, le=100), classified("internal")] = 8
    accuracy_sample_n: Annotated[int, Field(ge=1, le=1000), classified("internal")] = 25
    trace_retention_years: Annotated[int, Field(ge=1, le=50), classified("internal")] = 7


class AiPolicySections(BaseModel):
    """`sections`, schema_version 1 (ADR-186 item 2). Bounds here are shape only: whether a value
    loosens the platform's default is the validator's (422 `policy_loosening_refused`)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    autonomy: Annotated[AutonomySection, classified("internal")]
    gates: Annotated[list[GateOverride], Field(max_length=40), classified("internal")]
    policy_principal: Annotated[PolicyPrincipalSection, classified("internal")]
    auto_mode_defaults: Annotated[AutoModeDefaults, classified("internal")]
    client_data: Annotated[ClientDataSection, classified("internal")]
    governance: Annotated[GovernanceSection, classified("internal")]


# --- the read ------------------------------------------------------------------------------------


class GateRowOut(BaseModel):
    """One of fieldset A's twelve rows (chapter 05 §5.2.13), from the compiled gate catalogue
    cross-checked against the matrix (AC-32). `approver_rule` is the default human approver as a
    code the SPA words ("Named human, one batch"); `default_approver_roles` the matrix roles it
    resolves to."""

    model_config = ConfigDict(frozen=True)

    row: Annotated[int, Field(ge=1, le=40), classified("internal")]
    gate_key: Annotated[str, classified("internal")]
    action_keys: Annotated[list[str], classified("internal")] = Field(default_factory=list[str])
    approver_rule: Annotated[str, classified("internal")]
    default_approver_roles: Annotated[list[str], classified("internal")] = Field(
        default_factory=list[str]
    )
    # Rows 1 and 5 only (AC-32); always off and locked while the principal is dormant.
    policy_acceptance_available: Annotated[bool, classified("internal")] = False
    policy_acceptance_on: Annotated[bool, classified("internal")] = False
    policy_acceptance_locked: Annotated[bool, classified("internal")] = True
    # The policy a row's acceptance would name ("BH AJE thresholds v2"), as a reference.
    acceptance_policy_ref: Annotated[str | None, classified("internal")] = None
    attest: Annotated[AttestRule | None, classified("internal")] = None
    # Where the gate appears (screen ids; planned links where unbuilt) and its log line.
    where_shown: Annotated[list[str], classified("internal")] = Field(default_factory=list[str])
    log_action: Annotated[str, classified("internal")]


class CellLockOut(BaseModel):
    """A locked cell: its path in `sections` and why (the SPA shows Lock with the reason)."""

    model_config = ConfigDict(frozen=True)

    path: Annotated[str, classified("internal")]
    reason: Annotated[LockReason, classified("internal")]


class AiPolicyVersionOut(BaseModel):
    """A version's metadata: "v3 · published Jan 14, 2026 by Margaret Okonkwo · approved by
    Daniel Reyes", "Awaiting approval · Daniel Reyes", "v1 · carried over"."""

    model_config = ConfigDict(frozen=True)

    version_no: Annotated[int, Field(ge=1), classified("internal")]
    state: Annotated[VersionState, classified("internal")]
    schema_version: Annotated[int, Field(ge=1), classified("internal")] = 1
    effective_from: Annotated[datetime, classified("internal")]
    requested_by: Annotated[PolicyPersonOut | None, classified("internal")] = None
    requested_at: Annotated[datetime | None, classified("internal")] = None
    approver: Annotated[PolicyPersonOut | None, classified("internal")] = None
    decided_by: Annotated[PolicyPersonOut | None, classified("internal")] = None
    decided_at: Annotated[datetime | None, classified("internal")] = None
    carried_over: Annotated[bool, classified("internal")] = False
    # Derived: a later published version is effective now (never stored, ADR-186 item 1).
    superseded: Annotated[bool, classified("internal")] = False


class AiPolicyDiffRowOut(BaseModel):
    """One changed cell against the version before: "Override tolerance 8% → 6%"."""

    model_config = ConfigDict(frozen=True)

    path: Annotated[str, classified("internal")]
    before: Annotated[str | None, classified("internal")] = None
    after: Annotated[str | None, classified("internal")] = None


class AiPolicyVersionDetailOut(AiPolicyVersionOut):
    """ADM-04 j: a version with its sections and its diff against the one before."""

    sections: Annotated[AiPolicySections, classified("internal")]
    diff: Annotated[list[AiPolicyDiffRowOut], classified("internal")] = Field(
        default_factory=list[AiPolicyDiffRowOut]
    )


class AiPolicyVersionPageOut(ListPage[AiPolicyVersionOut]):
    """The version history, newest first (the P-36 envelope)."""


class AiPolicyDraftOut(BaseModel):
    """The firm's one draft (b): the base version, its sections, whether it differs from the
    base ("Unsaved changes"; "Save as v4…" enabled) and its version for If-Match."""

    model_config = ConfigDict(frozen=True)

    base_version_no: Annotated[int, Field(ge=1), classified("internal")]
    sections: Annotated[AiPolicySections, classified("internal")]
    differs: Annotated[bool, classified("internal")]
    diff: Annotated[list[AiPolicyDiffRowOut], classified("internal")] = Field(
        default_factory=list[AiPolicyDiffRowOut]
    )
    version: Annotated[int, Field(ge=0), classified("internal")]
    updated_at: Annotated[datetime | None, classified("internal")] = None
    updated_by: Annotated[PolicyPersonOut | None, classified("internal")] = None


class ClientDataOptInOut(BaseModel):
    """SPEC-036's opt-in ("AI on your clients' data"), shown, never re-implemented (AC-41)."""

    model_config = ConfigDict(frozen=True)

    on: Annotated[bool, classified("internal")]
    changed_at: Annotated[datetime | None, classified("internal")] = None
    changed_by: Annotated[PolicyPersonOut | None, classified("internal")] = None
    # The provider-terms register version the disclosure was generated from.
    register_version: Annotated[str | None, classified("internal")] = None


class PolicyAgentStageOut(BaseModel):
    """An agent's stage, read-only on ADM-04 ("Shadow since …", "Live since …")."""

    model_config = ConfigDict(frozen=True)

    agent_key: Annotated[str, classified("internal")]
    stage: Annotated[AgentStage, classified("internal")]
    since: Annotated[datetime | None, classified("internal")] = None


class FirmPauseOut(BaseModel):
    """ "Pause all agents" (ADR-157's per-firm switch): who paused and when (AC-42)."""

    model_config = ConfigDict(frozen=True)

    paused: Annotated[bool, classified("internal")]
    paused_at: Annotated[datetime | None, classified("internal")] = None
    paused_by: Annotated[PolicyPersonOut | None, classified("internal")] = None


class ImmediateControlsOut(BaseModel):
    """The band outside versioning (ADR-186 item 8)."""

    model_config = ConfigDict(frozen=True)

    client_data_opt_in: Annotated[ClientDataOptInOut, classified("internal")]
    agent_stages: Annotated[list[PolicyAgentStageOut], classified("internal")]
    firm_pause: Annotated[FirmPauseOut, classified("internal")]


class SubProcessorOut(BaseModel):
    """A sub-processor row, generated from the provider-terms register (DF-16): "Amazon Web
    Services (Bedrock) · model inference · US · no training"."""

    model_config = ConfigDict(frozen=True)

    name: Annotated[str, classified("public")]
    purpose: Annotated[str, classified("public")]
    region: Annotated[str, classified("public")]
    trains_on_data: Annotated[bool, classified("public")]
    retention_days: Annotated[int | None, classified("public")] = None


class AiPolicyOut(BaseModel):
    """ADM-04 a, e, g, h: the effective version, a pending one, the draft summary, the sections,
    fieldset A's rows, the locked cells, the immediate controls, the register's sub-processors and
    model family, and the viewer's actions (read-only without `ai_policy.draft`, AC-33)."""

    model_config = ConfigDict(frozen=True)

    effective: Annotated[AiPolicyVersionOut, classified("internal")]
    sections: Annotated[AiPolicySections, classified("internal")]
    pending: Annotated[AiPolicyVersionOut | None, classified("internal")] = None
    # The effective version a later effective date has not reached yet ("v4 · effective Sep 15").
    scheduled: Annotated[AiPolicyVersionOut | None, classified("internal")] = None
    draft: Annotated[AiPolicyDraftOut | None, classified("internal")] = None
    gates: Annotated[list[GateRowOut], classified("internal")]
    locks: Annotated[list[CellLockOut], classified("internal")]
    immediate: Annotated[ImmediateControlsOut, classified("internal")]
    sub_processors: Annotated[list[SubProcessorOut], classified("public")]
    # A model, never a processor (DEC-87): only ADM-04 names it.
    model_family: Annotated[str | None, classified("public")] = None
    # Not synthetic: Auto mode reads Off with a lock (the Season 1 rule).
    real_firm: Annotated[bool, classified("internal")]
    actions: Annotated[list[str], classified("internal")] = Field(default_factory=list[str])


class EffectiveAiPolicyOut(BaseModel):
    """`GET /v1/firm/ai-policy/effective`: the cells a run planner, ENG-03 (P-07) and KNW-04
    (K-02) read for one engagement type at one time (AC-39; `agents.api.effective_ai_policy`)."""

    model_config = ConfigDict(frozen=True)

    version_no: Annotated[int, Field(ge=1), classified("internal")]
    effective_from: Annotated[datetime, classified("internal")]
    engagement_type: Annotated[EngagementTypeKey, classified("internal")]
    at: Annotated[datetime, classified("internal")]
    autonomy_level: Annotated[int, Field(ge=0, le=3), classified("internal")]
    # Stored per type; `auto_mode_effective` is false on a real firm (Season 1) whatever stored.
    auto_mode: Annotated[bool, classified("internal")]
    auto_mode_effective: Annotated[bool, classified("internal")]
    auto_mode_lock: Annotated[LockReason | None, classified("internal")] = None
    policy_principal_on: Annotated[bool, classified("internal")] = False
    client_data: Annotated[ClientDataSection, classified("internal")]
    firm_paused: Annotated[bool, classified("internal")] = False


# --- writes --------------------------------------------------------------------------------------


class AiPolicyDraftIn(BaseModel):
    """Save the draft (If-Match: the draft's `version`; 409 `stale_version`). A security admin
    may change `client_data` only (AC-40); any loosening answers 422."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sections: Annotated[AiPolicySections, classified("internal")]


class AiPolicyPublishIn(BaseModel):
    """ "Publish v4": the effective date and the approving partner, who is not the requester
    (AC-37)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    effective_from: Annotated[date, classified("internal")]
    approver_user_id: Annotated[UUID, classified("internal")]


class AiPolicyDeclineIn(BaseModel):
    """A decline names why, as a code; a note is optional and Confidential."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    reason_code: Annotated[
        Literal["needs_changes", "wrong_effective_date", "other"], classified("internal")
    ]
    note: Annotated[str | None, Field(max_length=500), classified("confidential")] = None


# --- G-02-T24: the live routes' projections ------------------------------------------------------


def _person(user_id: UUID | None, names: dict[UUID, str]) -> PolicyPersonOut | None:
    if user_id is None:
        return None
    return PolicyPersonOut(user_id=user_id, display_name=names.get(user_id, ""))


def _version_out(
    v: svc.Version, names: dict[UUID, str], *, superseded: bool = False
) -> AiPolicyVersionOut:
    return AiPolicyVersionOut(
        version_no=v.version_no,
        state=cast(VersionState, v.state),
        schema_version=v.schema_version,
        effective_from=v.effective_from,
        requested_by=_person(v.requested_by, names),
        requested_at=v.requested_at,
        approver=_person(v.approver_user_id, names),
        decided_by=_person(v.decided_by, names),
        decided_at=v.decided_at,
        carried_over=v.carried_over,
        superseded=superseded,
    )


async def _names(*versions: svc.Version | None) -> dict[UUID, str]:
    ids: list[UUID | None] = []
    for v in versions:
        if v is not None:
            ids += [v.requested_by, v.approver_user_id, v.decided_by]
    return await svc.person_names(ids)


def _diff_out(
    before: dict[str, object] | None, after: dict[str, object]
) -> list[AiPolicyDiffRowOut]:
    return [AiPolicyDiffRowOut(path=p, before=b, after=a) for p, b, a in svc.diff(before, after)]


def _draft_out(d: svc.Draft, effective: svc.Version, names: dict[UUID, str]) -> AiPolicyDraftOut:
    rows = _diff_out(effective.sections, d.sections)
    return AiPolicyDraftOut(
        base_version_no=d.base_version_no,
        sections=AiPolicySections.model_validate(d.sections),
        differs=bool(rows),
        diff=rows,
        version=d.version,
        updated_at=d.updated_at,
        updated_by=_person(d.updated_by, names),
    )


def _gate_out(g: dict[str, object]) -> GateRowOut:
    return GateRowOut(
        row=cast(int, g["row"]),
        gate_key=str(g["gate_key"]),
        action_keys=cast(list[str], g.get("actions", [])),
        approver_rule=str(g["approver_rule"]),
        default_approver_roles=cast(list[str], g.get("approver_roles", [])),
        policy_acceptance_available=bool(g.get("policy_acceptance_available", False)),
        policy_acceptance_on=bool(g.get("policy_acceptance_on", False)),
        policy_acceptance_locked=True,
        attest=cast(AttestRule | None, g.get("attest")),
        where_shown=cast(list[str], g.get("where_shown", [])),
        log_action=str(g["log_action"]),
    )


ai_policy_router = AbacusRouter(prefix="/v1/firm/ai-policy", tags=["ai policy"])


@ai_policy_router.get("", action="ai_policy.read", response_model=AiPolicyOut, errors=(501,))
async def ai_policy_route(ctx: Ctx) -> AiPolicyOut:
    """ADM-04 a, e, g, h and the band: the effective policy for every firm member (AC-31 to
    AC-35, AC-41 to AC-44)."""
    view = await svc.read_policy(ctx)
    names = await _names(view.effective, view.pending, view.scheduled)
    draft = None
    if view.draft is not None:
        names |= await svc.person_names([view.draft.updated_by])
        draft = _draft_out(view.draft, view.effective, names)
    return AiPolicyOut(
        effective=_version_out(view.effective, names),
        sections=AiPolicySections.model_validate(view.effective.sections),
        pending=_version_out(view.pending, names) if view.pending else None,
        scheduled=_version_out(view.scheduled, names) if view.scheduled else None,
        draft=draft,
        gates=[_gate_out(g) for g in view.gates],
        locks=[CellLockOut(path=p, reason=cast(LockReason, r)) for p, r in view.locks],
        immediate=ImmediateControlsOut(
            client_data_opt_in=ClientDataOptInOut(on=view.opted_in),
            agent_stages=[],
            firm_pause=FirmPauseOut(paused=view.paused_at is not None, paused_at=view.paused_at),
        ),
        sub_processors=[
            SubProcessorOut(
                name=str(p["name"]),
                purpose=str(p["purpose"]),
                region=str(p["region"]),
                trains_on_data=False,
            )
            for p in view.sub_processors
        ],
        model_family=view.model_family,
        real_firm=view.real_firm,
    )


@ai_policy_router.get(
    "/versions", action="ai_policy.read", response_model=AiPolicyVersionPageOut, errors=(501,)
)
async def ai_policy_versions_route(
    ctx: Ctx,
    cursor: Annotated[str | None, Query(max_length=1024)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AiPolicyVersionPageOut:
    """ADM-04 j: the history, newest first (AC-34)."""
    versions, now = await svc.list_versions(ctx)
    names = await _names(*versions)
    rows = [_version_out(v, names, superseded=svc.superseded(versions, v, now)) for v in versions]
    return AiPolicyVersionPageOut(items=rows[:limit], total=len(rows))


@ai_policy_router.get(
    "/versions/{version_no}",
    action="ai_policy.read",
    response_model=AiPolicyVersionDetailOut,
    errors=(501,),
)
async def ai_policy_version_route(
    version_no: Annotated[int, Path(ge=1)], ctx: Ctx
) -> AiPolicyVersionDetailOut:
    """A version with its sections and its diff against the one before (AC-34)."""
    found, before = await svc.read_version(ctx, version_no)
    names = await _names(found)
    out = _version_out(found, names)
    return AiPolicyVersionDetailOut(
        **out.model_dump(),
        sections=AiPolicySections.model_validate(found.sections),
        diff=_diff_out(before.sections if before else None, found.sections),
    )


@ai_policy_router.get(
    "/effective",
    action="ai_policy.read",
    response_model=EffectiveAiPolicyOut,
    errors=(501,),
)
async def effective_ai_policy_route(
    ctx: Ctx,
    engagement_type: EngagementTypeKey,
    at: datetime | None = None,
) -> EffectiveAiPolicyOut:
    """AC-39: the version effective at `at` (now on `kernel.clock` when omitted)."""
    found = await svc.read_effective(ctx, engagement_type, at)
    sections = AiPolicySections.model_validate(found.version.sections)
    return EffectiveAiPolicyOut(
        version_no=found.version.version_no,
        effective_from=found.version.effective_from,
        engagement_type=engagement_type,
        at=found.at,
        autonomy_level=sections.autonomy.level,
        auto_mode=found.auto_mode,
        auto_mode_effective=found.auto_mode_effective,
        auto_mode_lock="real_firm_season_1" if found.auto_mode and found.real_firm else None,
        policy_principal_on=sections.policy_principal.on,
        client_data=sections.client_data,
        firm_paused=found.paused,
    )


@ai_policy_router.get(
    "/draft", action="ai_policy.draft", response_model=AiPolicyDraftOut, errors=(501,)
)
async def ai_policy_draft_route(ctx: Ctx) -> AiPolicyDraftOut:
    """ADM-04 b: the firm's draft (the effective sections when none is saved)."""
    draft, effective = await svc.read_draft(ctx)
    return _draft_out(draft, effective, await svc.person_names([draft.updated_by]))


@ai_policy_router.put(
    "/draft", action="ai_policy.draft", response_model=AiPolicyDraftOut, errors=(409, 501)
)
async def put_ai_policy_draft_route(
    body: AiPolicyDraftIn, if_match: IfMatch, ctx: Ctx
) -> AiPolicyDraftOut:
    """AC-36, AC-38, AC-40: save against If-Match (409 `stale_version`); 422
    `policy_loosening_refused` with `facts.field`. Audited `ai_policy.draft_saved`."""
    await svc.save_draft(ctx, body.sections.model_dump(mode="json"), if_match)
    draft, effective = await svc.read_draft(ctx)
    return _draft_out(draft, effective, await svc.person_names([draft.updated_by]))


@ai_policy_router.delete(
    "/draft", action="ai_policy.draft", response_model=AiPolicyDraftOut, errors=(409, 501)
)
async def discard_ai_policy_draft_route(if_match: IfMatch, ctx: Ctx) -> AiPolicyDraftOut:
    """AC-36 "Discard": the draft goes back to the effective version, which comes back. Audited
    `ai_policy.draft_discarded`."""
    await svc.discard_draft(ctx, if_match)
    draft, effective = await svc.read_draft(ctx)
    return _draft_out(draft, effective, await svc.person_names([draft.updated_by]))


@ai_policy_router.post(
    "/versions",
    action="ai_policy.publish",
    response_model=AiPolicyVersionOut,
    status_code=201,
    errors=(409, 501),
)
async def publish_ai_policy_route(body: AiPolicyPublishIn, ctx: Ctx) -> AiPolicyVersionOut:
    """ADM-04 d: request publication of the draft as the next version, `awaiting_approval`,
    raising the C13 gate for the approver (AC-37); 409 `approver_must_differ` when the approver
    is the requester. Audited `ai_policy.publish_requested`."""
    found = await svc.request_publish(ctx, body.effective_from, body.approver_user_id)
    return _version_out(found, await _names(found))


@ai_policy_router.post(
    "/versions/{version_no}/approve",
    action="ai_policy.approve",
    response_model=AiPolicyVersionOut,
    errors=(409, 501),
)
async def approve_ai_policy_route(
    version_no: Annotated[int, Path(ge=1)], ctx: Ctx
) -> AiPolicyVersionOut:
    """ADM-04 g: the named partner approves with fresh MFA (409 `approver_must_differ` for the
    requester). Audited `ai_policy.approved`."""
    found = await svc.approve(ctx, version_no)
    return _version_out(found, await _names(found))


@ai_policy_router.post(
    "/versions/{version_no}/decline",
    action="ai_policy.approve",
    response_model=AiPolicyVersionOut,
    errors=(409, 501),
)
async def decline_ai_policy_route(
    version_no: Annotated[int, Path(ge=1)], body: AiPolicyDeclineIn, ctx: Ctx
) -> AiPolicyVersionOut:
    """The named partner declines. Audited `ai_policy.declined`."""
    found = await svc.decline(ctx, version_no, body.reason_code)
    return _version_out(found, await _names(found))


@ai_policy_router.post(
    "/versions/{version_no}/withdraw",
    action="ai_policy.publish",
    response_model=AiPolicyVersionOut,
    errors=(409, 501),
)
async def withdraw_ai_policy_route(
    version_no: Annotated[int, Path(ge=1)], ctx: Ctx
) -> AiPolicyVersionOut:
    """The requester withdraws a version still awaiting approval. Audited
    `ai_policy.withdrawn`."""
    found = await svc.withdraw(ctx, version_no)
    return _version_out(found, await _names(found))
