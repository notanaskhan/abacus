"""Split test files across CI jobs, balanced by recorded run time (TASK-017).

Run: python -m abacus_tools.ci.shard <shard> <shards> <root>...

Prints the test files of shard `<shard>` (1-based) of `<shards>`, one per line. Every
`test_*.py` under the roots goes to exactly one shard, so the shards together run the whole suite:
a file missing from the timings (a new file) still runs, weighted as the median file. Greedy
longest-first, deterministic: the same files and timings always give the same split.

Timings: `tests/durations.json`, seconds per file, from a JUnit report of a full run:
python -m abacus_tools.ci.shard --record <junit.xml>
"""

from __future__ import annotations

import json
import statistics
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

DURATIONS = Path(__file__).resolve().parents[3] / "tests" / "durations.json"


def test_files(roots: list[Path]) -> list[str]:
    files = {path.as_posix() for root in roots for path in root.rglob("test_*.py")}
    return sorted(files)


def split(files: list[str], durations: dict[str, float], shards: int) -> list[list[str]]:
    if shards < 1:
        raise ValueError("at least one shard")
    if len(files) < shards:
        raise ValueError(f"{len(files)} test files can't fill {shards} shards")
    known = [durations[f] for f in files if f in durations]
    default = statistics.median(known) if known else 1.0
    weight = {f: durations.get(f, default) for f in files}
    loads = [0.0] * shards
    out: list[list[str]] = [[] for _ in range(shards)]
    for f in sorted(files, key=lambda f: (-weight[f], f)):
        lightest = min(range(shards), key=lambda i: (loads[i], i))
        out[lightest].append(f)
        loads[lightest] += weight[f]
    return [sorted(shard) for shard in out]


def file_durations(junit: str) -> dict[str, float]:
    """Seconds per test file, from a pytest JUnit report (classnames are dotted file paths)."""
    totals: dict[str, float] = defaultdict(float)
    for case in ET.fromstring(junit).iter("testcase"):  # noqa: S314 -- our own pytest report
        module = case.get("classname", "").split("::")[0]
        parts = module.split(".")
        # `tests.unit.kernel.test_x.TestClass` → `tests/unit/kernel/test_x.py`
        while parts and not parts[-1].startswith("test_"):
            parts.pop()
        if parts:
            totals["/".join(parts) + ".py"] += float(case.get("time", "0"))
    return {f: round(t, 2) for f, t in sorted(totals.items())}


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[0] == "--record":
        recorded = file_durations(Path(argv[1]).read_text(encoding="utf-8"))
        DURATIONS.write_text(json.dumps(recorded, indent=1) + "\n", encoding="utf-8")
        return 0
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
    print("\n".join(split(files, durations, shards)[shard - 1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
