---
id: TASK-8946
title: "Q-05-T25: Independent AC tests for records governance"
spec: SPEC-711
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s53-q05t25
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: Q-05-T25
---

## Objective
Independent AC tests (ADR-078) for records governance: I-HOLD across execution, I-SEGREGATION, typed phrase, shrink-only batches, shared-object protection, unexpired retain-until refused, 410 after destruction, derived stores purged, certificate byte-identical, below-floor policy refused.

## Done
- tests/integration/backfill/test_q05t25_records_governance_ac.py (4): below-floor 422; policy needs admin with fresh MFA; destruction approval refused to a manager, other firm 404; client never reads batches/documents/certificates

## Progress log
- `2026-11-23` — 2026-11-23: HTTP edge suite; workflow-level ACs (I-HOLD mid-batch, segregation, shrink-only, shared objects, retain-until, 410, purge, certificate bytes) held by Q-05-T11-T15 suites and listed for the end-pass security review. Integration in the end pass.
