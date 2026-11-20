---
id: TASK-8817
title: "Q-05-T13: Live-path retention and hold changes"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s52-q05t13
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: Q-05-T13
---

## Objective
Saving the 8879 policy at 2 years answers 422 below_floor, Victor Hammond can place a hold while Samuel Ito cannot, and the FIL-02g drawer lists every version.

## Done
- Migration 0994: retention_policies.policy_text/effective_from, retention_policy_history() copies them into the insert-only versions
- retention.create_override (POST /v1/retention/policies: service-line override at or above the type policy, 422 below_type_policy; floor stays the DB's 422 below_floor), policy_versions / versions_of_policy (GET …/policies/{id}/versions)
- legal hold place accepts document_classes, until_released, display_name and the state_controversy / client_dispute reasons
- registry update columns; reviewed audit action
- tests test_q05t13_retention_live.py

## Progress log
- `2026-11-20` — Plan (red): migration, service, routes, holds; rollback revert + downgrade 0994. Built dark-now (DEC-5800). Tests and security review at the end pass.
