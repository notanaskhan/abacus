---
id: TASK-2427
title: T-02-T19 TAX-03 states a, a2, b–f (Return › Intake)
spec: SPEC-000  # the backlog row; T-02 §3.4, DV-6, DV-7; docs/screens/TAX-03.md
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: T-02
plan_key: T-02-T19
branch: t02-t19-tax03-intake-fe
worktree: /Users/ayushkbhatia/Accrued/abacus-s19b5
created: 2026-10-31
updated: 2026-10-31
---

## Objective
TAX-03 over the live intake read (T-02-T18): rail with binder card, categories and Questions band;
request list with the K-1 dependency banner; dock with waiting files, code flags and the SHL-08
viewer with Approve Document; File to request, Not this…, Ignore reasons, duplicate actions,
Request more to SHL-14, Unpublish confirm, questions drawer, Add organizer and Ask the client, and
the live upload row by polling.

Acceptance: "Seven scenarios pass with axe and every filing, ignore and discard is a person's
click recorded in the audit log."

## Built
- `apps/web/src/screens/TAX-03/` (index, copy, scenarios, unit test); fixtures
  `seed/tax-intake.ts`, `scenarios/TAX-03.ts`; gallery entry; route
  `/tax-returns/$returnId/intake`; TAX-02's Intake tab live; `ov.SHL14`.
- Backend (additive contract): `message_id` on waiting files, `duplicate` on request rows
  (`evidence.pending_duplicates`), `current_version_id` on questionnaire templates.
- Tests: `TAX-03.test.tsx` (12), `e2e/screens/TAX-03.spec.ts` (7 axe runs, passing locally),
  `backend/tests/integration/test_t02t19_intake_actions.py` (2).

## Progress log
- `2026-10-31` — Built on `t02-t19-tax03-intake-fe` off main 29f567697. DEC-1475. Every write is
  its owner's route (triage apply, evidence accept, duplicate resolution, unpublish), so the audit
  row is the owner's. Deviations D2, D3 in the screen contract.
