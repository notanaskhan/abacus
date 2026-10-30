---
id: TASK-2602
title: T-01-T50 CLI-05 transcripts frontend and live swap (Transcripts a)
spec: SPEC-000
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: T-01
plan_key: T-01-T50
branch: s21-t01-t50
worktree: /Users/ayushkbhatia/Accrued/abacus-s21
created: 2026-10-30
updated: 2026-10-30
---

## Objective
CLI-05 Transcripts a on T-01-T43's live routes: the register table, the comparison card with the
TallyPill, difference rows and Total difference, the agreeing-forms line, the Comparing… spinner,
the fixture-only agent note, and the rail's Transcripts row.

- **[AC-1]** "Scenario test a passes and on staging the Whitley comparison shows off 3,120 from
  code with no agent note."

## Scope
**In**: `apps/web/src/screens/CLI-05/` (index, copy, scenarios, tests), `fixtures/seed/transcripts.ts`,
`fixtures/handlers/tax-compliance.ts`, the gallery artboard a, `docs/screens/CLI-05.md`, DEC-1652.
**Out**: the upload dialog; SHL-08 and NOT-02 (planned); parity Tier C (T-01-T52); staging walk.

## Plan
Fixtures for the four pulls and the TY2024 comparison; register and card in the screen; Compare
to return as a mutation that refetches the register and the comparison; tests for a (register,
card, note present and absent, Comparing…, selection) and b updated. Migrations, flags: none.
Rollback: revert the PR.

1. [x] Fixtures. 2. [x] Screen. 3. [x] Tests (run once: 13 passed). 4. [ ] End review; staging
walk after the batch deploy.

## Progress log
- `2026-10-30` — Built on `s21-t01-t50` (stacked on `s21-t01-t43`). CLI-05 tests run once: 13
  passed; eslint and tsc clean. The "on staging" half of the acceptance waits for the batch deploy.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-1652 | agent note fixture-only by prop; Compare re-runs the last return; planned controls kept | no |

## Handoff
- **Current state:** built, PR open, held for the batch.
- **Exact next step:** end review; walk CLI-05 a on staging after deploy.
