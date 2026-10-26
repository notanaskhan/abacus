---
id: TASK-1294
title: Brightwater Hale governance seed slices, fixtures and golden tests (ADM-04, ADM-06, ADM-07)
spec: SPEC-349
acceptance_criteria: [AC-2, AC-10, AC-16, AC-21, AC-25, AC-27, AC-34]
risk_zone: green
status: in-review
epic: G-02
plan_key: G-02-T07
branch: s9c-governance
created: 2026-10-26
updated: 2026-10-26
---

## Objective
The governance figures, verbatim from the handoff and G-02 §5.4, in one golden both fixture mode
and the backend read, so `make seed-demo` and fixture mode agree as each live slice lands.

## Plan
- Golden `backend/tests/golden/scenario/brightwater_hale/governance_e0.json` (JSON so the SPA
  reads it without a YAML dependency): INC-2026-003/004/005, 18,406 events and 4 of 1,962 via
  Agent, the Copperleaf 20,020.00 footing and 14,900.00 left out, MFA 46 of 46 and the Jan 11
  41 of 46, SSO Jan 12 by Felix, policy v1 to v3, exports, the Aug 17 support session, WISP v4
  and 18 of 20.
- Fixtures `apps/web/src/fixtures/seed/governance.ts` (ADM-04 and ADM-06 data; incidents typed
  with the compliance contract, the rest with local shapes until T11 and T15) beside T04's
  `seed/audit-log.ts`.
- Golden tests: `apps/web/src/fixtures/governance.foot.test.ts` (fixtures = golden) and
  `backend/tests/golden/scenario/test_governance_golden.py` (the register's FTC clock gives Day 4
  of 30 and Oct 10 for the seeded INC-2026-005 discovery, the footing in Decimal, approver ≠
  publisher, the counts).
- Rollback: delete the files.

## Not done here (DEC-419)
The live seed for the rest waits for its service, because the seed writes through service APIs
only: AI policy v1 to v3 (G-02-T23/T24), SSO enforcement and MFA counts (T14), closing
INC-2026-003 and 004 (T18; recording them now would also renumber the register, DEC-290), the
export history (Q-02-T43), the support session (T14 with SPEC-012's staff path), WISP and the
Pub 4557 statuses (T20, with the 20 control definitions imported as platform content, never
committed). The E0 audit-event slice is what built producers write when their slices load (the
wall, the sign-in, the SSN reveal, screening); 18,406 and 1,962 are fixture-only totals.
Notification email template rows are DB content imported per environment through the admin
import; no template text is committed (human to-do).

## Progress log
- 2026-10-26: fixtures, golden and both golden tests green (6 pytest, 6 Vitest). Partial: the
  live slices above are recorded in DEC-419 against their tasks.
