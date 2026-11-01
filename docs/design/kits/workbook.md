# Workbook kit (T6) and the TPL-06 specimen: hand-off to AUD-08, EBP-04, AUD-16, TXP-07

F-06-T23 (from F-06-T18 to T22). The T6 `WorkbookLayout` kit (statement, grid and calc panes, the
tally strip, SignOffSlots) is locked for its consumers: A-04's AUD-08, A-05's EBP-04/05/08/09,
A-06's AUD-16 and T-05's TXP-07. A fresh session builds EBP-04 on it from this page alone. Every
figure, total, tie and difference is the server's (ADR-050): the kit formats and lays out, and
never adds.

Code: `packages/ui/src/templates/workbook/` (`WorkbookLayout.tsx`, `types.ts`, `__ac__/`).
Specimens: `/components/screens/TPL-06?st=…`. Parity: `parity-manifest.json` keys `t6*`,
`tpl-06*`; the T22 lock.

## Frame

T2 cockpit chrome above; the control bar (44): the view Segmented left, the title centred, ghost
Open in Excel and Download right, and "Sign off…" when `signOff` is passed; the tally strip (52);
the panes (statement, grid, calc) in one match scope, sized panes in the PaneScroller.

## `WorkbookVM` ← the consumer's workpaper read

| Field | From | Notes |
|---|---|---|
| `views`, `view` | the workpaper's tabs | `onView` sets the route's `?tab=` |
| `title` | the workpaper title | centred on the control bar |
| `tally[]` | server tallies (`TallyItem` + optional `issue`) | an off pill with `issue` gains "Issue n" → `onOpenIssue` |
| `panes[]` | `statement` (`TablePayload`), `grid` (`GridPayload` with a typed `source`/`sheet` locator), `calc` (`CalcStep[]`) | values are server-formatted strings; match ids from typed xlsx locators (INV-2) |
| `signOffs[]` | P-04's ladder (`SignOffSlotVM`) | `stale` from the content hash; agent slots dropped (F-06-T21) |
| `building` | a running agent run | pills read Pending, rows skeleton, no sign-off enabled (Story 5.4) |

## Callbacks

`onOpenInExcel`, `onDownload` (audited downloads by the consumer), `onOpenIssue(issue)`,
`onExplain(row, columnKey)` (the consumer's O1 editor), `onOpenSignOff(target, level)` (SHL-12;
the kit never creates a sign-off).

## EBP-04 on T6 (A-05)

- Views: Reconciliation · Timeliness · Testing (`?tab=`).
- Tally: the server's reconciliation tallies; the late deposit's card links its issue.
- Panes: Reconciliation as a statement (no "$"), Timeliness as a statement of 26 payrolls with
  both day counts (DF-34), Testing as the attribute grid (A-05's tests).
- Sign-offs: HL L2; the correction is a person's event (`ebp_correction.record`), never the kit's.

## Other consumers

A-04 AUD-08 (risk register, linkage as a grid), A-06 AUD-16 (misstatements), T-05 TXP-07
(capital accounts, the TPL-06 twin), A-05 EBP-05/08/09.
