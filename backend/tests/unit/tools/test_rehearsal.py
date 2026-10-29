"""Q-02-T48 (DEC-958): the rehearsal command refuses outside staging and without a database, and
the walk's report counts failures by step."""

from __future__ import annotations

import uuid

import pytest

from abacus.kernel.config import settings
from abacus_tools import rehearsal


def _argv() -> list[str]:
    ids = [str(uuid.uuid4()) for _ in range(5)]
    names = ("--tenant", "--admin", "--partner", "--engagement", "--tax-engagement")
    return ["run", *(part for pair in zip(names, ids, strict=True) for part in pair)]


def test_the_rehearsal_refuses_outside_staging(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ABACUS_ENVIRONMENT", "test")
    monkeypatch.setenv("ABACUS_DATABASE_URL", "postgresql+asyncpg://app@localhost/app")
    settings.cache_clear()
    try:
        assert rehearsal.main(_argv()) == 2
    finally:
        settings.cache_clear()


def test_the_report_counts_each_failed_step() -> None:
    report = rehearsal.Report()
    report.ok("tenant is a real firm")
    report.fail("refused: firm", "not refused, expected firm")
    assert report.failed == 1
    assert report.lines == [
        "ok    tenant is a real firm",
        "FAIL  refused: firm: not refused, expected firm",
    ]


def test_the_rehearsal_is_an_allowlisted_operator_command() -> None:
    from abacus_tools.release import OPS_COMMANDS

    assert "abacus_tools.rehearsal run" in OPS_COMMANDS
