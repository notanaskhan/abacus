---
id: TASK-7908
title: T-05-T56 Independent AC tests for the entity amber services part 1
plan_key: T-05-T56
spec: SPEC-651
acceptance_criteria: [AC-F2, AC-F4, AC-F5]  # INV-1 and INV-3 on every route; RLS, insert-only, provenance, versions, preparer-only, L3, preview
risk_zone: amber
status: in-review
branch: t05-t56-independent
worktree: /Users/ayushkbhatia/Accrued/abacus-s42
created: 2026-11-13
updated: 2026-11-13
---

## Objective
ADR-078 suite for T-05-T17, T20, T27, T33, T34, T35 and T41, written from the spec and the rows'
acceptance: forced RLS and insert-only versions, human-only L3 allocation approval, preview never
persists, record_value provenance, 409 expected_version, preparer-only edits, INV-1 and INV-3 on
every workbook route.

## Plan
- Test: `backend/tests/unit/tax/test_t05t56_independent.py` (no production code).

## Partial
- Solo build: written in this session, not "N's session" (AMENDMENT-solo).
- The database-level guards (forced RLS, triggers, the approval CHECK) are asserted on the
  migrations' own constants and text; the live-database proofs stay in the integration suites
  (`test_s37_migrations.py`).
- T-05-T33/T34 read models are covered through INV-3 (every route reads through the wall).

## Progress log
- 2026-11-13: written, not run (S42 end pass).
