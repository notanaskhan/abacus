---
id: TASK-6531
title: "T-04-T12: the return review workspace frame and routes"
spec: SPEC-649
acceptance_criteria: [AC-1]  # the row's acceptance (Objective)
screens: [TAX-04, TAX-05, TAX-06, TAX-07, TAX-08, TXI-01]
risk_zone: green
status: done
branch: s33-t04-t12
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-09
updated: 2026-11-10
plan_key: T-04-T12
---

## Objective
With the flag off every new route shows the designed not-available state and no T-02 screen file
changes; with it on the tabs and chips render counts from one request.

## Build
- `apps/web/src/routes/firm/tax-review.tsx` (new): `/tax-returns/$returnId/review/$section`,
  `/issues`, `/activity`, `/k1-resolver/$activityId`, `/residency`, each with `?ov=assistant`,
  behind the `tax_returns` entitlement and `tax.review_workspace` (F-05's `FlagOffState`).
  Registered in `routes/firm/index.ts` with the Tax Returns area.
- `apps/web/src/screens/TAX-04/frame.tsx` (new): `WorkspaceFrame` over T-02's components,
  unchanged (`RecordCockpit`, `RecordHeader`, `Tabsbar`); header from the return's record, tabs
  Review n / Issues n / Activity, the Checkpoints chip ("n proposed" / "No changes needed") and
  the Assistant chip from one `GET /v1/tax/returns/{id}/workspace`.
- `packages/ui` `RecordHeader`: optional `checkpointsLabel` and `checkpointsIcon` (default
  unchanged: "Checkpoints" with the history icon), so the chip can read T-04 AC-5.2's words.
- Fixture: the workspace summary in `fixtures/handlers/tax-returns.ts` (Feld: 36, 4, nothing
  proposed). Test `screens/TAX-04/frame.test.tsx`.

## Progress log
- `2026-11-09` — Built; tests written, not run (end pass). No T-02 screen file changed. Partial:
  the workspace route still answers 501 (T-04-T05/T07's service), so counts are fixture-only until
  it lands; the section bodies are T-04-T13 onward; the K-1 dependency chip (`k1_dependency`) is
  read but not drawn until TXI-02's row.
- `2026-11-10` — Closed (bookkeeping, no code). T-04-T17 (#1605) made `GET …/workspace` live
  (`review_tree.summary`), and the frame already reads it through `workspaceOptions`, so Review n
  and the viewer level are live. Left to other rows: `issues_open` reads 0 and `assistant` reads
  `agents_off` until the issues read and TAX-08 land (T-04-T17's partial); the K-1 chip waits
  for TXI-02's row.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3131 | The workspace frame is new files over T-02's components; RecordHeader takes the chip's words | no |
