---
id: TASK-300
title: "Source viewer: citation chips open the evidence at the cited cell, highlighted in the source colours (Requests drawer; item page preview)"
spec: SPEC-029
acceptance_criteria: [AC-12]
risk_zone: green
status: done
branch: task-110-source-viewer
worktree: spec005
created: 2026-10-20
updated: 2026-10-20
---

## Scope
**In**
- `CitationChip` (design system): a numbered chip. When verified, it opens the source; when not, it's struck through in brick and disabled.
- `EvidencePreview`:
  - `highlightCell` ("C9", "Sheet1!$C$9"): the cell gets the match colours and a ring, and scrolls into view;
  - `parseCell` (pure, tested).
- `SourceDrawer`: a 560-wide drawer showing the evidence at a cell or page.
- Requests list: the screening's citation chips open the drawer for that evidence version.
- Request item page: the chips highlight the cell in the preview beside them and scroll it into view.

**Out**
- Entry-assessment citations in fieldwork. They point at evidence versions without a request item, and the preview is read per request item. This needs a version-level preview read.
- Highlighting a region in a PDF page (needs the plan's server-side regions, P-11).

## Definition of done
- [x] `task110source.test.tsx` (2), the Board citation test, and the preview/citation screen tests pass; the checks pass, apart from main's open `secrets_scan` finding in `docs/plan/epics/Q-02.md`.
