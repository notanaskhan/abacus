---
id: TASK-092
title: Design foundation, step 2 — the shell; a 46px toolbar replaces the icon rail, and the engagement gets a compact record header with one agent control and segmented tabs
spec: SPEC-016
acceptance_criteria: [AC-1]
risk_zone: green
status: done
branch: task-092-shell
worktree: spec005
created: 2026-10-19
updated: 2026-10-19
---

## Objective
Replace the icon rail and floating header controls with the plan's shell (SHL-01, ENG-02 record header, tabsbar).

## Scope
**In**
- `Layout.tsx`: a white 46px toolbar.
  - Left: the brand and text nav (Engagements, Knowledge), with no icons or badges on nav items.
  - Right: Firm settings (admins), the bell (a dot, never a count; the count is in its accessible name), the user chip "name · firm", and sign out.
  - The page sits on the shell ground at up to 1400 wide.
- `EngagementLayout.tsx`: one record row.
  - Contents: an "Engagements" back chip, the title, the client when it differs, the state, the period, and an agent chip ("Agent on / paused / off", "AI off").
  - The chip opens a popover holding pause / resume and the partner's AI exclusion.
  - The breadcrumb and the stacked agent rows are gone.
  - Tabs are reordered by use: Overview, Requests, Review, Fieldwork, Map, People, Activity, Setup.
- `Tabs.tsx`: a segmented track with a white active pill.
- Board: the duplicated engagement title block becomes an sr-only heading.
- The palette lint allows the plan's status tokens and still bans Tailwind's numbered shades and untokenised families.

**Out**
- The Go… command palette and the firm switcher menu: there is no search yet.
- Page layouts (step 3).

## Plan
Approved by founder (2026-10-19, "proceed with step 2"). Paths: `apps/web/eslint.config.js`, `packages/ui/src/**`. Approval file: `work/approvals/TASK-092.yaml`, expires 2026-10-26.

## Definition of done
- [x] Web tests pass (353); screens checked on the dev stack.
- [x] `make check-fast` passes.
