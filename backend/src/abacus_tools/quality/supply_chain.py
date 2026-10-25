"""Supply-chain findings to SLA (Q-03-T029; Q-03 §3.9 I2; ADR-099; DEC-366).

Run from backend/: python -m abacus_tools.quality.supply_chain <command>

`docs/quality/supply-chain-findings.yaml` lists every known high or critical finding from
pip-audit, bandit, Trivy (filesystem, IaC, image), CodeQL or Inspector that is not fixed yet: its
id, source, severity, the day it was first seen and, once fixed, the day it was closed. The SLA
runs from the first-seen day: critical 7 days, high 30 days.

- `check [--as-of DATE]`: the register parses, and no open finding is past its SLA (exit 1).
- `ignores --tool pip-audit|trivy`: the scanner's ignore list, made of the open findings for that
  tool that are still inside their SLA. The scanners fail CI on any other high or critical
  finding, so a finding is either fixed, inside its SLA in the register, or a red build; once the
  SLA passes, the ignore falls away and the build goes red until it is fixed (security.yml).
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Final, cast

import yaml

from abacus.kernel.clock import system_now

REPO = Path(__file__).resolve().parents[4]
REGISTER = REPO / "docs" / "quality" / "supply-chain-findings.yaml"

SLA_DAYS: Final = {"critical": 7, "high": 30}
SOURCES: Final = frozenset(
    {"pip-audit", "bandit", "trivy-fs", "trivy-iac", "trivy-image", "codeql", "inspector"}
)
# Which register sources each scanner's ignore list is made from.
TOOLS: Final = {"pip-audit": {"pip-audit"}, "trivy": {"trivy-fs", "trivy-iac", "trivy-image"}}
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{1,80}$")


class RegisterInvalid(ValueError):
    """The register is not in the shape this tool reads."""


@dataclass(frozen=True)
class Finding:
    id: str
    source: str
    severity: str
    first_seen: date
    closed: date | None
    package: str
    note: str

    @property
    def due(self) -> date:
        return self.first_seen + timedelta(days=SLA_DAYS[self.severity])

    def open_on(self, day: date) -> bool:
        return self.closed is None or self.closed > day


def _day(value: object, where: str) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise RegisterInvalid(f"{where}: {value!r} is not a YYYY-MM-DD date") from exc


def parse(text: str) -> list[Finding]:
    data = cast(dict[str, object], yaml.safe_load(text) or {})
    rows = data.get("findings")
    if rows is None:
        return []
    if not isinstance(rows, list):
        raise RegisterInvalid("findings: must be a list")
    found: list[Finding] = []
    seen: set[tuple[str, str]] = set()
    for n, raw in enumerate(cast(list[object], rows), start=1):
        if not isinstance(raw, dict):
            raise RegisterInvalid(f"finding {n}: must be a mapping")
        row = cast(dict[str, object], raw)
        where = f"finding {n} ({row.get('id')})"
        ident, source, severity = str(row.get("id", "")), row.get("source"), row.get("severity")
        if not _ID.match(ident):
            raise RegisterInvalid(f"{where}: id must be an advisory, CVE or rule id")
        if source not in SOURCES:
            raise RegisterInvalid(f"{where}: source must be one of {sorted(SOURCES)}")
        if severity not in SLA_DAYS:
            raise RegisterInvalid(f"{where}: severity must be critical or high")
        if (ident, str(source)) in seen:
            raise RegisterInvalid(f"{where}: listed twice")
        seen.add((ident, str(source)))
        first = _day(row.get("first_seen"), where)
        closed = None if row.get("closed") is None else _day(row.get("closed"), where)
        if closed is not None and closed < first:
            raise RegisterInvalid(f"{where}: closed before it was first seen")
        found.append(
            Finding(
                ident,
                str(source),
                str(severity),
                first,
                closed,
                str(row.get("package", "")),
                str(row.get("note", "")),
            )
        )
    return found


def overdue(findings: list[Finding], day: date) -> list[str]:
    return [
        f"{f.id} ({f.source}, {f.severity}, {f.package or 'no package'}): first seen "
        f"{f.first_seen}, due {f.due}, still open on {day}"
        for f in findings
        if f.open_on(day) and f.due < day
    ]


def ignores(findings: list[Finding], tool: str, day: date) -> list[str]:
    """Ids the tool may skip today: open, inside their SLA, from the tool's sources."""
    sources = TOOLS[tool]
    return sorted(
        {
            f.id
            for f in findings
            if f.source in sources and f.open_on(day) and f.first_seen <= day <= f.due
        }
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check")
    check.add_argument("--as-of", type=date.fromisoformat)
    check.add_argument("--register", type=Path, default=REGISTER)
    ignore = commands.add_parser("ignores")
    ignore.add_argument("--tool", choices=sorted(TOOLS), required=True)
    ignore.add_argument("--as-of", type=date.fromisoformat)
    ignore.add_argument("--register", type=Path, default=REGISTER)
    ignore.add_argument("--out", type=Path, help="write one id per line (a .trivyignore)")
    args = parser.parse_args(argv)
    day = cast(date | None, args.as_of) or system_now().date()
    try:
        findings = parse(cast(Path, args.register).read_text(encoding="utf-8"))
    except RegisterInvalid as exc:
        print(f"supply-chain register: {exc}")
        return 1
    if args.command == "check":
        late = overdue(findings, day)
        for line in late:
            print(f"past SLA: {line}")
        if not late:
            still = sum(1 for f in findings if f.open_on(day))
            print(f"supply-chain register: {still} open finding(s), none past SLA on {day}")
        return 1 if late else 0
    ids = ignores(findings, cast(str, args.tool), day)
    if args.out is not None:
        cast(Path, args.out).write_text("".join(f"{i}\n" for i in ids), encoding="utf-8")
    elif args.tool == "pip-audit":
        print(" ".join(f"--ignore-vuln {i}" for i in ids))
    else:
        print("\n".join(ids))
    return 0


if __name__ == "__main__":
    sys.exit(main())
