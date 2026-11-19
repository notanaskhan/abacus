---
id: TASK-8713
title: "Q-05-T11: Destruction eligibility and quarterly assembly (dark)"
spec: SPEC-711
acceptance_criteria: [AC-21, AC-22, AC-23]
risk_zone: red
status: in-review
branch: q05-t11-eligibility
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: Q-05-T11
---

## Objective
evidence/eligibility.py (pure): eligible_at = later of policy expiry and observed retain-until; never held, never inside an unlocked archive, never without a policy; objects shared with a non-eligible version excluded whole. evidence/destruction.py: assemble(tenant, now, observe) builds the quarter's batch once (items insert-only, destruction_batch.assembled to the admins), plus summary, batch list/detail and documents.csv (audited export, fresh MFA via matrix). Routes wired; dark behind records.destruction.

## Plan (red)
1. engagements api: engagement_retention_facts (client, type, period end) so evidence never reads engagements' table.
2. register_unlocked_archives hook for assurance's archive state.
3. Tests: tests/unit/evidence/test_q05t11_eligibility.py.

## Progress log
- `2026-11-19` — Built; unit tests pass (4). Not built: DestructionAssembleWorkflow on the platform schedule (assemble() is its activity; the quarterly schedule registration and the S3 HEAD observer wire in at the end pass or Q-05-T12's run) and the assurance archive reader registration; the 1,204 / 31 seed figure needs the Q-05 seed slice's former-client documents (not seeded). Gates and tests run once at the S51 end pass (build first, test last).
