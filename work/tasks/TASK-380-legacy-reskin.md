---
id: TASK-380
title: Legacy re-skin M1 - screens under legacy/, AppShell and Toolbar, firm pill menu, Accrued wordmark (F-05-T23)
spec: SPEC-000
acceptance_criteria: [AC-21]
risk_zone: green
status: done
epic: F-05
plan_key: F-05-T23
branch: f05-t23-legacy-reskin
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"No screen renders the rail or the Atelier look, firm admin opens from the firm pill, and all
existing tests stay green, including the three AI-text assertions."

## What changed
- `apps/web/src/screens/` → `apps/web/src/legacy/` (every screen and its tests; routes,
  eslint paths and the bundle-budget test repointed). Routes are unchanged.
- `legacy/Layout.tsx` renders the design system's `AppShell` and `Toolbar` (F-05-T18): nav Home ·
  Clients · Knowledge until P-01-T02 renders it from `nav.ts`; Go… and ⌘K open the palette
  (`Palette` now takes `open`/`onOpenChange` and drops its own trigger and key there); the bell
  opens the notification drawer; the firm pill opens SHL-03's menu (person · firm, Firm settings
  for administrators, Sign out). The toolbar has no avatar and no Accrued mark (its docstring).
- The splash, Join and Signup say "Accrued"; the page title is Accrued.
- `ClientBell` is retired from both portal headers (DEC-58 (d): no portal bell). The component
  and its SPEC-032 test stay until P-08's portal shell replaces client notifications (a test is
  never deleted).
- Layout tests now open the firm pill to read the person and to sign out; their assertions are
  unchanged.

## Left for later
- `legacy/ConnectionPanel.tsx` (portal) still says "Abacus": the portal never shows "Accrued",
  so it takes the firm's name with P-08's PortalBrand.
- The 47 native selects and the legacy `Input`: their own pass.

## Definition of done
- [x] Web suite 796 of 796, including the AI-text assertions
- [x] `make check-fast` (typecheck, lint, prettier, build, bundle budgets)

## Progress log
- 2026-10-22: built in one session.
