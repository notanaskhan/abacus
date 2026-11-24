"""Public interface of the closes module; other modules import only this (ADR-008).

C-01 (SPEC-655): the close engine. Contract stubs: the portfolio, record, runs and plans
(`contract.py`, C-01-T04) and the intake, accounts, reconciliation, review, flux and portal
question routes (`contract_work.py`, C-01-T05); `docs/contracts/closes.md`. The record service
(`service.py`, C-01-T14): the portfolio, the summary, the status machine and assignments. Consumer
API: `close_for`, the fail-closed `register_status_guard` slot C-02 fills (C-01 §4.4) and
`start_close`, the system's Not started → In progress on the first run or incorporation.
"""

from collections.abc import Callable
from typing import Any
from uuid import UUID

from abacus.kernel.audit_owners import register_engagement_owners, register_entity_owners
from abacus.kernel.dispatch import WorkClass, register_work_classes
from abacus.kernel.sync_scope import register_sync_scope
from abacus.kernel.uow.relay import Handler, OutboxEvent
from abacus.modules.closes.agent_runs import register as agent_runs_register
from abacus.modules.closes.agent_tools import AGENT_TOOLS
from abacus.modules.closes.audit_targets import (
    AUDIT_KINDS,
    ENTITY_KINDS,
    audit_entities,
    audit_owners,
)

# C-01-T44 (TASK-8700; DEC-5700): the services the Brightwater Hale CAS slice loads through.
from abacus.modules.closes.contract import (
    AssigneesIn,
    CloseFacts,
    CloseTemplateImportIn,
    PlanDraftIn,
    PlanRowIn,
    PlanRowPatchIn,
    PublishIn,
    RequestTemplateIn,
    StatusGuard,
    TransitionNotAvailable,
    close_for,
    closes_router,
    register_status_guard,
    status_guard,
)
from abacus.modules.closes.contract_work import close_work_router, portal_close_router
from abacus.modules.closes.delivery_contract import delivery_router
from abacus.modules.closes.gate_sources import register_close_gates
from abacus.modules.closes.intake import ACTIVITIES as INTAKE_ACTIVITIES
from abacus.modules.closes.intake import schedule_publish
from abacus.modules.closes.intake_destination import register as intake_destination_register
from abacus.modules.closes.issues import CLOSE_TARGET, add_note, open_exceptions, raise_exception
from abacus.modules.closes.kind import CloseKind
from abacus.modules.closes.plans import (
    add_request_template,
    add_row,
    create_draft,
    get_plan,
    import_template,
    new_agent_draft,
    patch_row,
    publish,
)
from abacus.modules.closes.reconciliations import SUBSCRIPTIONS as RECONCILIATION_SUBSCRIPTIONS
from abacus.modules.closes.reconciliations import register as reconciliations_register
from abacus.modules.closes.registrations import SUBSCRIPTIONS as REGISTRATION_SUBSCRIPTIONS
from abacus.modules.closes.registrations import register as registrations_register
from abacus.modules.closes.request_publish_types import (
    PUBLISH as PUBLISH_REQUESTS,
)
from abacus.modules.closes.request_publish_types import (
    RECOMPUTE as RECOMPUTE_REQUESTS,
)
from abacus.modules.closes.request_publish_types import (
    SECONDS_UNTIL as REQUESTS_SECONDS_UNTIL,
)
from abacus.modules.closes.request_publish_types import (
    PublishInput,
    PublishResult,
)
from abacus.modules.closes.request_publish_workflow import RequestPublishWorkflow
from abacus.modules.closes.run_plan import register_treatment_kind
from abacus.modules.closes.run_steps import register_close_run_steps
from abacus.modules.closes.seed import seed_synthetic_close_status
from abacus.modules.closes.service import (
    close_summary,
    generate_closes,
    set_assignees,
    start_close,
)
from abacus.modules.closes.sync_scope import sync_scope
from abacus.modules.engagements.api import register_work_item_kind

# F-03-T22: the `close` work-item kind.
register_work_item_kind("close", CloseKind())
# C-01-T15 (QC-8): a requested publication waits on the engagement's Managers and Partners.
register_close_gates()
# C-01-T23 (DEC-5410): reconciliations are reviewables; a new ledger snapshot recomputes them.
reconciliations_register()
# C-01-T26 (DEC-5412): C13 flux and L1 gates, HOME-01's tile, C15 search, KNW-04a examples.
registrations_register()
# C-01-T30 (DEC-5413): close.agent's flux and planner drafts are P-35 suggestions on these targets.
agent_runs_register()
# C-01-T58 (DEC-5414): INB-02's close_receipt destination (fails closed with closes.engine off).
intake_destination_register()
# C-01-T20: the close run's code plan (`closes.close_run`), its run-step kinds and the
# `close_treatment` decision card.
register_close_run_steps()
register_treatment_kind()
# C-01-T17: the entities with an unlocked close keep their ledger fresh (LedgerSyncWorkflow).
register_sync_scope(sync_scope)
# The explorer's owners for a close and its plan (SPEC-304).
register_engagement_owners(AUDIT_KINDS, audit_owners)
register_entity_owners(ENTITY_KINDS, audit_entities)

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS = (closes_router, close_work_router, portal_close_router, delivery_router)  # C-02-T07


