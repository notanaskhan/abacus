# CLS-02 · Close › Overview · run — Copperleaf August 2026

- **Epic / task:** C-01 · C-01-T34 (Overview), C-01-T42 (live) · SPEC-655 · contract written in C-01-T55 (TASK-8757)
- **Template:** T2 RecordCockpit without the dock (rail 330 · canvas flex) under the close RecordHeader
- **Route:** `/closes/$closeId` behind `closes.engine`
- **Reads:** `GET /v1/closes/{id}` (summary), `GET /v1/closes/{id}/runs` and `…/runs/{run_no}`, capabilities
- **Writes:** `POST /v1/closes/{id}/runs` (▶ Run), the status menu's transitions, the DecisionCard's answer (d)
- **Persona · clock:** Raj Malhotra · Mon Sep 14, 2026, 9:24 AM CT (b 9:40 AM)
- **Handoff:** `CLS-02 Close Overview - Copperleaf August 2026/` (folder not on this machine; states from C-01 §2)

## States → data

| State | Data condition | Scenario |
|---|---|---|
| a | Running · Run 2: 6 of 9, 3 running at once, started 18 min ago | `overview-a` |
| b | Complete with exceptions 9:40: 9 of 9, 7 open issues, Review | `overview-b` |
| c | Idle · September 2026 Close: Not started, Ready to run 22 tasks, 0 of 8 requests, publish Oct 1 (BD1) | `overview-c` |
| d | Needs input: the DecisionCard on the $6,412.40 Square transfer | `overview-d` |
| e | Failed task: Stopped at Shopify; Retry · View run | `overview-e` |
| shell | the close shell alone (tabs, record bar) | `shell` |
| off | `closes.engine` off: the designed C-20 flag-off state | `off` |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, b, c | C (locked; C-01-T50) | not run (handoff baselines not on this machine; axe light and forced colors in `e2e/screens/CLS-02.spec.ts`) | C-01 §5.4 |
| d, e | C (report only) | not run | — |
| host | D | — | close record bar 42 + close tabs 50; rail 330; pane header 46 at 14.5/500 |

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its target is built (DV-6 names the planned ones).

| From | To | Status |
|---|---|---|
| Opens WB-09 · run trace | WB-09 | designed (handoff link graph) |
| Opens CLS-06 · close review | CLS-06 | designed (handoff link graph) |
| Opens SHL-13 · agent dock with this close in context | SHL-13 | designed (handoff link graph) |
| Opens CLS-05 · reconciliation, Operating Checking ••4410 | CLS-05 | designed (handoff link graph) |
| Opens CLS-04 · Amex Business Card ••1009 | CLS-04 | designed (handoff link graph) |

## Deviations and gaps

- **DV-5 · Board views.** f (Board while running) and g (Board after B) are K-04's; the ViewToggle stays hidden until `board.enabled`.
- **DV-6 · Planned links.** Past due → HOME-03 (T-08) and Messages → INB-04 (N-03) render as planned targets; "Handoff to tax…" stays disabled with "Available after the December close locks" until C-02.
- **DV-7 · Client wording.** "Draft Email" opens template wording with code facts; agent-drafted client text waits on ADR P-25 per firm (N-03).
- **C-01-T50.** The status pill and the run history menu triggers are buttons (aria-allowed-attr); "Started … ago" and the composer prompt read at ink-3 (AA).
