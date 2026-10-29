# TXP-12 · K-1 package · Ridgeline 2025 Form 1065

| Field | Value |
|---|---|
| Route and params | `/tax-returns/$returnId/k1`; `?return=` switches 1065 / 1120-S / 1041 |
| Template and host frame | T1 `IndexList` (package rows, expandable) · `Wave 2 - Entities & Trusts.dc.html#txp12` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TXP-12 K-1 package - Ridgeline 2025 Form 1065/` (README.md, spec.md; revision.md wins where present) · HANDOFF_VERSION 2026-10-17 |
| Epic and tasks | T-02 · contract T-02-T06 (this file); fixtures T08; build T09 onward |
| Spec and ADRs | SPEC-502 AC-7; ADR-231; DEC-43 |
| Manifest status | planned until its build (DEC-195); pilot posture: agents off |

## States
Clock E0 is Mon Sep 14, 2026, 9:24 AM CT.

| Artboard | Viewer | Clock | Data condition | Parity tier | Status |
|---|---|---|---|---|---|
| a | samuel-ito | E0 | Drafts | C (lock) | fixture (T-02-T08) |
| a2 | samuel-ito | E0 | Row expanded: Jonah Feld | C report | fixture (T-02-T08) |
| a3 | samuel-ito | E0 | K-3 tooltip | C report | fixture (T-02-T08) |
| a4 | samuel-ito | E0 | Share draft internally (modal) | C report | fixture (T-02-T08) |
| a5 | samuel-ito | Tue Sep 15, 10:28 AM | Release · confirm | C report | fixture (T-02-T08) |
| b | samuel-ito | Tue Sep 15, 10:30 AM | Released | C (lock) | fixture (T-02-T08) |
| b2 | samuel-ito | Tue Sep 15 | Resend (composer) | C report | fixture (T-02-T08) |
| c | samuel-ito | E0 | 1120-S mode (`?return=bluestem-2025-1120s`) | C report | fixture (T-02-T08) |
| d | samuel-ito | E0 | 1041 mode (`?return=calloway-2025-1041`) | C report | fixture (T-02-T08) |
| e | samuel-ito | Mon Oct 5, 2026 | Superseded: amended Feld K-1 | C report | fixture (T-02-T08) |
| f | samuel-ito | E0 | Empty: a return with no import | C (lock) | fixture (T-02-T08) |

Non-artboard: not allowed (404, no count), flag off (C-20 "not turned on"; the portal item hidden), loading and error (F-05 ViewStates), walled rows absent with no hidden count.

## API
`GET /v1/tax-returns/{id}/k1-packages`, `/v1/k1-packages/{pid}`, release check, `:share-internal`, `:release` (202, Undo), `/v1/k1-releases/{rid}:undo`, `:resend`. Every write is a person's; the agent never holds Approve, Release, Send or Submit.

## Status
`k1_package`, `recipient_details_change`.

## Copy
Verbatim from the handoff's spec.md (and revision.md) into `screens/TXP-12/copy.ts`; portal copy never says "Accrued".

## Links
Outbound: SHL-08 (documents), TAX-03 (hand-off), POR-13 (client view). Inbound: TAX-02 K-1s.

## Acceptance
- TXP-12 acceptance: every artboard renders from its fixture scenario with the persona and clock above.
- TXP-12 acceptance: status is never colour alone.

## AVOID
Gradients, emoji, blue, heavy shadows, invented data, boxed inputs, the agent as approver, engine figures not from an approved import.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| D1 | Release is a person's act with an approval grant and an Undo window; drafts never reach the portal | T-02 §2 | DEC-1167 |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, b, f | C (lock at exit) | — | |
| others | C report | — | |
| host | D | — | toolbar 46, subbar 42, tabsbar 44, pane header 46, rows 38/44/56, pills 21/19 |
