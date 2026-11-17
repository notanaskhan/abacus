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
from abacus.modules.closes.contract import (
    CloseFacts,
    StatusGuard,
    TransitionNotAvailable,
    close_for,
    closes_router,
    register_status_guard,
    status_guard,
)
from abacus.modules.closes.contract_work import close_work_router, portal_close_router
from abacus.modules.closes.gate_sources import register_close_gates
from abacus.modules.closes.intake import ACTIVITIES as INTAKE_ACTIVITIES
from abacus.modules.closes.intake import schedule_publish
from abacus.modules.closes.intake_destination import register as intake_destination_register
from abacus.modules.closes.issues import CLOSE_TARGET, add_note, open_exceptions, raise_exception
from abacus.modules.closes.kind import CloseKind
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
from abacus.modules.closes.service import start_close
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
ROUTERS = (closes_router, close_work_router, portal_close_router)


# C-01-T19: the BD1 publish workflow; the worker reads these (no outbox subscriptions yet).
async def _on_close_created(event: OutboxEvent) -> None:
    close_id = event.payload.get("close_id")
    if isinstance(close_id, str):
        await schedule_publish(event.tenant_id, UUID(close_id))


SUBSCRIPTIONS: dict[str, Handler] = {
    "close.created": _on_close_created,
    **RECONCILIATION_SUBSCRIPTIONS,  # C-01-T23
    **REGISTRATION_SUBSCRIPTIONS,  # C-01-T26: close runs and answered questions (C16)
}
WORKFLOWS: dict[type, WorkClass] = {RequestPublishWorkflow: "background"}
register_work_classes(WORKFLOWS)
ACTIVITIES: tuple[Callable[..., Any], ...] = INTAKE_ACTIVITIES  # Any: Temporal activities

__all__ = [
    "ACTIVITIES",
    "AGENT_TOOLS",
    "CLOSE_TARGET",
    "PUBLISH_REQUESTS",
    "RECOMPUTE_REQUESTS",
    "REQUESTS_SECONDS_UNTIL",
    "ROUTERS",
    "SUBSCRIPTIONS",
    "WORKFLOWS",
    "CloseFacts",
    "PublishInput",
    "PublishResult",
    "RequestPublishWorkflow",
    "StatusGuard",
    "TransitionNotAvailable",
    "add_note",
    "close_for",
    "open_exceptions",
    "raise_exception",
    "register_status_guard",
    "schedule_publish",
    "start_close",
    "status_guard",
]
