---
id: TASK-8093
title: "A-09-T12: Migration 0898_assurance_group"
spec: SPEC-658
acceptance_criteria: [AUD-34, AUD-35, POR-23]
risk_zone: amber
status: in-review
branch: a09-t12-assurance-group
worktree: /Users/ayushkbhatia/Accrued/abacus-s46
created: 2026-11-15
updated: 2026-11-15
plan_key: A-09-T12
---

## Plan (amber, expand-only)
- `components` (planned work, scope areas, performer, auditor, PM): analytical-only has no PM; a
  component auditor performs exactly when one is named.
- `component_auditors` (organisation, city, EP contact, component, SAS 149 evaluations,
  make-reference); `component_instructions` (draft/sent/acknowledged; a send is a person's) with
  insert-only `component_instruction_versions`; `component_deliverables` (expected/received/
  reviewed, Late derived; review human-only; return fields paired); `component_milestones`.
- `materiality_versions` + `scope` (entity default, group) and `consolidation_id` (group ⇔ set).
- Forced RLS on every new table; column grants; rollback `alembic downgrade 0897`.

## Built
As planned. `tests/integration/test_a09_s46_migrations.py` covers T10, T11 and T12 (end pass).
Also: 0897's unique index narrowed to ledgers (bank feeds may sit several per entity).

## Progress log
- `2026-11-15` — Built.
