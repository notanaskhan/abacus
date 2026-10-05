"""Shared pytest configuration."""

from __future__ import annotations

from pathlib import Path

import pytest

NO_TESTS_COLLECTED = 5


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Treat "no tests collected" as success only when the selected suites are genuinely empty.

    Some suites (integration, security, workflows) have no tests until SPEC-000. A run over them
    passes; a run that selected test files but collected none (a bad -k, a broken import mode)
    still fails. Remove once every suite has tests.
    """
    if exitstatus != NO_TESTS_COLLECTED:
        return
    selected = [Path(str(arg).split("::", 1)[0]).resolve() for arg in session.config.args]
    if not any(any(p.rglob("test_*.py")) if p.is_dir() else p.exists() for p in selected):
        session.exitstatus = pytest.ExitCode.OK
