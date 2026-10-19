---
id: TASK-095
title: Design foundation, step 3c — the request item page as an evidence triad; evidence and preview on the left, the decision, the agent's screening and the checks on the right with the decision first, guidance and the request's comments below
spec: SPEC-016
acceptance_criteria: [AC-1]
risk_zone: green
status: done
branch: task-095-item-page
worktree: spec005
created: 2026-10-19
updated: 2026-10-19
---

## Objective
Put the reviewer's decision beside the evidence it's about, rather than at the bottom of a long column.

## Scope
**In**
- `ItemDetail.tsx`:
  - The title is 15/500 with its meta and status.
  - Left column: the evidence versions, then the preview.
  - Right column (sticky): the decision, screening, checks, AI review, then comments on this version.
  - Below: client guidance and the request's comments, side by side.
  - A version card shows a file kind ("Excel", "PDF") in place of the media type; the fingerprint is in mono with its full SHA-256 on hover.
- `EvidencePreview.tsx`: figures in spreadsheet previews align right with tabular digits. The cell text itself is never changed.

## Definition of done
- [x] Web tests pass (353); the screen checked on the dev stack.
- [x] `make check-fast` passes.
