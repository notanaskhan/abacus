"""The Contract Monday note (F-09 A4, one per sprint; F-09-T124 for S15; chapter 11 §11.8).

    python -m abacus_tools.contract_monday --sprint S15 --on 2027-05-17 \
        [--rk RK-01 --rk RK-04 ...] [--out docs/ops/programme/contract-monday/2027-05-17-S15.md]

When a sprint opens, the note lists every open application, contract and partner with its status
(from `docs/ops/vendors/README.md`, the tracker), flags each one past its "Needed by" date, and
lays out the risk-register triggers to check that day (from `docs/plan/11-risk-register.md`, the
"early-warning signal" and "contingency" columns), each with a "Fired?" cell a person answers. A
fired trigger's pre-agreed action is the register's contingency, taken that day (the acceptance).

The tool only reads the two files: it never fills in a status, decides whether a trigger fired, or
writes a price, a contract term, a partner's name or counsel's advice (the tracker's "Never in
git"). An open row is any status other than `approved` or `not needed`. "Needed by" is read as its
first month and day ("Oct 30", "Nov 13", "Dec 11 (draft)"); the year is the plan's: October to
December are 2026, January to September 2027, unless the cell names a year.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[2].parent
TRACKER: Final = ROOT / "docs" / "ops" / "vendors" / "README.md"
REGISTER: Final = ROOT / "docs" / "plan" / "11-risk-register.md"
CLOSED: Final = frozenset({"approved", "not needed"})
MONTHS: Final = {
    m: n
    for n, m in enumerate(
        ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
        start=1,
    )
}
_DAY: Final = re.compile(
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\.? (\d{1,2})(?:, (\d{4}))?"
)
# F-09-T124's own list for S15 (the row names them).
DEFAULT_RKS: Final = ("RK-01", "RK-04", "RK-05", "RK-47", "RK-50")


@dataclass(frozen=True)
class Application:
    section: str
    name: str
    needed_by: str
    gate: str
    status: str
    vault: str

    def due(self) -> date | None:
        match = _DAY.search(self.needed_by)
        if match is None:
            return None
        month = MONTHS[match.group(1)]
        year = int(match.group(3)) if match.group(3) else (2026 if month >= 10 else 2027)
        return date(year, month, int(match.group(2)))


@dataclass(frozen=True)
class Trigger:
    rk: str
    signal: str
    contingency: str


def applications(text: str) -> list[Application]:
    found: list[Application] = []
    section = ""
    header: list[str] | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("## "):
            section, header = line[3:].strip(), None
            continue
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if header is None:
            header = cells
            continue
        if all(set(c) <= {"-", ":"} for c in cells) or "Application" not in header:
            continue
        row = dict(zip(header, cells, strict=False))
        found.append(
            Application(
                section,
                row.get("Application", ""),
                row.get("Needed by", ""),
                row.get("Gate", ""),
                row.get("Status", ""),
                row.get("Vault", ""),
            )
        )
    return found


def triggers(text: str, wanted: Sequence[str]) -> list[Trigger]:
    """The register's trigger table rows (ID, early-warning signal, mitigation, contingency) for
    the wanted ids, in the order asked; a missing id is reported, not invented."""
    rows: dict[str, Trigger] = {}
    header: list[str] | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            header = None
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if header is None:
            header = cells
            continue
        if "Early-warning signal" not in header or all(set(c) <= {"-", ":"} for c in cells):
            continue
        row = dict(zip(header, cells, strict=False))
        rk = row.get("ID", "")
        if rk in wanted and rk not in rows:
            rows[rk] = Trigger(
                rk,
                row.get("Early-warning signal", ""),
                next((v for k, v in row.items() if k.startswith("Contingency")), ""),
            )
    return [rows[r] if r in rows else Trigger(r, "not in the register", "—") for r in wanted]


def _cell(text: str) -> str:
    return text.replace("|", "/").replace("\n", " ")


def note(sprint: str, on: date, apps: Sequence[Application], rks: Sequence[Trigger]) -> str:
    open_apps = [a for a in apps if a.status.lower() not in CLOSED]
    overdue = [a for a in open_apps if (d := a.due()) is not None and d < on]
    parts = [
        f"# Contract Monday · {sprint} · {on.isoformat()}\n\n",
        "F-09's sprint-opening note (A4). Status from `docs/ops/vendors/README.md`; triggers from "
        "`docs/plan/11-risk-register.md`. Never a price, a contract term, a partner's name or "
        "counsel's advice: those are in the vault.\n\n",
        f"**Open:** {len(open_apps)} of {len(apps)} · **past Needed by:** {len(overdue)}\n\n",
        "## Open applications, contracts and partners\n\n",
        "| Section | Application | Gate | Needed by | Status | Vault | Past due |\n"
        "|---|---|---|---|---|---|---|\n",
    ]
    for a in open_apps:
        late = "**yes**" if a in overdue else ""
        parts.append(
            f"| {_cell(a.section)} | {_cell(a.name)} | {_cell(a.gate)} | {_cell(a.needed_by)} | "
            f"{_cell(a.status)} | {_cell(a.vault) or '—'} | {late} |\n"
        )
    parts += [
        "\n## Triggers to check today\n\n",
        "A fired trigger's action is its contingency, taken today; write what was done.\n\n",
        "| RK | Early-warning signal | Contingency (trigger → action) | Fired? | Action taken |\n"
        "|---|---|---|---|---|\n",
    ]
    for t in rks:
        parts.append(f"| {t.rk} | {_cell(t.signal)} | {_cell(t.contingency)} | — | — |\n")
    parts += [
        "\n## Ledger and replies\n\n",
        "| Item | Done | Vault |\n|---|---|---|\n",
        "| Vendor tracker refreshed (every row's status and date checked) | — | — |\n",
        "| Spend ledger refreshed against the envelope (amounts stay in the vault) | — | — |\n",
        "| Vendor reviewer replies answered | — | — |\n",
    ]
    return "".join(parts)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="abacus_tools.contract_monday", description=__doc__)
    parser.add_argument("--sprint", required=True)
    parser.add_argument("--on", type=date.fromisoformat, required=True)
    parser.add_argument("--rk", action="append", default=[])
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    apps = applications(TRACKER.read_text(encoding="utf-8"))
    rks = triggers(REGISTER.read_text(encoding="utf-8"), args.rk or list(DEFAULT_RKS))
    body = note(args.sprint, args.on, apps, rks)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(body, encoding="utf-8")
    print(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
