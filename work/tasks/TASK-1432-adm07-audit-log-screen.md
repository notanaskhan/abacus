---
id: TASK-1432
title: ADM-07 Audit log explorer at /settings/audit-log (G-02-T13)
spec: SPEC-349
acceptance_criteria: [AC-1, AC-2, AC-5, AC-6, AC-7, AC-10, AC-12]
risk_zone: green
status: in-review
epic: G-02
plan_key: G-02-T13
branch: s11-security
created: 2026-10-27
updated: 2026-10-27
---

## Objective
ADM-07 a–g from the fixture scenarios (G-02-T04) and the live audit-log routes: the T1 feed in
the T12 frame, filter chips, count with Lock, search, rows with ok/no/pl markers, object chip,
actor-type tag, IP click-to-filter, planned "Run ›" links, Load more, the O2 drawer with values
or the withheld reason, the Export dialog and its ready toast; d fixture-only through the same
grammar.

## Plan
- `apps/web/src/screens/ADM-07/{index.tsx, copy.ts, scenarios.ts, ADM-07.test.tsx}`; route
  `/settings/audit-log` behind `audit_log.explorer` (`routes/firm/settings.tsx`); manifest path.
- `fixtures/scenarios/ADM-07.ts` exports the states' opening searches.
- Tests: one per artboard plus INV-1 (no "Accrued Agent"), no edit/delete, IP filter, row names.
- Rollback: revert; the route answers "not built yet" again.

## Progress log
- 2026-10-27: built. DEC-533. axe is the Playwright journey's (G-02-T21); not run here.
- 2026-10-27: Vitest green (one test per artboard a–g and c's withheld variant); registered for
  fixture journeys (`?screen=ADM-07`). tsc, eslint and prettier green. Playwright and axe not run.
