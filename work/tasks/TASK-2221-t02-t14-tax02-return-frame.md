---
id: TASK-2221
title: T-02-T14 ReturnFrame and TAX-02 a–f
spec: SPEC-502
acceptance_criteria: [AC-7]
risk_zone: green
status: in-review
epic: T-02
plan_key: T-02-T14
branch: s17-t02-t14
created: 2026-10-30
updated: 2026-10-30
---

## Objective
The `ReturnFrame` (subbar with Checkpoints and sync chips, tabsbar with the pilot tabs) and TAX-02
a–f on T2 RecordCockpit: the entity variant for 1065, 1120-S and 1041, the agents-off empty
state, Team rows naming SHL-12 at their level, "Open in CCH Axcess" deep link; fixture mode first,
live swap after T-02-T13.

Acceptance (backlog row): "Six scenarios render with axe clean and no Run draft, Re-run draft or
Assistant control exists in a production build."

## Plan
- Contract (additive, defaults empty): `TaxReturnRecordOut.card_detail`, `engine_url`;
  `TaxReturnOverviewOut` record links, filing, pipeline, engine sync date and footnote, pro
  forma, plan, K-1 classifications, carryforwards, top issues, two-year; statement grammar on
  `EngineSummaryLineOut` (nullable amount); ladder `step/state/note/blocked_by`; K-1 dependency
  banner fields. `make generate`; `docs/contracts/tax-returns.md` noted.
- `packages/ui` RecordHeader default variant: `stateTone` (additive).
- Fixtures: `seed/tax-return-overview.ts` (a–e verbatim from the handoff), record / overview /
  assignment handlers in `handlers/tax-returns.ts` by variant; `scenarios/TAX-02.ts`.
- Screen `screens/TAX-02/{index.tsx, copy.ts, scenarios.ts}`; route `/tax-returns/$returnId`
  behind `tax.returns_v1`; TAX-01 rows open it; manifest `fixture`; gallery entry.
- Tests: `TAX-02.test.tsx`, `TAX-02.production.test.tsx`.
- Rollback: revert.

## Acceptance
| Check | Test |
|---|---|
| a–f render their data condition | `TAX-02 artboards` |
| Estimate foots; 2a blank with ⚑ | `a: the estimate foots…` |
| Assign… live | `Assign… posts…` |
| Deep link https only, new tab | `Open in CCH Axcess…`, `a non-https…` |
| Entity variant | `an entity return…` |
| Production: no Run draft, Re-run draft, Assistant | `TAX-02.production.test.tsx` |
| Axe | end review |

## Progress log
- 2026-10-30: built in S17 Lane 2 on T-02-T12; tests run in the end review.
