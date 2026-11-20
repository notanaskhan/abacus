---
id: TASK-8837
title: "T-08-T13: review_checklist payload v2 with check codes"
spec: SPEC-710
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s52-t08t13
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: T-08-T13
---

## Objective
1065 Review Checklist v4 imports with 42 bound or manual items, an unknown check code is a row problem, and v1 payloads still read.

## Done
- methodology/check_codes.py slot
- ChecklistItem.check_code + two_year_threshold_pct (additive)
- validate_payload refuses unknown codes
- import route row problems check_code_unknown
- tests/unit/methodology/test_t08t13_checklist_v2.py
- DEC-5839

## Progress log
- `2026-11-20` — Plan (amber): contract additive fields, slot, validation; no migration; rollback = revert. make generate at end pass. Tests at the end pass.
