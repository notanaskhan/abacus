"""Public interface of the tax module; other modules import only this (ADR-008).

Pre-registered (F-03-T08; ADR-140). T-01-T02: the engine-bridge and e-file-record stubs
(`engine_contract`). T-01-T18: final approval and its blocker slot (`approval`).
"""

from datetime import date
from uuid import UUID

from sqlalchemy import text

from abacus.kernel._flags import TAX_REVIEW_WORKSPACE
from abacus.kernel.audit_owners import register_engagement_owners, register_entity_owners
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.uow import OutboxEvent
from abacus.modules.agents.api import register_session_subject
from abacus.modules.engagements.api import register_work_item_kind
from abacus.modules.identity.api import AbacusRouter, AuthContext, register_scope_resolver
from abacus.modules.organisations.api import register_office_facts
from abacus.modules.platform.api import register_search_projection
from abacus.modules.reporting.api import register_k1_rows
from abacus.modules.tax import analyst_modes as _analyst_modes
from abacus.modules.tax import answer_effects as _answer_effects
from abacus.modules.tax import consent_capture, filed_delivery, filing, k1_release
from abacus.modules.tax import draft_entry as _draft_entry
from abacus.modules.tax import drafter_workflow as _drafter
from abacus.modules.tax import explain as _explain
from abacus.modules.tax import extensions as _extensions
from abacus.modules.tax import fix_runner as _fix_runner
from abacus.modules.tax import return_events as _return_events
from abacus.modules.tax import return_issues as _return_issues
from abacus.modules.tax import return_tabs as _return_tabs
from abacus.modules.tax import schedule_jobs as _schedule_jobs
from abacus.modules.tax import workbook_service as _workbook_service
from abacus.modules.tax.analyst_modes import (  # S38: the recorder and replay test (ADR-090)
    AnalystModeWorkflow,
    ModeRunInput,
    ModeRunOutcome,
    mode_workflow_id,
)
from abacus.modules.tax.approval import Blocker as ApprovalBlocker
from abacus.modules.tax.approval import eligibility as final_approval_eligibility
from abacus.modules.tax.approval import register as register_approval
from abacus.modules.tax.approval import register_final_approval_blocker
from abacus.modules.tax.audit_targets import (
    AUDIT_KINDS,
    ENTITY_KINDS,
    audit_entities,
    audit_owners,
)
from abacus.modules.tax.board import KIND as SEARCH_TYPE
from abacus.modules.tax.board import return_search_document, returns_by_office
from abacus.modules.tax.due_dates import (
    FORM_FOR_RULES,
    on_reference_set_published,
    recompute_unfiled,
    register_due_dates_source,
    register_extension_dates_source,
    rule_texts,
    set_extended,
)
from abacus.modules.tax.engine_contract import engine_router, portal_filing_router
from abacus.modules.tax.engine_import import import_file as import_engine_file
from abacus.modules.tax.engine_sync import register as register_engine_sync
from abacus.modules.tax.estimates import (
    create_estimate_schedule,
    patch_installment,
    patch_schedule,
)
from abacus.modules.tax.estimates import (
    request_confirmation as request_estimate_confirmation,  # T-03-T15: the scenario loader's
)
from abacus.modules.tax.extensions import ProposedPayment, flag_new_likely, send_confirmation
from abacus.modules.tax.extensions import patch as patch_extension
from abacus.modules.tax.extensions import prepare as prepare_extensions
from abacus.modules.tax.filed_delivery import FiledReturn, filed_returns
from abacus.modules.tax.k1_contract import k1_router, portal_k1_router
from abacus.modules.tax.k1_packages import draft_k1_blockers, package_scope
from abacus.modules.tax.k1_packages import share_internal as share_k1_internal
from abacus.modules.tax.k1_portal import deliverable_k1_rows
from abacus.modules.tax.k1_release_workflow import (
    K1DeliveryInput,
    K1ReleaseFailure,
    K1ReleaseInput,
    K1ReleaseWorkflow,
)
from abacus.modules.tax.kind import TaxReturnKind
from abacus.modules.tax.overview import on_binder_published, on_sign_off_recorded
from abacus.modules.tax.returns_routes import returns_router
from abacus.modules.tax.schedules_contract import schedules_router
from abacus.modules.tax.status import TRANSITIONS, StaleReturn, TransitionRefused, next_status
from abacus.modules.tax.tax_profile import (
    authorization_on_file as authorization_on_file,
)
from abacus.modules.tax.tax_profile import register as register_tax_profile
from abacus.modules.tax.tax_profile import return_for_entity as return_for_entity
from abacus.modules.tax.tax_profile import return_label as return_label
from abacus.modules.tax.tax_profile import transcript_comparison_lines
from abacus.modules.tax.transitions import apply_transition, record_sync_state
from abacus.modules.tax.workbook_contract import workbook_router
from abacus.modules.tax.workspace_contract import workspace_router
from abacus.modules.tax.workspace_seed import (
    SeedField,
    SeedSection,
    SeedWorksheet,
    record_synthetic_workspace,
)

