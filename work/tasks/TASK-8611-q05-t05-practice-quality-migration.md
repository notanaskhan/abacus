---
id: TASK-8611
title: "Q-05-T05: Migration 0963 practice_quality and quality v1 route stubs"
spec: SPEC-711
acceptance_criteria: [AC-31, AC-7, AC-9, AC-33]
risk_zone: amber
status: in-review
branch: q05-t05-practice-quality-migration
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-18
updated: 2026-11-18
plan_key: Q-05-T05
---

## Objective
Spec section: docs/plan/epics/Q-05.md §4.2 NNNN_practice_quality, §4.3. The SQMS register, imports and risk reviews, selection rules, inspections with the objectivity trigger, QM findings and evaluations, links, annual evaluations and the two projections; Pydantic models and quality v1 route stubs.

## Plan (amber)
1. migrations/versions/0963_practice_quality.py on 0962: sixteen practice tables, forced RLS; five insert-only; risk reviews and finding evaluations human-only; inspections_not_ep CHECK and inspection_objectivity trigger against engagement_members (EQR included); partial unique open agent-monitoring finding per cycle and agent; projections keep DELETE for their rebuild.
2. practice/quality_contract.py: 24 routes under quality.*, inspection.*, qm_finding.* and todo.create, each 501 behind quality.management; api-client regenerated.
3. practice/registry.py and schema_check entries; quality-management.md marked stub.
4. Rollback: downgrade drops the tables and the function; the flag stays off.

## Progress log
- `2026-11-18` — Built in the S50 sequential stack (DEC-5611). Free text is sealed (bytea envelopes). Seed-derived fixtures come with Q-05-T04. Gates and tests run once at the S50 end pass (build first, test last).
