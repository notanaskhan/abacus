"""Q-03-T028 (Q-03 §3.5 E3): an integration statement over 100 ms warns in the PR, never fails the
run, and never prints its parameters."""

from __future__ import annotations

import pytest

from abacus_tools.quality import slow_statements
from abacus_tools.quality.slow_statements import Recorder, Slow, report


def test_t028_the_threshold_is_100_ms_unless_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ABACUS_SLOW_STATEMENT_MS", raising=False)
    assert slow_statements.threshold_ms() == 100.0
    monkeypatch.setenv("ABACUS_SLOW_STATEMENT_MS", "250")
    assert slow_statements.threshold_ms() == 250.0
    monkeypatch.setenv("ABACUS_SLOW_STATEMENT_MS", "soon")
    assert slow_statements.threshold_ms() == 100.0


def test_t028_only_statements_over_the_threshold_are_kept(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = iter([0.0, 0.050, 1.0, 1.150])
    monkeypatch.setattr(slow_statements.time, "perf_counter", lambda: next(clock))
    recorder = Recorder(limit_ms=100)
    recorder.test = "tests/integration/test_x.py::test_y"
    fast, slow = object(), object()
    recorder.before(fast)
    recorder.after(fast, "SELECT 1")
    recorder.before(slow)
    recorder.after(slow, "SELECT *\n  FROM clients\n WHERE tenant_id = $1")
    assert recorder.found == [
        Slow(
            "tests/integration/test_x.py::test_y",
            150.0,
            "SELECT * FROM clients WHERE tenant_id = $1",
        )
    ]
    assert slow_statements.load(recorder.dump()) == recorder.found


def test_t028_a_paused_recorder_times_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = iter([0.0, 5.0])
    monkeypatch.setattr(slow_statements.time, "perf_counter", lambda: next(clock))
    recorder = Recorder(limit_ms=100)
    cursor = object()
    with recorder.pause():
        recorder.before(cursor)
    recorder.after(cursor, "CREATE TABLE x ()")
    assert recorder.found == []


def test_t028_long_statements_are_shortened_to_one_line() -> None:
    text = slow_statements.shorten("SELECT " + "a, " * 200 + "\n FROM t", limit=40)
    assert len(text) == 40 and "\n" not in text and text.endswith("…")


def test_t028_the_report_lists_slowest_first_and_annotates_on_github() -> None:
    found = [
        Slow("t::a", 120.0, "SELECT 1"),
        Slow("t::b", 900.5, "SELECT 100%\nFROM x"),
    ]
    lines = report(found, 100, github=True)
    assert lines[0].startswith("2 statement(s) over 100 ms")
    assert "900.5 ms" in lines[1] and "120.0 ms" in lines[2]
    assert lines[3] == "::warning title=Slow statement (900.5 ms)::t::b: SELECT 100%25%0AFROM x"
    assert not any(line.startswith("::") for line in report(found, 100, github=False))
    assert report([], 100, github=True) == []


def test_t028_at_most_ten_annotations() -> None:
    found = [Slow(f"t::{i}", 200.0 + i, "SELECT 1") for i in range(15)]
    annotations = [line for line in report(found, 100, github=True) if line.startswith("::")]
    assert len(annotations) == slow_statements.ANNOTATIONS
