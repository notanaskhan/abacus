"""The weekly DAST baseline's triage (Q-03-T004; QD-9; Q-03 D4; DEC-366).

Run: python -m abacus_tools.quality.dast REPORT.json [--summary FILE] [--github-output FILE]

Reads the OWASP ZAP baseline's JSON report (`zap-baseline.py -J`) and counts its alerts by risk.
The repository and its Actions logs are public, so only counts leave this tool: no alert name,
URL, parameter or evidence is printed. The full report is encrypted to the founders' key before it
is kept (dast.yml). Exit 0 always; the workflow reads `high=<n>` from `--github-output`, opens or
updates the SEV3 ticket and fails the run when it is above zero.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Final, cast

RISKS: Final = {"3": "high", "2": "medium", "1": "low", "0": "informational"}


def counts(report: dict[str, object]) -> dict[str, int]:
    """Alerts (distinct ZAP rules per site) by risk; each risk present even at zero."""
    found = dict.fromkeys(RISKS.values(), 0)
    for site in cast(list[dict[str, object]], report.get("site") or []):
        for alert in cast(list[dict[str, object]], site.get("alerts") or []):
            risk = RISKS.get(str(alert.get("riskcode")))
            if risk is None:
                raise ValueError(f"unknown ZAP riskcode {alert.get('riskcode')!r}")
            found[risk] += 1
    return found


def summary(found: dict[str, int]) -> str:
    rows = ["## DAST baseline (OWASP ZAP) on staging", "", "| Risk | Alerts |", "|---|---|"]
    rows += [f"| {risk} | {n} |" for risk, n in found.items()]
    rows += [
        "",
        "Counts only: the report is encrypted to the founders' key and kept as this run's "
        "artifact (the repository is public).",
    ]
    if found["high"]:
        rows += ["", f"**{found['high']} high alert(s): a SEV3 ticket is open for triage.**"]
    return "\n".join(rows) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("report", type=Path)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args(argv)
    report = cast(dict[str, object], json.loads(cast(Path, args.report).read_text("utf-8")))
    found = counts(report)
    text = summary(found)
    if args.summary is not None:
        with cast(Path, args.summary).open("a", encoding="utf-8") as out:
            out.write(text)
    else:
        print(text, end="")
    if args.github_output is not None:
        with cast(Path, args.github_output).open("a", encoding="utf-8") as out:
            out.write(f"high={found['high']}\nmedium={found['medium']}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
