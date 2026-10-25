---
id: TASK-1219
title: POR-02 frontend part 2 — d, e (scope switcher and role chips), g and h fixture-only, M at 390 (P-08-T23)
spec: docs/screens/POR-02.md
acceptance_criteria: [P-08-T23]
risk_zone: green
status: done
epic: P-08
plan_key: P-08-T23
branch: s8b-portal-ui
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"Scenario tests for d, e, g, h and M pass, and Meera Shah's home lists nothing of the Ridgeline return."

## What was built
- `screens/POR-02/index.tsx`: the to-do kind registry gains glyphs and the R2 kinds (reconnect, review_statements, control_requests, exceptions, description_approved; planned sources, fixture builds only); overdue pill above the line; quiet (ink-3) titles for "nothing yet" cards; the grid takes as many columns as cards; the note row (Info glyph on the nested fill); the stage tally ("7 of 9"); My K-1s; the notices info row; the unread dot; the user menu with scopes and role chips (DEC-346); T7-M (`mobile`): stacked 76 cards with chevrons, the vertical tracker, the collapsed team card, tab bar badges.
- `packages/ui`: `PortalToolbar`/`MobileHeader`/`PortalLayout` take `userMenu`; `PortalNavItem.countLabel`; the `MobileTabBar` draws count badges.
- `routes/portal/index.tsx`: `?scope=` and the 390 switch for Home.
- Fixtures: d's data from the artboard (Colorado, the reconnect and answer lines, the 1120-S line, the notice, recent threads), e's to-dos, stages and thread, a's recent threads, g (`luis-ferrante`, Thu Oct 22) and h (`marisol-vega`) homes and portal shells; the home handler answers by `scope_id`.

## Progress log
- 2026-10-25: built; `vitest run src/screens/POR-02` 26 passed (12 new for d, e, g, h, M and the acceptance); footing tests extended for g and h (Tessellate 26 / 3 / Sep 12). DEC-346 recorded.
