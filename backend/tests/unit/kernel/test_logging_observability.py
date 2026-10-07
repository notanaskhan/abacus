"""AC-20: structured logs with trace IDs, class-name-only errors, levels and library logs
(TASK-013 interface contract, "Logging"; ADR-022, ADR-031).

Logging configures itself once per process, so tests that need a particular level or the stdlib
bridge reset that state around themselves.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Callable, Iterator
from decimal import Decimal
from types import SimpleNamespace
from typing import Annotated

import pytest
from pydantic import BaseModel

from abacus.kernel.classification import classified
from abacus.kernel.config import settings
from abacus.kernel.logging import configure_logging, get_logger
from abacus.kernel.telemetry import current_span_id, current_trace_id, tracer
from abacus.kernel.telemetry import test_exporter as shared_exporter

LEAKED = "CLIENT-CELL-VALUE-4417-MARKER"


class Balance(BaseModel):
    id: Annotated[uuid.UUID, classified("confidential")]
    amount: Annotated[str, classified("restricted")]


class Untagged(BaseModel):
    name: str


class CustomFailure(Exception):
    pass


@pytest.fixture(scope="module", autouse=True)
def tracing() -> None:
    shared_exporter()


def _lines(capsys: pytest.CaptureFixture[str]) -> list[dict[str, object]]:
    captured = capsys.readouterr()
    text = captured.out + captured.err
    return [json.loads(line) for line in text.splitlines() if line.strip().startswith("{")]


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[[str | None, str], None]]:
    """Configure logging afresh with the given `log_level` and `environment`; put the process's
    own configuration back afterwards (it is re-read on the next `get_logger`)."""

    def configure(level: str | None, environment: str) -> None:
        monkeypatch.setattr(
            "abacus.kernel.logging.settings",
            lambda: SimpleNamespace(log_level=level, environment=environment),
        )
        configure_logging(force=True)

    yield configure
    monkeypatch.undo()
    configure_logging(force=True)


# --- trace ids -----------------------------------------------------------------------------------


def test_ac20_lines_inside_a_span_carry_its_trace_and_span_ids(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with tracer("t").start_as_current_span("work"):
        get_logger("test").info("inside", rows=3)
        expected = (current_trace_id(), current_span_id())
    [line] = _lines(capsys)
    assert (line["trace_id"], line["span_id"]) == expected
    assert line["event"] == "inside"
    assert line["rows"] == 3


def test_ac20_lines_outside_a_span_omit_trace_and_span_ids(
    capsys: pytest.CaptureFixture[str],
) -> None:
    get_logger("test").info("outside")
    [line] = _lines(capsys)
    assert "trace_id" not in line
    assert "span_id" not in line


def test_ac20_each_line_gets_the_span_it_is_logged_in(capsys: pytest.CaptureFixture[str]) -> None:
    log = get_logger("test")
    with tracer("t").start_as_current_span("outer"):
        log.info("a")
        outer_span = current_span_id()
        with tracer("t").start_as_current_span("inner"):
            log.info("b")
            inner_span = current_span_id()
        log.info("c")
    log.info("d")
    a, b, c, d = _lines(capsys)
    assert (a["span_id"], b["span_id"], c["span_id"]) == (outer_span, inner_span, outer_span)
    assert a["trace_id"] == b["trace_id"] == c["trace_id"]
    assert "trace_id" not in d


@pytest.mark.parametrize("level", ["debug", "info", "warning", "error"])
def test_ac20_every_level_carries_the_trace_ids(
    capsys: pytest.CaptureFixture[str], level: str
) -> None:
    with tracer("t").start_as_current_span("work"):
        getattr(get_logger("test"), level)("evt")
        trace_id = current_trace_id()
    [line] = _lines(capsys)
    assert line["trace_id"] == trace_id
    assert re_hex(str(line["trace_id"]), 32)
    assert re_hex(str(line["span_id"]), 16)


def re_hex(value: str, length: int) -> bool:
    return len(value) == length and all(c in "0123456789abcdef" for c in value)


# --- exceptions as fields ------------------------------------------------------------------------


@pytest.mark.parametrize("exc", [ValueError(LEAKED), CustomFailure(LEAKED), KeyError(LEAKED)])
def test_ac20_an_exception_field_is_logged_as_its_class_name_only(
    capsys: pytest.CaptureFixture[str], exc: Exception
) -> None:
    get_logger("test").error("thing.failed", error=exc)
    output = capsys.readouterr()
    assert LEAKED not in output.out + output.err
    [line] = [json.loads(x) for x in output.out.splitlines() if x.startswith("{")]
    assert line["error"] == type(exc).__name__
    assert line["level"] == "error"


def test_ac20_an_exception_with_a_chained_cause_still_logs_only_its_class(
    capsys: pytest.CaptureFixture[str],
) -> None:
    try:
        try:
            raise OSError(LEAKED)
        except OSError as cause:
            raise CustomFailure("wrapped " + LEAKED) from cause
    except CustomFailure as caught:
        get_logger("test").warning("chained", error=caught)
    output = capsys.readouterr()
    assert LEAKED not in output.out + output.err
    [line] = [json.loads(x) for x in output.out.splitlines() if x.startswith("{")]
    assert line["error"] == "CustomFailure"


def test_ac20_an_exception_inside_a_sequence_is_reduced_to_its_class(
    capsys: pytest.CaptureFixture[str],
) -> None:
    get_logger("test").error("many", errors=[ValueError(LEAKED), KeyError(LEAKED)])
    output = capsys.readouterr()
    assert LEAKED not in output.out + output.err
    [line] = [json.loads(x) for x in output.out.splitlines() if x.startswith("{")]
    assert line["errors"] == ["ValueError", "KeyError"]


# --- existing refusals ---------------------------------------------------------------------------


def test_ac20_restricted_models_are_still_refused_and_nothing_is_written(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(ValueError, match="Restricted"):
        get_logger("test").info("evt", balance=Balance(id=uuid.uuid4(), amount=LEAKED))
    output = capsys.readouterr()
    assert LEAKED not in output.out + output.err
    assert _lines_from(output.out) == []


def test_ac20_unclassified_models_are_still_refused() -> None:
    with pytest.raises(ValueError):
        get_logger("test").info("evt", thing=Untagged(name="x"))


@pytest.mark.parametrize("value", [object(), {"a": 1}, Decimal("12.50"), 1 + 2j])
def test_ac20_arbitrary_objects_decimals_and_mappings_are_still_refused(value: object) -> None:
    with pytest.raises(ValueError):
        get_logger("test").info("evt", value=value)


def _lines_from(text: str) -> list[dict[str, object]]:
    return [json.loads(x) for x in text.splitlines() if x.startswith("{")]


# --- level ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("environment", ["local", "test"])
def test_ac20_no_log_level_means_debug_locally_and_in_tests(
    capsys: pytest.CaptureFixture[str],
    configured: Callable[[str | None, str], None],
    environment: str,
) -> None:
    configured(None, environment)
    capsys.readouterr()
    log = get_logger("test")
    log.debug("d")
    log.info("i")
    assert [x["event"] for x in _lines(capsys)] == ["d", "i"]


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_ac20_no_log_level_means_info_elsewhere(
    capsys: pytest.CaptureFixture[str],
    configured: Callable[[str | None, str], None],
    environment: str,
) -> None:
    configured(None, environment)
    capsys.readouterr()
    log = get_logger("test")
    log.debug("d")
    log.info("i")
    log.warning("w")
    log.error("e")
    assert [x["event"] for x in _lines(capsys)] == ["i", "w", "e"]


@pytest.mark.parametrize(
    ("level", "kept"),
    [
        ("debug", ["d", "i", "w", "e"]),
        ("info", ["i", "w", "e"]),
        ("warning", ["w", "e"]),
        ("error", ["e"]),
    ],
)
@pytest.mark.parametrize("environment", ["local", "production"])
def test_ac20_a_set_log_level_drops_lower_levels(
    capsys: pytest.CaptureFixture[str],
    configured: Callable[[str | None, str], None],
    level: str,
    kept: list[str],
    environment: str,
) -> None:
    configured(level, environment)
    capsys.readouterr()
    log = get_logger("test")
    log.debug("d")
    log.info("i")
    log.warning("w")
    log.error("e")
    assert [x["event"] for x in _lines(capsys)] == kept


def test_ac20_log_level_comes_from_the_log_level_setting(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ABACUS_LOG_LEVEL", "error")
    settings.cache_clear()
    try:
        assert settings().log_level == "error"
    finally:
        monkeypatch.undo()
        settings.cache_clear()


# --- library logs --------------------------------------------------------------------------------


def test_ac20_library_warnings_are_written_as_json_without_the_message(
    capsys: pytest.CaptureFixture[str], configured: Callable[[str | None, str], None]
) -> None:
    configured(None, "test")
    capsys.readouterr()
    logging.getLogger("uvicorn.error").warning("connection from %s: %s", "10.0.0.5", LEAKED)
    output = capsys.readouterr()
    assert LEAKED not in output.out + output.err
    assert "10.0.0.5" not in output.out + output.err
    [line] = _lines_from(output.out)
    assert line["event"] == "library.log"
    assert line["logger"] == "uvicorn.error"
    assert line["level"] == "warning"
    assert set(line) <= {"event", "logger", "level", "timestamp", "trace_id", "span_id"}


def test_ac20_library_errors_with_exception_text_leak_nothing(
    capsys: pytest.CaptureFixture[str], configured: Callable[[str | None, str], None]
) -> None:
    configured(None, "test")
    capsys.readouterr()
    try:
        raise RuntimeError(LEAKED)
    except RuntimeError:
        logging.getLogger("temporalio.worker").error("activity failed: %s", LEAKED, exc_info=True)
    output = capsys.readouterr()
    assert LEAKED not in output.out + output.err
    [line] = _lines_from(output.out)
    assert (line["event"], line["logger"], line["level"]) == (
        "library.log",
        "temporalio.worker",
        "error",
    )


def test_ac20_library_logs_below_warning_are_dropped(
    capsys: pytest.CaptureFixture[str], configured: Callable[[str | None, str], None]
) -> None:
    configured("debug", "test")
    capsys.readouterr()
    other = logging.getLogger("opentelemetry.sdk")
    other.debug("detail %s", LEAKED)
    other.info("progress %s", LEAKED)
    output = capsys.readouterr()
    assert _lines_from(output.out) == []
    assert LEAKED not in output.out + output.err


def test_ac20_library_log_lines_inside_a_span_carry_the_trace_ids(
    capsys: pytest.CaptureFixture[str], configured: Callable[[str | None, str], None]
) -> None:
    configured(None, "test")
    capsys.readouterr()
    with tracer("t").start_as_current_span("work"):
        logging.getLogger("asyncpg").warning("slow %s", LEAKED)
        trace_id = current_trace_id()
    [line] = _lines_from(capsys.readouterr().out)
    assert line["trace_id"] == trace_id


def _ours() -> list[logging.Handler]:
    return [
        h for h in logging.getLogger().handlers if type(h).__module__ == "abacus.kernel.logging"
    ]


def test_ac20_the_library_handler_is_added_once_however_often_logging_is_configured(
    configured: Callable[[str | None, str], None],
) -> None:
    configured(None, "test")
    configured("info", "test")
    configure_logging(force=True)
    assert len(_ours()) == 1


def test_ac20_configuring_logging_keeps_the_roots_existing_handlers(
    configured: Callable[[str | None, str], None],
) -> None:
    mine = logging.NullHandler()
    logging.getLogger().addHandler(mine)
    try:
        configured(None, "test")
        assert mine in logging.getLogger().handlers
        assert len(_ours()) == 1
    finally:
        logging.getLogger().removeHandler(mine)


@pytest.mark.parametrize("before", [logging.NOTSET, logging.DEBUG, logging.INFO])
def test_ac20_the_root_level_is_raised_to_warning_if_lower(
    configured: Callable[[str | None, str], None], before: int
) -> None:
    root = logging.getLogger()
    original = root.level
    root.setLevel(before)
    try:
        configured(None, "test")
        assert root.level == logging.WARNING
    finally:
        root.setLevel(original)


def test_ac20_a_root_level_above_warning_is_left_alone(
    configured: Callable[[str | None, str], None],
) -> None:
    root = logging.getLogger()
    original = root.level
    root.setLevel(logging.ERROR)
    try:
        configured(None, "test")
        assert root.level == logging.ERROR
    finally:
        root.setLevel(original)


def test_ac20_uvicorn_access_log_is_off_and_its_other_logs_go_through_ours(
    capsys: pytest.CaptureFixture[str], configured: Callable[[str | None, str], None]
) -> None:
    stray = logging.StreamHandler()
    logging.getLogger("uvicorn.error").addHandler(stray)
    access = logging.getLogger("uvicorn.access")
    was_disabled = access.disabled
    try:
        configured(None, "test")
        capsys.readouterr()
        assert access.disabled is True
        for name in ("uvicorn", "uvicorn.error"):
            server = logging.getLogger(name)
            assert server.handlers == []
            assert server.propagate is True
        access.error("GET /v1/clients/%s?q=%s", LEAKED, LEAKED)
        logging.getLogger("uvicorn.error").warning("boom %s", LEAKED)
        output = capsys.readouterr()
        assert LEAKED not in output.out + output.err
        [line] = _lines_from(output.out)
        assert isinstance(line, dict)
        assert (line["event"], line["logger"]) == ("library.log", "uvicorn.error")
    finally:
        logging.getLogger("uvicorn.error").removeHandler(stray)
        access.disabled = was_disabled


def test_ac20_an_explicit_level_overrides_the_setting(
    capsys: pytest.CaptureFixture[str], configured: Callable[[str | None, str], None]
) -> None:
    configured("debug", "local")
    configure_logging("error", force=True)
    capsys.readouterr()
    log = get_logger("test")
    log.warning("w")
    log.error("e")
    assert [x["event"] for x in _lines(capsys)] == ["e"]


def test_ac20_creating_a_logger_does_not_read_settings_or_configure_logging(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse() -> object:
        raise AssertionError("settings read while creating a logger")

    monkeypatch.setattr("abacus.kernel.logging.settings", refuse)
    monkeypatch.setattr("abacus.kernel.logging._configured", False)
    get_logger("quiet")  # no error: nothing is read until the first line is emitted
