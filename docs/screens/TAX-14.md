# TAX-14 · Firm standards run · 1065 Review Checklist v4

| Field | Value |
|---|---|
| Route and params | `/tax-returns/standards-runs` (T-08 §5.1); artboards `/components/screens/TAX-14?st=…` |
| Template and host frame | T1 IndexList |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TAX-14 Firm standards run - 1065 Review Checklist v4/` |
| Epic and tasks | T-08 · SPEC-710; T-08-T01 (TASK-8600); stubs T-08-T04; screens and live swap per `docs/plan/epics/T-08.tasks.csv` |
| Manifest status | fixture (T-08-T31, `/tax-returns/standards`, behind `tax.standards_runs`) |

Parity tier target: C (T-08 §5.5). Copy keys live in `apps/web/src/screens/TAX-14/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures` (F-04-T31), never hand-written.

## States
| Letter | Artboard | Scenario | Persona | Clock (CT) | Build | Owner |
|---|---|---|---|---|---|---|
| a | Running | `standards-run-0924` | Samuel Ito | Mon Sep 14, 9:24 AM | fixture (T-08-T31) | AY |
| b | Complete | `standards-run-0926` | Samuel Ito | Mon 14 Sep 2026, 9:26 AM | fixture (T-08-T31) | AY |
| c | Queued | `standards-run-0918` | Samuel Ito | Mon 14 Sep 2026, 9:18 AM | fixture (T-08-T31) | AY |
| d | Standard picker | `standards-run-0924` | Samuel Ito | Mon 14 Sep 2026, 9:24 AM | fixture (T-08-T31) | AY |
| e | Empty selection | `standards-run-0924` | Samuel Ito | Mon 14 Sep 2026, 9:24 AM | fixture (T-08-T31) | AY |

## Deviations
- README: the eight named checks are drawn inline; the other 34 bind to data-presence checks or stay manual (OQ-3).
- Check ids are namespaced in code as 1065-v4/C-17; the UI keeps 'C-17' (T-08-T02).

## Design deltas (T-08-T02, DEC-5601)
Each row is the frame it amends (a handoff screenshot) and the build answer; no new token or colour is introduced.

| Frame | Handoff | Build | Why |
|---|---|---|---|
| `TAX-14a.png` check ids | "C-17", "C-31" | code key `1065-v4/C-17`; the UI keeps "C-17" | check-id namespace (component codes collide) |
| `TAX-14a.png` unnamed checks | 8 of 42 named | the other 34 bind to data-presence checks or read "Needs review" for a reviewer to confirm | OQ-3 |

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen.

| From | To | Status |
|---|---|---|
| Opens TAX-01 · Tax Returns | TAX-01 | designed (handoff link graph) |
| Opens KNW-04 · version, owner and change log | KNW-04 | designed (handoff link graph) |
| Opens HOME-02 · My approvals, filtered to standards exceptions | HOME-02 | designed (handoff link graph) |
| Opens TXP-10 · both exceptions matched open Ridgeline issues, so its count stays 11 | TXP-10 | designed (handoff link graph) |
| Opens TXP-07 · Review capital accounts · Ridgeline 2025 Form 1065 · M-2 tax-exempt interest | TXP-07 | designed (handoff link graph) |

## T-08-T31 deviations (DEC-6037)
- The route is `/tax-returns/standards`. It shows the newest 1065 run (the run list's first).
- Prep and Rev are the handoff's initials. 01 §9.7 names only Olivia Brandt and Samuel Ito among them, so the chips carry no invented names.
- The summary reads "n selected of 6": the run's rows. The firm's count of 8 open 1065s is the board's, not the run read's.
- A check names its linked issue as "Linked to an existing issue" and opens TXP-10 (C-17 opens TXP-07). The issue's own words are on TXP-10.
- The filter chips draw the run's scope: Form 1065, Open, every office, any reviewer. Filtering by them is TAX-01's.
- KNW-01's "Applied to N returns" opens TAX-14 (link-contract rule 1).

