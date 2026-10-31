---
id: TASK-2704
title: F-06-T22 Tier-3 lock for T6, T10, TPL-06, TPL-10; freeze check
spec: SPEC-400
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: F-06
plan_key: F-06-T22
branch: s22-f06-t22
worktree: /Users/ayushkbhatia/Accrued/abacus-s22
created: 2026-10-31
updated: 2026-10-31
---

## Objective
- **[AC-1]** "By Fri Sep 3, 2027 all eight boards sit at their target tier with masks and
  deviations recorded, and parity.json lists every in-scope artboard."

## Scope
**In**: parity manifest entries (Tier B frames locked, Tier A strips, pinned sources) for T6a–e,
T10a–e, TPL-06a–e, TPL-10a–d; T10c–e boards; Tier D specs; axe + invariants on every state in the
two walks; the kit freeze pins and test; DECISIONS.md; screen contracts.
**Out**: redrawing the T10 paper header to pass Tier A (reported deviation stays); POR-20's 390
preview toggle; baselines (the PNGs are never committed).

## Plan
1. Tests first: Tier D specs, walk steps, the freeze test.
2. Manifest + boards. Rollback: revert (unlocks the frames).

## Progress log
- `2026-10-31` — built; tsc, eslint, prettier clean. The visual project (ABACUS_VISUAL=1, handoff dir) runs at the S22 end review; any frame over Tier B there gets a mask or a recorded deviation.
- `2026-10-31` — S22 end review: Tier D found T10 c–e clause rows at 47 then 35 (the kit stacked
  the reason under the label, and the kit Toggle is 22 high, not the spec's 20); the row now holds
  the label and the 12.5 ink-3 reason on one line at `py-[5px]`, 34 high as T10 spec.md says.
  The T10 d e2e matched the sr-only twin of its note (`.first()`); prettier on DECISIONS.md. Tier
  D 19/19, the specimen e2e 21/21, the kit 309/309. Tier A/B parity needs the cropped baselines
  (not on this machine) and runs in CI's visual job.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-1754 | parity-tier reading; freeze window | No |
