---
id: TASK-8712
title: "Q-05-T31: Retention floor reader switches to C21's retention_minimums (dark)"
spec: SPEC-711
acceptance_criteria: [AC-27]
risk_zone: red
status: in-review
branch: q05-t31-floor-source
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: Q-05-T31
---

## Objective
Migration 0982: the floor readers (retention_floor_of behind the policy-save guard, and retention_floors_published behind eligibility and FIL-02) follow the platform setting retention_floor_source; retention_minimums_in_effect() reads the published set in effect; retention_floor_differences() is the pre-switch check, and platform_setting_put refuses the switch to retention_minimums while any floor differs (floors_differ). Built dark: the source stays retention_floors until the Oct 24 train (platform_console floor-switch).

## Plan (red)
1. migrations/versions/0982_retention_floor_source.py (on 0981).
2. schema_check: three new definer readers.
3. abacus_tools/platform_console.py: floor-switch --to … --expected … (operator, two people named in the reason).
4. tests/integration/test_q05t31_floor_source.py (DB; end pass).
5. Rollback: downgrade restores 0112's readers and 0980's setter; the setting row is deleted.

## Progress log
- `2026-11-19` — Built dark. Not done: Q-02's retention_floors as a read-only view over the set (the contract step after the switch, with both approvals, Q-03-T081) and K-02-T15's drift test comparing the view (follows the contract step); the staging and canary equality checks and the Oct 24 switch are human. Gates and tests run once at the S51 end pass (build first, test last).
