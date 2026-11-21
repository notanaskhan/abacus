"""pytest plugin: record which test files a CI shard ran and how long each took (TASK-017).

Loaded by `make ci-unit` and `make ci-integration` (`-p abacus_tools.ci.record`); inert unless
ABACUS_SHARD_RECORD names the output file. On the pytest-xdist controller (or in a single process)
it adds up each test's setup, call and teardown time per file from the reports. The file is merged,
not overwritten, so the workers' pass and the serial pass of one shard land in one record:

    {"files": {"tests/unit/test_x.py": 1.23, ...}}

Every main run's records become the next runs' shard timings, and the coverage job checks the
records of all shards together ran every test file exactly once (`python -m abacus_tools.ci.shard
--verify`). Times under workers include contention and charge a worker's session fixtures to
the first file it runs; that is the same for every shard, so the balance holds.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path

import pytest

_TOTALS: defaultdict[str, float] = defaultdict(float)


def _output() -> Path | None:
    value = os.environ.get("ABACUS_SHARD_RECORD")
    return Path(value) if value else None


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if _output() is None:
        return
    path = report.nodeid.split("::", 1)[0]
    _TOTALS[path] += report.duration


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    output = _output()
    # A pytest-xdist worker's reports reach the controller, which writes the record.
    if output is None or hasattr(session.config, "workerinput"):
        return
    record: dict[str, dict[str, float]] = (
        json.loads(output.read_text(encoding="utf-8")) if output.exists() else {"files": {}}
    )
    files = record["files"]
    for path, seconds in _TOTALS.items():
        files[path] = round(files.get(path, 0.0) + seconds, 2)
    output.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")
