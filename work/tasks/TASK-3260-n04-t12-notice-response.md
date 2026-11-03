---
id: TASK-3260
title: N-04-T12 notice response part 1 (draft from the firm template, versions, edits, regenerate, reviewable, gate kinds)
spec: SPEC-000  # row (N-04 has no SPEC yet)
acceptance_criteria: [AC-12]
risk_zone: amber
status: in-review
epic: N-04
plan_key: N-04-T12
branch: s27-n04-t12
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
"A draft renders with the watermark, an edit makes L2 stale, Regenerate keeps the human
paragraph, and the partner level answers 409 decision_pending before the decision."

## Plan (amber)
- `notices/response.py`: draft from the firm's published `notice_response` template (C11
  database content through `methodology.api`), typed variables by code, insert-only versions
  with block provenance and edit diffs; `edit` (blocks and settings, If-Match, locked after send),
  `regenerate` (template blocks only); the `notice_response` reviewable and facts with
  `blocked_code` (`decision_pending`, `position_mismatch`, `explanation_required`); gate kinds
  `notice_position_decision`, `notice_response_signoff`, `notice_response_send`.
- `reporting.api.template_blocks`: the template's standard block texts for values (new read).
- `notices/contract.py`: draft, read, PUT and regenerate routes live.
- Error catalogue (3) and client regenerated.
- Tests: `tests/unit/notices/test_n04t12_response.py`.
- Partial: `register_document_kind('notice_response')` and the watermarked C11 render wait on a
  tenant-aware variables provider (C11's provider has no tenant context); enclosures and the
  payment method label are stored by N-04-T18's payment band.

## Progress log
- 2026-11-04: built.

## Decisions made during this task
DEC-2240.
