"""AC-20: the trace context on reports, flushing, and which activity failures are reported
(TASK-013 contract revision 1, "Sentry"; ADR-022, ADR-031)."""

from __future__ import annotations

import asyncio
import dataclasses
import json
from collections.abc import Iterator
from typing import Any, ClassVar, cast

import pytest
import sentry_sdk
from sentry_sdk.envelope import Envelope
from sentry_sdk.transport import Transport
from temporalio.exceptions import ApplicationError, CancelledError
from temporalio.testing import ActivityEnvironment
from temporalio.worker import ActivityInboundInterceptor, ExecuteActivityInput

from abacus.kernel.config import settings
from abacus.kernel.error_tracking import (
    ReportingInterceptor,
    configure_error_tracking,
    flush_errors,
    report,
)
from abacus.kernel.telemetry import current_span_id, current_trace_id, tracer
from abacus.kernel.telemetry import test_exporter as shared_exporter

Json = dict[str, Any]  # Sentry events and options: untyped JSON-like dicts
DSN = "https://public@example.invalid/1"


class Capture(Transport):
    events: ClassVar[list[Json]] = []

    def capture_envelope(self, envelope: Envelope) -> None:
        event = envelope.get_event()
        if event is not None:
            Capture.events.append(cast(Json, event))


@pytest.fixture(autouse=True)
def clean(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    shared_exporter()
    monkeypatch.delenv("ABACUS_SENTRY_DSN", raising=False)
    settings.cache_clear()
    monkeypatch.setattr("abacus.kernel.error_tracking._configured", False)
    Capture.events = []
    yield
    sentry_sdk.get_client().close()
    sentry_sdk.get_global_scope().set_client(None)
    monkeypatch.undo()
    settings.cache_clear()


@pytest.fixture
def started(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ABACUS_SENTRY_DSN", DSN)
    settings.cache_clear()
    real = sentry_sdk.init

    def init(**options: object) -> None:
        real(**cast(Json, options), transport=Capture)

    monkeypatch.setattr(sentry_sdk, "init", init)
    assert configure_error_tracking("abacus-worker") is True


def _error() -> RuntimeError:
    try:
        raise RuntimeError("boom")
    except RuntimeError as exc:
        return exc


# --- trace context -------------------------------------------------------------------------------


@pytest.mark.usefixtures("started")
def test_ac20_a_report_inside_a_span_carries_that_traces_ids() -> None:
    with tracer("t").start_as_current_span("work"):
        expected = {"trace_id": current_trace_id(), "span_id": current_span_id()}
        report(_error(), route="/v1/me")
    sentry_sdk.flush()
    [event] = Capture.events
    assert event["contexts"] == {"trace": expected}
    assert len(expected["trace_id"] or "") == 32


@pytest.mark.usefixtures("started")
def test_ac20_the_report_names_the_service() -> None:
    report(_error())
    sentry_sdk.flush()
    [event] = Capture.events
    assert event["server_name"] == "abacus-worker"


# --- flush_errors --------------------------------------------------------------------------------


def test_ac20_flush_errors_does_nothing_when_error_tracking_is_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []

    def fake(*args: object, **kwargs: object) -> None:
        calls.append((args, kwargs))

    monkeypatch.setattr(sentry_sdk, "flush", fake)
    flush_errors()
    assert calls == []


@pytest.mark.usefixtures("started")
def test_ac20_flush_errors_flushes_when_error_tracking_is_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []

    def fake(*args: object, **kwargs: object) -> None:
        calls.append((args, kwargs))

    monkeypatch.setattr(sentry_sdk, "flush", fake)
    flush_errors()
    assert len(calls) == 1


# --- ReportingInterceptor ------------------------------------------------------------------------


@dataclasses.dataclass
class Reported:
    exc: BaseException
    tags: dict[str, str | None]


@pytest.fixture
def reports(monkeypatch: pytest.MonkeyPatch) -> list[Reported]:
    seen: list[Reported] = []

    def fake(exc: BaseException, **tags: str | None) -> None:
        seen.append(Reported(exc, tags))

    monkeypatch.setattr("abacus.kernel.error_tracking.report", fake)
    return seen


async def _run(raised: BaseException, *, attempt: int = 1) -> BaseException:
    class Inner(ActivityInboundInterceptor):
        async def execute_activity(self, input: ExecuteActivityInput) -> object:
            raise raised

    async def activity_fn() -> None:
        return None

    outer = ReportingInterceptor().intercept_activity(
        Inner(cast(ActivityInboundInterceptor, None))
    )
    environment = ActivityEnvironment()
    environment.info = dataclasses.replace(
        environment.info, activity_type="screen", attempt=attempt
    )
    given = ExecuteActivityInput(fn=activity_fn, args=[], executor=None, headers={})
    with pytest.raises(BaseException) as raised_out:
        await environment.run(outer.execute_activity, given)
    return raised_out.value


async def test_ac20_a_cancelled_activity_is_not_reported_and_is_re_raised(
    reports: list[Reported],
) -> None:
    error = CancelledError("shutdown")
    assert await _run(error) is error
    assert reports == []


@pytest.mark.parametrize("attempt", [2, 3, 10])
async def test_ac20_a_retryable_application_error_is_reported_on_the_first_attempt_only(
    reports: list[Reported], attempt: int
) -> None:
    error = ApplicationError("down", type="ConnectionError")
    assert await _run(error, attempt=attempt) is error
    assert reports == []


async def test_ac20_a_retryable_application_error_is_reported_on_attempt_one(
    reports: list[Reported],
) -> None:
    error = ApplicationError("down", type="ConnectionError")
    assert await _run(error, attempt=1) is error
    [one] = reports
    assert one.tags == {"error_type": "ConnectionError", "activity": "screen"}


@pytest.mark.parametrize("attempt", [1, 2, 5])
async def test_ac20_a_non_retryable_application_error_is_never_reported(
    reports: list[Reported], attempt: int
) -> None:
    error = ApplicationError("decided", type="Forbidden", non_retryable=True)
    assert await _run(error, attempt=attempt) is error
    assert reports == []


@pytest.mark.parametrize("attempt", [2, 3])
async def test_ac20_any_other_exception_is_reported_on_the_first_attempt_only(
    reports: list[Reported], attempt: int
) -> None:
    error = ValueError("x")
    assert await _run(error, attempt=attempt) is error
    assert reports == []


async def test_ac20_any_other_exception_is_reported_on_attempt_one(
    reports: list[Reported],
) -> None:
    error = ValueError("x")
    assert await _run(error, attempt=1) is error
    [one] = reports
    assert one.tags == {"error_type": "ValueError", "activity": "screen"}


async def test_ac20_an_asyncio_cancellation_passes_through_unreported(
    reports: list[Reported],
) -> None:
    class Inner(ActivityInboundInterceptor):
        async def execute_activity(self, input: ExecuteActivityInput) -> object:
            raise asyncio.CancelledError

    async def activity_fn() -> None:
        return None

    outer = ReportingInterceptor().intercept_activity(
        Inner(cast(ActivityInboundInterceptor, None))
    )
    given = ExecuteActivityInput(fn=activity_fn, args=[], executor=None, headers={})
    with pytest.raises(asyncio.CancelledError):
        await ActivityEnvironment().run(outer.execute_activity, given)
    assert reports == []


@pytest.mark.usefixtures("started")
async def test_ac20_a_reported_activity_failure_reaches_sentry_without_its_message() -> None:
    await _run(ApplicationError("cell SECRET-ROW-1", type="ConnectionError"))
    sentry_sdk.flush()
    assert Capture.events
    assert "SECRET-ROW-1" not in json.dumps(Capture.events)
