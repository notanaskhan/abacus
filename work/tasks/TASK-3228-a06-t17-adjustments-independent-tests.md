---
id: TASK-3228
title: A-06-T17 Independent AC tests for the adjustments schema and services
spec: SPEC-642
acceptance_criteria: [AC-7, AC-1]
risk_zone: amber
status: in-review
epic: A-06
plan_key: A-06-T17
branch: s26-a06-t17
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-03
updated: 2026-11-03
---

# TASK-3228 · A-06-T17 · Independent AC tests for the adjustments schema and services

**Epic:** A-06 · **Sprint:** S26 · **Type:** TEST · **Zone:** amber · **Depends on:** A-06-T10, A-06-T09, A-06-T03 · **Status:** in-review

## Built
`backend/tests/contracts/c08_adjustments/test_a06t17_independent.py` (ADR-078): no route posts or writes back (ADR-040 route table); no adjustments module string sets `posted`, `failed_post` or `reversed`; 0643 keeps `pe_posting_dormant` and the attest `review_required` CHECK; decisions are a person's own; every write denies agent and system and requires independence; the send needs `mfa_recent`; no matrix action posts; the send is held on a grant that Undo voids.

## Partial
- The database behaviours (RLS, insert-only, the deferred balance trigger) are asserted by A-06-T03's migration suite; this suite holds the code and declarations to them. Approver-of-record scope beyond the matrix and the record-mode evidence check are not separately tested yet.

## Progress log
- 2026-11-03: written; ruff and pyright clean; not run (end pass).
