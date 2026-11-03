---
id: TASK-3202
title: T-03-T03 migration 0655 (organizer editor, answer effects, extensions and estimates)
spec: SPEC-643
acceptance_criteria: [AC-3]
risk_zone: amber
status: in-review
epic: T-03
plan_key: T-03-T03
branch: s26-t03-t03 (stacked on s26-t03-t02)
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-03
updated: 2026-11-03
---

## Objective
"schema_check passes up/down/up, generated tenancy tests pass, and trigger tests show a
published template version, an answer, an effect row and an approved payment cannot change."

## Plan (amber)
- Migration `0655_t03_questionnaires_and_tax_schedules` on 0654, expand-only. It is the delta
  over T-02's 0467:
  - Templates gain key, form family and owner.
  - Versions gain the editor lifecycle (status null on imported versions), one draft per
    template, and a tax year and human actor on publish.
  - Questionnaires gain `owner_kind` (a template-owned one has no engagement).
  - Sections gain key and retired_at.
  - Questions gain the editor columns and the type `date`.
  - Answers gain `question_wording_hash`.
- New tables: `answer_effects` (insert-only, once per answer and rule), `filing_extensions`,
  `extension_payments` (frozen once approved, human approval only), `estimate_schedules` and
  `estimate_installments`.
- Triggers: `questionnaire_template_versions_frozen`, `questionnaire_structure_frozen` (sections
  and questions of a published version), `extension_payments_frozen` and `t03_frozen_row`
  (answer_effects).
- Registries: `requests/registry.py` and `tax/registry.py` (tables, insert and update columns);
  `IMMUTABLE_TABLES["answer_effects"]`.
- Test: `tests/integration/test_t03t03_season_migration.py`.
- Rollback: `alembic downgrade 0654`.

## Progress log
- 2026-11-03: built. Tests at the S26 end review.

## Decisions made during this task
DEC-2202.
