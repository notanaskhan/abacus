# TAX-14 · Firm standards run · 1065 Review Checklist v4

| Field | Value |
|---|---|
| Route and params | `/tax-returns/standards-runs` (T-08 §5.1); artboards `/components/screens/TAX-14?st=…` |
| Template and host frame | T1 IndexList |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TAX-14 Firm standards run - 1065 Review Checklist v4/` |
| Epic and tasks | T-08 · SPEC-710; T-08-T01 (TASK-8600); stubs T-08-T04; screens and live swap per `docs/plan/epics/T-08.tasks.csv` |
| Manifest status | planned |

Parity tier target: C (T-08 §5.5). Copy keys live in `apps/web/src/screens/TAX-14/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures` (F-04-T31), never hand-written.

## States
| Letter | Artboard | Scenario | Persona | Clock (CT) | Build | Owner |
|---|---|---|---|---|---|---|
| a | Running | `standards-run-0924` | Samuel Ito | Mon Sep 14, 9:24 AM | planned | AY |
| b | Complete | `standards-run-0926` | Samuel Ito | Mon 14 Sep 2026, 9:26 AM | planned | AY |
| c | Queued | `standards-run-0918` | Samuel Ito | Mon 14 Sep 2026, 9:18 AM | planned | AY |
| d | Standard picker | `standards-run-0924` | Samuel Ito | Mon 14 Sep 2026, 9:24 AM | planned | AY |
| e | Empty selection | `standards-run-0924` | Samuel Ito | Mon 14 Sep 2026, 9:24 AM | planned | AY |

## Deviations
- README: the eight named checks are drawn inline; the other 34 bind to data-presence checks or stay manual (OQ-3).
- Check ids are namespaced in code as 1065-v4/C-17; the UI keeps 'C-17' (T-08-T02).

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen.

| From | To | Status |
|---|---|---|
| Opens TAX-01 · Tax Returns | TAX-01 | designed (handoff link graph) |
| Opens KNW-04 · version, owner and change log | KNW-04 | designed (handoff link graph) |
| Opens HOME-02 · My approvals, filtered to standards exceptions | HOME-02 | designed (handoff link graph) |
| Opens TXP-10 · both exceptions matched open Ridgeline issues, so its count stays 11 | TXP-10 | designed (handoff link graph) |
| Opens TXP-07 · Review capital accounts · Ridgeline 2025 Form 1065 · M-2 tax-exempt interest | TXP-07 | designed (handoff link graph) |
