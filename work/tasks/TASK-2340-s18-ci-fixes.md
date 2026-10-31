---
id: TASK-2340
title: S18-owned CI failures on main
spec: SPEC-501
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
epic: T-01
plan_key: S18-ci
branch: s18-ci-fixes
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-31
updated: 2026-10-31
---

## Objective
Fix the failures in main's CI (run 41193670987, 1d73f5d8e) that S18's work caused; leave other
sessions' failures to them (listed in DEC-1386).

## Plan
Tests only, no product code: the status-vocabulary helper (`const` and enum unions), P-11-T07's
watermark by character size, the platform-schedules expected set (`consent_sweep`), K-01-T03's
catalog test (`firm_standards` registered by K-02-T08). DEC-1386.

## Progress log
- `2026-10-31` — fixed; the four suites pass locally (golden render in its image). `[skip ci]` on
  commits; the merge runs CI.

## Handoff
- **Current state:** PR open.
- **Exact next step:** merge with CI.
