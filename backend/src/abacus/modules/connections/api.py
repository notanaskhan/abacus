"""Public interface of the connections module; other modules import only this (ADR-008)."""

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
from abacus.modules.connections.service import (
    CONNECTORS,
    NoConnection,
    RunNotRunning,
    connector_for,
    initiator_for_snapshot,
    load_system_context,
    start_retrieval,
)

__all__ = [
    "CONNECTORS",
    "Capabilities",
    "Connector",
    "ConnectorError",
    "Dataset",
    "FakeConnector",
    "NoConnection",
    "NotSupported",
    "Period",
    "RawPayload",
    "RunFailed",
    "RunNotRunning",
    "RunResult",
    "Unavailable",
    "connector_for",
    "fail_run",
    "fixture_path",
    "initiator_for_snapshot",
    "is_retryable",
    "load_system_context",
    "normalise_raw",
    "parse_trial_balance",
    "pull_raw",
    "render",
    "run_pipeline",
    "snapshot",
    "start_retrieval",
    "validate_run",
]
