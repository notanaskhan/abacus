"""Public interface of the connections module; other modules import only this (ADR-008)."""

from abacus.kernel.dispatch import WorkClass, register_work_classes
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
    WorkflowUnavailable,
    trigger_retrieval,
    workflow_id,
)
from abacus.modules.connections.routes import router
from abacus.modules.connections.service import (
    CONNECTORS,
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

# Each workflow's work class (ADR-071; SPEC-003 Q1): a person waits on a retrieval they start.
WORKFLOWS: dict[type, WorkClass] = {RetrievalWorkflow: "interactive"}
register_work_classes(WORKFLOWS)
# Outbox events this module handles (the worker's relay routes them): none yet.
SUBSCRIPTIONS: dict[str, Handler] = {}

__all__ = [
    "ACTIVITIES",
    "CONNECTORS",
    "SUBSCRIPTIONS",
    "WORKFLOWS",
    "Capabilities",
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
