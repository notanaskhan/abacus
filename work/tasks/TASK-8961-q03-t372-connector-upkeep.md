---
id: TASK-8961
title: "Q-03-T372: Contract and connector upkeep 2028 Q4 (AY-provided contracts)"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s53-quarterly-sweeps
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-24
updated: 2026-11-24
plan_key: Q-03-T372
---

## Objective
No fake is reported unverified at the quarter's end.

## Done
- C2, C10, C12, C13, C18, C21 consumer suites green in backend/tests/contracts
- docs/quality/fakes.yaml: 5 fakes, all verified_on null (provider sandboxes or live credentials, human)

## Progress log
- `2026-11-24` — 2026-11-24: partial: the fakes need provider sandboxes.
