---
id: TASK-8945
title: "C-02-T57: ADR-078 AC suite 3: console, vendor reads, TIN"
spec: SPEC-700
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s53-c02t57
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: C-02-T57
---

## Objective
ADR-078 AC suite 3 on the console, vendor reads and TIN handling: no unmasked TIN in API, DOM or logs; offshore reveal refused; every reveal logged naming the person; write interception on the vendor and payment read datasets (CONN-001, no write-shaped method); the ledger console's client-entity scope and ethical walls.

## Done
- tests/unit/quality/test_c02t57_connector_read_only.py (2, pass): CONN-001 refuses write-shaped vendor/payment methods, reads pass
- tests/integration/backfill/test_c02t57_console_tin_ac.py (2): console scoped to the team (other firm 404, outsider and client refused, no TIN in the body); TIN reveal refused off the team and to another firm

## Progress log
- `2026-11-23` — 2026-11-23: offshore refusal and reveal-log naming are held by the reveal suites (P-03); listed for the end-pass security review. Integration in the end pass.
