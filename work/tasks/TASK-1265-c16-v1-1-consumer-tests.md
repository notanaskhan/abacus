---
id: TASK-1265
title: C16 v1.1 consumer contract tests on behalf of R-01, P-06, N-02, A-02, A-08 and R-02 (R-01-T17)
spec: SPEC-345
acceptance_criteria: [AC-6, AC-7]
risk_zone: amber
status: in-review
epic: R-01
plan_key: R-01-T17
branch: s9a-contract-stubs
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"The suite runs in N's CI against the stub and fails if any variable can resolve to an amount,
an account number or a TIN" (R-01-T17).

## Plan (amber: tests only)
- `backend/tests/contracts/c16_notifications/test_c16_v1_1_consumers.py`: per consumer, the
  template keys it sends and the whitelisted variables it needs; no variable's sensitivity class
  is an amount, account number or TIN, and none is Restricted; the refusal reasons; the lint
  finding shape (identifier-only facts); the settings draft and publish shapes; the read-only
  preview shape (no mutation link, no session).
- No production code. Rollback: revert.

## Progress log
- 2026-10-26: built. `test_c16_v1_1_consumers.py` (consumers R-01, P-06, N-02, A-02, A-08,
  R-02): keys register through the slot with whitelisted variables; the kind list, every
  variable's kind, class and name exclude amounts, account numbers and TINs, and the editor's
  OpenAPI enum matches the closed list; refusal reasons; lint findings carry code, block and
  variable only; ADM-10 b's five-day draft; the fixed accent and host; the read-only preview.
- 2026-10-26 (security review, DEC-379): fix round on the same branch; see DEC-379 for this task's part (H1 preview scoping, M1 send_templated signature, M2 value lint, M3 connection.disconnect, M4 section requester, L1 test-send conditions, L4 support contact).
