"""abacus_tools.ci.record: a shard's per-file run times, merged across its pytest passes."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from abacus_tools.ci import record


def _pass(reports: list[tuple[str, float]], *, worker: bool = False) -> None:
    record._TOTALS.clear()  # pyright: ignore[reportPrivateUsage] -- one pytest session per pass
    for nodeid, seconds in reports:
        record.pytest_runtest_logreport(
            cast(pytest.TestReport, SimpleNamespace(nodeid=nodeid, duration=seconds))
        )
    config: Any = SimpleNamespace(workerinput={}) if worker else SimpleNamespace()
    record.pytest_sessionfinish(cast(pytest.Session, SimpleNamespace(config=config)), 0)


def test_records_each_file_and_merges_a_second_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "shard.json"
    monkeypatch.setenv("ABACUS_SHARD_RECORD", str(out))
    _pass([("tests/a/test_x.py::test_one", 1.0), ("tests/a/test_x.py::test_two", 0.5)])
    _pass([("tests/a/test_x.py::test_serial", 2.0), ("tests/b/test_y.py::test_t", 0.25)])
    assert json.loads(out.read_text(encoding="utf-8")) == {
        "files": {"tests/a/test_x.py": 3.5, "tests/b/test_y.py": 0.25}
    }


def test_a_worker_leaves_the_writing_to_the_controller(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "shard.json"
    monkeypatch.setenv("ABACUS_SHARD_RECORD", str(out))
    _pass([("tests/a/test_x.py::test_one", 1.0)], worker=True)
    assert not out.exists()


def test_inert_without_the_variable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ABACUS_SHARD_RECORD", raising=False)
    monkeypatch.chdir(tmp_path)
    _pass([("tests/a/test_x.py::test_one", 1.0)])
    assert list(tmp_path.iterdir()) == []
