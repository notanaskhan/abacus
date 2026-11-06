---
id: TASK-5300
title: A-04-T18 the risk drawer reads the awaiting significant_risk card
spec: SPEC-000  # row
acceptance_criteria: [AC-1]  # Remind through C3 and the routed and approve facts on the live read
risk_zone: amber
status: in-review
epic: A-04
plan_key: A-04-T18
branch: s25-a04-t18-remind
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-06
updated: 2026-11-06
---

## Objective
A-04-T18's "Remind through C3". The notify route exists; the risk drawer never said which card to
remind, who it waits for, or who may act, so the live page could not offer it.

## Plan (amber)
- `assurance/risks.py` `drawer`: the awaiting `significant_risk` card over a proposed row, the
  reserved person's name and `routed_at`, and `decision.decide` or `decision.notify`.
- `planning_contract.py`: `RiskDrawerOut.pending_card_id` (additive); client regenerated.
- Test: `test_ac4_3_the_drawer_reads_who_the_card_is_routed_to_and_who_may_remind`.
- Rollback: revert. No migration, no flag.

## Progress log
- 2026-11-06: built. Integration at the batch's test pass.

## Decisions made during this task
DEC-2420.
