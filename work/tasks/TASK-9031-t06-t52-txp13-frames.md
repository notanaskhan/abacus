---
id: TASK-9031
title: "T-06-T52: TXP-13 frames a, b, b2, c, c2, c3"
spec: SPEC-702
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
branch: s54-t06-t52-txp13
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-27
updated: 2026-11-27
plan_key: T-06-T52
---

## Objective
TXP-13 frames a, b, b2, c, c2 and c3 with the DF-08 views in fixture mode, per-form Group B tabs for 1120-S, 1120 and 990, Lock on Accepted, skeleton rows while the allocation runs.

## Done
- No partnership vocabulary on 1120 or 990 frames
- The 990 title reads '2025 Form 990 (FYE Jun 30, 2026)'
- Other-entity reads gain their lines (Postgres test)
- Consent subjects set on the return resource (8 consent-bearing actions were failing closed)
- Fixture from the Python scenario

## Progress log
- `2026-11-27` — 2026-11-27: built per DEC-6036. The three line reads were tested on Postgres; that found that nothing set consent_subjects, so every consent-bearing tax read 403'd live. Fixed in overview._resource; the neighbouring suites (26 tests) and tests/unit/tax (1218) are green. 10 TXP-13 tests are green. The DF-08 toggles' composed states from T-06-T02 are still the only part left: here the views are the control bar's segments.
