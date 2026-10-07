"""AC-20: error tracking with allowlist scrubbing (TASK-013 interface contract, "Error tracking";
ADR-022, ADR-031).

`scrub` is tested with hostile events: every value that must not leave the process carries a
marker, and nothing carrying it may survive. Configuration is tested with a capturing transport,
so no event leaves the process, and the module's remembered state is reset around each test.
"""

from __future__ import annotations

import copy
import dataclasses
import json
from collections.abc import Iterator, Mapping
from typing import Any, ClassVar, cast

import pytest
import sentry_sdk
from sentry_sdk.envelope import Envelope
from sentry_sdk.transport import Transport
from sentry_sdk.types import Event
from temporalio.exceptions import ApplicationError
from temporalio.testing import ActivityEnvironment
from temporalio.worker import ActivityInboundInterceptor, ExecuteActivityInput

from abacus.kernel.config import settings
from abacus.kernel.error_tracking import (
    ReportingInterceptor,
    configure_error_tracking,
    report,
    scrub,
)

Json = dict[str, Any]  # Sentry events and options: untyped JSON-like dicts
MARKER = "HOSTILE-MARKER-7731"
DSN = "https://public@example.invalid/1"
TOP_LEVEL_ALLOWED = {
    "event_id",
    "timestamp",
    "level",
    "platform",
    "environment",
    "release",
    "sdk",
    "server_name",
    "exception",
    "contexts",
    "tags",
}
FRAME_ALLOWED = {"module", "function", "lineno", "in_app", "filename"}
TAGS_ALLOWED = {"route", "tenant_id", "error_type", "activity"}


def _frame(**extra: object) -> dict[str, object]:
    return {
        "module": "abacus.modules.ledger.service",
        "function": "load_trial_balance",
        "lineno": 42,
        "in_app": True,
        "filename": "abacus/modules/ledger/service.py",
        "abs_path": "/srv/abacus/modules/ledger/service.py",
        **extra,
    }


def _kept_frame(**changes: object) -> dict[str, object]:
    """The frame as scrubbed: location only (no `abs_path`, no variables, no source)."""
    kept = {k: v for k, v in _frame().items() if k != "abs_path"}
    return {**kept, **changes}


def hostile() -> dict[str, object]:
    return {
        "event_id": "0123456789abcdef0123456789abcdef",
        "timestamp": "2026-10-07T10:00:00.000000Z",
        "level": "error",
        "platform": "python",
        "environment": "production",
        "release": "2026.10.07",
        "sdk": {"name": "sentry.python", "version": "2.0.0"},
        "message": f"cell value {MARKER}",
        "logentry": {"message": f"bad row {MARKER}", "params": [MARKER]},
        "logger": f"logger.{MARKER}",
        "transaction": f"/v1/clients/{MARKER}",
        "transaction_info": {"source": "url"},
        "server_name": "abacus-api",
        "fingerprint": [MARKER],
        "modules": {MARKER: "1.0"},
        "exception": {
            "values": [
                {
                    "type": "ValueError",
                    "value": f"trial balance row {MARKER} does not balance",
                    "module": "builtins",
                    "mechanism": {"type": "generic", "data": {"note": MARKER}},
                    "thread_id": 7,
                    "stacktrace": {
                        "frames": [
                            _frame(
                                vars={"trial_balance": MARKER, "amount": "1234.56"},
                                pre_context=[f"before {MARKER}"],
                                context_line=f"raise ValueError('{MARKER}')",
                                post_context=[f"after {MARKER}"],
                                data={"secret": MARKER},
                            ),
                            _frame(function="inner", lineno=7, vars={"x": MARKER}),
                        ],
                        "registers": {"rip": MARKER},
                    },
                },
                {
                    "type": "KeyError",
                    "value": MARKER,
                    "stacktrace": {"frames": [_frame(vars={"k": MARKER})]},
                },
            ]
        },
        "request": {
            "url": f"https://api.example.invalid/v1/clients/{MARKER}?token={MARKER}",
            "method": "POST",
            "headers": {"Authorization": f"Bearer {MARKER}", "Cookie": f"sid={MARKER}"},
            "cookies": {"sid": MARKER},
            "query_string": f"q={MARKER}",
            "data": {"balance": MARKER},
            "env": {"REMOTE_ADDR": "10.1.2.3"},
        },
        "user": {"id": MARKER, "email": f"{MARKER}@example.test", "ip_address": "10.1.2.3"},
        "extra": {"rows": [MARKER], "sys.argv": [MARKER]},
        "breadcrumbs": {"values": [{"category": "log", "message": MARKER, "data": {"a": MARKER}}]},
        "contexts": {
            "trace": {
                "trace_id": "a" * 32,
                "span_id": "b" * 16,
                "parent_span_id": "c" * 16,
                "op": f"http.server.{MARKER}",
                "status": "internal_error",
                "data": {"sql": MARKER},
            },
            "device": {"name": MARKER},
            "runtime": {"name": "CPython", "version": MARKER},
            "response": {"data": MARKER},
            "trial_balance": {"lines": [MARKER]},
        },
        "tags": {
            "route": "/v1/engagements/{engagement_id}/request-items",
            "tenant_id": "11111111-1111-1111-1111-111111111111",
            "error_type": "ValueError",
            "activity": "screen",
            "client_name": MARKER,
            "url": f"/v1/clients/{MARKER}",
            "runtime": MARKER,
        },
    }


