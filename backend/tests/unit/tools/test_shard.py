"""The CI shard split runs every test file exactly once, balanced (TASK-017)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from abacus_tools.ci import shard

FILES = [f"tests/x/test_{i}.py" for i in range(10)]


@pytest.mark.parametrize("shards", [1, 2, 3, 4, 10])
def test_every_file_runs_in_exactly_one_shard(shards: int) -> None:
    split = shard.split(FILES, {}, shards)
    flat = [f for s in split for f in s]
    assert sorted(flat) == sorted(FILES)
    assert len(flat) == len(set(flat))
    assert all(split)


def test_the_split_balances_recorded_time() -> None:
    durations = {"a": 10.0, "b": 6.0, "c": 4.0, "d": 3.0, "e": 3.0}
    split = shard.split(list(durations), durations, 2)
    assert sorted(sum(durations[f] for f in s) for s in split) == [13.0, 13.0]


def test_a_new_file_is_weighted_as_the_median_and_still_runs() -> None:
    durations = {"a": 1.0, "b": 5.0, "c": 9.0}
    split = shard.split(["a", "b", "c", "new"], durations, 2)
    assert sorted(f for s in split for f in s) == ["a", "b", "c", "new"]
    assert split == [["a", "c"], ["b", "new"]]  # "new" weighs 5, the median: 10 and 10


def test_the_split_is_deterministic() -> None:
    assert shard.split(FILES, {}, 3) == shard.split(list(reversed(FILES)), {}, 3)


@pytest.mark.parametrize("shards", [0, 11])
def test_impossible_splits_are_refused(shards: int) -> None:
    with pytest.raises(ValueError):
        shard.split(FILES, {}, shards)


def test_test_files_finds_only_test_modules(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    for name in ("test_a.py", "sub/test_b.py", "support.py", "conftest.py"):
        (tmp_path / name).write_text("", encoding="utf-8")
    found = shard.test_files([tmp_path])
    assert sorted(Path(f).name for f in found) == ["test_a.py", "test_b.py"]


def test_durations_are_summed_per_file_from_junit() -> None:
    junit = """<testsuites><testsuite>
      <testcase classname="tests.unit.kernel.test_x" name="a" time="1.5"/>
      <testcase classname="tests.unit.kernel.test_x.TestThing" name="b" time="0.5"/>
      <testcase classname="tests.integration.test_y" name="c" time="3"/>
      <testcase classname="" name="d" time="9"/>
    </testsuite></testsuites>"""
    assert shard.file_durations(junit) == {
        "tests/integration/test_y.py": 3.0,
        "tests/unit/kernel/test_x.py": 2.0,
    }


def test_main_prints_one_shard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    for i in range(4):
        (tmp_path / f"test_{i}.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(shard, "DURATIONS", tmp_path / "missing.json")
    printed: list[str] = []
    for i in (1, 2):
        assert shard.main([str(i), "2", str(tmp_path)]) == 0
        printed += capsys.readouterr().out.split()
    assert sorted(printed) == sorted(shard.test_files([tmp_path]))


def test_main_refuses_bad_arguments(capsys: pytest.CaptureFixture[str]) -> None:
    assert shard.main(["3", "2", "tests"]) == 2
    assert shard.main(["1"]) == 2
    capsys.readouterr()


def test_main_records_durations(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    report = tmp_path / "junit.xml"
    report.write_text(
        '<testsuite><testcase classname="tests.a.test_z" name="t" time="2"/></testsuite>',
        encoding="utf-8",
    )
    out = tmp_path / "durations.json"
    monkeypatch.setattr(shard, "DURATIONS", out)
    assert shard.main(["--record", str(report)]) == 0
    assert json.loads(out.read_text(encoding="utf-8")) == {"tests/a/test_z.py": 2.0}
