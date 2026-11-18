---
id: TASK-8641
title: "S50-FOLLOWUP: S50 immutability triggers to the ADR-004 shape (schema_check on main)"
spec: SPEC-711
acceptance_criteria: [AC-32]
risk_zone: red
status: in-review
branch: s50-schema-fix
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-18
updated: 2026-11-18
plan_key: S50-FOLLOWUP
---

## Objective
schema_check on main d394ba3c1 reported 12 problems in S50 tables: immutability functions that RETURN (evidence tombstone, tax hand-off supersede), filing_deadline_alerts without DELETE and TRUNCATE refusal, return_supersessions miscounted, tax_handoffs_supersede() not reviewed.

## Plan (red)
1. migrations/versions/0968_s50_immutability_triggers.py on 0966: evidence_versions_immutable and tax_handoffs_immutable refuse only; the one permitted write moves into each UPDATE trigger's WHEN (the 0144 pattern); filing_deadline_alerts refuses UPDATE, DELETE and TRUNCATE; abacus_app may execute tax_handoffs_supersede (trigger-only).
2. schema_check: a RETURN statement is matched as a word (return_supersessions contains it); tax_handoffs_supersede reviewed in DEFINER_FUNCTIONS.
3. tests/integration/test_s50_migrations.py: the new triggers exist, each WHEN holds its permitted write, each function has no RETURN; the head check keeps 0966 on the line.
4. Rollback: downgrade 0968 restores 0964/0965/0962's triggers.

## Progress log
- `2026-11-18` — Built after the S50 batch merge (DEC-5641), reported by the S49 session from a clean main worktree. schema_check clean locally (up, down to base, up). Gates and tests run once at the S50 end pass (build first, test last).