def _scrubbed(event: Mapping[str, object] | None = None) -> Json:
    result = scrub(cast(Event, hostile() if event is None else dict(event)))
    assert result is not None
    return cast(Json, result)


# --- scrub: nothing hostile survives -------------------------------------------------------------


def test_ac20_scrub_leaves_no_trace_of_any_hostile_value() -> None:
    assert MARKER not in json.dumps(_scrubbed())


def test_ac20_scrub_keeps_only_allowlisted_top_level_keys() -> None:
    assert set(_scrubbed()) <= TOP_LEVEL_ALLOWED


@pytest.mark.parametrize(
    "key",
    [
        "message",
        "logentry",
        "logger",
        "request",
        "user",
        "extra",
        "breadcrumbs",
        "modules",
        "fingerprint",
        "transaction",
    ],
)
def test_ac20_scrub_drops_these_top_level_keys(key: str) -> None:
    assert key not in _scrubbed()


@pytest.mark.parametrize(
    "path",
    [
        ("request", "headers", "Authorization"),
        ("request", "cookies"),
        ("request", "data"),
        ("request", "query_string"),
        ("request", "url"),
        ("user", "email"),
    ],
)
def test_ac20_scrub_drops_the_request_and_user_parts_even_when_they_are_alone(
    path: tuple[str, ...],
) -> None:
    event: dict[str, object] = {"level": "error"}
    cursor: dict[str, object] = event
    for part in path[:-1]:
        nested: dict[str, object] = {}
        cursor[part] = nested
        cursor = nested
    cursor[path[-1]] = MARKER
    result = _scrubbed(event)
    assert MARKER not in json.dumps(result)
    assert result["level"] == "error"


def test_ac20_scrub_keeps_the_allowlisted_event_fields_as_they_are() -> None:
    result = _scrubbed()
    for key in (
        "event_id",
        "timestamp",
        "level",
        "platform",
        "environment",
        "release",
        "sdk",
        "server_name",
    ):
        assert result[key] == hostile()[key]


def test_ac20_scrub_keeps_the_service_name_but_never_a_path_in_frames() -> None:
    result = _scrubbed()
    assert result["server_name"] == "abacus-api"
    for value in result["exception"]["values"]:
        for frame in value["stacktrace"]["frames"]:
            assert "abs_path" not in frame
    assert "/srv/abacus" not in json.dumps(result)


def test_ac20_scrub_exception_values_are_type_value_module_and_frames_only() -> None:
    values = _scrubbed()["exception"]["values"]
    assert [v["type"] for v in values] == ["ValueError", "KeyError"]
    for value in values:
        assert set(value) <= {"type", "value", "module", "stacktrace"}
        assert value["value"] == value["type"]  # the message is replaced by the type name
    assert values[0]["module"] == "builtins"
    assert "module" not in values[1]