# T-01-T10: §7216 consent capture behind C19's routes, and the `consent_set` envelope source.
consent_capture.register()
filing.register()  # T-01-T36: the `tax_return` envelope source (C7 v1.1)

# F-03-T22: the `tax_return` work-item kind.
register_work_item_kind("tax_return", TaxReturnKind())

# DEC-121: the audit explorer asks which engagement each `tax_return` target belongs to.
register_engagement_owners(AUDIT_KINDS, audit_owners)
register_entity_owners(ENTITY_KINDS, audit_entities)  # T-01: a tax profile's rows
# T-02-T09: ADM-03a's per-office "TY returns" count (G-01) and the C15 search projection.
register_office_facts("tax_returns", returns_by_office)
register_search_projection(SEARCH_TYPE, return_search_document)
# T-01-T18: the return's reviewable facts and the `tax_final_approval` gate kind (C13).
register_approval()
# T-02-T20 (DV-4): a K-1 shared to a return as a draft blocks its final approval until released.
register_final_approval_blocker("draft_k1", draft_k1_blockers)
# T-02-T21 (DEC-34): a `k1_recipient` grant's `k1_package` scope (own-only in the portal reads).
register_scope_resolver("k1_package", package_scope)
# R-02-T09 (DEC-2805): T-02's released K-1s on POR-09's rail, through C10's slot.
register_k1_rows(deliverable_k1_rows)
# T-01-T43: CLI-05's authorizations, elections, transcripts and comparisons (DEC-1651).
register_tax_profile()
# T-01-T27: the engine-sync gate kinds (C13) and notification kinds (C16) (DEC-1463).
register_engine_sync()

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (
    returns_router,  # tax returns v1 (T-02-T09 board); `/summary` before `/{return_id}`
    engine_router,  # the engine bridge and the e-file record (T-01-T02 stub)
    k1_router,  # K-1 packages (T-02-T02 stub)
    portal_k1_router,  # POR-13 (T-02-T02 stub)
    portal_filing_router,  # T-01-T41: the filed client copy's download
    schedules_router,  # extensions, estimates and payments (T-03-T02 stub)
    workspace_router,  # RW-1 and WS-1, the return workspace (T-04-T05 stub)
    workbook_router,  # tax workbook v1, entity returns (T-05-T06 stub; dark)
)


# T-02-T10: a published reference-set correction recomputes every unfiled return's due dates
# (K-02-T12 fans `reference_set.published` out per tenant).
async def _reference_set_published(event: OutboxEvent) -> None:
    """Due dates follow a published set (T-02-T10); corrected 8879 tolerances recheck every open
    binding (T-01-T36)."""
    await on_reference_set_published(event)
    await filing.on_tolerances_published(event)
    await _extensions.on_reference_set_published(event)


async def _filing_acknowledged(event: OutboxEvent) -> None:
    await _extensions.on_filing_acknowledged(event)


