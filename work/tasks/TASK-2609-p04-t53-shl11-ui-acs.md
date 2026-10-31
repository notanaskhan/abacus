---
id: TASK-2609
title: P-04-T53 independent AC tests for the SHL-11 UI
spec: SPEC-000
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5]
risk_zone: amber
status: in-review
epic: P-04
plan_key: P-04-T53
branch: s21-p04-t53
worktree: /Users/ayushkbhatia/Accrued/abacus-s21
created: 2026-10-31
updated: 2026-10-31
---

## Objective
ADR-078's independent suite for P-04-T50 and T52: "Tests written in notanaskhan's session pass
and fail if any persona other than the reserved person can select an option."

- **[AC-1]** Reserved-person radios only (and the inline card lets no one choose).
- **[AC-2]** Rationale required (blank or whitespace is none; no option, no Decide).
- **[AC-3]** Decided read-only with name and time.
- **[AC-4]** Superseded struck.
- **[AC-5]** Agent wording never as the decider.

## Scope
**In**: `apps/web/src/screens/SHL-11/__ac__/shl11.ac.test.tsx` (stacked on P-04-T52 #909 for the
inline card). **Out**: Tier C pixels (P-04-T58).

## Plan
1. [x] The card as C3 serves it to each persona: `decision.decide` in `allowed_actions` only for
   the reserved person (Margaret Okonkwo). Seven other seeded people get frame a with no
   selectable radio, no Decide, no rationale; Margaret with the action can select; Margaret
   without the action cannot (the screen never infers the right from who is signed in).
2. [x] Rationale, decided, superseded and wording checks on frames a to h and the inline card.
Rollback: revert the PR.

## Progress log
- `2026-10-31` — 25 tests, all passing on first green run (one harness fix: an overriding fixture
  handler needs a JSON content type). No defect found.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| — | none | No |
