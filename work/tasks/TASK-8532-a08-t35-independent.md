---
id: TASK-8532
title: "A-08-T35: Independent AC tests for A-08's amber services"
spec: SPEC-657
acceptance_criteria: [AC-5, AC-6, AC-8, AC-9]
risk_zone: amber
status: in-review
branch: a08-t35-independent
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: A-08-T35
---

## Objective
ADR-078 independent AC tests for T12, T13, T14, T16, T17, T18, T21, T22 and T24: I-AGENT-NEVER rows, segregation of expansion approval and reconciliation acceptance, threshold rules, materiality and CT lines, address and follow-up rules, preparation legend.

## Plan (amber)
1. tests/unit/assurance/test_a08t35_independent.py from SPEC-657 and A-08 §4-§6: matrix agent/system/client deny on every accept, approve, decide and send; not_preparer_of_target and is_named_approver; over needs both 10% and the amount; subtotals derived; unexplained status; review default 10% and 50,000; CT strictly below; coverage 15.3%; follow-up 7 + 7 days; UDL 8.8 at 0 of 25; legend wording

## Progress log
- `2026-11-17` — Built in this session for the notanaskhan row (solo build, ADR-078 independence by writing from the spec, not the services' tests); 21 pass. DB CHECK rows (human-only actor kinds) and the address gate's database path are covered at the end pass by the integration suite. Gates and tests run once at the S49 end pass (build first, test last).
