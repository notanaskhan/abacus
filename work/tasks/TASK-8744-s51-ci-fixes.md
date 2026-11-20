---
id: TASK-8744
title: "S51-CI: Main CI reds after the S51 partials batches"
spec: SPEC-000
acceptance_criteria: []
risk_zone: amber
status: in-review
branch: s51r-fixes
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: S51-CI
---

## Objective
Turn main green after batch 2 (13f8a9f84; CI run 44534286568): eighteen unclassified model fields, the A-06-T17 posting-status contract, fixed sets behind S47 to S51 (platform schedules, emailed notification kinds, platform workflows, schema_check update columns, immutable tables and definer functions), the evidence trigger tests still naming the row trigger 0968 split, and the firms_tenant_code unique violation.

## Plan (amber)
1. Classify the eighteen model fields (internal or confidential, per field).
2. A-06-T17: `posting.py` may set `posted` and `failed_post` (W1 posting worker, ADR-344, DEC-5704).
3. Catch the fixed sets up from the registries; never remove an entry.
4. Evidence trigger tests: drop and restore `evidence_versions_no_update` and `evidence_versions_no_delete` (0968) instead of the old combined trigger.
5. Migration 0987: `provision_firm` names the tenant code itself, 01 upward, retrying on the `firms_tenant_code` index. The 0921 trigger's probe was blind under FORCE RLS, so a second firm with the same initials always failed. Regression test `test_firms_tenant_code_race.py` (sequential and concurrent). Rollback: 0987 downgrade restores the 0086 body.

## Progress log
- `2026-11-19` — Built and the failing tests rerun green locally (contracts 10,528 passed; schema_check 192; provisioning, schedules, notifications, race tests). Gates and tests run once at the S51 end pass (build first, test last).
