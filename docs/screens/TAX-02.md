# TAX-02 · Return · Overview

| Field | Value |
|---|---|
| Route and params | `/tax-returns/$returnId` (the `ReturnFrame` layout route; every form family dispatches here in the pilot, DV-5) |
| Template and host frame | T2 `RecordCockpit` (RecordHeader return variant, Tabsbar, rail, OverviewCard) · `Wave 1 - Service Lines.dc.html#tax02` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TAX-02 Return - Overview/` (README.md, spec.md; revision.md wins where present) · HANDOFF_VERSION 2026-10-17 |
| Epic and tasks | T-02 · contract T-02-T06 (this file); fixtures T08; build T09 onward |
| Spec and ADRs | SPEC-502 AC-7; ADR-231; DEC-43 |
| Manifest status | planned until its build (DEC-195); pilot posture: agents off |

## States
Clock E0 is Mon Sep 14, 2026, 9:24 AM CT.

| Artboard | Viewer | Clock | Data condition | Parity tier | Status |
|---|---|---|---|---|---|
| a | samuel-ito | E0 | In review · Feld 2025 Form 1040 | C (lock) | fixture (T-02-T08) |
| b | samuel-ito | E0 | Not started · Rafael Quintero | C (lock) | fixture (T-02-T08) |
| c | samuel-ito | Tue Feb 3, 2026 (snapshot) | Gathering · Feld on Feb 3 | C report | fixture (T-02-T08) |
| d | samuel-ito | E0 | Prepared · Juliet Okonjo | C report | fixture (T-02-T08) |
| e | samuel-ito | Sat Sep 19, 2026 (snapshot) | Accepted · Feld on Sep 19 | C (lock) | fixture (T-02-T08) |
| f | samuel-ito | E0 | Loading | C report | fixture (T-02-T08) |

Non-artboard: not allowed (404, no count), flag off (C-20 "not turned on"; the portal item hidden), loading and error (F-05 ViewStates), walled rows absent with no hidden count.

## API
`GET /v1/tax-returns/{id}`, `/{id}/overview`, `POST …/assignments`, `…/transitions`; final approval through T-01 (`tax.api`). Every write is a person's; the agent never holds Approve, Release, Send or Submit.

## Status
`return`, `return_flag`, `return_sync_chip`, `consent` chip.

## Copy
Verbatim from the handoff's spec.md (and revision.md) into `screens/TAX-02/copy.ts`; portal copy never says "Accrued".

## Links
Outbound: TAX-03 (Intake tab), TXP-12 (K-1s), TAX-09, TAX-12, SHL-12 h (final approval), SHL-15 (issues). Inbound: TAX-01 rows.
| Opens SHL-16 · checkpoint drawer | SHL-16 | planned (handoff link; tooltip-only) |
| Opens TAX-09 · engine sync | TAX-09 | planned (handoff link; tooltip-only) |
| Opens TAX-08 · assistant panel | TAX-08 | planned (handoff link; tooltip-only) |
| Opens TXP-01 · Ridgeline review summary (pack 9) | TXP-01 | planned (handoff link; tooltip-only) |
| Opens TAX-05 · Leadsheets with this line lit | TAX-05 | planned (handoff link; tooltip-only) |
| Opens TAX-06 · Issues with this item selected | TAX-06 | planned (handoff link; tooltip-only) |
| Opens TXI-02 · K-1 treatment resolver | TXI-02 | planned (handoff link; tooltip-only) |
| Opens TAX-10 · two-year comparison | TAX-10 | planned (handoff link; tooltip-only) |
| Opens CLI-02 · client record | CLI-02 | planned (handoff link; tooltip-only) |
| Opens ENG-02 · engagement record | ENG-02 | planned (handoff link; tooltip-only) |
| Opens BND-02 · binder | BND-02 | planned (handoff link; tooltip-only) |
| Opens FIL-01 · client folder | FIL-01 | planned (handoff link; tooltip-only) |
| Opens TAX-12 · delivery and e-file | TAX-12 | planned (handoff link; tooltip-only) |
| Opens TXI-01 · 1040 worksheet editor | TXI-01 | planned (handoff link; tooltip-only) |
| Opens TXI-03 · state residency and allocation | TXI-03 | planned (handoff link; tooltip-only) |

## Acceptance
- TAX-02 acceptance: every artboard renders from its fixture scenario with the persona and clock above.
- TAX-02 acceptance: status is never colour alone.

## AVOID
Gradients, emoji, blue, heavy shadows, invented data, boxed inputs, the agent as approver, engine figures not from an approved import.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DV-5 | Every form family opens TAX-02 in the pilot | T-02 §2 | DEC-1167 |
| D1 | Engine figures only from approved imports (ADR-231) | T-02 §2 | DEC-1167 |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, b, e | C (lock at exit) | — | |
| others | C report | — | |
| host | D | — | toolbar 46, subbar 42, tabsbar 44, pane header 46, rows 38/44/56, pills 21/19 |
