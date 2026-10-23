---
id: TASK-957
title: Firm initial bundle back under its 250 KB budget (F-05-T17 budget on main)
spec: SPEC-048
acceptance_criteria: [AC-8]
risk_zone: green
status: done
epic: F-05
plan_key: F-05-T17
branch: fix/firm-bundle-budget
created: 2026-10-23
updated: 2026-10-23
---

## Objective
`make check-fast` failed on main at the bundle-budget step (F-05-T17; SPEC-048 says the firm
250 KB, portal 150 KB and route 120 KB gzip budgets are enforced there):
`OVER 257.7 KB of 250.0 KB firm initial (index.html)`. Bring the firm initial load back under
250 KB by moving code out of it, with no threshold change, no test change and no behaviour change.

## What landed in the entry (measured, not guessed)
A build with a throwaway analysis plugin (module ids and rendered sizes per chunk, plus the
static module graph) showed the firm entry statically importing one shared chunk,
`sdk.gen-*.js`, of 129.2 KB gzip on its own. It held 445 modules: the whole `@abacus/ui`
design system (291 KB rendered, including `status.gen.ts` at 58 KB), lucide icons, Radix,
tailwind-merge and the generated SDK.

The cause: the shell (`main.tsx`, `root.tsx`, the firm menu, the notifications drawer and others)
imports `@abacus/ui` through its barrel, `src/index.ts`. `packages/ui/package.json` declared no
`sideEffects`, so the bundler had to treat every module the barrel re-exports as part of the
entry's static graph. Every kit a lazy route used (templates, data grids, the record and tracing
kits, the binder kit, overlays) was therefore placed in a chunk the entry loads up front.

## Change
`packages/ui/package.json`: `"sideEffects": ["**/*.css"]`. Only stylesheets have side effects; no
module in `packages/ui/src` runs top-level statements (checked: no bare imports, no top-level
calls). With that declared, the bundler follows the barrel only to the modules the entry actually
uses, and the rest go with the route chunks that use them.

Moved out of the firm initial load: 60 `@abacus/ui` modules (165 KB rendered) and
`@radix-ui/react-popover`, among them `status.gen.ts`, `status.ts`, the templates (index list,
record cockpit, auth card, portal layout), the data kits (data grid, cells, account tree,
evidence, tally strip, variance), the record and rail kits, the tracing kit (cite, match store,
popover host), the requests/binder kit, sheet, wizard and popover overlays, record header,
split layout, tabs bar, timeline, inputs, toggles, data table, amount and citation. Nothing was
added to the initial load.

## Sizes (gzip level 9, `scripts/bundle-budget.mjs`)
- Firm initial: 257.7 KB before, 236.8 KB after (budget 250.0 KB).
- Largest route chunks after: ItemDetail 36.4 KB, ClientEngagement 35.6 KB, Board 34.8 KB (of
  120 KB each).
- Portal (`vite build --mode portal`): initial 105.6 KB of 150 KB (unchanged); POR-01 route
  86.9 KB, down from 90.4 KB; `portal-dist-check` 10 files clean.

## Not done here (recorded)
- The generated SDK (`sdk.gen.ts`) is one module, so every function any screen uses still sits
  in the initial load (about 24 KB gzip). Splitting it would need a generator change; not needed
  for the budget now.
- `src/status/status.test.ts` ("holds every row of the registry", expects 68 kinds, registry has
  71) fails on main without this change; it is not touched here.

## Checks
`apps/web` vitest (1213 passed; the one failure above is pre-existing on main), eslint, prettier;
`packages/ui` tsc, eslint, prettier; firm `vite build` + `bundle-budget dist`; portal build,
`portal-dist-check` and `bundle-budget dist/portal`; every `make check-fast` step run on its own.
`make check-fast` as a whole still stops before the bundle step for reasons that are on main
already and are not touched here: `validate_docs` (duplicate ids TASK-943, TASK-944, TASK-945),
`secrets_scan` (SECRET-003 in `apps/web/src/fixtures/scenarios/POR-01.ts:34`) and `apps/web`
`tsc` (the known errors in generated `packages/api-client/src/{client,core}/*.gen.ts`). The
remaining steps pass, the bundle budget included (46 budgets met).

## Progress log
- 2026-10-23: measured the entry closure from the manifest and a module-graph build; declared
  `sideEffects` on `@abacus/ui`; firm initial 257.7 to 236.8 KB.