def test_ac20_scrub_frames_keep_location_but_never_variables_or_source() -> None:
    frames = _scrubbed()["exception"]["values"][0]["stacktrace"]["frames"]
    assert len(frames) == 2
    assert frames[0] == _kept_frame()
    assert frames[1] == _kept_frame(function="inner", lineno=7)
    for frame in frames:
        assert set(frame) <= FRAME_ALLOWED
        for dropped in ("vars", "pre_context", "context_line", "post_context", "data"):
            assert dropped not in frame


def test_ac20_scrub_drops_stacktrace_extras() -> None:
    stacktrace = _scrubbed()["exception"]["values"][0]["stacktrace"]
    assert set(stacktrace) == {"frames"}


def test_ac20_scrub_keeps_only_the_trace_and_span_ids_of_the_trace_context() -> None:
    result = _scrubbed()
    assert result["contexts"] == {"trace": {"trace_id": "a" * 32, "span_id": "b" * 16}}


def test_ac20_scrub_drops_other_contexts_when_there_is_no_trace() -> None:
    event = hostile()
    contexts = cast(dict[str, object], event["contexts"])
    del contexts["trace"]
    result = _scrubbed(event)
    assert "device" not in json.dumps(result.get("contexts", {}))
    assert MARKER not in json.dumps(result)


def test_ac20_scrub_keeps_only_the_four_allowed_tags() -> None:
    tags = _scrubbed()["tags"]
    assert tags == {
        "route": "/v1/engagements/{engagement_id}/request-items",
        "tenant_id": "11111111-1111-1111-1111-111111111111",
        "error_type": "ValueError",
        "activity": "screen",
    }
    assert set(tags) <= TAGS_ALLOWED


def test_ac20_scrub_drops_a_tag_that_is_not_on_the_allowlist_when_alone() -> None:
    result = _scrubbed({"level": "error", "tags": {"customer": MARKER, "route": "/v1/me"}})
    assert result["tags"] == {"route": "/v1/me"}


def test_ac20_scrub_returns_a_new_event_and_leaves_the_input_untouched() -> None:
    event = hostile()
    before = copy.deepcopy(event)
    result = scrub(cast(Event, event))
    assert result is not event
    assert event == before
    exception = cast(Json, result)["exception"]
    exception["values"].append({"type": "Changed"})
    assert event == before


def test_ac20_scrub_handles_a_bare_event() -> None:
    result = _scrubbed({"level": "error"})
    assert result["level"] == "error"
    assert set(result) <= TOP_LEVEL_ALLOWED


BARE_EXCEPTIONS: list[dict[str, object]] = [
    {"values": [{"type": "ValueError", "value": MARKER}]},
    {"values": [{"type": "ValueError", "value": MARKER, "stacktrace": {"frames": []}}]},
    {"values": [{"type": "ValueError", "value": MARKER, "stacktrace": {}}]},
]


@pytest.mark.parametrize("exception", BARE_EXCEPTIONS)
def test_ac20_scrub_replaces_the_message_even_without_frames(exception: object) -> None:
    result = _scrubbed({"level": "error", "exception": exception})
    assert MARKER not in json.dumps(result)
    assert result["exception"]["values"][0]["value"] == "ValueError"


# --- configure_error_tracking --------------------------------------------------------------------


class Capture(Transport):
    """A Sentry transport that keeps the events it is given (and sends nothing)."""

    events: ClassVar[list[Json]] = []

    def capture_envelope(self, envelope: Envelope) -> None:
        event = envelope.get_event()
        if event is not None:
            Capture.events.append(cast(Json, event))


