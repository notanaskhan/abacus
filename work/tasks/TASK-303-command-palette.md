---
id: TASK-303
title: "Command palette: ⌘K across engagements, request items, findings and pages"
spec: SPEC-302
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4]
risk_zone: amber
status: done
branch: task-303-palette
worktree: spec005
created: 2026-10-20
updated: 2026-10-20
---

## Plan
- Backend: `requests.search_items` (`visible_items`) and `fieldwork.search_findings` (`visible`).
- Firm routes: `/v1/firm/search/request-items` and `/v1/firm/search/findings`.
- UI: a `CommandPalette` component in packages/ui.
- Web: `shell/Palette.tsx`, mounted in the toolbar.
- No migration.

## Definition of done
- [x] `tests/unit/requests/test_search.py`, `src/shell/palette.test.tsx` and the Layout tests pass; check-fast passes.

## Progress log
- 2026-10-20: built and merged.
