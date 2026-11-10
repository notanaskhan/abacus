---
id: TASK-6525
title: "T-04-T14: the tax_form_line citable, box citations and linked-figure labels"
spec: SPEC-649
acceptance_criteria: [AC-1]  # the row's acceptance (AC-cite)
risk_zone: red
status: in-review
branch: s33-t04-t14
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-09
updated: 2026-11-09
plan_key: T-04-T14
---

## Objective
A fabricated box value, page or bbox fails verification, a corrected 1099 marks the old citation
moved, and the regions API returns rects only for citations the viewer may see.

## Plan (red)
1. `tax/form_line_citations.py` (PROTECTED): `verify_tax_form_line` (authorise
   `return_worksheet.read` on the anchor's engagement first; a return of another engagement is
   `source_not_found`; value against the field's current amount; quote against its label),
   `display_tax_form_line` (by code), `linked_label` ("Form 1040 · Line 3b 14,820"), `box_claim`
   (an extracted box as a `document_text` claim with page and bbox, verified by the existing word
   layer, moved by evidence's detector on a superseding version). Registered from `tax/api.py`.
2. Unit tests.
Rollback: revert.

## Progress log
- `2026-11-09` — Built; tests written, not run (end pass). The regions API already returns rects
  only for citations the reader may see (C4); the wiring that cites each extracted box as the
  workspace drafts lands with T-04-T15 onward.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3125 | The form line's locator, its checks and where box citations verify | no (ADR-166) |
