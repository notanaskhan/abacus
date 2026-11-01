---
id: TASK-2817
title: A-04-T06 migration 0613 assurance_planning
spec: SPEC-620
acceptance_criteria: [AC-13, AC-16, AC-20]
risk_zone: amber
status: in-review
epic: A-04
plan_key: A-04-T06
branch: s23-a04-t06
worktree: /Users/ayushkbhatia/Accrued/abacus-s23
created: 2026-11-01
updated: 2026-11-01
---

## Objective

A-04 §4.2 M2: the planning tables for materiality versions, the risk register, its linkages, service organizations and the fraud brainstorm, with forced row-level security and the human-only guards at the database.

## Acceptance (backlog)

up/down/up passes, a decided materiality row without a decision_id is refused, and an agent-context insert into fraud_minutes_approvals fails at the database.

## Plan

- **Migration `0613_assurance_planning`** (expand-only, on 0612). Every table carries `tenant_id`, `engagement_id` and `work_item_id` with the `work_items` FK and forced RLS. Deletes are revoked; inserts and updates go column by column.
  - `materiality_versions` (insert-only). Status ∈ {proposed, decided, reassessed, revised}; `superseded` is derived. CHECK: status ≠ proposed ⇒ `decision_id` set.
    - Guard trigger: the decision is the firm's own and on the version's card. Decisions are human-only, `decisions_human_only`, 0094.
  - `risk_register_rows`, the plan's `risks` (DEC-1866).
    - CHECK: management override is never rebuttable.
    - UNIQUE (work_item_id, code).
  - `risk_linkages`, with a partial UNIQUE while not removed.
  - `service_organizations`, UNIQUE (work_item_id, name).
  - `fraud_brainstorm_sessions`, one per work item.
  - `fraud_minutes_approvals` (insert-only).
    - `actor_kind = 'human'`.
    - A guard binds `approved_by_user_id` and the actor to the session's GUCs (the 0566 pattern).
  - `fraud_inquiries`: a contact or a governance body. The status is derived from `answered_at`.
- **Status CHECKs** are the status vocabulary's codes, frozen in the migration. A test holds them equal to `status-vocabulary.yaml`.
- **Registry:** `assurance/registry.py` `PLANNING_TABLES`, `INSERT_ONLY`, `INSERT_COLUMNS` and `UPDATE_COLUMNS`. Then `make regenerate` for the tenant-isolation suite.
- **Tests:** `tests/integration/test_a04t06_assurance_planning_migration.py`.
  - up/down/up.
  - A decided row without a decision is refused.
  - A decision from another card is refused.
  - An agent-context approval is refused.
  - Management override is not rebuttable.
  - The app role has no UPDATE on the insert-only tables.
  - The vocabulary equals the CHECKs.
- **Rollback:** `downgrade()` drops the seven tables and the two guard functions. Nothing reads them yet (A-04-T07, T12, T13 and T19 do).

## Decisions made during this task

DEC-1866.

## Progress log

- `2026-11-01` — built: migration 0613, registry and test.
