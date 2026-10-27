"""Public interface of the connections module; other modules import only this (ADR-008)."""

from datetime import timedelta

from abacus.kernel.audit_owners import register_engagement_owners, register_entity_owners
from abacus.kernel.dispatch import PlatformSchedule, register_work_classes
from abacus.kernel.uow import Handler
from abacus.modules.connections.activities import ACTIVITIES as RUN_ACTIVITIES
from abacus.modules.connections.audit_targets import AUDIT_KINDS, audit_entities, audit_owners
from abacus.modules.connections.auto_retrieval import (
    auto_retrieve,
    available_datasets,
    on_connection_created,
    on_item_classified,
)
from abacus.modules.connections.connector import (
    Capabilities,
    Connector,
    ConnectorError,
    Dataset,
    NotSupported,
    Period,
    RawPayload,
    Unavailable,
)
from abacus.modules.connections.entity import (
    ActivityLine,
    AuthorizationRequired,
    Completed,
    ConnectionDetail,
    ConnectionNeedsReauth,
    ConnectorNotAvailable,
    ConnectTarget,
    ConsentShown,
    ConsentVersionStale,
    EntityConnections,
    EntityConnectionView,
    LedgerAlreadyConnected,
    RunRef,
    RunSummary,
    Started,
    authorised_engagement,
    complete_any,
    connection_detail,
    disconnect,
    entity_connections,
    entity_of_connection,
    retry,
    start_entity,
)
from abacus.modules.connections.events import (
    ConnectionCreated,
    ConnectionReauthorized,
    ConnectionRevoked,
    LedgerSnapshotRecorded,
)
from abacus.modules.connections.fake import FakeConnector, fixture_path
from abacus.modules.connections.fake_format import parse_trial_balance
from abacus.modules.connections.gl_import import WORKFLOWS as GL_WORKFLOWS
from abacus.modules.connections.gl_import import on_ledger_snapshot_recorded
from abacus.modules.connections.grants import GrantRevocationRequested, revoke_retired
from abacus.modules.connections.health import check_connection_health_activity
from abacus.modules.connections.pipeline import (
    RunFailed,
    RunResult,
    fail_run,
    is_retryable,
    normalise_raw,
    pull_raw,
    render,
    run_pipeline,
    snapshot,
    validate_run,
)
from abacus.modules.connections.reconnect import (
    ReconnectRequested,
    reconnect_todo_count,
    request_reconnect,
)
from abacus.modules.connections.retrievals import (
    WORKFLOWS,
    WorkflowUnavailable,
    trigger_retrieval,
    workflow_id,
)
from abacus.modules.connections.routes import complete_router, connection_router, router
from abacus.modules.connections.service import (
    CONNECTORS,
    NETWORKLESS_PROVIDERS,
    ActionCapReached,
    NoConnection,
    RetrievalView,
    RunNotRunning,
    StartedRun,
    connector_for,
    load_system_context,
    qbo_app,
    retrieval_status,
    start_retrieval,
)
from abacus.modules.connections.workflow_types import (
    FailInput,
    GlImportInput,
    RetrievalInput,
    RetrievalOutcome,
)
from abacus.modules.connections.workflows import (
    CONNECTION_HEALTH_ID,
    ConnectionHealthWorkflow,
    GlImportWorkflow,
    RetrievalWorkflow,
)
from abacus.modules.engagements.api import register_auto_retrieval
from abacus.modules.identity.api import AbacusRouter
from abacus.modules.requests.api import register_available_datasets

# Outbox events this module handles (the worker's relay routes them): automatic retrieval when a
# client connects or an item becomes retrievable (SPEC-022 AC-4).
SUBSCRIPTIONS: dict[str, Handler] = {
    # A-02-T16 review M1: a retired grant is revoked at the provider after commit.
    GrantRevocationRequested.event_type: revoke_retired,
    "connection.created": on_connection_created,
    "request_item.classified": on_item_classified,
    # SPEC-034 (TASK-069): a trial balance arrived; general ledgers waiting for it follow.
    LedgerSnapshotRecorded.event_type: on_ledger_snapshot_recorded,
}
WORKFLOWS.update(GL_WORKFLOWS)
# A-02-T25 (DEC-708): the daily health pass, a platform job.
WORKFLOWS[ConnectionHealthWorkflow] = "background"
register_work_classes({ConnectionHealthWorkflow: "background"})
ACTIVITIES = (*RUN_ACTIVITIES, check_connection_health_activity)
SCHEDULES: tuple[PlatformSchedule, ...] = (
    PlatformSchedule(
        id=CONNECTION_HEALTH_ID,
        workflow=ConnectionHealthWorkflow,
        every=timedelta(days=1),
        note="A-02-T25: refresh and health of every live provider connection, daily",
    ),
)
# SPEC-022 D2: requests learns what the live connection can deliver from here.
register_available_datasets(available_datasets)

# SPEC-027 (TASK-050): the engagement agent starts this rule through engagements (ADR-106).
register_auto_retrieval(auto_retrieve)

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (
    router,
    connection_router,
    complete_router,
)

# DEC-121: the audit explorer asks each owner which engagement its targets belong to.
register_engagement_owners(AUDIT_KINDS - {"connection"}, audit_owners)
register_entity_owners({"connection"}, audit_entities)

__all__ = [
    "ACTIVITIES",
    "CONNECTORS",
    "NETWORKLESS_PROVIDERS",
    "ROUTERS",
    "SCHEDULES",
    "SUBSCRIPTIONS",
    "WORKFLOWS",
    "ActionCapReached",
    "ActivityLine",
    "AuthorizationRequired",
    "Capabilities",
    "Completed",
    "ConnectTarget",
    "ConnectionCreated",
    "ConnectionDetail",
    "ConnectionNeedsReauth",
    "ConnectionReauthorized",
    "ConnectionRevoked",
    "Connector",
    "ConnectorError",
    "ConnectorNotAvailable",
    "ConsentShown",
    "ConsentVersionStale",
    "Dataset",
    "EntityConnectionView",
    "EntityConnections",
    "FailInput",
    "FakeConnector",
    "GlImportInput",
    "GlImportWorkflow",
    "LedgerAlreadyConnected",
    "LedgerSnapshotRecorded",
    "NoConnection",
    "NotSupported",
    "Period",
    "RawPayload",
    "ReconnectRequested",
    "RetrievalInput",
    "RetrievalOutcome",
    "RetrievalView",
    "RetrievalWorkflow",
    "RunFailed",
    "RunNotRunning",
    "RunRef",
    "RunResult",
    "RunSummary",
    "Started",
    "StartedRun",
    "Unavailable",
    "WorkflowUnavailable",
    "authorised_engagement",
    "auto_retrieve",
    "complete_any",
    "complete_router",
    "connection_detail",
    "connection_router",
    "connector_for",
    "disconnect",
    "entity_connections",
    "entity_of_connection",
    "fail_run",
    "fixture_path",
    "is_retryable",
    "load_system_context",
    "normalise_raw",
    "parse_trial_balance",
    "pull_raw",
    "qbo_app",
    "reconnect_todo_count",
    "render",
    "request_reconnect",
    "retrieval_status",
    "retry",
    "revoke_retired",
    "router",
    "run_pipeline",
    "snapshot",
    "start_entity",
    "start_retrieval",
    "trigger_retrieval",
    "validate_run",
    "workflow_id",
]
