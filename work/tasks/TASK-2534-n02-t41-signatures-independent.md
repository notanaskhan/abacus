---
id: TASK-2534
title: N-02-T41 independent AC tests for N-02-T27, N-02-T28 and N-02-T38
spec: SPEC-381  # N-02 §3.3, §3.7, §3.13; C7 v1.1
acceptance_criteria: [AC-13, AC-14, AC-15]
risk_zone: red
status: in-review
epic: N-02
plan_key: N-02-T41
branch: s20d-n02-t41
worktree: /Users/ayushkbhatia/Accrued/abacus-s20b
created: 2026-11-01
updated: 2026-11-01
---

## Objective
Independent AC tests (ADR-078) for T27, T28 and T38: three failures route to verification_failed
with no retry and no SMS, a hand-signed upload needs an attestation, taxpayer before ERO order,
countersign only by the named firm signer, remind cap and human-only, packages carry the five IRS
items and verify by hash, retention never shortened (I-RETENTION-FLOOR), superseded envelopes
keep the gate unmet.

Acceptance (backlog row): "The suite passes and fails on a fourth remote attempt or a shortened
retain-until."

## Plan (red: tests only)
- `tests/integration/backfill/test_n02t41_signatures_independent.py` on N-02-T14's 8879 and
  N-02-T27's fixtures: the fourth attempt, SMS, attestation, paper order, reminders, the five
  items by hash, retention at the service and the database, the superseded gate.
- `tests/integration/test_n02t41_countersign_independent.py` on N-02-T28's letter harness.
- Rollback: delete the two files.

## Progress log
- `2026-11-01` — Written on `s20d-n02-t41` off main; run in the end review.
