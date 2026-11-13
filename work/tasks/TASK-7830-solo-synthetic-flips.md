---
id: TASK-7830
title: "Q-04-T107: the solo builder approves their own flips on the synthetic firm; finish the walk"
spec: SPEC-403  # AC-8 (flip guard)
acceptance_criteria: [AC-8]
risk_zone: red  # loosens a release control (synthetic firms only)
status: in-review
branch: q04-t107-solo-synthetic-flips
worktree: /Users/ayushkbhatia/Accrued/abacus-lo39-rec
created: 2026-11-13
updated: 2026-11-13
plan_key: Q-04-T107
---

## Objective
Let the rollback and flip runbooks be walked by one builder on PF-X1 without weakening the
two-person rule for real pilot firms (DEC-4822).

## Plan
- `backend/src/abacus_tools/flip_guard.py`: `approver_is_operator` only for a non-synthetic firm;
  a synthetic self-approval adds the audit reference `self_approved: 1`.
- `deploy/windows.yaml`: the PF-X1 comment says so.
- `backend/tests/unit/tools/test_q04t004_flip_guard.py`: a synthetic firm accepts a self-approval
  and records it, still needs an approver and a rollback; a real firm refuses in and out of window.
- Walk RB-33 §2.3/§4.2, review-approvals-flip §3/§5 and RB-01's flag flips on PF-X1 (local stack);
  record in `docs/ops/rehearsals/2026-11-13-runbook-walk.md`.
- Rollback: revert the commit; the guard refuses self-approval again everywhere.

## Progress log
- 2026-11-13: Ayush chose "synthetic firms only". Guard, test and DEC-4822 written; 19 guard tests
  pass, ruff and pyright clean.
- 2026-11-13: walk on PF-X1 (offset-90 stack): RB-33, review-approvals-flip, RB-01 flips passed, 8
  `self_approved` events; control refused. Fixed the runbooks' ROLLBACK values and `make flag` /
  `make entitlement` writing to the default stack (one stray write into the S35 stack, rows
  removed). Mistake made once: ran `make flag` assuming it honoured ABACUS_PORT_OFFSET. Open: the
  RB-37 onboarding walk.

## Decisions made during this task
- DEC-4822.