_answer_effects.register()  # T-03-T06 (DEC-2352): review points from organizer answers

SUBSCRIPTIONS = {
    "reference_set.published": _reference_set_published,
    "filing.acknowledged": _filing_acknowledged,
    # T-01-T36: a return's approved checkpoint rechecks its 8879 binding (I-8879-DRIFT).
    "checkpoint.approved": filing.on_checkpoint_approved,
    # T-01-T10: a completed `consent_set` envelope signs its consents (C7 → C19).
    "envelope.completed": consent_capture.on_envelope_completed,
    # T-02-T13: the record projection (a published binder opens intake; the L1 marks prepared).
    "binder.published": on_binder_published,
    "sign_off.recorded": on_sign_off_recorded,
    # T-02-T21: a release starts its workflow; a resend gives the corrected contact access.
    **k1_release.SUBSCRIPTIONS,
    # T-01-T37: a published filed return emails the client's owners "Deliverable ready".
    **filed_delivery.SUBSCRIPTIONS,
    # T-04-T23: a released K-1 resolves the receiving returns' Draft K-1 issues (the system's).
    **_return_issues.SUBSCRIPTIONS,
}


async def _k1_package_released(event: OutboxEvent) -> None:
    """T-04-T23's Draft K-1 issues resolve, then T-04-T36's activities release and diff."""
    from abacus.modules.tax.k1_treatments import on_package_released

    await _return_issues.on_k1_package_released(event)
    await on_package_released(event)


SUBSCRIPTIONS["k1_package.released"] = _k1_package_released


async def _residency_confirmed(event: OutboxEvent) -> None:
    """T-04-T39 (AC-8.6): the option's worksheets activate and the re-import is flagged."""
    from abacus.modules.tax.residency_service import on_residency_confirmed

    await on_residency_confirmed(event)


SUBSCRIPTIONS["residency_determination.confirmed"] = _residency_confirmed
# T-02-T21: `K1ReleaseWorkflow` and its activities (the worker composes every module's parts).
WORKFLOWS: dict[type, str] = {
    **k1_release.WORKFLOWS,
    **_schedule_jobs.WORKFLOWS,
    **_drafter.WORKFLOWS,  # T-04-T25: ReturnDrafterWorkflow
    **_fix_runner.WORKFLOWS,  # T-04-T31: FixRunWorkflow
    **_explain.WORKFLOWS,  # T-04-T31: IssueExplainWorkflow
    **_analyst_modes.WORKFLOWS,  # T-04-T38: AnalystModeWorkflow
}
ACTIVITIES: tuple[object, ...] = (
    *k1_release.ACTIVITIES,
    *_schedule_jobs.ACTIVITIES,
    *_drafter.ACTIVITIES,
    *_fix_runner.ACTIVITIES,
    *_explain.ACTIVITIES,
    *_analyst_modes.ACTIVITIES,
)
start_draft = _drafter.start_draft
# T-04-T49 (DEC-4524): the individual engines' CPA review (`make entitlement` reads it).
from abacus.modules.tax.compute.individual.review import (  # noqa: E402
    review_signed as individual_review_signed,
)

# T-04-T55 (DEC-4514): the draft-run entry (TAX-02 Run draft) and the return frame's tab seam.
run_draft = _draft_entry.run_draft
DraftNotAllowed = _draft_entry.DraftNotAllowed
register_return_tab = _return_tabs.register_return_tab
# T-04's workspace tabs on the shared return frame, each behind the flag that gates its screen.
for _order, _tab in enumerate(("review", "issues", "activity"), start=10):
    register_return_tab(
        _tab, TAX_REVIEW_WORKSPACE, order=_order, forms=frozenset({"1040", "1040x"})
    )
