---
id: TASK-2633
title: Q-03-T132 tax-surge scenario content in the load profiles
spec: SPEC-000  # no Q-03 SPEC: chapter 10 section 10.11.3 and the Q-03-T132 row
acceptance_criteria: [AC-1]  # the tax profile loads through service APIs on the perf stack
risk_zone: amber
status: in-review
epic: Q-03
plan_key: Q-03-T132
branch: s21-q03-t132
worktree: /Users/ayushkbhatia/Accrued/abacus-s21
created: 2026-11-01
updated: 2026-11-01
---

## Objective
"The tax profile loads through service APIs on the perf stack." (Q-03 §10.11.3, S21 row: x25 plus
the tax surge, 8879 sends and K-1 releases.)

## Plan (amber)
- `backend/src/abacus_tools/synthetic/fleet_tax.py` (new): returns per firm, the bootstrap of each
  return, the organizer template once per firm and its attachment, the 8879 family's engine PDFs,
  the 1065s' K-1 PDFs and set, the tax rollout flags; idempotent per step.
- `fleet.load` calls it after each firm's audits (`tax=True`; a shape without room skips it).
- Tests: `tests/unit/tools/test_q03t132_tax_surge_content.py`,
  `tests/integration/test_q03t132_tax_surge_load.py`.
- Runbook row in `docs/ops/loadtests/README.md`; DEC-1675. No migration, no flag registry change.
  Rollback: revert; loaded tax rows stay on the throwaway perf database.

## Deviations
- The 8879 envelope drafts and sends and the K-1 releases are not preloaded: they are the person
  acts the surge run times (`signing_surge`), and drafting needs signer contacts the fleet's
  clients do not carry yet (DEC-1675).
- **Human / waits:** the perf-stack run (Q-03-T036) and the x25 tax-surge test (Q-03-T131).

## Progress log
- 2026-11-01: built; unit test 3 passed; the integration test runs at the batch's end review.
