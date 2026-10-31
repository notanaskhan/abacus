# TAX-03 · Return · Intake · Feld 2025 Form 1040

| Field | Value |
|---|---|
| Route and params | `/tax-returns/$returnId/intake`; the dock hosts the waiting list or SHL-08 for the request opened |
| Template and host frame | T2 `RecordCockpit` with the dock slot · `Wave 2 - Tax Returns.dc.html#tax03` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TAX-03 Return - Intake - Feld 2025 Form 1040/` (README.md, spec.md; revision.md wins where present) · HANDOFF_VERSION 2026-10-17 |
| Epic and tasks | T-02 · contract T-02-T06 (this file); fixtures T08; build T09 onward |
| Spec and ADRs | SPEC-502 AC-7; ADR-231; DEC-43 |
| Manifest status | fixture (T-02-T19, DEC-1475) over the live read; pilot posture: agents off |

## States
Clock E0 is Mon Sep 14, 2026, 9:24 AM CT.

| Artboard | Viewer | Clock | Data condition | Parity tier | Status |
|---|---|---|---|---|---|
| a | kevin-osei | E0 | Waiting on client | C (lock) | built (T-02-T19) |
| a2 | kevin-osei | E0 | Document open: the 1095-C request | C report | built (T-02-T19) |
| b | kevin-osei | Mon Sep 14, 9:26 AM | Filed | C (lock) | built (T-02-T19) |
| c | kevin-osei | Tue Sep 15, 9:02 AM | Complete · Sep 15 | C report | built (T-02-T19) |
| d | kevin-osei | Tue Sep 15, 10:30 AM | K-1 released · Sep 15 (hand-off received) | C report | built (T-02-T19) |
| e | kevin-osei | E0 | Duplicate upload (illustrative): a duplicate W-2 | C report | built (T-02-T19) |
| f | kevin-osei | E0 | Empty binder (illustrative): Meera Shah's return | C (lock) | built (T-02-T19) |

Non-artboard: not allowed (404, no count), flag off (C-20 "not turned on"; the portal item hidden), loading and error (F-05 ViewStates), walled rows absent with no hidden count.

## API
`GET /v1/tax-returns/{id}/intake`; questionnaires (`questionnaire.read`), duplicate resolution (`evidence.resolve_duplicate`). Every write is a person's; the agent never holds Approve, Release, Send or Submit.

## Status
`k1_handoff`, `questionnaire`, request and evidence words (C5).

## Copy
Verbatim from the handoff's spec.md (and revision.md) into `screens/TAX-03/copy.ts`; portal copy never says "Accrued".

## Links
Outbound: SHL-08 (viewer), SHL-14 (request), POR-05 (organizer). Inbound: TAX-02 Intake tab.
| Opens POR-05 · answers · read-only | POR-05 | planned (handoff link; tooltip-only) |
| Opens SHL-14 · request composer | SHL-14 | planned (handoff link; tooltip-only) |
| Opens TXP-01 · Ridgeline 2025 Form 1065 | TXP-01 | planned (handoff link; tooltip-only) |
| Opens BND-02 · binder builder | BND-02 | planned (handoff link; tooltip-only) |
| Opens INB-01 with the thread selected | INB-01 | planned (handoff link; tooltip-only) |
| Clicking a received request opens it in the dock (SHL-08), with Approve Document in the footer | SHL-08 | planned (handoff link; tooltip-only) |

## Acceptance
- TAX-03 acceptance: every artboard renders from its fixture scenario with the persona and clock above.
- TAX-03 acceptance: status is never colour alone.

## AVOID
Gradients, emoji, blue, heavy shadows, invented data, boxed inputs, the agent as approver, engine figures not from an approved import.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| D1 | Duplicate acceptance applies to client channels only behind `evidence.duplicate_review`; firm uploads keep the 409 | T-02 §2 | DEC-1167 |
| D2 | a2 opens the W-2 (seeded SHL-08 document) rather than the password-protected 1099 | fixture viewer document | DEC-1475 |
| D3 | Row sub-lines read the version's channel (`portal`, `email`) without the uploader's name; the banner names the source return, not the approving partner; d's box note is absent | not in the read | DEC-1475 |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, b, f | C (lock at exit) | — | |
| others | C report | — | |
| host | D | — | toolbar 46, subbar 42, tabsbar 44, pane header 46, rows 38/44/56, pills 21/19 |
