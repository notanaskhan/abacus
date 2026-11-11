---
id: TASK-6825
title: "S36 end pass: gates, targeted tests, one security review and fix round, workflow histories"
spec: SPEC-647
acceptance_criteria: [AC-P1]
risk_zone: red
status: in-review
branch: s36-end-pass
worktree: /Users/ayushkbhatia/Accrued/abacus-s36
created: 2026-11-11
updated: 2026-11-11
plan_key: S36-END
---

## Objective
Every S36 PR's gates, tests and one security review pass on the whole stack before the batch
merge, with CI only on this last PR.

## Built
See DEC-3417 and `docs/plan/status/S36.md` "Outcome". Fixes:
- run_files actor;
- metering redelivery;
- C17 claim replay;
- the auto-mode Ref;
- migration 0813;
- the engine-mirror guard;
- the review run-status slot;
- the workpapers run step;
- the spec_problems deferral;
- Picker and lint fixes in the front end;
- the stale exact-set tests;
- the task files' AC ids;
- error codes, the isolation list and secrets ALLOW entries;
- three workflow histories and their replay test.

## Progress log
- `2026-11-11` — End pass (S36). Gates and targeted tests green; one review round; no re-review
  findings.
