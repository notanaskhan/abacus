"""Structured logging that refuses Restricted data (ADR-022, ADR-031). TASK-005 design §7.

    log = get_logger(__name__)
    log.info("ledger.pull.completed", entity_id=entity.id, rows=n)

Each event is one JSON object with `event`, `level`, `timestamp` and the fields. Field values
must be plain scalars, UUIDs, dates, sequences of those, or classified Pydantic models without
Restricted fields; anything else raises, so client data can never reach a log by accident (no
`repr` of arbitrary objects, no Decimal amounts — client financial figures are Restricted).
"""

from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any, cast
from uuid import UUID

import structlog
from pydantic import BaseModel

from abacus.kernel.classification import restricted_fields, unclassified_fields

_SCALARS = (str, int, float, bool, UUID, date)
_configured = False


def _restricted_paths(value: object, path: str = "") -> list[str]:
    """Dotted paths of Restricted or unclassified fields anywhere in `value`, nested included."""
    found: list[str] = []
    if isinstance(value, BaseModel):
        restricted = set(restricted_fields(type(value)))
        unclassified = set(unclassified_fields(type(value)))
        for field in type(value).model_fields:
            here = f"{path}.{field}" if path else field
            if field in restricted:
                found.append(here)
            elif (
                field in unclassified
            ):  # untagged means unknown, which must be treated as Restricted
                found.append(f"{here} (unclassified)")
            else:
                found += _restricted_paths(getattr(value, field), here)
    elif isinstance(value, Mapping):
        for key, item in cast(Mapping[object, object], value).items():
            found += _restricted_paths(item, f"{path}[{key!r}]")
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes):
        for index, item in enumerate(cast(Sequence[object], value)):
            found += _restricted_paths(item, f"{path}[{index}]")
    return found


def _clean(name: str, value: object) -> object:
    if value is None or isinstance(value, _SCALARS):
        return str(value) if isinstance(value, UUID | date) else value
    if isinstance(value, BaseModel):
        restricted = _restricted_paths(value)
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


def _configure() -> None:
    global _configured
    if _configured:
        return
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(sort_keys=True),
        ],
        # A fresh stdout reference per logger, so redirected stdout (tests, workers) is honoured.
        logger_factory=lambda *_: structlog.PrintLogger(sys.stdout),
        cache_logger_on_first_use=False,
    )
    _configured = True


class Logger:
    """The only logger product code uses; validates every field before it reaches structlog."""

    def __init__(self, name: str) -> None:
        _configure()
        self._log: Any = structlog.get_logger(name)  # Any: structlog's BoundLogger is untyped

    def _emit(self, level: str, event: str, fields: Mapping[str, object]) -> None:
        cleaned = {key: _clean(key, value) for key, value in fields.items()}
        getattr(self._log, level)(event, **cleaned)

    def debug(self, event: str, **fields: object) -> None:
        self._emit("debug", event, fields)

    def info(self, event: str, **fields: object) -> None:
        self._emit("info", event, fields)

    def warning(self, event: str, **fields: object) -> None:
        self._emit("warning", event, fields)

    def error(self, event: str, **fields: object) -> None:
        self._emit("error", event, fields)


def get_logger(name: str) -> Logger:
    return Logger(name)
