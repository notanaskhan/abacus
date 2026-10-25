"""Slow-statement warnings for the integration suites (Q-03-T028; Q-03 §3.5 E3; chapter 10
§10.11.1): a statement the app's engines run for longer than 100 ms in a test warns in the PR.

`tests/integration/conftest.py` installs `Recorder` on SQLAlchemy's `Engine` cursor events (the
async engines run their statements through their sync engine, so every engine is covered), names
the running test, and prints what it recorded at the end of the session: in the terminal summary,
and on GitHub Actions as `::warning` annotations, which the PR's checks show. It never fails a
run. Only the statement's text is kept, never its parameters, so no test data reaches the log.

The threshold is `ABACUS_SLOW_STATEMENT_MS` (default 100). Under pytest-xdist each worker hands its
records to the controller through `workeroutput`.
"""

from __future__ import annotations

import os
import re
import time
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from typing import Final

DEFAULT_MS: Final = 100.0
ANNOTATIONS: Final = 10  # GitHub shows ten warning annotations per step
_SPACE = re.compile(r"\s+")


def threshold_ms() -> float:
    raw = os.environ.get("ABACUS_SLOW_STATEMENT_MS", "")
    try:
        return float(raw) if raw else DEFAULT_MS
    except ValueError:
        return DEFAULT_MS


def shorten(statement: str, limit: int = 200) -> str:
    """One line, at most `limit` characters; parameters are placeholders already."""
    flat = _SPACE.sub(" ", statement).strip()
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


@dataclass(frozen=True)
class Slow:
    test: str
    ms: float
    statement: str


class Recorder:
    """Times each statement between SQLAlchemy's before and after cursor events."""

    def __init__(self, limit_ms: float | None = None) -> None:
        self.limit_ms = threshold_ms() if limit_ms is None else limit_ms
        self.test = "(outside a test)"
        self.found: list[Slow] = []
        self._started: dict[int, float] = {}
        self.paused = False

    @contextmanager
    def pause(self) -> Generator[None]:
        """Statements inside are not timed: building the test database is not a test."""
        previous, self.paused = self.paused, True
        try:
            yield
        finally:
            self.paused = previous

    def before(self, cursor: object) -> None:
        if not self.paused:
            self._started[id(cursor)] = time.perf_counter()

    def after(self, cursor: object, statement: str) -> None:
        started = self._started.pop(id(cursor), None)
        if started is None:
            return
        ms = (time.perf_counter() - started) * 1000
        if ms > self.limit_ms:
            self.found.append(Slow(self.test, round(ms, 1), shorten(statement)))

    def dump(self) -> list[dict[str, object]]:
        return [asdict(s) for s in self.found]


def load(rows: list[dict[str, object]]) -> list[Slow]:
    return [Slow(str(r["test"]), float(str(r["ms"])), str(r["statement"])) for r in rows]


def report(found: list[Slow], limit_ms: float, *, github: bool) -> list[str]:
    """Lines for the terminal summary, slowest first; on GitHub, the slowest as annotations."""
    if not found:
        return []
    ordered = sorted(found, key=lambda s: -s.ms)
    lines = [
        f"{len(found)} statement(s) over {limit_ms:g} ms (Q-03-T028; a warning, never a failure):"
    ]
    lines += [f"  {s.ms:8.1f} ms  {s.test}  {s.statement}" for s in ordered]
    if github:
        lines += [
            f"::warning title=Slow statement ({s.ms:g} ms)::"
            f"{_escape(s.test)}: {_escape(s.statement)}"
            for s in ordered[:ANNOTATIONS]
        ]
    return lines


def _escape(text: str) -> str:
    """GitHub's workflow-command escaping for a message."""
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
