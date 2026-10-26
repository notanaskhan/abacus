"""Public interface of the audit_trail module; other modules import only this (ADR-008)."""

from abacus.kernel.uow.chain import Checkpoint, latest_checkpoint, verify_chain
from abacus.modules.audit_trail import audit_log_routes
from abacus.modules.audit_trail.activity_catalogue import (
    CatalogueEntry,
    activity_of,
    register_activity_kinds,
)
from abacus.modules.audit_trail.audit_log_contract import router as audit_log_router
from abacus.modules.audit_trail.explorer import (
    EventFilter,
    events_for_work_item,
    get_event,
    list_events,
)
from abacus.modules.audit_trail.labels import backfill as backfill_labels
from abacus.modules.audit_trail.labels import index_batch as index_labels
from abacus.modules.audit_trail.routes import router
from abacus.modules.audit_trail.service import events_for_target
from abacus.modules.identity.api import AbacusRouter, register_target_events

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (
    router,
    audit_log_router,  # G-02-T04 contract; list and detail live since G-02-T08, export T17
)

# G-01-T09 (AC8.6): the wall log reads its wall's events from the trail.
register_target_events(events_for_target)

# Q-02-T21: the audit hash chain lives beside the events it seals (kernel.uow); the audit trail
# answers for it (Q-02 §4.1: `latest_checkpoint`, `verify_chain`).
# G-02-T08 (SPEC-349 §5): `list_events`, `get_event`, `events_for_work_item` (A-01's binder
# export reads the last); modules register catalogue entries with `register_activity_kinds`.
# G-02-T10: the label index (`index_labels`, `backfill_labels`) for operators and, later, its
# Schedule (DEC-436).
# G-02-T08: importing the live reads registers them on the contract's router.
LIVE_READS = audit_log_routes.router

__all__ = [
    "LIVE_READS",
    "ROUTERS",
    "CatalogueEntry",
    "Checkpoint",
    "EventFilter",
    "activity_of",
    "backfill_labels",
    "events_for_target",
    "events_for_work_item",
    "get_event",
    "index_labels",
    "latest_checkpoint",
    "list_events",
    "register_activity_kinds",
    "router",
    "verify_chain",
]
