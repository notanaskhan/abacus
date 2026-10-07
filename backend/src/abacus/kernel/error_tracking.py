"""Error tracking with scrubbing by allowlist (ADR-022, ADR-031; TASK-013 design §4, Q4).

    configure_error_tracking("abacus-api")   # once, at process start; no-op without a DSN
    report(exc)                              # an unexpected error

Sentry is an external processor (ADR-021): it receives only what `scrub` keeps. Every event is
rebuilt from an allowlist, so nothing classified can slip through a denylist we forgot to extend:
the exception's type and stack frames (module, function, line; never local variables or source
context), environment, release, the trace and span IDs, and two tags (route template, tenant ID).
Exception messages are replaced by the type name (they can quote client data); requests,
headers, cookies, users, breadcrumbs, extras and any other context are dropped.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

import sentry_sdk
from sentry_sdk.types import Event, Hint
from temporalio import activity
from temporalio.exceptions import ApplicationError, CancelledError
from temporalio.worker import (
    ActivityInboundInterceptor,
    ExecuteActivityInput,
    Interceptor,
)

from abacus.kernel.config import settings
from abacus.kernel.telemetry import current_span_id, current_trace_id

_FRAME_KEYS = ("module", "function", "lineno", "in_app", "filename")
_TAGS = ("route", "tenant_id", "error_type", "activity")
_configured = False


def _frames(stacktrace: object) -> dict[str, object] | None:
    if not isinstance(stacktrace, Mapping):
        return None
    frames = cast(Mapping[str, object], stacktrace).get("frames")
    if not isinstance(frames, list):
        return None
    kept: list[dict[str, object]] = []
    for frame in cast(list[object], frames):
        if isinstance(frame, Mapping):
            mapping = cast(Mapping[str, object], frame)
            kept.append({k: mapping[k] for k in _FRAME_KEYS if k in mapping})
    return {"frames": kept}


def _exceptions(exception: object) -> dict[str, object] | None:
    if not isinstance(exception, Mapping):
        return None
    values = cast(Mapping[str, object], exception).get("values")
    if not isinstance(values, list):
        return None
    kept: list[dict[str, object]] = []
    for value in cast(list[object], values):
        if not isinstance(value, Mapping):
            continue
        mapping = cast(Mapping[str, object], value)
        kind = mapping.get("type")
        name = kind if isinstance(kind, str) else "Exception"
        entry: dict[str, object] = {"type": name, "value": name}
        if isinstance(mapping.get("module"), str):
            entry["module"] = mapping["module"]
        frames = _frames(mapping.get("stacktrace"))
        if frames is not None:
            entry["stacktrace"] = frames
        kept.append(entry)
    return {"values": kept}


def _trace(contexts: object) -> dict[str, object] | None:
    if not isinstance(contexts, Mapping):
        return None
    trace = cast(Mapping[str, object], contexts).get("trace")
    if not isinstance(trace, Mapping):
        return None
    mapping = cast(Mapping[str, object], trace)
    return {k: mapping[k] for k in ("trace_id", "span_id") if isinstance(mapping.get(k), str)}


def scrub(event: Event, _hint: Hint | None = None) -> Event | None:
    """The event Sentry may receive: rebuilt from the allowlist above."""
    raw = cast(Mapping[str, object], event)
    kept: dict[str, object] = {
        k: raw[k]
        for k in (
            "event_id",
            "timestamp",
            "level",
            "platform",
            "environment",
            "release",
            "sdk",
            "server_name",  # our service name ("abacus-api", "abacus-worker"), set at init
        )
        if k in raw
    }
    exception = _exceptions(raw.get("exception"))
    if exception is not None:
        kept["exception"] = exception
    trace = _trace(raw.get("contexts"))
    if trace:
        kept["contexts"] = {"trace": trace}
    tags = raw.get("tags")
    if isinstance(tags, Mapping):
        tag_map = cast(Mapping[str, object], tags)
        kept["tags"] = {k: tag_map[k] for k in _TAGS if isinstance(tag_map.get(k), str)}
    return cast(Event, kept)


def configure_error_tracking(service: str) -> bool:
    """Start Sentry if `sentry_dsn` is set (idempotent). True if errors are being reported."""
    global _configured
    if _configured:
        return True
    s = settings()
    if s.sentry_dsn is None:
        return False
    sentry_sdk.init(
        dsn=s.sentry_dsn.get_secret_value(),
        environment=s.environment,
        release=s.release,
        server_name=service,
        send_default_pii=False,
        include_local_variables=False,
        include_source_context=False,
        max_breadcrumbs=0,
        # No automatic integrations: they attach requests, logs and breadcrumbs. Errors are
        # reported explicitly (`report`) and scrubbed.
        default_integrations=False,
        auto_enabling_integrations=False,
        traces_sample_rate=0.0,
        # Nothing but scrubbed error events leaves: no metrics, logs, sessions or client reports.
        enable_metrics=False,
        enable_logs=False,
        auto_session_tracking=False,
        send_client_reports=False,
        before_send=scrub,
        before_send_transaction=lambda _event, _hint: None,
    )
    _configured = True
    return True


def report(exc: BaseException, **tags: str | None) -> None:
    """Report an unexpected error with allowlisted tags (scrubbed; no-op when tracking is off)."""
    if not _configured:
        return
    with sentry_sdk.new_scope() as scope:
        # Sentry's own trace context is unrelated to ours: use the OpenTelemetry trace.
        trace_id, span_id = current_trace_id(), current_span_id()
        if trace_id is not None:
            scope.set_context("trace", {"trace_id": trace_id, "span_id": span_id})
        for key, value in tags.items():
            if key in _TAGS and value is not None:
                scope.set_tag(key, value)
        sentry_sdk.capture_exception(exc)


class _ReportingActivityInbound(ActivityInboundInterceptor):
    async def execute_activity(self, input: ExecuteActivityInput) -> object:
        try:
            return await super().execute_activity(input)
        except CancelledError:
            raise  # shutdown or workflow cancellation: not a fault
        except ApplicationError as exc:
            # Activities raise ApplicationError named after the original class (class name only).
            # Non-retryable ones are decided outcomes (a failed run, a forbidden action), not
            # faults; retryable ones are infrastructure trouble worth an alert, reported once per
            # activity (its first attempt), not on every retry.
            info = activity.info()
            if not exc.non_retryable and info.attempt == 1:
                report(exc, error_type=exc.type, activity=info.activity_type)
            raise
        except Exception as exc:
            info = activity.info()
            if info.attempt == 1:
                report(exc, error_type=type(exc).__name__, activity=info.activity_type)
            raise


class ReportingInterceptor(Interceptor):
    """Worker interceptor: report unexpected activity failures to error tracking."""

    def intercept_activity(self, next: ActivityInboundInterceptor) -> ActivityInboundInterceptor:
        return _ReportingActivityInbound(next)


def flush_errors(timeout_seconds: float = 2.0) -> None:
    """Send reports still queued (process shutdown)."""
    if _configured:
        sentry_sdk.flush(timeout_seconds)
