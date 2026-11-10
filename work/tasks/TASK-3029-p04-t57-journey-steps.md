---
id: TASK-3029
title: P-04-T57 review grammar journey steps
spec: SPEC-308
acceptance_criteria: [AC-5]
risk_zone: green
status: done
epic: P-04
plan_key: P-04-T57
branch: s25-p04-t57 (stacked on s25-k01-t25)
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-02
updated: 2026-11-02
---

## Objective
"The named steps pass on staging with assertInvariants and axeStep, and every step not yet live is
an explicit test.fixme naming its epic."

## Built
- `apps/web/e2e/journeys/p04-review-steps.spec.ts`.

## Progress log
- 2026-11-02: built; runs in the end pass (fixture project). Staging waits for the review flags in
  the demo firm (`test.fixme` names it); Granite Peak (A-09) and sign/e-file (T-04) are fixme.

## Decisions made during this task
DEC-2076.
