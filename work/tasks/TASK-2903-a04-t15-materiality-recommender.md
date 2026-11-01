---
id: TASK-2903
title: A-04-T15 decisions.recommender for materiality (AUD-07)
spec: SPEC-620
acceptance_criteria: [A-04 §6.1, AC3.4]
risk_zone: red
status: in-review
epic: A-04
plan_key: A-04-T15
branch: s24-a04-t15 (stacked on s24-a04-t12)
worktree: /Users/ayushkbhatia/Accrued/abacus-s24
created: 2026-11-01
updated: 2026-11-01
---

## Objective

A-04 §6.1: the materiality recommender — one gateway call over code-computed facts whose accepted answer tags one option on the partner's `planning_materiality` card.

## Acceptance (backlog)

On the fake model the Northwind card shows Recommended by Accrued Agent on 1.5% with reasons, the agent principal's decide returns 403, and evals/decision_recommendation passes every threshold.

## Plan

- Spec `agents/specs/decisions.recommender.yaml` v1 (single call, medium, interactive, $0.01, task scope `materiality.read`, `decision_card.raise`, `suggestion.create`, `decision_recommend.run`, suite `evals/decision_recommendation`, `client_data: none`); `_specs.py`, `_eval_suites.py`, the permission matrix regenerated; `decision_recommend.run` in `agents.yaml`.
- Prompt `decisions.recommend@v1`; output schema `Recommendation` (key, 1-3 reasons with fact references); input type `DecisionRecommendInput`.
- `agents/decision_recommend.py`: run row on behalf of the proposer, the agent context from it, facts as the task, factors untrusted, one call, code check (key in the option set and in range, references are facts, numbers are facts, no claimed partner act), the agent's suggestion on target `materiality` (the work item), then the agent raises the card with its tag; refused answers end the run escalated with the reason and the card is raised untagged. Fake responder reads the task.
- `assurance/materiality.propose(recommend=True)`: 409 `drafting_not_enabled` without `workpapers.drafting`; the recommender raises the card; options carry `recommended`.
- `assurance.api` registers suggestion target `materiality`.
- Tests: `tests/integration/backfill/test_a04t15_materiality_recommender.py`.

## Decisions

DEC-1953.

## Progress log

- 2026-11-01: built in abacus-s24, stacked on A-04-T12. Pyright clean on the touched files; tests written, not run. The `Generator` and typed-dict fixes to `materiality.py`/`planning_contract.py` belong to T12 and go back to it in the end pass.
