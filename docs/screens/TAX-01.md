# TAX-01 · Tax Returns · practice board

| Field | Value |
|---|---|
| Route and params | `/tax-returns`; `?tile=`, `?office=grouped`, `?q=`, `?tax_year=`; `?view=board` falls back to list (DV-15) |
| Template and host frame | T1 `IndexList` (StatusTileRow, FilterBar, ledger DataTable) · `Wave 1 - Service Lines.dc.html#tax01` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TAX-01 Tax Returns - practice board/` (README.md, spec.md; revision.md wins where present) · HANDOFF_VERSION 2026-10-17 |
| Epic and tasks | T-02 · contract T-02-T06 (this file); fixtures T08; build T09 onward |
| Spec and ADRs | SPEC-502 AC-7; ADR-231; DEC-43 |
| Manifest status | planned until its build (DEC-195); pilot posture: agents off |

## States
Clock E0 is Mon Sep 14, 2026, 9:24 AM CT.

| Artboard | Viewer | Clock | Data condition | Parity tier | Status |
|---|---|---|---|---|---|
| a | samuel-ito | E0 | Default: 224 TY2025 returns, tiles in the blueprint's order | C (lock) | fixture (T-02-T08) |
| b | samuel-ito | E0 | `?tile=awaiting_signature` | C report | fixture (T-02-T08) |
| c | samuel-ito | E0 | `?office=grouped` | C (lock) | fixture (T-02-T08) |
| d | samuel-ito | E0 | Bulk selection: Feld, Shah, Varga | C (lock) | fixture (T-02-T08) |
| e | samuel-ito | E0 | Filtered empty: `?q=Schwab` | C report | fixture (T-02-T08) |
| f | samuel-ito | E0 | Season start · TY2026 (`?tax_year=2026`) | C report | fixture (T-02-T08) |
| g | samuel-ito | E0 | Loading (`GET /v1/tax-returns` never answers) | C (lock) | fixture (T-02-T08) |
| h | samuel-ito | E0 | Board (falls back to list in the pilot, DV-15) | C report | fixture (T-02-T08) |
| i | samuel-ito | E0 | Dragging (board; deferred with h) | C report | fixture (T-02-T08) |
| j | samuel-ito | E0 | Drop guard (board; deferred with h) | C report | fixture (T-02-T08) |

Non-artboard: not allowed (404, no count), flag off (C-20 "not turned on"; the portal item hidden), loading and error (F-05 ViewStates), walled rows absent with no hidden count.

## API
`GET /v1/tax-returns`, `/summary`, `POST /v1/tax-returns:bulk-assign` (`tax_return.read_metadata`, `tax_return.assign`). Every write is a person's; the agent never holds Approve, Release, Send or Submit.

## Status
`return` (tile words: Issues, Ready), `return_flag`, `return_sync_chip`.

## Copy
Verbatim from the handoff's spec.md (and revision.md) into `screens/TAX-01/copy.ts`; portal copy never says "Accrued".

## Links
Outbound: TAX-02 (row), TAX-09 (sync chip), SIG-01 (awaiting signature). Inbound: SHL-01 nav (Tax Returns), HOME-01 tiles.

## Acceptance
- TAX-01 acceptance: every artboard renders from its fixture scenario with the persona and clock above.
- TAX-01 acceptance: status is never colour alone.

## AVOID
Gradients, emoji, blue, heavy shadows, invented data, boxed inputs, the agent as approver, engine figures not from an approved import.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DV-15 | Board view (h, i, j) is not built in the pilot; `?view=board` renders the list | T-02 §2 | DEC-1167 |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, c, d, g | C (lock at exit) | — | |
| others | C report | — | |
| host | D | — | toolbar 46, subbar 42, tabsbar 44, pane header 46, rows 38/44/56, pills 21/19 |
