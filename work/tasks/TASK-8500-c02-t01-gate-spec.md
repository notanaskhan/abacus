---
id: TASK-8500
title: "C-02-T01: Gate check, ADR-344 (P-16) and SPEC-700 ledger posting and CAS approvals"
spec: SPEC-700
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
branch: c02-t01-gate-spec
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: C-02-T01
---

## Objective
Spec section: docs/plan/epics/C-02.md §0.1, §3 F1–F6, §11.2. Gate check for C-02's posting block: ADR P-16 (W1) and P-13 accepted on main; SPEC with numbered ACs; contract issues C8 v2 posting and C20 v2.1 W1 with every CLS-07 and CLS-11 state; consumer requests to R-02 (C18 close_package) and T-06 (C12 v1).

## Plan (red)
1. Gate: P-16 was never drafted (backlog row 'to draft'); the plan's ADR-161 alias is P-35 on main and ADR-142 is the AWS topology (P-13 is ADR-164). Draft P-16 as the next free number, ADR-344, and accept it (AMENDMENT-solo).
2. `docs/adr/ADR-344-client-ledger-writes-w1.md`; backlog.md row and minted list; README index row.
3. `docs/specs/SPEC-700-c02-ledger-posting-cas-approvals.md`: gate table, contract issues (§3), open-question answers Q1/Q2/Q4/Q5/Q6/Q11/Q15/Q16, AC-1..AC-24 over US-1.1..US-6.1.
4. Rollback: docs only; W1 stays enabled: false.

## Progress log
- `2026-11-17` — Built in the S49 sequential stack (DEC-5500). Docs only. The registry entry's `decision: P-16` is renamed to ADR-344 in the T02 protected bundle. Gates and tests run once at the S49 end pass (build first, test last).
