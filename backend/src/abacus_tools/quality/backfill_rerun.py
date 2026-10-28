"""The S12 re-run of the 44 back-filled suites (Q-03-T059; Q-03 §3.2; chapter 10 §10.3).

    make backfill-rerun                                  # run and write the triage report
    python -m abacus_tools.quality.backfill_rerun plan   # the suites per task, as JSON

`docs/quality/backfill.md` is the list: every row whose status is `tranche 0` or `back-filled`
(9 + 35 = 44 tasks) is re-run against `main`'s contracts. A row names its suites in backticks
(`backfill/test_x.py`, `tests/unit/...`, `legacy/specNNNstates.test.tsx`); a tranche-0 row that
names none ("re-run at S12") is re-run through every backend test file that cites its SPEC. The
Python suites run in one pytest invocation (JUnit XML), the web ones in one vitest invocation, and
each file's outcome is folded back onto its tasks. The report
(`docs/quality/backfill-rerun-<date>.md`) lists each task green or red with its failing tests; a
red task needs a defect in `docs/quality/escaped-defects.md` with an owner before Q-03-T059
closes (AC: all 44 green, or each failure ticketed). Nothing here changes a test.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[4]  # the repository
BACKEND: Final = ROOT / "backend"
WEB: Final = ROOT / "apps" / "web"
TRACKER: Final = ROOT / "docs" / "quality" / "backfill.md"
RERUN: Final = frozenset({"tranche 0", "back-filled"})
_TICKED = re.compile(r"`([^`]+)`")
_SPEC = re.compile(r"SPEC-\d{3}")


@dataclass(frozen=True)
class Row:
    task: str
    spec: str
    status: str
    suites: str


@dataclass
class Plan:
    task: str
    spec: str
    python: list[str] = field(default_factory=list[str])
    web: list[str] = field(default_factory=list[str])


def rows(text: str) -> list[Row]:
    """The tracker's rows: `| TASK | Zone | Area | Spec | Sprint | Q-03 row | Status | Suite |`."""
    found: list[Row] = []
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 8 or not re.fullmatch(r"\d{3}", cells[0]):
            continue
        found.append(Row(cells[0], cells[3], cells[6], cells[7]))
    return found


def _python_path(token: str, previous: str | None) -> str | None:
    if not token.endswith(".py"):
        return None
    token = token.removeprefix("backend/")
    if token.startswith("tests/"):
        return token
    if token.startswith("backfill/"):
        return f"tests/integration/{token}"
    if token.startswith(("unit/", "integration/", "security/", "contracts/")):
        return f"tests/{token}"
    if "/" not in token and previous is not None:
        return str(Path(previous).parent / token)  # "`a/test_x.py`, `test_y.py`": same folder
    return None


def _web_path(token: str) -> str | None:
    if not token.endswith((".test.tsx", ".test.ts")):
        return None
    token = token.removeprefix("apps/web/")
    return token if token.startswith("src/") else f"src/{token}"


def _citing(spec: str, tests: Path) -> list[str]:
    """Backend test files that cite `spec` (a tranche-0 row with no suite named)."""
    found: list[str] = []
    for path in sorted(tests.rglob("test_*.py")):
        if spec in path.read_text(encoding="utf-8", errors="ignore"):
            found.append(str(path.relative_to(tests.parent)))
    return found


def plan(text: str, tests: Path = BACKEND / "tests") -> list[Plan]:
    """Each re-run task with its Python and web suites."""
    plans: list[Plan] = []
    for row in rows(text):
        if row.status not in RERUN:
            continue
        p = Plan(row.task, row.spec)
        previous: str | None = None
        for token in _TICKED.findall(row.suites):
            py = _python_path(token, previous)
            if py is not None:
                p.python.append(py)
                previous = py
                continue
            web = _web_path(token)
            if web is not None:
                p.web.append(web)
        if not p.python and not p.web:
            for spec in _SPEC.findall(row.spec):
                p.python.extend(_citing(spec, tests))
        plans.append(p)
    return plans


