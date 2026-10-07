"""Structured logging that refuses Restricted data (ADR-022, ADR-031). TASK-005 design §7.

    log = get_logger(__name__)
    log.info("ledger.pull.completed", entity_id=entity.id, rows=n)

Each event is one JSON object with `event`, `level`, `timestamp`, the current `trace_id` and
`span_id` (when inside a span; TASK-013) and the fields. Field values must be plain scalars,
UUIDs, dates, sequences of those, or classified Pydantic models without Restricted fields;
anything else raises, so client data can never reach a log by accident (no `repr` of arbitrary
objects, no Decimal amounts — client financial figures are Restricted). An exception may be
passed as a field (`error=exc`): only its class name is logged, never its message, which can
carry data. `log_level` filters; third-party libraries' own logs (warnings and up) are rendered
as the same JSON lines, as `event="library.log"` with the logger name and level only.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any, cast
from uuid import UUID

import structlog
from pydantic import BaseModel
from structlog.types import EventDict

from abacus.kernel.classification import sensitive_paths
from abacus.kernel.config import settings
from abacus.kernel.telemetry import current_span_id, current_trace_id

_SCALARS = (str, int, float, bool, UUID, date)
_configured = False


def _clean(name: str, value: object) -> object:
    if isinstance(value, BaseException):
        return type(value).__name__  # never the message: it can carry client data
    if value is None or isinstance(value, _SCALARS):
        return str(value) if isinstance(value, UUID | date) else value
    if isinstance(value, BaseModel):
        restricted = sensitive_paths(value)
        if restricted:
            raise ValueError(
                f"log field {name!r}: {type(value).__name__} carries Restricted data "
                f"({', '.join(restricted)}); log identifiers instead"
            )
        return value.model_dump(mode="json")
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return [_clean(name, item) for item in cast(Sequence[object], value)]
    raise ValueError(
        f"log field {name!r}: {type(value).__name__} is not loggable; "
        "pass scalars, UUIDs, dates or classified models"
    )


def _add_trace(_logger: object, _method: str, event: EventDict) -> EventDict:
    trace_id = current_trace_id()
    if trace_id is not None:
        event["trace_id"] = trace_id
        event["span_id"] = current_span_id()
    return event


_LEVELS = {"debug": logging.DEBUG, "info": logging.INFO, "warning": logging.WARNING}


class _LibraryHandler(logging.Handler):
    """Third-party logs as our JSON lines: logger name and level only. Library messages and
    exception text can quote data (SQL parameters, URLs, payloads), so they are never kept."""

    def emit(self, record: logging.LogRecord) -> None:
        get_logger(record.name).library(record.levelname.lower(), record.name)


def configure_logging(level: str | None = None, *, force: bool = False) -> None:
    """Set up logging (done lazily on the first log line; call it to choose a level, or with
    `force` to reconfigure, e.g. in tests)."""
    global _configured
    if _configured and not force:
        return
    s = settings()
    # Default: everything locally and in tests, info and up elsewhere.
    chosen = level or s.log_level or ("debug" if s.environment in ("local", "test") else "info")
    threshold = _LEVELS.get(chosen, logging.ERROR)
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _add_trace,
            structlog.processors.JSONRenderer(sort_keys=True),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(threshold),
        # A fresh stdout reference per logger, so redirected stdout (tests, workers) is honoured.
        logger_factory=lambda *_: structlog.PrintLogger(sys.stdout),
        cache_logger_on_first_use=False,
    )
    _configured = True
    root = logging.getLogger()
    if not any(isinstance(h, _LibraryHandler) for h in root.handlers):
        # Added, not replacing: a test runner's capture handlers stay in place.
        root.addHandler(_LibraryHandler())
    if root.level == logging.NOTSET or root.level < logging.WARNING:
        root.setLevel(logging.WARNING)
    # uvicorn configures its own plain-text handlers: its access log carries paths and query
    # strings, so it is off (requests are traced instead); its other logs go through ours.
    logging.getLogger("uvicorn.access").disabled = True
    for name in ("uvicorn", "uvicorn.error"):
        server = logging.getLogger(name)
        server.handlers = []
        server.propagate = True


class Logger:
    """The only logger product code uses; validates every field before it reaches structlog."""

    def __init__(self, name: str) -> None:
        self._name = name

    def _emit(self, level: str, event: str, fields: Mapping[str, object]) -> None:
        configure_logging()  # lazily: importing a module that logs never reads settings
        cleaned = {key: _clean(key, value) for key, value in fields.items()}
        log: Any = structlog.get_logger(self._name)  # Any: structlog's BoundLogger is untyped
        getattr(log, level)(event, **cleaned)

    def debug(self, event: str, **fields: object) -> None:
        self._emit("debug", event, fields)

    def info(self, event: str, **fields: object) -> None:
        self._emit("info", event, fields)

    def warning(self, event: str, **fields: object) -> None:
        self._emit("warning", event, fields)

    def error(self, event: str, **fields: object) -> None:
        self._emit("error", event, fields)

    def library(self, level: str, logger: str) -> None:
        """A third-party log record, reduced to where it came from (see the module docstring)."""
        method = level if level in ("debug", "info", "warning", "error") else "error"
        log: Any = structlog.get_logger(self._name)  # Any: structlog's BoundLogger is untyped
        getattr(log, method)("library.log", logger=logger)


def get_logger(name: str) -> Logger:
    return Logger(name)
