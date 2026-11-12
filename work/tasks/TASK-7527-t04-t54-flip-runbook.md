---
id: TASK-7527
title: T-04-T54 M17 tax workspace flip plan and flag renewal
plan_key: T-04-T54
spec: SPEC-649  # T-04 §0; chapter 10 M17
acceptance_criteria: [AC-1]  # the runbook is rehearsed on staging; the renewal PR is registry-only; the M17 checklist green or dated exceptions
risk_zone: red
status: in-progress
branch: t04-t54-flip-runbook
worktree: /Users/ayushkbhatia/Accrued/abacus-s39
created: 2026-11-12
updated: 2026-11-12
---

## Objective
`docs/runbooks/tax-workspace-flip.md` (rollback is flags off; data persists; CCH stays
authoritative), per-firm flips after six weeks of shadow, `tax_agents.enabled` only for cleared
capabilities with consents, the registry-only renewal of the three flags.

## Plan (built)
- The runbook: flags in order, renewal, preconditions (the M17 checklist), the flip, rollback,
  rehearsal record. Test `tests/unit/tax/test_t04t54_flip_runbook.py`.

## Partial
- Rehearsal on staging, the shadow, the canary and both founders' approvals are human/ops.
- The renewal PR rides the Tue Apr 25, 2028 train (registry-only); the three flags expire
  2027-05-07 today and are on the flag-renewals calendar.

## Progress log
- `2026-11-12` — Runbook written (DEC-4527). Tests run at the S39 end pass.
