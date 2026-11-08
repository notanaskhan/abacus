---
id: TASK-6220
title: P-09-T02 C6 v1.1 consumer contract tests
spec: SPEC-648
acceptance_criteria: [AC-1]  # green in the provider's CI; fails when a field the dock or drawer reads is removed
risk_zone: red
status: in-review
epic: P-09
plan_key: P-09-T02
branch: s31-p09-t02
worktree: /Users/ayushkbhatia/Accrued/abacus-s31
created: 2026-11-08
updated: 2026-11-08
---

## Plan (red: written before building)
- `backend/tests/contracts/c06_agent_runs/test_p09t02_c6_v11_consumers.py`: one case per field
  SHL-13 and WB-09 read (and C6 v1.1's additions for them) against the OpenAPI document; every
  route they call exists; the feed takes `after_seq`; the step route authorises before its flag.
  It runs in the backend contracts job (the provider's CI).
- `apps/web/src/fixtures/c6-v11.contract.test.ts`: every E0 fixture run carries each field the
  dock and drawer read; the trace summary foots its own records read.
- No code change. Rollback: delete the two files.

## Progress log
- 2026-11-08: written; runs at the S31 end pass.
