---
id: TASK-7927
title: W-02-T14 rest: the Paperclip chip's context count
plan_key: W-02-T14
spec: SPEC-653
acceptance_criteria: [AC-L1]
risk_zone: green
status: in-review
branch: w02-t14-context-count
worktree: /Users/ayushkbhatia/Accrued/abacus-s42
created: 2026-11-13
updated: 2026-11-13
---

## Objective
Finish W-02-T14's partial: WB-01's Paperclip chip names the selected session's attached context count.

## Done
- `Row.context_count` from `context_refs` (already in the candidate read: no new query); `SessionSummaryOut.context_count` (Internal, ge 0), null on a locked row (DEC-87) and on the TAX-08 subject list.
- Contract doc and generated client updated; WB-01 passes it to `ChatHeader` (`Context: n items`).
- Test: two attached refs count 2; a locked row's count is withheld.

## Partial
- The fixture rows carry no count (the handoff names none per row); the chip reads 0 on fixtures.

## Progress log
- 2026-11-13: built in the S42 partials round; tests written, run at the partials end pass.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
