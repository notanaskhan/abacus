---
id: TASK-7429
title: "P-10-T54 rest: the M17 shadow evidence built from the database (runtime_v2_flip shadow)"
spec: SPEC-647
acceptance_criteria: [AC-T7]
risk_zone: amber
status: done
branch: s38-p10-t54-rest
worktree: /Users/ayushkbhatia/Accrued/abacus-s38
created: 2026-11-12
updated: 2026-11-12
plan_key: P-10-T54
---

## Objective
The flip request's shadow evidence comes from the records, not from a hand-typed file.

## Built
- `runtime_v2_flip.shadow_evidence` and the `shadow` subcommand: the synthetic firm's
  `engagements.run` runs started in the window and INV-1 + INV-5 over its audit events in it;
  `--canary-from` from the canary job; refuses a firm that is not synthetic; the load profiles'
  database guards; exit 1 when a floor is missed. `evidence_json` round-trips with `check`.
- The flip runbook names it. Tests: unit 1 added (21 in the file), integration 2.

## Left (P-10-T54)
The 14-day shadow window and the canary on staging, the rehearsal, both founders' approvals.

## Progress log
- 2026-11-12: built and tested.
