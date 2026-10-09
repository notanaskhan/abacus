"""Public interface of the connections module; other modules import only this (ADR-008)."""

from abacus.kernel.uow import Handler
from abacus.modules.connections.activities import ACTIVITIES
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
from abacus.modules.connections.events import ConnectionCreated, ConnectionRevoked
from abacus.modules.connections.fake import FakeConnector, fixture_path
from abacus.modules.connections.fake_format import parse_trial_balance
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
from abacus.modules.connections.retrievals import (
    WORKFLOWS,
    WorkflowUnavailable,
    trigger_retrieval,
    workflow_id,
)
from abacus.modules.connections.routes import complete_router, connection_router, router
from abacus.modules.connections.service import (
    CONNECTORS,
    ActionCapReached,
    NoConnection,
    RetrievalView,
    RunNotRunning,
    StartedRun,
    connector_for,
    load_system_context,
    retrieval_status,
    start_retrieval,
)
from abacus.modules.connections.workflow_types import FailInput, RetrievalInput, RetrievalOutcome
from abacus.modules.connections.workflows import RetrievalWorkflow

# Outbox events this module handles (the worker's relay routes them): none yet.
SUBSCRIPTIONS: dict[str, Handler] = {}

__all__ = [
    "ACTIVITIES",
    "CONNECTORS",
    "SUBSCRIPTIONS",
    "WORKFLOWS",
    "ActionCapReached",
    "Capabilities",
    "ConnectionCreated",
    "ConnectionRevoked",
    "Connector",
    "ConnectorError",
    "Dataset",
    "FailInput",
    "FakeConnector",
    "NoConnection",
    "NotSupported",
    "Period",
    "RawPayload",
    "RetrievalInput",
    "RetrievalOutcome",
    "RetrievalView",
    "RetrievalWorkflow",
    "RunFailed",
    "RunNotRunning",
    "RunResult",
    "StartedRun",
    "Unavailable",
    "WorkflowUnavailable",
    "complete_router",
    "connection_router",
    "connector_for",
    "fail_run",
    "fixture_path",
    "is_retryable",
    "load_system_context",
    "normalise_raw",
    "parse_trial_balance",
    "pull_raw",
    "render",
    "retrieval_status",
    "router",
    "run_pipeline",
    "snapshot",
    "start_retrieval",
    "trigger_retrieval",
    "validate_run",
    "workflow_id",
]
