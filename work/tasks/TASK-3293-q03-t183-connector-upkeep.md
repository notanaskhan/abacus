---
id: TASK-3293
title: Q-03-T183 Contract and connector upkeep 2027 Q4 (AY-provided contracts)
spec: SPEC-000  # Q-03-T183 row; docs/quality/sweeps/2026-11-05-q03-t183-connector-upkeep.md
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
epic: Q-03
plan_key: Q-03-T183
branch: s27-q-03-t183
created: 2026-11-05
updated: 2026-11-05
---

## Objective
Consumer suites for AY-provided contracts (C2 half, C10, C12, C13, C18, C21) and the nightly connector
suites against provider sandboxes, fakes marked unverified fixed.

Acceptance (backlog row): "No fake is reported unverified at the quarter's end."

## Progress log
- 2026-11-05: `docs/quality/fakes.yaml` lists 5 fakes, all with `verified_on: null`. The nightly passes
  on fakes with the sandbox step skipped, so no date can honestly be set.

## Open (not met here)
- All 5 fakes stay unverified: each needs a provider sandbox or live credentials (human).
