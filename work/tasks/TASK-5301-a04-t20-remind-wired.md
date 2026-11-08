---
id: TASK-5301
title: A-04-T20 AUD-08's Remind and Approve footers wired to the pending card
spec: SPEC-000  # row
acceptance_criteria: [AC-1]  # Hannah's footer (Routed to Margaret, Remind) and the partner footer opening SHL-11
risk_zone: green
status: in-review
epic: A-04
plan_key: A-04-T20
branch: s25-a04-t20-remind
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-06
updated: 2026-11-06
---

## Objective
AUD-08's Remind button did nothing: the host passed no handler. Not significant… had no handler
either, and both partner buttons keyed off `approved_card_id`, which is set only after approval.

## Plan (green)
- `RiskDrawer.tsx`: reads `pending_card_id` and the drawer's actions; Remind calls
  `decisionCardNotifyMutation` and confirms in words; Not significant… opens the card too.
- Fixtures: `aud08Drawer` and the AUD-08 scenarios' notify handler.
- Test: `b: Remind calls C3's notify on the pending card and confirms in words`.
- Rollback: revert. Stacked on TASK-5300's generated client.

## Progress log
- 2026-11-06: built; AUD-08 tests pass.

## Decisions made during this task
DEC-2420 (TASK-5300).
