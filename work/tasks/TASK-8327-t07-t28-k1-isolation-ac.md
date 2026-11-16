---
id: TASK-8327
title: "T-07-T28: ADR-078 independent AC tests for N's T11, T13, T19 and T24 plus K-1 recipient isolation"
spec: SPEC-656
acceptance_criteria: [AC-9]
risk_zone: red
status: in-review
branch: t07-t28-k1-isolation-ac
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: T-07-T28
---

## Objective
Spec section: docs/plan/epics/T-07.md §9.
ADR-078 independent AC tests for N's T11, T13, T19 and T24 plus K-1 recipient isolation.

## Plan (red)
1. `tests/integration/test_t07t28_k1_recipient_isolation.py` (`ac-test-author: ayushkbhatia`) on T-02-T26's released harness: each recipient reads only their own package (list, detail, download), a foreign package answers exactly as an unknown one, a firm principal reads nothing through the portal route.
2. T24's release-gate truth table is `tests/unit/tax/test_t07t24_release_gate.py`.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack. Lint and pyright clean; runs at the end pass under the test lock. Deviation: the isolation suite sits in `tests/integration/` (the released harness lives there) rather than `tests/security/`. Partial: the clause verifier (T11), reader consent (T13) and CCH 1041 (T19) independent tests, the trustee's beneficiary read, and the seeded-vulnerable-build runs are not written. Gates and
  tests run once at the S47 end pass (build first, test last).
