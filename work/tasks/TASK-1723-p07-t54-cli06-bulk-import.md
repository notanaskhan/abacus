---
id: TASK-1723
title: P-07-T54 CLI-06 bulk import UI (g)
spec: SPEC-332
acceptance_criteria: [AC-23]
risk_zone: green
status: in-review
epic: P-07
plan_key: P-07-T54
branch: s14-p07-t54
created: 2026-10-28
updated: 2026-10-28
---

## Objective
Backlog row P-07-T54: "CLI-06 bulk import UI: segmented Bulk import, upload and mapping,
review-duplicates table with TallyStrip and Merge, Keep both, Skip, progress pill, result toast."
Acceptance: "Scenario g passes with axe and the toast reads 210 records imported, 2 skipped, 0 new
clients." Built ahead of P-07-T62, whose bulk-import walk needs it.

## Plan
- `apps/web/src/domain/clients/imports.ts`: the import, its review rows, decide, upload (raw body,
  DEC-374), run (Idempotency-Key), polling while `importing`; `toImport` (rows less skipped and
  undecided).
- `apps/web/src/screens/CLI-06/BulkImport.tsx`: Source · Map fields · Review duplicates · Import on
  the O6 Wizard; `index.tsx` splits into `SingleIntake` and the mode switch; `?mode=import` on
  `/clients/new`.
- Fixture: `fixtures/handlers/imports.ts` (live semantics) and scenario g from P-07-T50's file
  (212 rows; the eight review rows and their scores); the gallery artboard; e2e screen spec g.
- Docs: screen contract g row, copy and deviations; contract words; DEC-812.

## Acceptance
| Check | Test |
|---|---|
| g renders: tallies 204 / 8 / 0, eight rows, rows 7–8 Skip, "Import 210 records" | `CLI-06.test.tsx` g |
| Footing 204 + 8 + 0 = 212; 212 − 2 = 210; every match a seed client | same |
| Decision saved; count follows; undecided rows left out | same |
| Run: "Importing 210 records…" then toast "210 records imported · 2 skipped · 0 new clients" | same |
| Upload maps headings; a refused file says why; the header switches modes | same |
| Axe on g | `e2e/screens/CLI-06.spec.ts` (Playwright, runs in the batch) |

## Progress log
- `2026-10-28` — Built. 23 CLI-06 tests pass; fixtures, gallery, routes, app-core and clients
  domain suites (628) pass. Playwright axe for g added, not run here (no browser stack in this
  session; it runs with the batch).

## Handoff
- **Current state:** PR open, held for the batch (stacked on P-07-T60, #572).
