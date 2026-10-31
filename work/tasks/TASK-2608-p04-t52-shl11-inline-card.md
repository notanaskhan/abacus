---
id: TASK-2608
title: P-04-T52 SHL-11 e inline dock card, chat variant and HOME-02 ?ov= deep links
spec: SPEC-000
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: P-04
plan_key: P-04-T52
branch: s21-p04-t52
worktree: /Users/ayushkbhatia/Accrued/abacus-s21
created: 2026-10-31
updated: 2026-10-31
---

## Objective
- **[AC-1]** "The inline card specimen matches SHL-11e and Open decision opens the sheet on the
  same card."

## Scope
**In**: `screens/SHL-11/InlineCard.tsx` (`DecisionInlineCard`, `dock` 330 px and `chat` for
P-09), scenario e, `ov.SHL11` and `ov.SHL12` typed overlay builders, HOME-02's decision and
sign-off rows opening their sheets as `?ov=` layers (`openOverlayOf`), tests.
**Out**: mounting the card in SHL-13's dock and the P-09 thread (their epics: SHL-13 is planned,
the run thread is C-12/P-09); TPL-02's specimen keeps the packages/ui DecisionCard drawing.

## Plan
1. [x] Card over the C3 read (`useDecisionCard`): "?" chip and question, compact read-only option
   rows, the agent's "Recommended" tag (sparkle, screen-reader "by Accrued Agent"), a decided card
   shows its option and "Decided", footer "Open decision" primary opening `?ov=decision:<id>`.
2. [x] Scenario e (seed board "Inline dock variant", Margaret Okonkwo) added to STATES.
3. [x] HOME-02: `overlayOf` ahead of `hrefOf`; the owner's `overlay` code wins, else the kind.
4. [x] Tests: InlineCard.test.tsx (4), hosts.test.ts (4), SHL-11 states. Rollback: revert.

## Progress log
- `2026-10-31` — Built; SHL-11 and HOME-02 suites 23 passed; eslint and tsc clean on the files.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-1658 | SHL-11e's tag reads "Recommended" (screenshot) with "by Accrued Agent" for screen readers; HOME-02 rows open sheets as layers | No |
