---
id: TASK-2639
title: The portal bundle carries no product name and no fixture firm (build spa job)
spec: SPEC-000  # INV-4, DEC-01, ADR-133; scripts/portal-dist-check.mjs
acceptance_criteria: [AC-1]  # portal-dist-check passes on `vite build --mode portal`
risk_zone: green
status: in-review
epic: P-08
plan_key: P-08-T07
branch: s21-portal-dist
worktree: /Users/ayushkbhatia/Accrued/abacus-s21
created: 2026-11-01
updated: 2026-11-01
---

## Objective
Build run 41308365405 failed its `spa` job at the portal check: "Brightwater" in POR-05's chunk and
"Accrued" in two portal chunks. The check passes again (24 files clean), with the firm app unchanged.

## Scope
- POR-05: `onlyTeam`, `analyticsFrom`, `emptyBody` take the firm from `usePortalBrand()`.
- `packages/ui/src/product.ts` / `portal-product.ts` and the `portalProduct` Vite plugin;
  `states.tsx` and the generated status registry read `PRODUCT` (codegen emits templates).
- DEC-1681.

## Open
- The bundle budget (same build step) fails on main too: five portal route chunks over 120 KB.

## Progress log
- 2026-11-01: built; portal check clean; web 100 + ui 1,293 + codegen 121 tests passed.
