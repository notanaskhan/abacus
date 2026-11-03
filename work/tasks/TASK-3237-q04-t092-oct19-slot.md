---
id: TASK-3237
title: Q-04-T092 Tuesday slot Oct 19 rehearsed on PF-X1; window close and the Oct 21 train
spec: SPEC-000  # row
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: Q-04
plan_key: Q-04-T092
branch: s26b-q04-t092
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-03
updated: 2026-11-03
---

# TASK-3237 · Q-04-T092 · Oct 19 slot, window close, Oct 21 train

## Done
`docs/ops/windows/2027-10-19-tuesday-slot.md`: the real gate run on PF-X1 (synthetic, DEC-2081) at the Oct 19 slot, the last minute of the window (Oct 20) and the first Thursday train (Oct 21); the `ledger.tb_mapping` flip recorded as synthetic; `deploy/windows.yaml` ends `autumn-2027` on Oct 20, so nothing needs retiring.

## Not done (needs a live firm)
The flip on a real tenant with its approvals, and the Oct 21 production promotion.

## Progress log
- 2026-11-03: rehearsed with `abacus_tools.window_rehearsal`.
