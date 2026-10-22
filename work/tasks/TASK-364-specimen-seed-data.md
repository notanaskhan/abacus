---
id: TASK-364
title: Specimen data from the Brightwater Hale seed at E0, personas, footing tests and the L10 scan (F-05-T33)
spec: SPEC-048
acceptance_criteria: [AC-8]
risk_zone: green
status: done
epic: F-05
plan_key: F-05-T33
branch: f05-t33-specimen-data
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"Every specimen figure foots in a seed test, jonah-feld and dana-whitley exist as fixture personas
for TPL-15 and T15a, and no kit sample data such as Elena Ruiz or Ridgeview Partners appears in
gallery data."

## Scope
- `packages/ui/src/specimens/seed-figures.ts` (exported as `SPECIMEN_SEED` from
  `@abacus/ui/specimens`): the canonical names (FELD, RIDGELINE, NORTHWIND …), E0, staff, persona
  slugs, Northwind PY2025 figures, request counts and the footings specimens draw.
- `apps/web/src/fixtures/specimen-figures.test.ts`: each constant equals the seed's; every footing
  adds up in bigint cents; the personas exist; L10 scans specimens, fixtures and the gallery for kit
  sample data and the gaps.md §4 variant spellings.
- `dana-whitley` added as a portal persona (Marcus & Dana Whitley); `jonah-feld` already existed.
- Specimens moved off kit sample data: the C-01 ledger and statement now draw Northwind's figures;
  RatioStat draws the seed's request counts; the Elena Ruiz contact, the Whitcombe binder path and
  the "86 of the 119 returns" chat line are gone.

## Not yet
The TPL-02 to TPL-18 specimens the F-05 table lists do not exist yet; each adds its footings to
`FOOTINGS` when it lands.

## Findings
The scan found kit sample data in four specimen files (overlays, progress, states) and one
non-canonical spelling (a comment in shell.tsx). All fixed here. "Thomas Whitcombe" is a seed
partner, so the scan bans the kit's Whitcombe household ("Whitcombes", "Whitcombe ›"), not the name.
