"""`python -m abacus_tools.evals [--agent ID] [--tier small|medium|large] [--subset fast|full]
[--out DIR]`: run an agent's evaluation suite; exit 0 only if the run passed (SPEC-005 AC-1)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import cast

from abacus.ai_gateway import Tier
from abacus_tools.evals.runner import Subset, run

DEFAULT_OUT = Path(__file__).resolve().parents[3] / ".evals"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m abacus_tools.evals")
    parser.add_argument("--agent", default="evidence.screener")
    parser.add_argument("--tier", choices=["small", "medium", "large"], default=None)
    parser.add_argument("--subset", choices=["fast", "full"], default="full")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    summary = run(
        cast(str, args.agent),
        cast(Tier | None, args.tier),
        cast(Subset, args.subset),
        cast(Path, args.out),
    )
    shown = {k: v for k, v in summary.items() if k != "cases"}
    print(json.dumps(shown, indent=2))
    return 0 if summary.get("status") == "passed" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
