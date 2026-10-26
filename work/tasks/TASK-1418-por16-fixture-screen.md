---
id: TASK-1418
title: POR-16 Connections in fixture mode (A-02-T18)
spec: SPEC-333
acceptance_criteria: [AC-35, AC-36, AC-38, AC-43]
risk_zone: green
status: in-progress
epic: A-02
plan_key: A-02-T18
branch: s11-integrations
created: 2026-10-27
updated: 2026-10-27
---

## Objective
"POR-16a-g render from their scenarios, Continue stays disabled until the toggle is on, and no
write scope or vendor logo appears."

## Plan
- `apps/web/src/screens/POR-16/` (`index.tsx`, `copy.ts`, `POR16.test.tsx`): T7 reduced pane 720
  (and the 390 layout), relationship header, cards in catalogue order with status pills from the
  registry words, Export instead beside every ledger Connect, the consent sheet with the
  authorization toggle gating Continue, connecting, reconnected, details drawer, disconnect
  dialog, sync error with Try again. Lucide glyph tiles only.
- Scenarios a-g from `fixtures/scenarios/POR-16.ts` (A-02-T06); route in the portal tree and the
  gallery entry.
- Tests: Vitest per scenario. Playwright not run.

## Progress log
- 2026-10-27: plan written.
