---
id: TASK-1251
title: Independent acceptance tests for TASK-076 (Q-02-T09; SPEC-036 AC-3, AC-6, stages)
spec: SPEC-036
acceptance_criteria: [AC-3, AC-6]
risk_zone: red
status: done
epic: Q-02
plan_key: Q-02-T09
branch: lo-optin-tests
created: 2026-10-26
updated: 2026-10-26
---

## Objective
Q-02-T09: acceptance tests for TASK-076 from SPEC-036 and Q-02's row, over HTTP. AC-5 (shadow hidden on every read) is held by TASK-1210's suites; AC-7 (no model text to clients) by the portal contract tests that refuse agent fields.

## Plan
- `tests/integration/backfill/test_q02t09_optin_independent.py`:
  - AC-3: a firm admin with fresh MFA opts in (who, when, the terms' material recorded); a manager and a stale MFA are refused; opting out takes the firm's `opted_in` fact back at once; flag off: opting in and the read answer 404, opting out works.
  - AC-6: only the engagement partner excludes, audited; the boundary refuses the fake and Bedrock routes for that engagement.
  - Stages: the app role cannot write `agent_stages`; `abacus_tools.agent_stage` refuses `live` before the shadow period and records `shadow`.
- `backfill/support.py`: `Migrated` exposes `owner_url` (the stage command runs as the owner).

## Progress log
- 2026-10-26: 4 passed. Found ED-059 (an opt-out with the flag off answered 404 after taking effect) and fixed it. While writing the stage test, the command read the dev database through cached settings; the test clears the settings cache after setting the owner URL.
