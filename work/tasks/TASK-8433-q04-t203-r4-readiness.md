---
id: TASK-8433
title: "Q-04-T203: R4 Sep-1 readiness review on PF-X1"
spec: SPEC-000  # row (Q-04-T203)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
branch: q04-t202-t203-ops
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: Q-04-T203
---

## Objective
Q-04-T203: R4 Aug 25, 2028 Sep-1 readiness review per firm (LEVEL=season); extended on-call published; the R4 dossier green per live firm and signed by both founders before Sep 1. On PF-X1 (synthetic, DEC-4100).

## Plan (red)
1. `docs/ops/pilot/pf-x1/season.md`: the R4 record (steps, state, the exact go-live-check command).
2. `docs/ops/go-live/PF-X1.md` operations-5 points at it.

## Progress log
- `2026-11-17` — Recorded in the S48 sequential stack. Partial (synthetic): the go-live check was not run (the local stack was not up); the extended on-call rota and both founders' sign-off are human steps. Flag hygiene (Q-04-T202) passes today. Gates and tests run once at the S48 end pass (build first, test last).
