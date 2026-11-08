---
id: TASK-6225
title: A-05-T58 close, EBP-07's 4i schedule, Part IV's 13 lines and keyed values
spec: SPEC-640
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-05
plan_key: A-05-T58
branch: s31c-a05-t58
worktree: /Users/ayushkbhatia/Accrued/abacus-s31
created: 2026-11-08
updated: 2026-11-08
---

## Plan (amber)
- Migration 0742 on 0741: `ebp_form5500_lines.keyed_by` and `keyed_note_sealed`, set together, with the UPDATE grant. Expand-only; the downgrade drops both.
- `ebp_form5500.schedule_4i_facts`, `schedule_4i_view` and `key_line_value`.
- Contract (additive):
  - Part IV lists 4a to 4m, with `not_checked`;
  - `GET /ebp/form-5500/schedules/4i`;
  - the keyed route is live.
- Completion fact `schedules`.
- EBP-07: all 13 Part IV lines; the Schedules tab reads the 4i route.
- Tests:
  - `test_a05t58_close.py`;
  - `test_a05t58_form5500_read.py`: the old five-line assertion becomes the 13-line one;
  - `EBP-07.test.tsx`.

## Left
- The 4i description column, the C11 render, and the note and remind writes (DV-EBP-07-3 and 4).

## Progress log
- 2026-11-08: built; runs at the close end pass.
