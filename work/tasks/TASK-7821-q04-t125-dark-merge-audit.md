---
id: TASK-7821
title: "Q-04-T125: the dark-merge audit as a script"
spec: SPEC-000  # row Q-04-T125
acceptance_criteria: [AC-1]  # every merged PR listed dark_only, with no live-path file in its diff
risk_zone: green  # tooling only
status: in-review
branch: lo39-q04-t125
worktree: /Users/ayushkbhatia/Accrued/abacus-lo39
created: 2026-11-13
updated: 2026-11-13
plan_key: Q-04-T125
---

## Objective
The row audits the Jan 25-27, 2028 trains by hand. Under the solo edition (DEC-4818) it becomes a
script any window can run: each merged PR between two refs, dark_only or not, with the reason.

## Plan
- `backend/src/abacus_tools/dark_merge_audit.py`: flags added with a default that is not false,
  contract migrations by `quality.expand_only`, files under `deploy/live-paths.yaml`.
- `deploy/live-paths.yaml`: PF-X1's PW1 surfaces (DEC-4819).
- `make dark-merge-audit`; a section in `docs/ops/release-windows.md`.
- `tests/unit/tools/test_q04t125_dark_merge_audit.py` on a throwaway git repository.

## Progress log
- 2026-11-13: built; unit tests 13 passed, ruff and pyright clean. The audit runs over the lo39
  batch in its end pass (evidence for the row's clause).

## Decisions made during this task
DEC-4819.
