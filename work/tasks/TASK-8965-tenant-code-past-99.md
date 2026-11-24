---
id: TASK-8965
title: "CI-HANG: Tenant codes past 99: the integration shard hang (#2475's fix, migration 1019)"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s53-ci-speed
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-24
updated: 2026-11-24
plan_key: CI-HANG
---

## Objective
No integration shard hangs on the 100th seeded firm; the 100th firm with the same initials gets a code through the trigger, provisioning and sign-up.

## Done
- migration 1019 (was 1003 on the ci-speed branch): firms_tenant_code_default, provision_firm and 1003's firm_signup pad to two digits and keep longer numbers whole
- tests/integration/test_1019_tenant_code_past_99.py: the trigger and provisioning 101 times under a 10 s statement timeout; every tenant-code function's body
- downgrade restores 1003's firm_signup and 0921/0987's bodies
- DEC-5944; #2475's second half (template database per process, recorded shard timings, shard proof) not landed: main's TASK-8868 to TASK-8870 built their own timing record in the same files

## Progress log
- `2026-11-24` — 2026-11-25: migration tests 10 passed; downgrade/upgrade clean on the dev database.
