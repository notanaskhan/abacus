"""`python -m abacus_tools.evals [--agent ID] [--tier small|medium|large] [--subset fast|full]
[--out DIR] [--route fake|direct]`: run an agent's evaluation suite; exit 0 only if the run
passed (SPEC-005 AC-1)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import cast

from abacus.ai_gateway import Tier
from abacus.modules.agents.api import ASSESSOR, DRAFTER, MATCHER, REVIEWER, spec
from abacus_tools.evals import entry_assessment, guidance_drafting, matching
from abacus_tools.evals.decision_recommendation import AGENT as RECOMMENDER
from abacus_tools.evals.decision_recommendation import recommend_main
from abacus_tools.evals.methodology_import import AGENT as IMPORTER
from abacus_tools.evals.methodology_import import import_suite_main
from abacus_tools.evals.report import render
from abacus_tools.evals.runner import EvalRoute, Subset, guard, guard_real, prepare, run
from abacus_tools.evals.section_drafting import AGENT as SECTION_DRAFTER
from abacus_tools.evals.section_drafting import Mode as DraftMode
from abacus_tools.evals.section_drafting import draft_suite_main
from abacus_tools.evals.upload_review import (
    evaluate,
    fake_answers,
    fake_reviewer,
    load_suite,
    validate,
)
from abacus_tools.stack import Stack, run_with_stack

DEFAULT_OUT = Path(__file__).resolve().parents[3] / ".evals"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m abacus_tools.evals")
    parser.add_argument("--agent", default="evidence.screener")
    parser.add_argument("--tier", choices=["small", "medium", "large"], default=None)
    parser.add_argument("--subset", choices=["fast", "full"], default="full")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    # SPEC-026: `direct` and `bedrock` run the real model (evaluation environment, synthetic data
    # only); `bedrock` is the clearance run (N-01-T26) once the route passes parity.
    parser.add_argument("--route", choices=["fake", "direct", "bedrock"], default="fake")
    # N-01-T21: the matcher's suite has an audit section and an intake section.
    parser.add_argument("--section", choices=["audit", "intake"], default="audit")
    # A-04-T14: the section drafter's suite has a case set per mode.
    parser.add_argument(
        "--mode",
        choices=["gap", "risk_narrative", "risk", "ic", "soc1", "ebp_provisions", "ebp_attribute"],
    )
    args = parser.parse_args(argv)
    if args.agent == "evidence.upload_reviewer":  # SPEC-030 (TASK-058 D4): its own runner
        return review_main(
            cast(Tier | None, args.tier),
            cast(str, args.route),
            cast(Path, args.out),
            cast(Subset, args.subset),
        )
    if args.agent == IMPORTER:  # K-01-T22: code-graded, no stack (TASK-2921)
        return import_suite_main(
            cast(str, args.route), cast(Path, args.out), cast(Subset, args.subset)
        )
    if args.agent == RECOMMENDER:  # A-04-T09: code-graded, no stack (TASK-2802)
        return recommend_main(
            cast(str, args.route), cast(Path, args.out), cast(Subset, args.subset)
        )
    if args.agent == SECTION_DRAFTER:  # A-04-T14: code-graded, no stack (TASK-2902)
        return draft_suite_main(
            cast(str, args.route),
            cast(Path, args.out),
            cast(Subset, args.subset),
            cast(DraftMode | None, args.mode),
        )
    if args.agent == DRAFTER:  # SPEC-035 (TASK-072): its own runner
        return draft_main(
            cast(Tier | None, args.tier), cast(str, args.route), cast(Path, args.out)
        )
    if args.agent == ASSESSOR:  # SPEC-037 Q4 (TASK-085): its own runner
        return assess_main(
            cast(Tier | None, args.tier), cast(str, args.route), cast(Path, args.out)
        )
    if args.agent == MATCHER:  # SPEC-033 (TASK-065): its own runner
        return match_main(
            cast(Tier | None, args.tier),
            cast(str, args.route),
            cast(Path, args.out),
            cast(str, args.section),
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


def review_main(tier: Tier | None, route: str, out: Path, subset: Subset = "full") -> int:
    """The upload reviewer's suite, on a throwaway stack (TASK-058 D4). P-06-T21: `--route fake`
    answers from the recorded answers (`upload_review.fake_answers`), never a model."""
    guard()
    if route != "fake":
        guard_real(cast(EvalRoute, route))
    chosen: Tier = tier or spec(REVIEWER).tier
    suite = load_suite()
    validate(suite)
    answers = fake_answers() if route == "fake" else {}
    results: list[dict[str, object]] = []

    async def record(stack: Stack) -> None:
        world = await prepare(stack)
        if route == "fake":
            with fake_reviewer(answers):
                results.append(await evaluate(stack, world, suite, chosen, route, out, subset))
        else:
            results.append(await evaluate(stack, world, suite, chosen, route, out, subset))

    run_with_stack(record)
    return 0 if results and results[0]["status"] == "passed" else 1


def assess_main(tier: Tier | None, route: str, out: Path) -> int:
    """The entry assessor's suite, on a throwaway stack; real routes only (no fake answers)."""
    if route == "fake":
        print("the entry assessor has no fake answers: run it with --route direct")
        return 2
    guard()
    guard_real(cast(EvalRoute, route))
    chosen: Tier = tier or spec(ASSESSOR).tier
    suite = entry_assessment.load_suite()
    entry_assessment.validate(suite)
    results: list[dict[str, object]] = []

    async def record(stack: Stack) -> None:
        world = await prepare(stack)
        results.append(await entry_assessment.evaluate(stack, world, suite, chosen, route, out))

    run_with_stack(record)
    return 0 if results and results[0]["status"] == "passed" else 1


def match_main(tier: Tier | None, route: str, out: Path, section: str = "audit") -> int:
    """The matcher's suite, on a throwaway stack. The audit section runs on real routes only; the
    intake section (N-01-T21) also runs on `--route fake` from its recorded matcher answers."""
    if route == "fake" and section != "intake":
        print("the matcher's audit section has no fake answers: run it with --route direct")
        return 2
    guard()
    if route != "fake":
        guard_real(cast(EvalRoute, route))
    chosen: Tier = tier or spec(MATCHER).tier
    suite = matching.load_suite()
    matching.validate(suite)
    results: list[dict[str, object]] = []

    async def record(stack: Stack) -> None:
        world = await prepare(stack)
        results.append(await matching.evaluate(stack, world, suite, chosen, route, out, section))

    run_with_stack(record)
    return 0 if results and results[0]["status"] == "passed" else 1


def draft_main(tier: Tier | None, route: str, out: Path) -> int:
    """The guidance drafter's suite, on a throwaway stack; real routes only (no fake answers)."""
    if route == "fake":
        print("the guidance drafter has no fake answers: run it with --route direct")
        return 2
    guard()
    guard_real(cast(EvalRoute, route))
    chosen: Tier = tier or spec(DRAFTER).tier
    suite = guidance_drafting.load_suite()
    guidance_drafting.validate(suite)
    results: list[dict[str, object]] = []

    async def record(stack: Stack) -> None:
        world = await prepare(stack)
        results.append(await guidance_drafting.evaluate(stack, world, suite, chosen, route, out))

    run_with_stack(record)
    return 0 if results and results[0]["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
