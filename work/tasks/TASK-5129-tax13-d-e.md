---
id: TASK-5129
title: T-03-T16 TAX-13 d and e: Extend sheet, Mark filed dialog, ack pills, TAX-01 bulk Extend
spec: SPEC-000  # row (T-03-T16)
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: T-03
plan_key: T-03-T16
branch: s29-t03-t16
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-06
updated: 2026-11-06
---

## Objective
TAX-13 d and e per the handoff: the Extend sheet with per-row figures, editable payment and check line, approve and send as the reviewer or Submit for approval otherwise, TAX-01's bulk Extend entry, the Mark filed dialog, and Filed, Accepted, Rejected pills with the reject code.

## Plan
ExtendSheet.tsx, MarkFiledDialog.tsx. Extensions gains selection, `?ov=` overlays, ack cells. GET /tax/extensions gains `return_id`; JurisdictionLineOut gains `row_version`. Fixtures d, e, not-allowed.

## Progress log
- 2026-11-06: built. TAX-13.test.tsx d, e, not-allowed and Mark filed written; TAX-01 tests updated for Extend live; held for the end pass.

## Decisions made during this task
DEC-2425
