---
id: TASK-8944
title: "C-02-T36: ADR-078 AC suite 2 on the W1 path"
spec: SPEC-700
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s53-c02t36
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: C-02-T36
---

## Objective
ADR-078 AC suite 2 on the W1 path: write interception, idempotency under retry and timeout, dry run, read-back mismatch, closing-date conflict, I-POLICY-NOT-ATTEST at registry, grant and posting, kill switch, revoked grant mid-batch, grant payload-hash mismatch, client-visible write log scope, the POR-16 grant routes.

## Done
- tests/integration/backfill/test_c02t36_w1_ac.py (5): write grant is the client's (firm principal refused; unknown connection 404); posting log never a client's; other firm's batch 404; staff cannot undo or retry; kill switch closes the posting routes

## Progress log
- `2026-11-23` — 2026-11-23: HTTP edge suite written from SPEC-700 and the matrix; provider-boundary ACs (interception, idempotency, read-back, closing-date, attest policy, revoked grant, payload hash) are held by C-02-T18/T19/T24 service suites and are listed for the end-pass security review. Integration run in the end pass.
