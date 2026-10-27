---
id: TASK-1433
title: ADM-06 Security center at /settings/security (G-02-T16)
spec: SPEC-349
acceptance_criteria: [AC-15, AC-16, AC-17, AC-18, AC-19, AC-20, AC-21, AC-24, AC-25, AC-26, AC-27, AC-28, AC-29, AC-30, AC-49]
risk_zone: green
status: in-review
epic: G-02
plan_key: G-02-T16
branch: s11-security
created: 2026-10-27
updated: 2026-10-27
---

## Objective
ADM-06 a–h from the fixture scenarios (G-02-T11) and the live routes as each backend task lands:
fieldsets A–F (F read-only), the Data export, Support access and Posture cards, the export dialog
and history tray, the incident drawer with its clock bar, the MFA-gap variant, the read-only
partner with Approve export, the sessions drawer with sign-out and unlock, the step-up; revision
R2's rows and states i and j fixture-only.

## Plan
- `apps/web/src/screens/ADM-06/{index.tsx, copy.ts, scenarios.ts, ADM-06.test.tsx}`; route
  `/settings/security` behind `security_center.v1`; manifest path.
- `fixtures/scenarios/ADM-06.ts`: i and j, `ENTERPRISE` (R2 data from the seat seed), `OPENS`;
  the fixture contract test lists i and j.
- Tests: one per artboard and T03 state, production without R2 rows, a save with its version.
- Rollback: revert; the route answers "not built yet" again.

## Progress log
- 2026-10-27: built. DEC-534. axe is the Playwright journey's (G-02-T21); not run here.
- 2026-10-27: Vitest green (a–j, sessions, unlock, the three support states, production without
  R2 rows, a save with its version); registered for fixture journeys (`?screen=ADM-06`). tsc,
  eslint and prettier green. Playwright and axe not run.
