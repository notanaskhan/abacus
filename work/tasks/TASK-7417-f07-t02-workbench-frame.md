---
id: TASK-7417
title: "F-07-T02: T4 WorkbenchLayout (tabsbar 60 with -10 margin, list 358 or 320, chat flex), SessionList (48h rows, search, filter, spinner, awaiting dot, via-Agent meta, locked rows, filtered-empty) and ChatHeader (context chip, LiveDot, Bug/Pencil/Trash2, Create Agent...)"
spec: SPEC-652
acceptance_criteria: [AC-1, AC-2, AC-3]
risk_zone: amber
status: in-review
branch: s38-f07-t02
worktree: /Users/ayushkbhatia/Accrued/abacus-s38
created: 2026-11-12
updated: 2026-11-12
plan_key: F-07-T02
---

## Objective
T4a to T4f frames render from props with Tier D geometry (list 358, chat 1008, panes 742 tall) and
every meta line comes from formatActor.

## Plan (amber)
- `packages/ui/src/templates/workbench-layout.tsx`: `WorkbenchLayout` (tabsbar 60, −10 margin,
  centred Segmented; list 358 at x12, 320 in the T4f agent-detail variant; chat flex; panes 742;
  `restricted` and `flag-off` keep the frame and draw no content), `WORKBENCH_GEOMETRY`.
- `packages/ui/src/agent/chat/session-list.tsx`: header 46 with the round "+", search row 42,
  48-high rows, meta from `formatActor`, spinner, amber awaiting dot ("Awaiting your answer"),
  locked rows, filtered-empty.
- `packages/ui/src/agent/chat/chat-header.tsx`: context chip, LiveDot, title and owner, Bug, Pencil,
  Trash2, "Create Agent…"; intents only; locked disables all.
- Exports from `templates/index.ts`, `agent/chat/index.ts` and `src/index.ts`.
- Tests `packages/ui/src/agent/chat/chat.test.tsx` (10 pass, jsdom).
- Rollback: revert.

## Partial
- The gallery's T4a–f specimen pages and their Tier D Playwright spec land with TPL-04 (F-07-T04
  fixtures and the S39 specimen row); the frame's geometry is pinned by the unit tests here.

## Progress log
- `2026-11-12` — Built (S38). 10 vitest pass; tsc and biome clean for the new files.
