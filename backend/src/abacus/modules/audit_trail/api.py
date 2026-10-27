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
from abacus.modules.audit_trail.exports import SUBSCRIPTIONS
from abacus.modules.audit_trail.jobs import ACTIVITIES, SCHEDULES, WORKFLOWS
from abacus.modules.audit_trail.labels import backfill as backfill_labels
from abacus.modules.audit_trail.labels import index_batch as index_labels
from abacus.modules.audit_trail.metrics import (
    METRIC_ACTIONS,
    MetricActionRefused,
    TargetDuration,
    Window,
    event_counts,
    first_to_last_durations,
)
from abacus.modules.audit_trail.routes import router
from abacus.modules.audit_trail.service import events_for_target
from abacus.modules.audit_trail.workflows import (
    CHECKPOINT_ID,
    LABELS_ID,
    PARTITIONS_ID,
    VERIFY_ID,
    AuditChainVerifyWorkflow,
    AuditCheckpointWorkflow,
    AuditExportFacts,
    AuditExportFailure,
    AuditExportInput,
    AuditExportWorkflow,
    AuditLabelIndexerWorkflow,
    AuditPartitionsWorkflow,
)
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
# G-02-T10: the label index (`index_labels`, `backfill_labels`) for operators, kept current by
# the `AuditLabelIndexer` Schedule every 60 seconds (DEC-453; a search still catches up first).
# G-02-T08, T17: importing the live routes registers them on the contract's router; G-02-T17's
# `SUBSCRIPTIONS` start `AuditExportWorkflow` from `audit_export.requested`.
LIVE_READS = audit_log_routes.router

# Q-02-T20, T21: partitions, checkpoints and the nightly verify on Schedules (the daily anchor is
# evidence's).
__all__ = [
    "ACTIVITIES",
    "CHECKPOINT_ID",
    "LABELS_ID",
    "LIVE_READS",
    "METRIC_ACTIONS",
    "PARTITIONS_ID",
    "ROUTERS",
    "SCHEDULES",
    "SUBSCRIPTIONS",
    "VERIFY_ID",
    "WORKFLOWS",
    "AuditChainVerifyWorkflow",
    "AuditCheckpointWorkflow",
    "AuditExportFacts",
    "AuditExportFailure",
    "AuditExportInput",
    "AuditExportWorkflow",
    "AuditLabelIndexerWorkflow",
    "AuditPartitionsWorkflow",
    "CatalogueEntry",
    "Checkpoint",
    "EventFilter",
    "MetricActionRefused",
    "TargetDuration",
    "Window",
    "activity_of",
    "backfill_labels",
    "event_counts",
    "events_for_target",
    "events_for_work_item",
    "first_to_last_durations",
    "get_event",
    "index_labels",
    "latest_checkpoint",
    "list_events",
    "register_activity_kinds",
    "router",
    "verify_chain",
]
