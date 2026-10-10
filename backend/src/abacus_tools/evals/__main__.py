"""`python -m abacus_tools.evals [--agent ID] [--tier small|medium|large] [--subset fast|full]
[--out DIR] [--route fake|direct]`: run an agent's evaluation suite; exit 0 only if the run
passed (SPEC-005 AC-1)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import cast

from abacus.ai_gateway import Tier
from abacus_tools.evals.report import render
from abacus_tools.evals.runner import EvalRoute, Subset, run

DEFAULT_OUT = Path(__file__).resolve().parents[3] / ".evals"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m abacus_tools.evals")
    parser.add_argument("--agent", default="evidence.screener")
    parser.add_argument("--tier", choices=["small", "medium", "large"], default=None)
    parser.add_argument("--subset", choices=["fast", "full"], default="full")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    # SPEC-026: `direct` runs the real model (evaluation environment, synthetic data only).
    parser.add_argument("--route", choices=["fake", "direct"], default="fake")
    args = parser.parse_args(argv)
    [summary] = run(
        cast(str, args.agent),
        cast(Tier | None, args.tier),
        cast(Subset, args.subset),
        cast(Path, args.out),
        route=cast(EvalRoute, args.route),
    )
    print(summary.model_dump_json(indent=2, exclude={"cases"}))
    if summary.report is not None:
        print(render(summary.report))
    return 0 if summary.status == "passed" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