# C-01-T19: the BD1 publish workflow; the worker reads these (no outbox subscriptions yet).
async def _on_close_created(event: OutboxEvent) -> None:
    from abacus.modules.closes.registrations import on_close_for_reversals

    close_id = event.payload.get("close_id")
    if isinstance(close_id, str):
        await schedule_publish(event.tenant_id, UUID(close_id))
        await on_close_for_reversals(event)  # C-02-T24: last month's reversals carry here


SUBSCRIPTIONS: dict[str, Handler] = {
    "close.created": _on_close_created,
    **RECONCILIATION_SUBSCRIPTIONS,  # C-01-T23
    **REGISTRATION_SUBSCRIPTIONS,  # C-01-T26: close runs and answered questions (C16)
}
from abacus.modules.closes.package_render import ACTIVITIES as _PACKAGE_ACTIVITIES  # noqa: E402
from abacus.modules.closes.package_render import FINISH as PACKAGE_FINISH  # noqa: E402
from abacus.modules.closes.package_render import PackageAssemblyWorkflow  # noqa: E402
from abacus.modules.closes.release import register as _register_release  # noqa: E402
from abacus.modules.closes.vendor_screen import register as _register_vendor_screen  # noqa: E402
from abacus.modules.closes.vendor_tins import __all__ as _VENDOR_TINS  # noqa: E402, F401

_register_release()  # C-02-T29: C18's fs_package provider
_register_vendor_screen()  # C-02-T34: the vendor screen's tools and its suggestion applier

WORKFLOWS: dict[type, WorkClass] = {
    RequestPublishWorkflow: "background",
    PackageAssemblyWorkflow: "background",  # C-02-T28: CLS-08's render, then the DET run's end
}
register_work_classes(WORKFLOWS)
ACTIVITIES: tuple[Callable[..., Any], ...] = (  # Any: Temporal activities
    *INTAKE_ACTIVITIES,
    *_PACKAGE_ACTIVITIES,  # type: ignore[arg-type] -- activity functions
)

__all__ = [
    "ACTIVITIES",
    "AGENT_TOOLS",
    "CLOSE_TARGET",
    "PACKAGE_FINISH",
    "PUBLISH_REQUESTS",
    "RECOMPUTE_REQUESTS",
    "REQUESTS_SECONDS_UNTIL",
    "ROUTERS",
    "SUBSCRIPTIONS",
    "WORKFLOWS",
    "AssigneesIn",
    "CloseFacts",
    "CloseTemplateImportIn",
    "PackageAssemblyWorkflow",
    "PlanDraftIn",
    "PlanRowIn",
    "PlanRowPatchIn",
    "PublishIn",
    "PublishInput",
    "PublishResult",
    "RequestPublishWorkflow",
    "RequestTemplateIn",
    "StatusGuard",
    "TransitionNotAvailable",
    "add_note",
    "add_request_template",
    "add_row",
    "close_for",
    "close_summary",
    "create_draft",
    "generate_closes",
    "get_plan",
    "import_template",
    "new_agent_draft",
    "open_exceptions",
    "patch_row",
    "publish",
    "raise_exception",
    "register_status_guard",
    "schedule_publish",
    "seed_synthetic_close_status",
    "set_assignees",
    "start_close",
    "status_guard",
]

# C-02-T02 (DEC-5501): the posting, W1 and delivery error codes, declared before their services.
from abacus.modules.closes import delivery_errors as delivery_errors  # noqa: E402

# T-06-T20 (DEC-5631): C12 hand-off gates this module owns (ledger never imports closes).
from abacus.modules.closes import handoff_gate as _handoff_gate  # noqa: E402

_handoff_gate.register()

# T-08-T20 (DEC-5917): this module's due dates on HOME-03 through platform's filing-deadline slot.
from abacus.modules.closes import deadline_sources as _filing_deadline_sources  # noqa: E402

_filing_deadline_sources.register()

# C-02-T39 (DEC-5922): the close-to-tax hand-off (CLS-12), closes side.
from abacus.modules.closes import tax_handoff as tax_handoff  # noqa: E402
