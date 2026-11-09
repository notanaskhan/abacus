---
id: TASK-6312
title: A-07-T27 report builder service (AUD-23)
spec: SPEC-644  # A-07 F5
acceptance_criteria: [AC-1]
risk_zone: amber
status: partial
epic: A-07
plan_key: A-07-T27
branch: s32-a07-t27
worktree: /Users/ayushkbhatia/Accrued/abacus-s32
created: 2026-11-09
updated: 2026-11-09
---

## Objective
AUD-23's service: validated structured choices, server-side assembly from the C11 template's
blocks, insert-only versions with hashes, block diff, draft DOCX through C11.

## Plan
- New `assurance/report_builder.py`; `methodology.api.published_body`.
- AUD-23 routes live: read, versions, diff, choices.
- Tests: `tests/unit/assurance/test_a07t27_report_builder.py`.
- No migration (0668).

## Progress log
- `2026-11-09` — Built; ruff, pyright clean; tests written, not run (end pass). Partial: the
  request-decision route (raising the `audit_report.opinion` SHL-11 card) and the documents route
  (C11 `render` with a generated document row and Out of date) still answer 501, with
  `draft_docx` ready for them; the EP's L4 sign-off target registration, review and compilation
  templates' own choices, the reissue shape (Q-05) and C11's word-level compare are not built;
  the diff counts blocks switched, not words.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3012 | Choice fields, opinion card key, clause-id conventions, going-concern lock | no |
- `2026-11-09` — S32 end pass: gates, unit, contract, S32 integration and web suites run; fixes folded into the end-pass PR. Status partial.
