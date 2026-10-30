---
id: TASK-2319
title: T-01-T21 independent §7216 AC tests
spec: SPEC-501
acceptance_criteria: []
risk_zone: red
status: in-review
epic: T-01
plan_key: T-01-T21
branch: s18-t01-t21
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Independent AC tests (ADR-078) for T-01-T08, T-01-T11 and T-01-T12: the I-7216 property over every
in-force dimension, revocation on the next request, expiry on the clock, register drift, the
planted `tri` spec refusal, and the shared eval case pack.

## Plan
- `backend/tests/security/test_t01t21_consent_7216_independent.py` (Postgres, security conftest).
- `evals/_shared/consent_7216/cases.yaml`.
- DEC-1365. Rollback: revert.

## Progress log
- `2026-10-30` — written (DEC-1365). The two non-database tests run once (pass); the Postgres
  cases run in the S18 end review. `[skip ci]`.

## Handoff
- **Current state:** written, PR open, held for the S18 batch.
- **Exact next step:** T-01-T23 scenario slice.
