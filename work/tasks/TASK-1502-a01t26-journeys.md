---
id: TASK-1502
title: Engagement export and Source Documents journey steps (A-01-T26)
spec: SPEC-330
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: A-01
plan_key: A-01-T26
branch: s12b-a01-t26
created: 2026-10-27
updated: 2026-10-27
---

## Objective
A-01 §10's journey steps: j03 4e, 5, 5c and 6 (host); j04 1; j20 1 (entry); the binder-export
full-stack steps; the rollback rehearsal on staging.

## Plan
- The fixture screen switch serves AUD-01 and AUD-03 (`?screen=…`, AUD-03 states name their
  audit and row, `IDS`), so the fixture project walks the real route.
- `J03-ebp-audit.spec.ts`: 4e (Remind…, a person sends), 5 (Accept, 12 of 24), 5c (the 62% match
  returned as Wrong document), 6 host (AUD-01); the dock steps stay `fixme` (P-09/P-10, SHL-13).
- `J04-fs-audit.spec.ts`: j04 1 on AUD-01.
- `J20-group-audit.spec.ts`: j20 1 entry, `fixme` (AUD-01's New audit is "Not built yet"; K-04,
  A-09).
- `binder-export.spec.ts` under `e2e/journeys/` (DEC-642): export 1 to 4, `fixme` until the S12
  batch is on staging.
- Full stack and staging: every step `fixme` until `audits.cockpit` is on in E0 and the batch is
  deployed (M6). The rollback rehearsal is a staging step (human).

## Progress log
- 2026-10-27: specs written; not run yet (the S12 batch runs one test pass at the end). Selectors
  follow AUD-03's copy; the first Playwright run may need small selector fixes.
