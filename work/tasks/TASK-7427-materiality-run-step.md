---
id: TASK-7427
title: "Engagement run: the materiality step holds on the card a person's proposal raised (DEC-4417; follows DEC-4416)"
spec: SPEC-647
acceptance_criteria: [AC-W4]
risk_zone: red
status: done
branch: s38-materiality-step
worktree: /Users/ayushkbhatia/Accrued/abacus-s38
created: 2026-11-12
updated: 2026-11-12
plan_key: P-10-T39
---

## Objective
P-10-T39's "holds Planning on the materiality card" and AC-W4 with the matrix intact: the agent
never proposes materiality (`materiality.propose` is `agent: deny`).

## Plan (red)
- `agents/run_waits.py`: a decision-source slot (`register_decision_source`, `HeldCard`): for a
  kind with a source, the decision step holds on the owner's awaiting card, succeeds when a
  decision is in force, fails closed with the owner's code otherwise. Audited
  `agent_run.decision_held`. `run_activities` finishes a step the source reports decided.
- `assurance/materiality.py`: `held_card` for `planning_materiality`, registered at import.
- Rollback: revert; the step falls back to DEC-4416's fail-closed path.

## Built
- The slot, the source, `tests/unit/agents/test_dec4417_decision_source.py` (8 pass).
- J23 step 1 (`test_runtime_v2_journey.py`): before a proposal the step fails closed
  (`materiality_not_proposed`); after Marcus raises the card through review with assurance's
  computed options, the run holds on it (`blocked_on_decision`), reserved to the engagement
  partner. The strict xfail is removed. 4 journeys pass.

## Open
- C3 decision cards are not a C13 gate source, so Home's decisions band does not count the held
  card (the journey asserts the card's role instead).

## Progress log
- 2026-11-12: built and tested.
