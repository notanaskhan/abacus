---
id: TASK-2806
title: P-04-T56 independent AC tests for the SHL-15 and SHL-09 UI
spec: SPEC-000  # P-04-T56 row; docs/screens/SHL-15.md, SHL-09.md
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: P-04
plan_key: P-04-T56
branch: s23-p04-t56 (stacked on s23-p04-t55)
worktree: /Users/ayushkbhatia/Accrued/abacus-s23
created: 2026-11-01
updated: 2026-11-01
---

## Objective
- **[AC-1]** "Tests written pass and fail if the internal note reaches the portal request."

## Plan
`apps/web/src/screens/SHL-15/__ac__/p04t56.ac.test.tsx`: client wording never shows the internal
note (the send body, sentence by sentence; no client field prefilled from it), no propose-only
checkbox (a, e), an agent assignee cannot resolve (no control on agent elements; resolve only a
HumanAction), an edit needs a citation note (SHL-09: blank and whitespace refused, the PUT carries
it), Unsupported blocks field sign-off (SHL-09 e: disabled, no tick sent). No production code.
Rollback: revert.

## Progress log
- `2026-11-01` — written; tsc and eslint clean. Run at the S23 end review.

## Decisions made during this task
None.
