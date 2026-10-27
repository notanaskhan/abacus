"""Shared pytest configuration."""

from __future__ import annotations

import os
from pathlib import Path
from typing import cast

import pytest

from abacus.kernel import controls
from abacus.kernel.controls import Active

NO_TESTS_COLLECTED = 5


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Under mutmut (it sets `MUTANT_UNDER_TEST` for every run it makes) the tests marked
    `source_scan` are left out (Q-03-T051, DEC-599): they read source or repository files, not
    behaviour, so mutmut's rewritten copies fail them before any mutant is scored, and on a mutant
    they would only report a textual difference. Every other run keeps them."""
    if "MUTANT_UNDER_TEST" not in os.environ:
        return
    kept = [item for item in items if item.get_closest_marker("source_scan") is None]
    left = [item for item in items if item.get_closest_marker("source_scan") is not None]
    if left:
        config.hook.pytest_deselected(items=left)
        items[:] = kept


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


async def _no_switches() -> Active:
    return frozenset()


@pytest.fixture(autouse=True)
def _no_kill_switches(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Q-01-T36, T37: every suite but integration runs without a database (unit, contracts,
    security, property, acceptance, workflows), where an unreadable switch state fails closed and
    every write would answer `read_only`. They read "no switch on" instead; integration tests read
    the real `platform_controls`, and switch tests replace `_read` with their own."""
    node = cast(pytest.Item, request.node)  # pyright: ignore[reportUnknownMemberType] -- pytest's request.node is untyped
    if "integration" in node.path.parts:
        return
    controls.forget_controls()
    monkeypatch.setattr(controls, "_read", _no_switches)
