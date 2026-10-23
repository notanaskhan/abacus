---
id: TASK-951
title: Design-system consumer contract tests for C2, C4, C5 and the P-36 list envelope (F-05-T44)
spec: SPEC-048
acceptance_criteria: [AC-8]
risk_zone: green
status: done
epic: F-05
plan_key: F-05-T44
branch: f05-t43-grammars-contracts
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"A breaking change to any consumed schema fails the provider's CI before a template breaks."

## What
`apps/web/src/fixtures/contracts/design-system.contract.test.ts` (9 tests), typed with the
generated client and checked against `openapi.json` with `schema-check`:
- **P-36 (T1 IndexList).** Every generated `ListPage*` adapts to `ListEnvelope<T>` through the one
  adaptation CLI-01 and BND-01 make; the list of pages must equal the schema's `ListPage_*` set, and
  each keeps `items`, `next_cursor`, `total`, `counts` and `facets`.
- **C2 (status.ts, StatusPill, tiles).** `EnumCovered` for binder, request, engagement, client,
  citation state, viewer status and evidence unlock; every registry code reads as a word, none is
  the match purple.
- **C4 (E1, E2, C-07, the E5 shell).** `CitationV2Out["kind"]` equals the E1 `LocatorKind` union both
  ways; a citation maps to `CitationView` with the server's `match_id` through `contractMatchId`
  (INV-2); a region's `match_id` and page-point rects; the manifest's pages, masks and region rects
  fit the shapes the shell reads, and the manifest carries no text. The C4 stub (P-03-T02) had
  landed on main, so C4 is covered, not pending.
- **C5 (T7 PortalLayout, PortalToolbar).** `MePortalOut["shell"]` maps to a T7 variant and every
  `nav` code to a `PORTAL_AREAS` label (`satisfies Record<…>`), so a new literal fails `tsc`; a
  portal block validates and its scopes carry labels.
- `tracing/types.ts`: `ContractMatch` also takes a C4 region (`match_id` with `rects`).

## Progress log
- 2026-10-23: 9 tests pass; `tsc` for apps/web adds no error (only the known api-client gen set).
