"""The flaky-test quarantine (Q-03-T097; quality strategy §10.4, F-01).

    python -m abacus_tools.quality.quarantine [--today YYYY-MM-DD]

A flaky test is quarantined, never skipped: the backend marks it

    @pytest.mark.quarantine(issue="#123", owner="ayushkbhatia", since="2027-05-31")

and a Playwright spec carries, on the line above its `test(`:

    // quarantine: issue=#123 owner=ayushkbhatia since=2027-05-31

A quarantined test still runs; the marker records who fixes it and by when. Each one has a
deadline of at most 10 working days from `since`. More than 5 in quarantine, or any past its
deadline, fails this check, and the next batch is test-fix only.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from abacus.kernel.clock import system_now

ROOT = Path(__file__).resolve().parents[3]
BACKEND_TESTS = ROOT / "tests"
WEB = ROOT.parent / "apps" / "web"
MAX_QUARANTINED = 5
MAX_WORKING_DAYS = 10
_WEB_MARK = re.compile(r"//\s*quarantine:\s*issue=(\S+)\s+owner=(\S+)\s+since=(\d{4}-\d{2}-\d{2})")


@dataclass(frozen=True)
class Quarantined:
    where: str
    issue: str
    owner: str
    since: date

    @property
    def deadline(self) -> date:
        return add_working_days(self.since, MAX_WORKING_DAYS)


def add_working_days(start: date, days: int) -> date:
    """`days` Monday-to-Friday days after `start` (holidays are not counted out)."""
    day = start
    left = days
    while left > 0:
        day += timedelta(days=1)
        if day.weekday() < 5:
            left -= 1
    return day


def working_days_between(start: date, end: date) -> int:
    count, day = 0, start
    while day < end:
        day += timedelta(days=1)
        if day.weekday() < 5:
            count += 1
    return count


def _keyword(call: ast.Call, name: str) -> str | None:
    for kw in call.keywords:
        if (
            kw.arg == name
            and isinstance(kw.value, ast.Constant)
            and isinstance(kw.value.value, str)
        ):
            return kw.value.value
    return None


def _is_quarantine(node: ast.expr) -> ast.Call | None:
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "quarantine"
    ):
        return node
    return None


def backend(root: Path = BACKEND_TESTS) -> Iterator[Quarantined | str]:
    """Each quarantined backend test, or a problem string for a malformed marker."""
    for path in sorted(root.rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                continue
            for decorator in node.decorator_list:
                call = _is_quarantine(decorator)
                if call is None:
                    continue
                where = f"{path.relative_to(root.parent)}::{node.name}"
                issue, owner, since = (_keyword(call, k) for k in ("issue", "owner", "since"))
                if issue is None or owner is None or since is None:
                    yield f"{where}: quarantine needs issue, owner and since"
                    continue
                try:
                    yield Quarantined(where, issue, owner, date.fromisoformat(since))
                except ValueError:
                    yield f"{where}: since {since!r} is not a date"


def web(root: Path = WEB) -> Iterator[Quarantined]:
    for folder in (root / "e2e", root / "src"):
        if not folder.exists():
            continue
        for path in sorted(folder.rglob("*.ts*")):
            if "node_modules" in path.parts:
                continue
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                found = _WEB_MARK.search(line)
                if found is not None:
                    yield Quarantined(
                        f"{path.relative_to(root.parent.parent)}:{n}",
                        found.group(1),
                        found.group(2),
                        date.fromisoformat(found.group(3)),
                    )


def check(
    today: date, tests: Path | None = None, web_root: Path | None = None
) -> tuple[list[Quarantined], list[str]]:
    held: list[Quarantined] = []
    problems: list[str] = []
    for item in [*backend(tests or BACKEND_TESTS), *web(web_root or WEB)]:
        if isinstance(item, str):
            problems.append(item)
        else:
            held.append(item)
    if len(held) > MAX_QUARANTINED:
        problems.append(f"{len(held)} tests in quarantine (at most {MAX_QUARANTINED})")
    problems.extend(
        f"{q.where}: past its deadline {q.deadline.isoformat()} ({q.issue}, {q.owner})"
        for q in held
        if today > q.deadline
    )
    return held, problems


def summary(today: date) -> tuple[int, int | None]:
    """How many are in quarantine and the oldest one's age in working days (for the report)."""
    held, _ = check(today)
    ages = [working_days_between(q.since, today) for q in held]
    return len(held), (max(ages) if ages else None)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--today", type=date.fromisoformat, default=None)
    args = parser.parse_args(argv)
    today: date = args.today or system_now().date()
    held, problems = check(today)
    for q in held:
        print(f"quarantined: {q.where} {q.issue} {q.owner} until {q.deadline.isoformat()}")
    for p in problems:
        print(p)
    print(f"{len(held)} in quarantine")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
