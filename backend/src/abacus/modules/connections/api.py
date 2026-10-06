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
from abacus.modules.connections.pipeline import (
    RunFailed,
    RunResult,
    extract,
    normalise_raw,
    render,
    run_pipeline,
    snapshot,
    store_raw,
    validate_run,
)
from abacus.modules.connections.service import (
    NoConnection,
    StartedRun,
    connector_for,
    start_retrieval,
)

__all__ = [
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
    "RunResult",
    "StartedRun",
    "Unavailable",
    "connector_for",
    "extract",
    "fixture_path",
    "normalise_raw",
    "render",
    "run_pipeline",
    "snapshot",
    "start_retrieval",
    "store_raw",
    "validate_run",
]
