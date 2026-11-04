---
id: TASK-3261
title: T-03-T05 organizer editor service and routes (read, atomic save with If-Match, dry run, client preview)
spec: SPEC-643
acceptance_criteria: [AC-5]
risk_zone: amber
status: in-review
epic: T-03
plan_key: T-03-T05
branch: s27-t03-t05
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
"Kevin's edits save atomically with 412 on a stale version, the preview DTO equals the portal DTO
with no internal fields, and only the template owner can publish v7 with fresh MFA."

## Plan (amber)
- `requests/questionnaire_editor.py`: the editor read (sections, questions, answers, effects,
  counts), `save` (one unit of work against `row_version`; 409 `question_answered` for a type
  change on an answered question; missing questions retired; follow-ups linked by key; dry run
  writes nothing and lists client-visible changes and the effect rules that would fire), the
  client projection (client fields only).
- `questionnaire_editor_contract.py`: `GET …/editor`, `PUT /questionnaires/{id}`,
  `GET …/client-preview` live.
- Tests: `tests/unit/requests/test_t03t05_questionnaire_editor.py`.
- Partial (recorded): the organizer template lifecycle routes (owner, draft from current,
  discard, diff, owner-only publish with fresh MFA for a tax year), `questionnaire_from_template`
  and the KNW-01 catalog provider stay 501 for T-03's next batch; the binder read too.

## Progress log
- 2026-11-04: built. The repo has no 412 path (`DomainConflict` answers 409), so a stale save is
  409 `stale_version` (DEC-2241).

## Decisions made during this task
DEC-2241.
