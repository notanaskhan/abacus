---
id: TASK-8103
title: W-01-T12 WB-10 live — /workbench/connect on T5 CatalogLayout, tiles, categories, picker, search, allowed actions, disabled reasons, Notify me, Build on Accrued
spec: SPEC-659
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-31]
risk_zone: green
status: in-review
branch: w01-t12-wb10-live
created: 2026-11-15
updated: 2026-11-15
---

## Objective
WB-10 on the live C20 v2 routes, a–i on fixtures.

## Built
- `apps/web/src/screens/WB-10/` (screen, copy, scenarios, tests a–i): honest tiles from the API, catalogue-total category counts, status Picker, search, Enable/Connect/Reconnect/Notify me from `allowed_actions`, a disabled Enable that stays focusable with `aria-disabled` and its reason through `aria-describedby`, Connecting in a status region, Build on Accrued (ADM-08 live; ADM-09 planned).
- Route `/workbench/connect?category=&status=&q=` behind `integrations.connect_v1` (flag-off: F-05's state); WB-01's Connect tab opens it; ADM-08's "Workbench › Connect ›" footer links to it; manifest WB-10 `fixture`.
- Catalogue icons the icon set lacks (`id-card`, `shopping-bag`) become `user-round` and `store` in `connect_v2.yaml`.

## Partly built
- a, b, c, d and g from the staging seed: not walked here (no staging); e and f are staging-only by the contract.
- Axe in every state runs in `e2e/screens` (not run in this lane).
- Details… opens WB-11, planned until W-01-T15.
- Some side copy is marked (undesigned): the handoff is not on this machine; Ayush's DF-36 sign-off.

## Progress log
- 2026-11-15: built; WB-10 tests (11) and the full web suite green; stacked on #2102.
