---
id: TASK-8746
title: "F-08-T07: Agent-column cells: AgentFilledCell suggested/adopted/edited states, citation tooltip, running spinners, agents-unavailable states"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s51-f08t07
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: F-08-T07
---

## Objective
An agent value stays ink-2 with an ink-3 atom until a human onAdopt resolves, edits keep 'Edited by HL · was ...', and citations come only from typed C4 locators (T18d/T18e; TPL-20 a-c).

## Plan (amber)
1. `packages/ui/src/sheet/AgentFilledCell.tsx` on the C-31 `AgentFilledMarker`: suggested, adopted (only after onAdopt resolves; a pending or refused adopt stays suggested), edited, and running (spinner) on empty cells. Citations are typed `CitationView[]` only.
2. types: agent cell fields (by, at, was, citations, exception), `AgentUnavailable`, `SheetRunState`/`SheetRunSource` (the consumer adapts its E6 RunStore), and grid props viewer/onAdopt/onEditAgentValue/onOpenRow/run.
3. SheetGrid: agent cells render through AgentFilledCell; the run store drives the spinners and 'Agent column running'; a DF-04 state shows its reason on the header and drops the run intents.
4. Tests: `AgentFilledCell.test.tsx` (8), including INV-1 (no human verb for the agent or the system) and INV-2 ('[n]' in text is never a marker).
5. Rollback: revert the PR; no backend.

## Progress log
- `2026-11-19` — Built, stacked on #2384 (F-08-T06); sheet tests 20 passed, tsc and eslint clean. Gates and tests run once at the S51 end pass (build first, test last).
- `2026-11-20` — F-08-T11 (TASK-8750) AC tests run against this kit: cut on a locked row was not refused and a no-citation tooltip read "0 citations"; both fixed in #2389 (DEC-5740).
