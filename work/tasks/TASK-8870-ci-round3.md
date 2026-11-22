---
id: TASK-8870
title: "S52: CI round 3: lock waits fail, sign-up numbering, hidden failures"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: ci-round3
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-22
updated: 2026-11-22
plan_key: S52
---

## Objective
Tip CI on ae1d847b0 (run 45011497632): five integration shards still hung (the guard fired 1 to 3 times each, every hang an async test waiting on the database), three shards had real failures, and the frontend job ran past 10 minutes with both suites green.

## Done
- Test databases (schema_check.provisioned_database): lock_timeout 120 s and idle_in_transaction_session_timeout 300 s as database settings, so a leaked transaction makes the next test fail naming the lock instead of hanging the shard
- Migration 1003: firm_signup names its tenant code and takes the next number on a firms_tenant_code clash (as 0987 did for provision_firm). The trigger's probe can't see other firms under forced RLS, so a second sign-up with matching initials returned 500
- test_firm_level_reads: a consent read (T-01-T11, C19) fails closed at a firm-level target for every role; the test now expects the six tax reads refused there
- test_scenario_sampling: own_engines fixture puts the identity engine on the module's database and this loop (it kept a closed loop's pool)
- test_q03t028: the entity_relationships case names to_entity_id (0954: exactly one target)
- frontend job: 15 minutes (it took 10 with both suites green)
- durations.json merged from run 45011497632 (partial): 1,765 files

## Progress log
- `2026-11-22` — Local: sign-up 19, firm-level reads 15, sampling 1, q03t028 relationships, g02t12/q03t028/review-undo 182 pass; schema_check reversible. DEC-5867.
