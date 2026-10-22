---
id: TASK-395
title: Make targets - seed-demo, seed-staging, fixtures, journeys, journeys-full (F-04-T15)
spec: SPEC-307
acceptance_criteria: [F-04.15, F-04.16, F-04.17]
risk_zone: red
status: done
epic: F-04
plan_key: F-04-T15
branch: f04-t15-make-targets
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"Targets run; seed-staging refuses while a staging deploy is in flight; N approved the protected
edit." Under AMENDMENT-solo, the protected Makefile edit is decided and recorded here rather than
waiting for an approval.

## What changed (Makefile)
- `seed-demo` (`SNAPSHOT=E0`, `HOLDOUT="a b"`, `NO_SETTLE=1`): runs `db-guard` first, then the F-04-T13 loader on the local stack.
- `seed-staging` (`RESET_CLOCK=E0`): the loader with `--staging`. It skips `db-guard` because staging is hosted. The loader itself refuses production, a real firm, and a `deploy-staging` run in flight, naming the run. It replaces the old stub that pointed at a missing module.
- `fixtures`: fails with "not implemented: F-04-T31". The export slides to S10–S11 (F-04 §1.4).
- `journeys` (fixture mode) and `journeys-full` (full stack, behind `db-guard`): run Playwright over `apps/web/e2e/journeys/`, which is new and holds a README. They pass while no specs exist yet; the journey specs land per `.claude/skills/journey-e2e`.

## Progress log
- 2026-10-22: ran the targets on the local stack:
  - `make migrate` reached head;
  - `make seed-demo NO_SETTLE=1` replayed 234 events, and a second run replayed 0 (234 already loaded);
  - `make seed-staging` refused outside staging;
  - `make fixtures` exited with the T31 message;
  - `make journeys` ran with no specs.