@pytest.fixture(autouse=True)
def clean(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """No DSN, no remembered configuration, and an empty Sentry client, around every test."""
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
def dsn(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("ABACUS_SENTRY_DSN", DSN)
    monkeypatch.setenv("ABACUS_ENVIRONMENT", "test")
    monkeypatch.setenv("ABACUS_RELEASE", "2026.10.07-abc")
    settings.cache_clear()
    return DSN


@pytest.fixture
def inits(monkeypatch: pytest.MonkeyPatch) -> list[Json]:
    """Every `sentry_sdk.init` call's options; the real init runs with the capturing transport."""
    calls: list[Json] = []
    real = sentry_sdk.init

    def init(**options: object) -> None:
        calls.append(dict(options))
        real(**cast(Json, options), transport=Capture)

    monkeypatch.setattr(sentry_sdk, "init", init)
    return calls


def test_ac20_without_a_dsn_error_tracking_stays_off(inits: list[Json]) -> None:
    assert configure_error_tracking("abacus-api") is False
    assert inits == []
    assert sentry_sdk.get_client().is_active() is False


def test_ac20_without_a_dsn_a_repeated_call_is_still_off(inits: list[Json]) -> None:
    assert configure_error_tracking("abacus-api") is False
    assert configure_error_tracking("abacus-worker") is False
    assert inits == []


def test_ac20_with_a_dsn_error_tracking_starts(dsn: str, inits: list[Json]) -> None:
    assert configure_error_tracking("abacus-api") is True
    assert len(inits) == 1
    assert sentry_sdk.get_client().is_active() is True


def test_ac20_with_a_dsn_the_sdk_is_set_up_to_collect_nothing_extra(
    dsn: str, inits: list[Json]
) -> None:
    configure_error_tracking("abacus-api")
    options = sentry_sdk.get_client().options
    assert options["dsn"] == dsn
    assert options["send_default_pii"] is False
    assert options["include_local_variables"] is False
    assert options["include_source_context"] is False
    assert options["max_breadcrumbs"] == 0
    assert options["default_integrations"] is False
    assert options["auto_enabling_integrations"] is False
    assert options["before_send"] is scrub
    assert options["enable_logs"] is False
    assert options["auto_session_tracking"] is False
    assert options["send_client_reports"] is False
    assert options["traces_sample_rate"] == 0.0
    assert not options.get("enable_metrics", False)
    assert options["environment"] == "test"
    assert options["release"] == "2026.10.07-abc"


def test_ac20_with_a_dsn_the_sdk_receives_the_secret_value_not_its_repr(
    dsn: str, inits: list[Json]
) -> None:
    configure_error_tracking("abacus-api")
    assert inits[0]["dsn"] == DSN
    assert "**" not in str(inits[0]["dsn"])


def test_ac20_configure_error_tracking_is_idempotent(dsn: str, inits: list[Json]) -> None:
    assert configure_error_tracking("abacus-api") is True
    assert configure_error_tracking("abacus-api") is True
    assert configure_error_tracking("abacus-worker") is True
    assert len(inits) == 1


# --- report --------------------------------------------------------------------------------------


@pytest.fixture
def captured_calls(monkeypatch: pytest.MonkeyPatch) -> list[BaseException]:
    seen: list[BaseException] = []

    def fake(exc: BaseException | None = None, **_: object) -> None:
        if exc is not None:
            seen.append(exc)

    monkeypatch.setattr(sentry_sdk, "capture_exception", fake)
    return seen


def test_ac20_report_is_a_no_op_when_error_tracking_is_off(
    captured_calls: list[BaseException],
) -> None:
    report(RuntimeError(MARKER), route="/v1/me", tenant_id="t")
    assert captured_calls == []
    assert Capture.events == []


def _raised() -> RuntimeError:
    try:
        secret_row = MARKER  # a local the report must never carry
        raise RuntimeError(f"{secret_row} is not a number")
    except RuntimeError as exc:
        return exc


def test_ac20_report_sends_one_scrubbed_event_with_only_allowlisted_tags(
    dsn: str, inits: list[Json]
) -> None:
    configure_error_tracking("abacus-api")
    report(
        _raised(),
        route="/v1/engagements/{engagement_id}",
        tenant_id="11111111-1111-1111-1111-111111111111",
        error_type="RuntimeError",
        activity="screen",
        customer=MARKER,
        url=f"/v1/clients/{MARKER}",
    )
    sentry_sdk.flush()
    [event] = Capture.events
    assert MARKER not in json.dumps(event)
    assert event["tags"] == {
        "route": "/v1/engagements/{engagement_id}",
        "tenant_id": "11111111-1111-1111-1111-111111111111",
        "error_type": "RuntimeError",
        "activity": "screen",
    }
    [value] = event["exception"]["values"]
    assert (value["type"], value["value"]) == ("RuntimeError", "RuntimeError")
    assert set(event) <= TOP_LEVEL_ALLOWED
    assert event["environment"] == "test"
    assert event["release"] == "2026.10.07-abc"
    for frame in value["stacktrace"]["frames"]:
        assert set(frame) <= FRAME_ALLOWED
    assert event["server_name"] == "abacus-api"


def test_ac20_report_skips_tags_that_are_none(dsn: str, inits: list[Json]) -> None:
    configure_error_tracking("abacus-api")
    report(_raised(), route=None, activity="screen")
    sentry_sdk.flush()
    [event] = Capture.events
    assert event["tags"] == {"activity": "screen"}


def test_ac20_tags_do_not_leak_from_one_report_to_the_next(dsn: str, inits: list[Json]) -> None:
    configure_error_tracking("abacus-api")
    report(_raised(), route="/first", tenant_id="t-1")
    report(_raised(), activity="second")
    sentry_sdk.flush()
    first, second = Capture.events
    assert first["tags"] == {"route": "/first", "tenant_id": "t-1"}
    assert second["tags"] == {"activity": "second"}


def test_ac20_report_carries_no_request_user_breadcrumbs_or_extra(
    dsn: str, inits: list[Json]
) -> None:
    configure_error_tracking("abacus-api")
    sentry_sdk.set_user({"id": MARKER, "email": f"{MARKER}@example.test"})
    sentry_sdk.set_extra("rows", MARKER)
    sentry_sdk.set_context("trial_balance", {"lines": MARKER})
    sentry_sdk.add_breadcrumb(category="log", message=MARKER)
    report(_raised(), route="/v1/me")
    sentry_sdk.flush()
    [event] = Capture.events
    assert MARKER not in json.dumps(event)
    for key in ("user", "extra", "breadcrumbs", "request", "message", "logentry"):
        assert key not in event


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


async def _run(raised: BaseException, activity_type: str = "screen") -> BaseException:
    """Drive an activity that raises `raised` through the interceptor; return what comes out."""

    class Inner(ActivityInboundInterceptor):
        async def execute_activity(self, input: ExecuteActivityInput) -> object:
            raise raised

    async def activity_fn() -> None:
        return None

    outer = ReportingInterceptor().intercept_activity(
        Inner(cast(ActivityInboundInterceptor, None))
    )
    environment = ActivityEnvironment()
    environment.info = dataclasses.replace(environment.info, activity_type=activity_type)
    given = ExecuteActivityInput(fn=activity_fn, args=[], executor=None, headers={})
    with pytest.raises(BaseException) as raised_out:
        await environment.run(outer.execute_activity, given)
    return raised_out.value


async def test_ac20_a_retryable_application_error_is_reported_with_its_type_and_activity(
    reports: list[Reported],
) -> None:
    error = ApplicationError("provider down", type="ConnectionError")
    out = await _run(error, "ledger.pull")
    assert out is error
    [one] = reports
    assert one.exc is error
    assert one.tags == {"error_type": "ConnectionError", "activity": "ledger.pull"}


async def test_ac20_a_non_retryable_application_error_is_not_reported(
    reports: list[Reported],
) -> None:
    error = ApplicationError("decided", type="Forbidden", non_retryable=True)
    out = await _run(error)
    assert out is error
    assert reports == []


@pytest.mark.parametrize("error", [ValueError("x"), RuntimeError("y"), KeyError("z")])
async def test_ac20_any_other_exception_is_reported_and_re_raised_unchanged(
    reports: list[Reported], error: Exception
) -> None:
    out = await _run(error, "evidence.store")
    assert out is error
    [one] = reports
    assert one.exc is error
    assert one.tags == {"error_type": type(error).__name__, "activity": "evidence.store"}


async def test_ac20_an_activity_that_succeeds_is_not_reported(reports: list[Reported]) -> None:
    class Inner(ActivityInboundInterceptor):
        async def execute_activity(self, input: ExecuteActivityInput) -> object:
            return "fine"

    async def activity_fn() -> None:
        return None

    outer = ReportingInterceptor().intercept_activity(
        Inner(cast(ActivityInboundInterceptor, None))
    )
    given = ExecuteActivityInput(fn=activity_fn, args=[], executor=None, headers={})
    assert await ActivityEnvironment().run(outer.execute_activity, given) == "fine"
    assert reports == []
