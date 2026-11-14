---
id: TASK-7955
title: "I-02-T22: rollout and close-out (code part: §7216 subjects on the briefing call, RB-83 budgets and runbook)"
plan_key: I-02-T22
spec: SPEC-654 (I-02 §7)
acceptance_criteria: [AC]  # flag on only for synthetic tenants; runbook drill logged; ledger and log carry actuals
risk_zone: red
status: in-review
branch: i02-t22-today-rollout
worktree: /Users/ayushkbhatia/Accrued/abacus-s43
created: 2026-11-14
updated: 2026-11-14
---

## Plan (red)
- `agents/briefing/today.py`: `tri_subjects`; `_call` names the collected TRI subjects
  (DEC-4945; the S42 security review's Low item).
- `docs/runbooks/RB-83-today-brief.md` and the README index row; `docs/contracts/today.md` marked
  live (I-02-T14) stays the contract of record.
- Tests: `backend/tests/unit/briefing/test_i02t22_subjects.py`.

## Partial
- The staging steps (flag on for Brightwater Hale and the canary, the J13/J23 step 1 walk, the
  p95 readings, the runbook drill) are the S43 close's on staging; they are logged there. The flag
  stays synthetic-only (DEC-1391).

## Progress log
- 2026-11-14: code part built; tests written, not run (S43 end pass).
