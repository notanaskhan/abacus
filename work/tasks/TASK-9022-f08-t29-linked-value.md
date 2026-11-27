---
id: TASK-9022
title: "F-08-T29: LinkedValue atom node and Lineage popover (C-37)"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s54-f08-t29-linked-value
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-27
updated: 2026-11-27
plan_key: F-08-T29
---

## Objective
Backlog row acceptance: "A linked number cannot be typed over, deleted or pasted into, stale overrides show the Relink action on amber tint, and hover lights only that value."

## Done
- packages/ui/src/editor/linked.tsx: linkedValue inline atom (id, value, source tb_linked / formula / override, stale, dollar) drawn by a React node view with the shared dotted underline (LINKED_UNDERLINE, for T22's cells too); E1 useMatch in an editor MatchScope so hover lights only that value (match tint and ring) and shows LineagePopover (groups with their total, formula, override by and reason, prior-year source); click opens the Lineage dock (onOpenLineage); a stale override on amber tint with a Relink button that only fires onRelink; OverrideForm (a figure and a reason, submit disabled until both)
- protect.ts guards linkedValue like statement tables (attrs unchanged, never removed), so typing, deleting and pasting over one are refused while text beside it edits
- Tests: src/editor/LinkedValue.test.tsx (4) beside the engine's 6

## Progress log
- `2026-11-27` — Built; 10 editor vitest pass.
