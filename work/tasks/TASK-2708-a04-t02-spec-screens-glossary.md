---
id: TASK-2708
title: A-04-T02 SPEC-620, screen contracts AUD-04/05/07/08/09/10, glossary
spec: SPEC-620
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: A-04
plan_key: A-04-T02
branch: s22-a04-t02
worktree: /Users/ayushkbhatia/Accrued/abacus-s22
created: 2026-10-31
updated: 2026-10-31
---

## Objective
- **[AC-1]** "The SPEC and glossary record the Contract Monday answers to OQ-1, OQ-3, OQ-4, OQ-7,
  OQ-13 and OQ-15, and each screen contract lists every post-revision artboard with its persona,
  clock and tier."

## Scope
**In**: SPEC-620 (supersedes SPEC-008's materiality/risk non-goal); six screen contracts; eleven
glossary rows; DEC-1758.
**Out**: code; the fixture scenarios (each screen's FE task).

## Plan
Docs only, stacked on A-04-T01 (the contracts the screens cite). Rollback: revert.

## Progress log
- `2026-10-31` — written from A-04 §2–§5, §11 and the six handoff READMEs/specs (AUD-07 and AUD-08
  revisions win). No tests (docs); `make check-fast` doc gates run at the S22 end review.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-1758 | Contract Monday answers decided with the plan's options; deviations per screen | No |
