---
id: TASK-7502
title: P-02-T04 glossary rows for search (protected)
plan_key: P-02-T04
spec: SPEC-000  # glossary change
acceptance_criteria: [AC-1]  # banned_patterns accepts the new identifiers
risk_zone: red
status: in-review
branch: p02-t04-search-glossary
worktree: /Users/ayushkbhatia/Accrued/abacus-s39
created: 2026-11-12
updated: 2026-11-12
---

## Objective
Add `search_document`, `search_recent` and the UI term "Go…" to the glossary, and confirm the
palette's "To-do", "saved prompt" and "Session" usage (P-02 §4.10, DEC-14).

## Plan
- `docs/product/glossary.md` "New terms: platform": Search document (`search_documents`; bans
  `search_index_row`, `search_entry`), Search recent (`search_recents`; bans `search_history`,
  `recently_viewed`), Go… (`command_palette`, the two actions and two flags; group words To-dos,
  Saved prompts, Sessions).
- Reserved words: `search_documents` joins the compounds `document` may open.
- No existing identifier uses the new bans (`git grep -w` on backend and apps: none).

## Partial
- The protected glossary change carries the founders' approval (notanaskhan's in the plan); Ayush
  records it at the batch merge, as for earlier protected rows.

## Progress log
- `2026-11-12` — Rows added (DEC-4502). L12 is checked at the end pass.
