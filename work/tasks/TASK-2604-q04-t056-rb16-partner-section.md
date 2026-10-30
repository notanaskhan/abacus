---
id: TASK-2604
title: Q-04-T056 RB-16 partner-facing section
spec: SPEC-000
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: Q-04
plan_key: Q-04-T056
branch: s21-q04-t056
worktree: /Users/ayushkbhatia/Accrued/abacus-s21
created: 2026-10-30
updated: 2026-10-30
---

## Objective
RB-16's partner-facing section: the window and deadline-week notice text, the office-hours schedule,
the escalation path and what defect-only means for firms.

- **[AC-1]** "The partner section is approved by both founders and reused unchanged in the window
  notices."

## Scope
**In**: the Partner-facing section of `docs/runbooks/RB-16-busy-season-readiness.md`; DEC-1654.
**Out**: sending the notice (Q-04-T064); the founders' signatures (the approval table, by hand).

## Plan
Notice text with placeholders only for dates and the pilot-desk address; office hours table;
escalation path from the pilot README's service levels; defect-only in plain words. No firm, person,
price or contact. Rollback: revert the PR.

1. [x] Section. 2. [ ] Both founders sign the approval table (human). 3. [ ] End review.

## Progress log
- `2026-10-30` — Written on `s21-q04-t056` (stacked on `s21-q04-t055`). The approval half of the
  acceptance is a human step: both founders sign the table before Q-04-T064 sends the notice.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-1654 | one notice text reused unchanged; deadline-week desk hours; escalation path; defect-only words | no |

## Handoff
- **Current state:** written, PR open, held for the batch; approval table unsigned.
- **Exact next step:** both founders sign; Q-04-T064 sends the notice unchanged.
