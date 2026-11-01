---
id: TASK-2624
title: T-02-T31 independent AC tests for T-02-T16, T20, T22 and T26
spec: SPEC-502
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
epic: T-02
plan_key: T-02-T31
branch: s21-t02-t31
worktree: /Users/ayushkbhatia/Accrued/abacus-s21
created: 2026-11-01
updated: 2026-11-01
---

## Objective
"Tests written in notanaskhan's session pass on main and fail on a planted draft leak to the
portal." (ADR-078; POR-05, TXP-12, POR-13.)

## Plan
One file, `backend/tests/integration/test_t02t31_independent.py`, written from the questionnaire
and k1-packages contracts, reusing only T-02-T09's board world and T-02-T21/T26's release world.
No production code changes; rollback is deleting the file.

## Scope
- AC: a question added but not sent never reaches the portal list or detail, and answering it is
  refused (the planted draft).
- Autosave is optimistic: two saves at `If-Match: 1`, the second answers 409.
- A hostile answer (markup, a formula, a template, a bidi override) is stored and served as the
  same inert string.
- A malformed template row (unknown type, no section, a key outside the pattern, no wording) is
  named in the dry run's problems and refused (422) by the real import, storing nothing; wording
  with markup, a formula or a template expression is kept verbatim as text (T-02 §3.5, ADR-052:
  hostile content is rendered as text, not refused).
- An inquiry addressed to one client contact does not list for another client principal.
- A K-1 details change refuses an unknown field (a TIN), stores no full TIN, and another
  recipient's id answers not found.
**Covered by the implementing suites, not repeated (DEC-1668)**: DEC-88 link visibility and walls
(T-02-T20), the inquiry lock after sending (T-02-T22), POR-13 download access events (T-02-T26).

## Progress log
- 2026-11-01: written; runs at the batch's end review.
- 2026-11-01 end review: 5 pass. Fixed the suite: `long_text` (not `text`) as the question type,
  a client membership drops its level and office, the answer is the stored value, and the
  template rule follows the spec (the first draft asserted a refusal the spec does not make).
