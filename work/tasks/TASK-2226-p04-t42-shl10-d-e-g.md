---
id: TASK-2226
title: P-04-T42 SHL-10 frames d, e, e′, g and the AUD-03 Review entry
spec: SPEC-000  # the backlog row; SPEC-360 and the handoff
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: done
epic: P-04
plan_key: P-04-T42
branch: s17-p04-t42
created: 2026-10-30
updated: 2026-11-01
---

## Objective
SHL-10 frames d, e, e′ and g in fixture mode: over-threshold routing to Priya Raman,
within-threshold batch under BH AJE thresholds v2 with Undo, part-of-set link row to SHL-19; the
AUD-03 Review entry point into SHL-10.

Acceptance (backlog row): "Frames d, e, e-prime and g render from fixtures, Review all in package
approves nothing, and the batch line names a person, never the agent."

## Plan
- Seed `fixtures/seed/review.ts`: d (JE lines, cause, policy words), e (four entries verbatim),
  e′, g (Front Range Freight Co., evidence, set, policy note); board personas; e approve answers
  e′, e′ undo answers e.
- Kit (additive): ApprovalCard `rowsContent`, `setRow`, `primary`.
- `domain/review/proposals.ts`: `route` write (`POST …/route`, Idempotency-Key).
- SHL-10: batch title and JE table, route primary with "Your limit…", approved line with Undo, set
  row; scenarios d, e, ep, g.
- Contract (additive): `ScreeningCardOut.proposal_ref`; AUD-03 "Review…" opens `?ov=approve:<ref>`.
- Tests: SHL-10 d, e, e′, g.

## Progress log
- 2026-10-30: built in S17 Lane 2 off main; tests run in the end review. AUD-03 fixtures carry no
  `proposal_ref` yet (the button hides when null).
- 2026-11-01: merged to main in #798 (0c04e6bcb).
