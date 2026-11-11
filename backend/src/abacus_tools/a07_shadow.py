"""`make a07-shadow` (Q-04-T136; DEC-3305): A-07's dark code shadowed on one engagement per audit
firm ahead of M16. Read-only: the shadow facts (`assurance.api.a07_shadow_facts`) against the
firm tool's own dates, one row per check, written as Markdown for the go-live dossier.

    python -m abacus_tools.a07_shadow --firm F --work-item W --firm-tool tool.yaml [--out x.md]

The firm-tool file (the firm's own record of the engagement, typed by the champion):

    engagement: Northwind Robotics 401(k) Plan PY2025
    tool: Firm's audit tool
    report_released_on: 2026-10-09
    documentation_completion_date: 2026-12-08
    archived_on: 2026-12-03
    opinion: unmodified

A check matches, differs, or is not yet comparable (one side has no date). Nothing is written to
the firm; the report is the operator's, and a person reads every difference.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Final, Literal, cast
from uuid import UUID

import yaml

from abacus.kernel.db import TenantContext

Outcome = Literal["match", "differs", "not_yet"]
DATE_KEYS: Final = ("report_released_on", "documentation_completion_date", "archived_on")
LABEL: Final = {
    "report_released_on": "Report released",
    "documentation_completion_date": "Documentation completion date (AU-C 230)",
    "archived_on": "Archive locked",
}


@dataclass(frozen=True)
class Check:
    key: str
    label: str
    accrued: str | None
    firm_tool: str | None
    outcome: Outcome


def _day(value: object) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def compare(
    accrued: Mapping[str, date | None],
    gates: Mapping[str, bool],
    firm_tool: Mapping[str, object],
) -> list[Check]:
    """One check per date and one for the gates on the firm's release date: Accrued's G5 to G7
    all met when the firm's tool released (a gate still open is a difference to read)."""
    out: list[Check] = []
    for key in DATE_KEYS:
        ours, theirs = accrued.get(key), _day(firm_tool.get(key))
        outcome: Outcome = (
            "not_yet"
            if ours is None or theirs is None
            else "match"
            if ours == theirs
            else "differs"
        )
        out.append(
            Check(
                key,
                LABEL[key],
                None if ours is None else ours.isoformat(),
                None if theirs is None else theirs.isoformat(),
                outcome,
            )
        )
    released = _day(firm_tool.get("report_released_on"))
    open_gates = sorted(g for g, met in gates.items() if not met)
    out.append(
        Check(
            "gates_at_release",
            "G5 to G7 met when the firm released",
            "all met" if not open_gates else f"open: {', '.join(open_gates)}",
            None if released is None else f"released {released.isoformat()}",
            "not_yet" if released is None else "match" if not open_gates else "differs",
        )
    )
    return out


def render(engagement: str, tool: str, firm: UUID, checks: list[Check], synthetic: bool) -> str:
    words = {"match": "Match", "differs": "Differs", "not_yet": "Not yet comparable"}
    lines = [
        f"# A-07 shadow · {engagement}",
        "",
        f"Firm `{firm}`{' (synthetic, PF-X1)' if synthetic else ''} · compared against {tool}.",
        "",
        "| Check | Accrued (shadow) | Firm tool | Outcome |",
        "|---|---|---|---|",
    ]
    lines += [
        f"| {c.label} | {c.accrued or '—'} | {c.firm_tool or '—'} | {words[c.outcome]} |"
        for c in checks
    ]
    differs = [c for c in checks if c.outcome == "differs"]
    lines += [
        "",
        f"{len(differs)} difference(s) to read."
        if differs
        else "No differences. Every comparable check matches.",
        "",
    ]
    return "\n".join(lines)


async def _run(firm: UUID, work_item: UUID, tool_file: Path) -> str:
    from abacus.modules.assurance.api import a07_shadow_facts
    from abacus.modules.identity.api import is_synthetic_firm

    raw = cast(dict[str, object], yaml.safe_load(tool_file.read_text(encoding="utf-8")) or {})
    tenant = TenantContext(firm, "system", "a07_shadow")
    facts = await a07_shadow_facts(tenant, work_item)
    accrued: dict[str, date | None] = {
        "report_released_on": facts.released_on,
        "documentation_completion_date": facts.documentation_completion_date,
        "archived_on": facts.archived_on,
    }
    checks = compare(accrued, dict(facts.gates), raw)
    return render(
        str(raw.get("engagement", work_item)),
        str(raw.get("tool", "the firm's own tool")),
        firm,
        checks,
        await is_synthetic_firm(tenant),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="a07_shadow", description=__doc__)
    parser.add_argument("--firm", required=True, type=UUID)
    parser.add_argument("--work-item", required=True, type=UUID)
    parser.add_argument("--firm-tool", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    report = asyncio.run(_run(args.firm, args.work_item, args.firm_tool))
    if args.out is not None:
        args.out.write_text(report, encoding="utf-8")
    else:
        sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
