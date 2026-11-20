# CLS-10 · Flux analysis — Copperleaf August vs July 2026

- **Epic / task:** C-01 · C-01-T40 (TASK-8420) · SPEC-655 AC-48, AC-49
- **Template:** T6 inside the close shell's Review tab (control bar · tally strip · statement table)
- **Route:** `/closes/$closeId/flux` behind `closes.engine`
- **Reads:** `GET /v1/closes/{id}/flux?basis=mom|yoy` (C-01-T25), `GET /v1/closes/{id}` (period,
  open issues, engagement), capabilities (`flux.accept` on the close's engagement)
- **Writes:** `POST /v1/analytic-lines/{id}/explain` (the agent drafts, C-01-T30), `POST
  /v1/analytic-lines/{id}/accept` (Manager or Partner, If-Match); Open in Excel is
  `GET …/flux.xlsx?basis=`
- **Persona · clock:** Priya Raman · Mon Sep 14, 2026, 9:24 AM CT (b 1:12 PM, c 3:05 PM)
- **Handoff:** `CLS-10 Flux analysis - Copperleaf August vs July 2026/`

## States → data

| State | Data condition | Scenario |
|---|---|---|
| a default | 13 tested, Payroll (+7,670, 12.5%) explained as an agent draft, Repairs (+2,560, 400.0%) unexplained (amber cell); Accept for Priya | `a` |
| raj | a's data for Raj Malhotra: no `flux.accept`, so no Accept | `raj` |
| b explained | Repairs explained from the client's answer; Explained 2, Unexplained 0 | `b` |
| c accepted | both "Accepted · PR"; Accepted 2 of 2; the commentary banner | `c` |
| d year over year | August 2025 not in the ledger: every line "Not comparable", dashes | `d` (`initial.basis`) |
| e agent explaining | Repairs shows "Accrued Agent is tracing the change…" | `e` (`initial.explaining`) |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, d | C (locked in C-01-T50) | not run (handoff baselines not on this machine; axe light and forced colors in `e2e/screens/CLS-10.spec.ts`) | — |
| b, c, e | C (report only) | not run | — |
| host | D | — | pane header 46 at 14.5/500; DataTable rows by grammar |

## Links

| From | To | Status |
|---|---|---|
| Both legs must be exceeded · opens KNW-04 | KNW-04 | designed (handoff link graph); KNW-04 not built |
| Opens CLS-06 with the Sound Electric issue | CLS-06 | designed (handoff link graph); "Issue ›" calls `onOpen("CLS-06")` |
| Opens SHL-08 · Payroll register — August 2026 | SHL-08 | designed (handoff link graph); not wired (DV-c) |

## Deviations and gaps

- **DV-a.** Closed (S48 rest, TASK-8443): Gross profit, Total operating expenses and Net income are
  `FluxSetOut.subtotals`, computed by code over the set's lines (cost of goods sold and operating
  expense by QuickBooks account type) and drawn after the line each follows.
- **DV-b.** Closed (S48 rest): the Adjustments segment counts the close's live AJEs
  (`CloseSummaryOut.adjustments`); Adjustments → CLS-07 still waits on CLS-07.
- **DV-c.** Citation markers name each driver; opening SHL-08 and amounts → SHL-09 are not wired.
- **DV-d.** The year-over-year narrative note is left out (client-specific content with no field).
- **DV-e.** Accept is enabled only for a person's explanation (`explained`); an agent draft is
  adopted by saving the person's own explanation first (DEC-5413).