def _junit_failures(report: Path) -> dict[str, list[str]]:
    """Failed or errored test ids by file (path relative to backend/)."""
    failed: dict[str, list[str]] = {}
    tree = ET.parse(report)  # noqa: S314 -- written by our own pytest run
    for case in tree.iter("testcase"):
        if case.find("failure") is None and case.find("error") is None:
            continue
        module = case.get("classname", "")
        path = module.replace(".", "/") + ".py" if module else case.get("file", "")
        failed.setdefault(path, []).append(case.get("name", "?"))
    return failed


def _owned(path: str, failures: dict[str, list[str]]) -> list[str]:
    stem = path.removesuffix(".py")
    return [
        f"{Path(path).name}::{name}"
        for module, names in failures.items()
        if module.removesuffix(".py").endswith(stem.removeprefix("tests/"))
        for name in names
    ]


def _run_python(paths: Iterable[str], junit: Path) -> int:
    unique = sorted({p for p in paths if (BACKEND / p).exists()})
    if not unique:
        return 0
    argv = ["uv", "run", "pytest", "-q", f"--junitxml={junit}", *unique]
    return subprocess.call(argv, cwd=BACKEND)  # noqa: S603 -- a fixed argv of our own paths


def _run_web(paths: Iterable[str]) -> set[str]:
    """The web suites that failed (vitest exits non-zero on any; run each to tell them apart)."""
    failed: set[str] = set()
    for path in sorted({p for p in paths if (WEB / p).exists()}):
        argv = ["pnpm", "exec", "vitest", "run", path]
        code = subprocess.call(argv, cwd=WEB)  # noqa: S603 -- a fixed argv of our own paths
        if code != 0:
            failed.add(path)
    return failed


def report(plans: Sequence[Plan], failures: dict[str, list[str]], web_failed: set[str]) -> str:
    today = date.today().isoformat()
    lines = [
        f"# Back-fill re-run, {today} (Q-03-T059)",
        "",
        "The 44 back-filled suites (tranche 0 and S6 to S11) re-run on `main` against the final",
        "MVP contracts. A red task needs a defect in `escaped-defects.md` with an owner.",
        "",
        "| TASK | Spec | Suites | Result | Failing |",
        "|---|---|---|---|---|",
    ]
    green = 0
    for p in plans:
        missing = [s for s in p.python if not (BACKEND / s).exists()] + [
            s for s in p.web if not (WEB / s).exists()
        ]
        failing = [f for s in p.python for f in _owned(s, failures)]
        failing += [f"{s} (vitest)" for s in p.web if s in web_failed]
        failing += [f"{s} (missing)" for s in missing]
        ok = not failing and (p.python or p.web)
        green += 1 if ok else 0
        suites = len(p.python) + len(p.web)
        result = "green" if ok else "red" if suites else "no suite found"
        lines.append(
            f"| {p.task} | {p.spec} | {suites} | {result} | {'; '.join(failing[:5]) or '—'} |"
        )
    lines += ["", f"**{green} of {len(plans)} green.**", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    plans = plan(TRACKER.read_text(encoding="utf-8"))
    if args[:1] == ["plan"]:
        print(json.dumps([p.__dict__ for p in plans], indent=2))
        return 0
    junit = BACKEND / ".backfill-rerun.xml"
    _run_python((s for p in plans for s in p.python), junit)
    failures = _junit_failures(junit) if junit.exists() else {}
    web_failed = _run_web(s for p in plans for s in p.web)
    out = ROOT / "docs" / "quality" / f"backfill-rerun-{date.today().isoformat()}.md"
    out.write_text(report(plans, failures, web_failed), encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}")
    return 0 if not failures and not web_failed else 1


if __name__ == "__main__":
    sys.exit(main())
