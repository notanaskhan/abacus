"""Every register ID appears once (Q-03-T087; the integration and conflict lane).

    python -m abacus_tools.quality.register_ids

The registers are append-only tables that many branches add rows to: the decision log's
decisions, the escaped-defect log and the runbook index. A batch of stacked PRs, squash-merged one
by one, can leave the same row twice (git adds both copies without a conflict) or two versions of
one row (a branch that revised a row its base added). Either way the register no longer says one
thing per ID. This check fails on a repeated ID and names both lines; the fix keeps the newer
version and deletes the other, by hand, in the lane's PR.

The decision log's "Register facts" table repeats DEC-01 to DEC-101 by design (one fact row per
decision): only the rows under `## Decisions` are checked there.
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[3].parent


@dataclass(frozen=True)
class Register:
    path: Path
    pattern: re.Pattern[str]
    section: str | None = None  # only rows after this heading (up to the next `## `)


REGISTERS: Final = (
    Register(
        ROOT / "docs/product/decision-log.md", re.compile(r"^\| (DEC-\d+) \|"), "## Decisions"
    ),
    Register(ROOT / "docs/quality/escaped-defects.md", re.compile(r"^\| (ED-\d+) \|")),
    Register(ROOT / "docs/runbooks/README.md", re.compile(r"^\| (RB-\d+) \|")),
)


def repeated(
    text: str, pattern: re.Pattern[str], section: str | None = None
) -> dict[str, list[int]]:
    """Each ID found on more than one line, with its line numbers."""
    lines: dict[str, list[int]] = defaultdict(list)
    inside = section is None
    for number, line in enumerate(text.splitlines(), start=1):
        if section is not None and line.startswith("## "):
            inside = line.strip() == section
            continue
        if not inside:
            continue
        match = pattern.match(line)
        if match:
            lines[match.group(1)].append(number)
    return {key: found for key, found in lines.items() if len(found) > 1}


def check(registers: tuple[Register, ...] = REGISTERS) -> list[str]:
    problems: list[str] = []
    for register in registers:
        text = register.path.read_text(encoding="utf-8")
        rel = (
            register.path.relative_to(ROOT)
            if register.path.is_relative_to(ROOT)
            else register.path
        )
        for key, numbers in sorted(repeated(text, register.pattern, register.section).items()):
            body = text.splitlines()
            same = len({body[n - 1] for n in numbers}) == 1
            kind = "the same row twice" if same else "two versions of the row"
            problems.append(f"{rel}: {key} on lines {', '.join(map(str, numbers))} ({kind})")
    return problems


def main() -> int:
    problems = check()
    for problem in problems:
        print(f"register ids: {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
