---
id: TASK-9021
title: "F-08-T28: DocumentEditor engine on TipTap/ProseMirror (T20)"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s54-f08-t28-document-editor
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-27
updated: 2026-11-27
plan_key: F-08-T28
---

## Objective
Backlog row acceptance: "The editor renders only through React and ProseMirror nodes, pasted HTML lands as plain text, CSP style-src 'self' holds, and another editor's section is read-only with its banner."

## Done
- packages/ui/src/editor (its own entry @abacus/ui/editor, never the barrel, so TipTap stays in the engine-editor chunk): schema.ts (doc of sections; headings 1-3, body, lists; statementTable atom as a React node view; no links, code, blockquote, rules or strike), StatementTable.tsx (read-only, contenteditable false, $ only where the row says, negatives in parentheses on paper ink), PaperWell.tsx (612 x 792 at 0.82, 44 px scaled margins, watermark slot), paste.ts (paste and drop insert only text/plain), protect.ts (filterTransaction: statement tables never change or vanish; a section another person is editing refuses every step that touches it), DocumentEditor.tsx (injectCSS false, one editable editor per page, SectionEditingBanner per lock)
- Tests: src/editor/DocumentEditor.test.tsx (6): no injected style and a React node view; the kit source has no innerHTML family or injectCSS true; pasted HTML lands as text with no marks or script; a select-all delete leaves the table; Note 5 locked by Hannah Leclerc refuses an insert there and allows one elsewhere, with the banner; a second editor mounts read-only
- T20a-f specimens and the layout are F-08-T31 (S55); LinkedValue is T29 and tracked changes T30

## Progress log
- `2026-11-27` — Built; 6 vitest pass; ui lint and tsc clean.
