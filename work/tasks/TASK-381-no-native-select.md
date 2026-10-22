---
id: TASK-381
title: No native select or boxed Input in new code (F-05-T15 remainder)
spec: SPEC-000
acceptance_criteria: [AC-21]
risk_zone: green
status: done
epic: F-05
plan_key: F-05-T15
branch: f05-t15-select-ban
created: 2026-10-22
updated: 2026-10-22
---

## Objective
F-05-T15's "no native select or boxed input exists", held because the legacy screens use 51
native selects and the boxed `Input`.

## Decision (recorded here; plan 04 §M2–M3)
Every native select and boxed `Input` now lives under `apps/web/src/legacy/` (F-05-T23). M2
replaces each legacy screen with its Accrued screen and M3 deletes `legacy/` and the Atelier
`Input`, so converting them in place would be thrown away. Instead an ESLint rule refuses a
`<select>` element and an `Input` import from `@abacus/ui` anywhere outside `src/legacy/`, so no
new one can appear, and the legacy ones leave with their screens.

## What changed
- `apps/web/eslint.config.js`: the shared selectors are `SCREEN_SYNTAX`; a block for non-legacy
  source adds `NEW_CODE_SYNTAX` (flat config replaces a rule's options per block, so the block
  carries both).
- `src/lint/eslint-rules.test.ts`: refused outside legacy, other rules still apply, legacy left.

## Definition of done
- [x] ESLint clean repo-wide; rule tests pass
- [x] `make check-fast`

## Progress log
- 2026-10-22: done in one session.
