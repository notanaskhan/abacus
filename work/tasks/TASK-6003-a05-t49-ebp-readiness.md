---
id: TASK-6003
title: "A-05-T49 the ebp_audits entitlement, the EBP CPA memo and the flip plan"
spec: SPEC-000  # row (A-05-T49)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-05
plan_key: A-05-T49
branch: s29l-a05-t49
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-07
updated: 2026-11-07
---

## Objective
On Fri Dec 10, 2027 J03 fieldwork P0 (EBP-01 to EBP-06) is walkable in production on the canary tenant, and the entitlement refuses a non-synthetic firm without the signed memo.

## Plan
Migration 0700 (on 0687): `ebp_audits` joins tenant_entitlements' module CHECK; firms with ebp.modules on are backfilled. platform.entitlements: Module gains ebp_audits; REVIEWED_MODULES and register_module_review; for a reviewed module a non-synthetic firm holds it only when the owner's check says signed (none registered refuses). assurance: compute/ebp/review.py reads reference/review.yaml (signed, date, V- vault reference), registered from assurance/api.py. ebp_contract._gate checks the entitlement after the flag (404 `ebp_audits`). Seed: Brightwater Hale's ebp slice grants it. Frontend MODULES and the shell fixture list it. docs/quality/golden-reviews/ebp@1.md (draft, awaiting the CPA) names the golden case list hash; docs/ops/pilot/ebp-flip-plan.md (gates, Tuesday 19:00 CT, shadow run, rollback = flag off, both founders, the M15 renewal recipe). EBP integration fixtures seed the entitlement. Rollback: revert; the migration's downgrade drops the rows and the CHECK member.

## Progress log
- 2026-11-07: built. tests/unit/platform/test_a05t49_ebp_entitlement.py passes (9): real firm refused unsigned, holds once signed, synthetic holds unsigned, no check refuses, other modules untouched, memo and record in step, a signed record needs date and V- reference, the memo names the case list. Integration fixtures updated, run at the end pass. Not done: staging soak, canary walk, the CPA's signature, the flag renewals (registry-only on Tue Dec 7, 2027: a renewal runs from its day, so it can't reach past Apr 20, 2028 today).

## Decisions made during this task
DEC-2603
