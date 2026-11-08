---
id: TASK-6206
title: A-07-T22 completion projector read model
spec: SPEC-000  # A-07 F2 (docs/plan/epics/A-07.md)
acceptance_criteria: [AC-1]  # 12 complete, 1 N/A, 5 open, five blockers; rebuild identical
risk_zone: amber
status: in-review
epic: A-07
plan_key: A-07-T22
branch: s31-a07-t22
worktree: /Users/ayushkbhatia/Accrued/abacus-s31
created: 2026-11-08
updated: 2026-11-08
---

## Objective
AUD-19's checklist as a projector over the engagement's facts, from the firm's checklist content,
inert until M16.

## Plan (amber)
- Migration 0741 (on 0740; renumbered from 0720 at the S31 end pass): `assurance_checklist_templates` and `_versions` (methodology; firm
  content; published versions frozen by trigger); FK from `completion_items.template_version_id`.
- `methodology/assurance_checklists.py`: import (JSON, dry run first) and publish (fresh MFA)
  routes; `published_checklist`. Matrix `assurance_checklist_template.import` / `.publish`.
- `assurance/completion_dark.py` (`COMPLETION_LIVE = False`), `completion_projector.py` (derive,
  project idempotent on `last_event_id`, rebuild, the outbox consumer, the manual N/A through
  `completion.update`), `completion_facts.py` (eleven items assurance derives itself).
- Subscriptions chained onto existing handlers for shared event types.
- Seed: the BH checklists now load through the import (DEC-2315's leftover closed).
- Tests: `tests/unit/assurance/test_a07t22_completion_projector.py` (run at the end pass).
- Rollback: inert by design; revert drops the read model, 0741 is expand-only.

## Partial
- Seven completion items have no fact provider yet (`sum`, `sign_offs`, `disclosure_checklist`,
  `form5500_tie`, `schedules`, `certification`, `filing`): they read "Not yet derived" until the
  owning module registers one. The AUD-19 routes stay 501 until A-07-T33's flags.

## Progress log
- `2026-11-08` — Built; pyright clean; app imports.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-2806 | Checklists in the DB; projector facts by provider; dark constant beside completion.py | no |
