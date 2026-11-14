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
from abacus_tools.evals.notices_responder import AGENT as RESPONDER
from abacus_tools.evals.notices_responder import responder_main
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
    if args.agent == "audit_completion":  # A-07-T40: A-07's deterministic conformance suite
        from abacus_tools.evals.audit_completion import main as completion_main

        return completion_main(cast(Path, args.out))
    if args.agent == "agent_trajectories":  # P-10-T34: runtime v2's trajectory graders
        from abacus_tools.evals.trajectory import main as trajectory_main

        subset = "fast" if args.subset == "fast" else "full"
        return trajectory_main(cast(Path, args.out), subset)
    if args.agent == "briefing_today":  # I-02-T09: briefing.today's graders (fake model)
        from abacus_tools.evals.briefing_today import main as briefing_main

        if args.route != "fake":  # I-02-T20: the evaluation account's direct and Bedrock runs
            from abacus_tools.evals.briefing_today_real import real_main as briefing_real

            return briefing_real(
                cast(str, args.route),
                cast(Path, args.out),
                "fast" if args.subset == "fast" else "full",
            )
        return briefing_main(cast(Path, args.out), "fast" if args.subset == "fast" else "full")
    if args.agent == "workbench_assistant":  # W-02-T07: workbench.assistant's turn graders
        from abacus_tools.evals.workbench_assistant import main as workbench_main

        if args.route != "fake":
            print("workbench_assistant: real routes arrive with W-02-T12 and W-02-T25")
            return 2
        subset = "fast" if args.subset == "fast" else "full"
        return workbench_main(cast(Path, args.out), subset)
    if args.agent == "runtime_conformance" and args.route != "fake":  # P-10-T46: real routes
        from abacus_tools.evals.runtime_conformance_real import real_main as conformance_real

        return conformance_real(
            cast(str, args.route),
            cast(Path, args.out),
            "fast" if args.subset == "fast" else "full",
        )
    if args.agent == "runtime_conformance":  # P-10-T41: runtime.conformance's suite (code only)
        from abacus_tools.evals.runtime_conformance import main as conformance_main

        return conformance_main(cast(Path, args.out), "fast" if args.subset == "fast" else "full")
    if args.agent == "tax_return" and args.route != "fake":  # T-04-T43: real routes
        from abacus_tools.evals.tax_return_real import real_main as tax_real

        return tax_real(
            cast(str, args.route),
            cast(Path, args.out),
            "fast" if args.subset == "fast" else "full",
        )
    if args.agent == "tax_return":  # T-04-T18: the tax agents' suite, frozen thresholds
        from abacus_tools.evals.tax_return import main as tax_main

        return tax_main(cast(Path, args.out), "fast" if args.subset == "fast" else "full")
    if args.agent == "workbook_fix":  # T-05-T50 rest (DEC-4927), frozen
        from abacus_tools.evals.workbook_fix import main as workbook_fix_main

        return workbook_fix_main(cast(Path, args.out), "fast" if args.subset == "fast" else "full")
    if args.agent in (
        "tax_account_mapper", "tax_agreement_reader", "tax_memo_drafter", "tax_recommender_modes"
    ) and args.route != "fake":  # T-05-T64: the evaluation account's clearance runs
        from abacus_tools.evals.tax_entity_real import real_main as entity_real

        return entity_real(
            args.agent,
            cast(str, args.route),
            cast(Path, args.out),
            "fast" if args.subset == "fast" else "full",
        )
    if args.agent in ("tax_memo_drafter", "tax_recommender_modes"):  # T-05-T30, frozen
        from abacus_tools.evals.tax_entity_part2 import main as part2_main

        return part2_main(
            args.agent,
            cast(Path, args.out),
            "fast" if args.subset == "fast" else "full",
        )
    if args.agent in ("tax_account_mapper", "tax_agreement_reader"):  # T-05-T18, frozen
        from abacus_tools.evals.tax_entity import main as entity_main

        return entity_main(
            args.agent,
            cast(Path, args.out),
            "fast" if args.subset == "fast" else "full",
        )
    if args.agent == "agent_blocks":  # P-09-T15: the deterministic AgentBlocks conformance suite
        from abacus_tools.evals.agent_blocks import main as blocks_main

        return blocks_main(cast(Path, args.out))
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
    if args.agent == RESPONDER:  # N-04-T18: code-graded, no stack (DEC-2312)
        return responder_main(
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
