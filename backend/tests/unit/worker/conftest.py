"""Worker test fixtures."""

from __future__ import annotations

import pytest

from abacus.worker import __main__ as worker_main


@pytest.fixture(autouse=True)
def tracing_shutdowns(monkeypatch: pytest.MonkeyPatch) -> list[bool]:
    """`run()` shuts the process's tracer provider down on exit. In the test process that provider
    is shared (`telemetry.test_exporter`), and shutting it down drops every later test's spans, so
    record the call instead."""
    calls: list[bool] = []
    monkeypatch.setattr(worker_main, "shutdown_tracing", lambda: calls.append(True))
    return calls


@pytest.fixture(autouse=True)
def metrics_shutdowns(monkeypatch: pytest.MonkeyPatch) -> list[bool]:
    """Likewise for the process's meter provider (`metrics.test_reader`)."""
    calls: list[bool] = []
    monkeypatch.setattr(worker_main, "shutdown_metrics", lambda: calls.append(True))
    return calls
