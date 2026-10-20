---
id: TASK-101
title: "Components sprint: Drawer, Sheet, Fieldset, Toast with a deferred 10-second Undo, DataTable (sort, selection, bulk bar, row clicks), Popover, Menu, Tooltip, the status vocabulary, and a dev component gallery"
spec: SPEC-016
acceptance_criteria: [AC-1]
risk_zone: green
status: done
branch: task-101-components
worktree: spec005
created: 2026-10-20
updated: 2026-10-20
---

## Objective
Build the shared components the next features need (Home queue, review notes, follow-ups v2, requests v2), once, in `packages/ui`.

## Scope
**In**
- Overlays (`overlays.tsx`, Radix Dialog):
  - `Drawer` (the plan's O2): right side, 420/480/560 wide, white header, optional meta and footer;
  - `Sheet` (O3): 500 wide, rising from the bottom, title centred, action on the right;
  - `Fieldset`: the cards inside them.
- `toast.tsx`:
  - `toast.show` and `toast.deferred(message, commit, onUndo)`. The action is held for 10 seconds (`UNDO_MS`) and committed then, or straight away if the page is leaving; Undo cancels it.
  - `Toaster`, mounted once.
- `data-table.tsx`: `DataTable<T>` with typed columns, sortable columns (`aria-sort`), row selection, a "Select all" box and a bulk bar, rows that can't be selected, row clicks, and a sticky band header.
- `popover.tsx` (Radix popover, dropdown-menu and tooltip): `Popover`, `Menu` (a greige tray with white sections; destructive items in brick), `Tooltip`, and `TooltipProvider`, mounted once.
- `status.tsx`: one table of every state's word and tone (request, engagement, workpaper, result, decision), `statusWord` and `<Status>`.
- Motion keyframes for the drawer, sheet, popover and toast. Reduced motion is already respected.
- `apps/web`: `Toaster` and `TooltipProvider` at the root; `/_ds` component gallery in dev builds only.
- Dependencies: `@radix-ui/react-popover`, `@radix-ui/react-tooltip`, `@radix-ui/react-dropdown-menu` (already allowed as `@radix-ui/*`).

**Out**
- Moving existing screens onto these components. That happens as each feature touches them (Home queue, review notes, follow-ups, requests v2).
- The command palette, which needs search.

## Plan
Approved by founder (2026-10-20, "proceed with the components sprint"). Paths: `packages/ui/**`, `pnpm-lock.yaml`. Approval file: `work/approvals/TASK-101.yaml`.

## Definition of done
- [x] Component tests pass (5); the gallery checked on the dev stack; `make check-fast` passes.
