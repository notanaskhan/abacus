---
id: TASK-7416
title: "F-07-T01: Tier-4 kickoff: E6 and C6 inventory from P-09/P-10, SPEC addendum (template props as contracts), DECISIONS.md conflict entries, missing C2 status rows held as kit-local draft types"
spec: SPEC-652
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
branch: s38-f07-t01
worktree: /Users/ayushkbhatia/Accrued/abacus-s38
created: 2026-11-12
updated: 2026-11-12
plan_key: F-07-T01
---

## Objective
The inventory and SPEC addendum merge at the first S38 batch as new files only, every handoff
conflict has a DECISIONS.md line, and any missing status words exist only as kit-local draft types
listed for F-07-T25.

## Built
- `docs/design/tier4-inventory.md` (new): E6 pieces present or missing (ToolCard, RunCard and
  ProgressCard missing in `packages/ui`), the C6 v2 session contract, status words, decisions.
- `docs/specs/SPEC-652-f07-tier4-templates.md` (new): props of `WorkbenchLayout`, `SessionList`,
  `ChatHeader`, `ChatThread` (registry keyed by C6's eight kinds plus consumer slots),
  `QuestionCard`, and T13/T14/T17 outlines.
- `packages/ui/src/tier4/draft-status.ts` (new): `FilingDeadlineDraftStatus` for F-07-T25.
- `packages/ui/src/tokens/DECISIONS.md`: Tier-4 kickoff lines (item kinds, slots, ToolCard gap,
  placeholder board data, viewers, T14b/T17 substitutions, draft status, picker, layout).

## Progress log
- `2026-11-12` — Written (S38).
