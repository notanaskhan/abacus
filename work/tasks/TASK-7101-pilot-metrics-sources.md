---
id: TASK-7101
title: "make pilot-metrics registers W4 to W7 before computing"
spec: SPEC-403  # Q-04-T008 metrics workflow (as TASK-1744)
acceptance_criteria: [AC-10]
risk_zone: green
status: in-review
branch: pfx1-pw1-pw2
worktree: /Users/ayushkbhatia/Accrued/abacus-pfx1
created: 2026-11-10
updated: 2026-11-10
---

## Objective
Found running Q-04-T050 on PF-X1 (DEC-4100): `python -m abacus_tools.pilots metrics` imported
only identity and platform, so no module registered its pilot metric source and the platform
(fail closed) wrote nothing for any week. The worker imports every module's api; the CLI must
too.

## Plan
- `abacus_tools/pilots.py`: `register_metric_sources()` imports `abacus.modules.<name>.api` for
  every name in `MODULES` (the `reproject_human_gates` pattern), called before `metrics`.
- Tests first: `backend/tests/unit/tools/test_t7101_pilot_metrics_sources.py`.
- Rollback: revert; the CLI writes nothing again (the weekly workflow is unaffected).

## Progress log
- 2026-11-10: red then green. On PF-X1 week 2026-09-14 wrote 2 snapshots (W4 0.0%, W5 45.8%);
  a rerun wrote 0 new.
