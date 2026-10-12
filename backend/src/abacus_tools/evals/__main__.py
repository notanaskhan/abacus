"""`python -m abacus_tools.evals [--agent ID] [--tier small|medium|large] [--subset fast|full]
[--out DIR] [--route fake|direct]`: run an agent's evaluation suite; exit 0 only if the run
passed (SPEC-005 AC-1)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import cast

from abacus.ai_gateway import Tier
from abacus.modules.agents.api import REVIEWER, spec
from abacus_tools.evals.report import render
from abacus_tools.evals.runner import EvalRoute, Subset, guard, guard_real, prepare, run
from abacus_tools.evals.upload_review import evaluate, load_suite, validate
from abacus_tools.stack import Stack, run_with_stack

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
    if args.agent == "evidence.upload_reviewer":  # SPEC-030 (TASK-058 D4): its own runner
        return review_main(
            cast(Tier | None, args.tier), cast(str, args.route), cast(Path, args.out)
        )
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


def review_main(tier: Tier | None, route: str, out: Path) -> int:
    """The upload reviewer's suite, on a throwaway stack; real routes only (TASK-058 D5)."""
    if route == "fake":
        print("the upload reviewer has no fake answers: run it with --route direct")
        return 2
    guard()
    guard_real(cast(EvalRoute, route))
    chosen: Tier = tier or spec(REVIEWER).tier
    suite = load_suite()
    validate(suite)
    results: list[dict[str, object]] = []

    async def record(stack: Stack) -> None:
        world = await prepare(stack)
        results.append(await evaluate(stack, world, suite, chosen, route, out))

    run_with_stack(record)
    return 0 if results and results[0]["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
