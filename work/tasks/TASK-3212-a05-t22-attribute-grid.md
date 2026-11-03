---
id: TASK-3212
title: A-05-T22 shared attribute-test grid engine
spec: SPEC-640
acceptance_criteria: [AC-20]
risk_zone: amber
status: in-review
epic: A-05
plan_key: A-05-T22
branch: s26-a05-t22 (stacked on s26-a05-t24)
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-03
updated: 2026-11-03
---

## Objective
"The seed yields exactly two exceptions (rows 8 and 15) and one Needs human (row 22), and an agent
can never set pass, exception or no effect."

## Plan (amber)
- `workpapers/attribute_grid.py` (shared; A-08 reuses it):
  - `create_test` from an **approved** sample version;
  - `grid` (newest `seq` per cell; row state; counts);
  - `record_agent_result` (`agent_tested` or `needs_human` only);
  - `mark` (a person's pass, exception or no effect; sealed note required for exception and no
    effect; new test version and content hash; `attribute_test.version_created`);
  - `exception_prefill` for SHL-15;
  - the `attribute_test` reviewable and its facts, so adoption is C3's L1/L2 sign-off.
- `review.stale`: `attribute_test.version_created` makes sign-offs on the test stale.
- `sampling.api.approved_items`: items get a stable id from uuid5(version, position), since
  sample items have no id column.
- `assurance/ebp_tests.py`: the variants, the attribute sets and the paper choice. Routes:
  `POST /tests` and `PUT …/results/{attribute}` are live; `GET /tests/{test_id}` is new.
- Test: `tests/unit/workpapers/test_a05t22_attribute_grid.py`.

## Progress log
- 2026-11-03: built. Partial: EBP-03's census-vs-HR dual-source matrix, the eligibility matrix
  and the computation trace render from the agent's `value`/`trace` on each cell (A-05-T21's
  `ebp_attribute` mode writes them). A dedicated matrix read is left for the EBP-03 screen row
  (A-05-T23). Tests at the S26 end review.

## Decisions made during this task
DEC-2212.