# T-04-T25: the history recorder's workflow and its types (abacus_tools reaches tax only here).
DraftInput = _drafter.DraftInput
DraftOutcome = _drafter.DraftOutcome
ReturnDrafterWorkflow = _drafter.ReturnDrafterWorkflow
drafter_workflow_id = _drafter.drafter_workflow_id
# T-04-T31: the fix and Explain workflows and their types, for the history recorder.
FixRunInput = _fix_runner.FixRunInput
FixRunOutcome = _fix_runner.FixRunOutcome
FixRunWorkflow = _fix_runner.FixRunWorkflow
fix_workflow_id = _fix_runner.fix_workflow_id
ExplainRunInput = _explain.ExplainRunInput
ExplainRunOutcome = _explain.ExplainRunOutcome
IssueExplainWorkflow = _explain.IssueExplainWorkflow
explain_workflow_id = _explain.explain_workflow_id
SCHEDULES = _schedule_jobs.SCHEDULES


async def extension_for(tenant: TenantContext, tax_return_id: UUID) -> list[dict[str, object]]:
    """C21-side read for T-08 and R-03: the return's lines (contract §2)."""
    async with tenant_session(tenant) as session:
        found = await session.execute(
            text("SELECT * FROM filing_extensions WHERE tax_return_id = :r ORDER BY jurisdiction"),
            {"r": tax_return_id},
        )
        return [dict(row) for row in found.mappings()]


async def estimates_for(
    tenant: TenantContext, client_entity_id: UUID, tax_year: int
) -> list[dict[str, object]]:
    async with tenant_session(tenant) as session:
        found = await session.execute(
            text(
                "SELECT * FROM estimate_schedules WHERE client_entity_id = :c AND tax_year = :y "
                "ORDER BY jurisdiction"
            ),
            {"c": client_entity_id, "y": tax_year},
        )
        return [dict(row) for row in found.mappings()]


async def installments_due(
    tenant: TenantContext, start: date, end: date
) -> list[dict[str, object]]:
    async with tenant_session(tenant) as session:
        found = await session.execute(
            text(
                "SELECT i.*, s.client_entity_id, s.form, s.jurisdiction "
                "FROM estimate_installments i JOIN estimate_schedules s ON s.id = i.schedule_id "
                "WHERE i.due_on BETWEEN :a AND :b ORDER BY i.due_on, i.id"
            ),
            {"a": start, "b": end},
        )
        return [dict(row) for row in found.mappings()]


__all__ = [
    "ACTIVITIES",
    "FORM_FOR_RULES",
    "ROUTERS",
    "SCHEDULES",
    "SUBSCRIPTIONS",
    "TRANSITIONS",
    "WORKFLOWS",
    "AnalystModeWorkflow",
    "ApprovalBlocker",
    "DraftInput",
    "DraftNotAllowed",
    "DraftOutcome",
    "ExplainRunInput",
    "ExplainRunOutcome",
    "FiledReturn",
    "FixRunInput",
    "FixRunOutcome",
    "FixRunWorkflow",
    "IssueExplainWorkflow",
    "K1DeliveryInput",
    "K1ReleaseFailure",
    "K1ReleaseInput",
    "K1ReleaseWorkflow",
    "ModeRunInput",
    "ModeRunOutcome",
    "ProposedPayment",
    "ReturnDrafterWorkflow",
    "SeedField",
    "SeedSection",
    "SeedWorksheet",
    "StaleReturn",
    "TaxCalendarSweepWorkflow",
    "TransitionRefused",
    "apply_transition",
    "create_estimate_schedule",
    "drafter_workflow_id",
    "estimates_for",
    "explain_workflow_id",
    "extension_for",
    "filed_returns",
    "final_approval_eligibility",
    "fix_workflow_id",
    "flag_new_likely",
    "import_engine_file",
    "individual_review_signed",
    "installments_due",
    "mode_workflow_id",
    "next_status",
    "patch_extension",
    "patch_installment",
    "patch_schedule",
    "prepare_extensions",
    "recompute_unfiled",
    "record_sync_state",
    "record_synthetic_workspace",
    "register_due_dates_source",
    "register_extension_dates_source",
    "register_final_approval_blocker",
    "register_return_tab",
    "request_estimate_confirmation",
    "rule_texts",
    "run_draft",
    "send_confirmation",
    "set_extended",
    "share_k1_internal",
    "start_draft",
    "transcript_comparison_lines",
]

