"""Split test files across CI jobs, balanced by recorded run time (TASK-017).

Run: python -m abacus_tools.ci.shard [--by-count] <shard> <shards> <root>...

Prints the test files of shard `<shard>` (1-based) of `<shards>`, one per line. Every
`test_*.py` under the roots goes to exactly one shard, so the shards together run the whole suite:
a file missing from the timings (a new file) still runs, weighted as the median file. Greedy
longest-first, deterministic: the same files and timings always give the same split.

Timings: `tests/durations.json`, seconds per file, from the durations report of a full run in
one process (`-n 0`: under pytest-xdist workers contend for the cores and each worker's session
fixtures, its containers among them, are charged to the first file it runs; DEC-335):
pytest -n 0 --durations=0 --durations-min=0 > report.txt, then
python -m abacus_tools.ci.shard --record report.txt

Or from the runs themselves (TASK-8868): with `ABACUS_DURATIONS_OUT=<path>` set, the suites append
one JSON line per test phase to `<path>.jsonl` as they go (tests/conftest.py), so a shard cancelled
at its timeout still leaves what it ran. CI uploads them; merge a run's files with
python -m abacus_tools.ci.shard --record-runs [--partial] <file.jsonl>...
A complete run replaces each recorded file's time; `--partial` (a run with cancelled shards) only
raises a time, since a file cut short reads low. Files no longer on disk are dropped.
"""

from __future__ import annotations

import contextlib
import io
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import pytest

DURATIONS = Path(__file__).resolve().parents[3] / "tests" / "durations.json"


def test_files(roots: list[Path]) -> list[str]:
    files = {path.as_posix() for root in roots for path in root.rglob("test_*.py")}
    return sorted(files)


def split(
    files: list[str],
    durations: dict[str, float],
    shards: int,
    counts: dict[str, int] | None = None,
) -> list[list[str]]:
    """Greedy longest-first over each file's weight: its recorded seconds, else (with `counts`,
    TASK-8868) its collected test count times the recorded seconds per test, else the median."""
    if shards < 1:
        raise ValueError("at least one shard")
    if len(files) < shards:
        raise ValueError(f"{len(files)} test files can't fill {shards} shards")
    known = [durations[f] for f in files if f in durations]
    default = statistics.median(known) if known else 1.0
    if counts is None:
        weight = {f: durations.get(f, default) for f in files}
    else:
        rates = [durations[f] / counts[f] for f in files if f in durations and counts.get(f, 0)]
        rate = statistics.median(rates) if rates else 1.0
        weight = {f: durations.get(f, max(counts.get(f, 1), 1) * rate) for f in files}
    loads = [0.0] * shards
    out: list[list[str]] = [[] for _ in range(shards)]
    for f in sorted(files, key=lambda f: (-weight[f], f)):
        lightest = min(range(shards), key=lambda i: (loads[i], i))
        out[lightest].append(f)
        loads[lightest] += weight[f]
    return [sorted(shard) for shard in out]


class _Counter:
    """A pytest plugin that keeps the collected test count per file."""

    def __init__(self) -> None:
        self.counts: dict[str, int] = defaultdict(int)

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        for item in session.items:
            self.counts[item.nodeid.split("::", 1)[0]] += 1


def collected_counts(roots: list[str]) -> dict[str, int]:
    """Tests per file, from a collect-only pytest session over the roots (TASK-8868). A file that
    fails to collect is absent here and weighs as one test; its own run reports the error."""
    counter = _Counter()
    with contextlib.redirect_stdout(io.StringIO()):  # stdout carries the shard's file list
        pytest.main(["--collect-only", "-q", "-p", "no:cacheprovider", *roots], plugins=[counter])
    return dict(counter.counts)


# A line of pytest's durations report: `1.23s call     tests/unit/kernel/test_x.py::test_y`.
_DURATION = re.compile(r"^\s*(\d+(?:\.\d+)?)s\s+(?:setup|call|teardown)\s+(\S+?\.py)::")


def file_durations(report: str) -> dict[str, float]:
    """Seconds per test file (setup, call and teardown), from `pytest --durations=0` output."""
    totals: dict[str, float] = defaultdict(float)
    for line in report.splitlines():
        match = _DURATION.match(line)
        if match:
            totals[match.group(2)] += float(match.group(1))
    return {f: round(t, 2) for f, t in sorted(totals.items())}


def run_durations(lines: str) -> dict[str, float]:
    """Seconds per test file from the recorder's JSON lines (`{"file", "when", "seconds"}`)."""
    totals: dict[str, float] = defaultdict(float)
    for line in lines.splitlines():
        if line.strip():
            row = json.loads(line)
            totals[str(row["file"])] += float(row["seconds"])
    return {f: round(t, 2) for f, t in sorted(totals.items())}


def merge(
    recorded: dict[str, float], ran: dict[str, float], present: set[str], *, partial: bool
) -> dict[str, float]:
    """`recorded` updated with a run's times (raised only, for a partial run), minus gone files."""
    out = {f: t for f, t in recorded.items() if f in present}
    for f, t in ran.items():
        if f in present:
            out[f] = max(out.get(f, 0.0), t) if partial else t
    return dict(sorted(out.items()))


def main(argv: list[str]) -> int:
    if argv[:1] == ["--record-runs"]:
        partial = "--partial" in argv
        paths = [a for a in argv[1:] if a != "--partial"]
        ran: dict[str, float] = defaultdict(float)
        for path in paths:
            for f, t in run_durations(Path(path).read_text(encoding="utf-8")).items():
                ran[f] += t
        recorded: dict[str, float] = (
            json.loads(DURATIONS.read_text(encoding="utf-8")) if DURATIONS.exists() else {}
        )
        root = DURATIONS.parents[1]
        present = {f for f in {*recorded, *ran} if (root / f).is_file()}
        merged = merge(recorded, dict(ran), present, partial=partial)
        DURATIONS.write_text(json.dumps(merged, indent=1) + "\n", encoding="utf-8")
        return 0
    if len(argv) == 2 and argv[0] == "--record":
        recorded = file_durations(Path(argv[1]).read_text(encoding="utf-8"))
        DURATIONS.write_text(json.dumps(recorded, indent=1) + "\n", encoding="utf-8")
        return 0
    by_count = "--by-count" in argv
    argv = [a for a in argv if a != "--by-count"]
    if len(argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    shard, shards = int(argv[0]), int(argv[1])
    if not 1 <= shard <= shards:
        print(f"shard {shard} is not in 1..{shards}", file=sys.stderr)
        return 2
    durations: dict[str, float] = (
        json.loads(DURATIONS.read_text(encoding="utf-8")) if DURATIONS.exists() else {}
    )
    files = test_files([Path(root) for root in argv[2:]])
    counts = collected_counts(argv[2:]) if by_count else None
    print("\n".join(split(files, durations, shards, counts)[shard - 1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
