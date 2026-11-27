---
id: TASK-9010
title: "K-03-T17: Template drafts and components service"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s54-k03-t17-template-drafts
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-26
updated: 2026-11-26
plan_key: K-03-T17
---

## Objective
Row acceptance: PUT with a stale ETag answers 412, a second draft answers 409 draft_exists, a published version answers 409 not_draft, and every save writes one audit event attributed to the QM owner.

## Done
- template_drafts.py: create_draft, component, save_component (ETag, one event per save)
- DomainPreconditionFailed (412) in the kernel and app
- template_version comment anchor in workpapers
- KNW-06a version read with rail counts
- tests/integration/backfill/test_k03t17_template_drafts.py proves the four acceptance items on Postgres

## Progress log
- `2026-11-26` — Built and proven on Postgres (2 passed); templates v2 contract tests green (44). Fixed my own json-column map against 1010 before commit (row_source is text).
