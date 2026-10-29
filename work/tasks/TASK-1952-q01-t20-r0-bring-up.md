---
id: TASK-1952
title: "Q-01-T20: R0 bring-up on staging"
spec: SPEC-050
acceptance_criteria: [AC-6, AC-17, AC-19]
risk_zone: red
status: in-progress
epic: Q-01
plan_key: Q-01-T20
branch: q01-t20-r0
created: 2026-10-29
updated: 2026-10-29
---

## Objective
Every R0 item chapter 06 §8.2 assigns to Q-01 checked, with the walking skeleton on staging.

## Plan
- Built: the bootstrap task (`abacus_tools.db_bootstrap`, #627), the staging stack (#628–#642,
  DEC-1003 to DEC-1010), `docs/ops/readiness/R0.md`.
- Runs (builder, by hand, in order): bootstrap task, first migrate, Canary & Co provisioning
  (`ops tenants provision ... --synthetic`), the Brightwater Hale load (`ops` task, DEC-1005), the
  first `deploy-staging.yml`, the SPEC-000 AC-21 walkthrough once WorkOS sign-in works.
- Rollback: the stack is Terraform-managed; the database has 7 days of snapshots.

## Progress log
- 2026-10-29: stack applied; secrets filled; R0.md written with each item's state.
