---
id: TASK-8720
title: "T-06-T25: E11 ASC 740 provision engine with rate reconciliation"
spec: SPEC-702
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
branch: t06-t25-provision
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: T-06-T25
---

## Objective
tax/compute/provision.py (pure Decimal): provision = current + deferred; blended state rate net of federal benefit; rate reconciliation (statutory on pretax, state net, permanent items) tied to the provision with any gap reported as the unclassified difference (never plugged); ETR to one place. Ashford: 2,134,650 + 122,550 = 2,257,200 at 28.9%; the B2 variant reports 1,200 unclassified.

## Plan (amber)
1. tax/compute/provision.py; tests/unit/tax/test_t06t25_provision.py (pretax income synthetic: the handoff gives totals and the ETR only).

## Progress log
- `2026-11-19` — Built; tests pass (2). Gates and tests run once at the S51 end pass (build first, test last).
