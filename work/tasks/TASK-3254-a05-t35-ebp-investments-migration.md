---
id: TASK-3254
title: A-05-T35 migration 0665 EBP investments and Form 5500 (A-05 M6)
spec: SPEC-000  # row (SPEC-640 AC-35)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: A-05
plan_key: A-05-T35
branch: s27-a05-t35
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
"Upgrade and downgrade pass on the seed, and an agent cannot write a certification evaluation."

## Plan (red)
- Migration 0665 on 0664 (expand-only), A-05 §4.2 M6: `ebp_trust_report_lines` (cited,
  superseded not overwritten), `ebp_certification_points`, insert-only
  `ebp_certification_evaluations` (human, transaction-bound actor; trigger),
  `ebp_form5500_drafts` (one current per plan year), `ebp_form5500_lines` (code's tie; a
  reconciling item needs its note), `ebp_part_iv_answers` (4a–4m; inconsistent needs an issue),
  `ebp_supplemental_schedules` (4i, 4a), insert-only firm content `ebp_schedule_h_mappings`
  (versioned by plan year, published by a person).
- Registry `EBP_INVESTMENT_TABLES`, INSERT_ONLY, column grants; `IMMUTABLE_TABLES`; the tenant
  list.
- Tests: `tests/integration/test_a05t35_ebp_investments_migration.py`.
- Rollback: the downgrade drops the eight tables and the trigger function.

## Progress log
- 2026-11-04: built. Tests at the S27 end review.

## Decisions made during this task
DEC-2234.