# T-03 (S27): imported so its refusal codes are catalogued (the routes import it lazily).
from abacus.modules.tax import (  # noqa: E402
    estimates as _estimates,  # noqa: F401  # pyright: ignore[reportUnusedImport] -- codes
)
from abacus.modules.tax import (  # noqa: E402
    extensions as _extensions_codes,  # noqa: F401  # pyright: ignore[reportUnusedImport] -- imported to register and catalogue it
)

# I-01-T23 (S29 leftovers, DEC-2609): a return at final approval waiting for its engine export.
from abacus.modules.tax.gate_sources import register_tax_gates  # noqa: E402

register_tax_gates()

# S29 leftovers (TASK-6012): what the replay recorders and the OCR suite runner read (BOUND-001).
# T-04-T14 (DEC-3125): the `tax_form_line` citable.
from abacus.modules.tax.form_line_citations import register as _register_form_line  # noqa: E402
from abacus.modules.tax.schedule_workflows import (  # noqa: E402
    TaxCalendarSweepWorkflow as TaxCalendarSweepWorkflow,
)

_register_form_line()

# T-04-T15 (DEC-3208): the workspace's reviewables, field owner, suggestion targets and appliers.
from abacus.modules.tax.worksheet_review import (  # noqa: E402
    register as _register_worksheet_review,
)

_register_worksheet_review()

# T-04-T31 (DEC-3413): a return's issues are fixed and explained by the tax agents, through P-04's
# fail-closed slots (keyed by the issue's record type).
from abacus.modules.review.api import register_explainer, register_fix_runner  # noqa: E402

register_fix_runner(_fix_runner.RECORD_TYPE, _fix_runner.start_fix)
register_explainer(_fix_runner.RECORD_TYPE, _explain.start_explain)

# T-04-T19 (DEC-3211): the tax tools on C17 register at their module's import.
from abacus.modules.tax.tools import (  # noqa: E402
    read_return as _tax_tools_loaded,
)

del _tax_tools_loaded


# T-04-T37 (DEC-4316): a TAX-08 thread is a workbench session bound to the return; the person must
# read the return. Workbench may not import tax, so the resolver sits in agents' subject slot.
async def _assistant_subject(ctx: AuthContext, return_id: UUID) -> UUID:
    from abacus.kernel.errors import NotFound
    from abacus.modules.engagements.api import get_ref, work_item_engagement
    from abacus.modules.identity.api import authorise

    engagement = await work_item_engagement(ctx.tenant, return_id)
    if engagement is None or ctx.client:
        raise NotFound("tax_return")
    ref = await get_ref(ctx, engagement)  # a wall answers 404
    await authorise(ctx, "tax_return.read", ref.resource())
    return engagement


register_session_subject("tax_return", _assistant_subject, "tax.assistant")

# T-04-T29 (DEC-4318): the return's counts reach its topics on `/v1/events`.
_return_events.register()
# T-05-T27 (DEC-4519): the workbook's cells are review fields; SHL-09 reads their provenance.
_workbook_service.register()

# P-02-T07 (DEC-4613): the C15 v1 search projection this module owns, registered at import.
# T-05-T31 (DEC-4616): the entity workbook run plan provider, registered at import.
from abacus.modules.tax import (  # noqa: E402
    entity_run_plan as _entity_run_plan,  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registers at import
)

# T-05-T32 (DEC-4617): the workbook run step handlers, registered at import.
from abacus.modules.tax import run_steps as _run_steps  # noqa: E402
from abacus.modules.tax import (  # noqa: E402
    search as _search,  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registers at import
)

_run_steps.register()

# T-05-T41 (DEC-4701): the allocation structure's reviewable, facts and proposal adapter.
from abacus.modules.tax import allocation_structure as _allocation_structure  # noqa: E402

_allocation_structure.register()
