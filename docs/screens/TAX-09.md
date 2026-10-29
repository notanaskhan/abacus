# TAX-09 · Return · Tax-engine sync · Feld 2025 Form 1040

| Field | Value |
|---|---|
| Route and params | `/tax-returns/$returnId?ov=engine-sync` and `?ov=engine-sync:import:<importId>` (O1 popover on the chip; O4 diff sheet), mounted in T-02's `ReturnFrame` |
| Template and host frame | O1 + O4 · `Wave 2 - Tax Returns.dc.html#tax09` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TAX-09 Return - Tax-engine sync - Feld 2025 Form 1040/` (README.md, spec.md) · HANDOFF_VERSION 2026-10-17 |
| Epic and tasks | T-01 · contract T-01-T05; fixtures T09; build T22–T26 |
| Spec and ADRs | SPEC-501 AC-11; ADR-231; R-04 |
| Flags | `tax.engine_bridge` |
| Manifest status | planned; built on fixtures with T-01-T09's scenarios, `live` with its build tasks (pilot posture: agents off) |

## States
| Artboard | Viewer | Clock (CT) | Data condition | Parity tier | Status |
|---|---|---|---|---|---|
| a | samuel-ito | Wed Sep 16, 2026 11:42 AM | Export motion (Exporting… then Synced); approved 11:20 AM by Daniel Reyes | C (lock) | fixture (T-01-T09) |
| a2 | samuel-ito | Wed Sep 16, 2026 11:20 AM | Ready for export | C (lock) | fixture (T-01-T09) |
| b | samuel-ito | Mon Sep 14, 2026 9:24 AM | Blocked: draft Ridgeline K-1 | C (lock) | fixture (T-01-T09) |
| c | samuel-ito | Mon Sep 14, 2026 9:31 AM | Out of sync: box 18A change, 3 fields | C (lock) | fixture (T-01-T09) |
| d | samuel-ito | Wed Sep 16, 2026 11:43 AM | Diagnostics returned | C (lock) | fixture (T-01-T09) |
| d2 | samuel-ito | Wed Sep 16, 2026 11:20 AM | Export failed | C (lock) | fixture (T-01-T09) |
| e | samuel-ito | Thu Sep 10, 2026 9:30 AM | Import diff: 2025I:FeldJ:V3, 5 differing fields; 1.10 × 123,223 = 135,545 − 55,585 = 79,960 ÷ 4 = 19,990; 141,634 + 96,989 + 69,277 = 307,900 | C (lock) | fixture (T-01-T09) |

Non-artboard: not allowed (a principal the matrix refuses: 404, no count), flag off (the frame with the C-20 "not turned on" state), loading and error (F-05 ViewStates), walled rows absent with no hidden count.

## API
| Read or write | Endpoint | Shape | Matrix action |
|---|---|---|---|
| read | `GET /v1/tax-returns/{id}/engine-sync` | EngineSyncOut | `tax_return.read` |
| write | `POST /v1/tax-returns/{id}/engine-exports; GET /v1/engine-exports/{id}/file; POST …/mark-exported` | EngineExportOut | `tax_return.export` |
| write | `POST /v1/tax-returns/{id}/engine-imports` | EngineImportOut | `engine_import.create` |
| read/write | `GET /v1/engine-imports/{id}; POST …/approve, …/reject` | EngineImportOut | tax_return.read, engine_import.approve |

Every write denies the agent and the system; no agent-owned control says Approve, Release, Send, Post or Decide.

## Status
`return_sync_chip` (the blueprint's seven chip states).

## Copy
Verbatim from the handoff's spec.md into `screens/TAX-09/copy.ts`. Banned (T-01 §5.7; `apps/web/src/copy-bans.test.ts`): any phrase in which Accrued or the agent transmits, e-files or files a return; vendor logos.

## Links
Outbound: SHL-12 h (final approval), TAX-02, KNW-05 (planned). Inbound: TAX-02 chip, TPL-01 board rows.

## Acceptance
- TAX-09 acceptance: every artboard a, a2, b, c, d, d2, e renders from its fixture scenario with the persona and clock above.
- TAX-09 acceptance: the figures in the States table foot in the seed test (T-01-T09).
- TAX-09 acceptance: status is never colour alone; every pill and disc has text (T-01 §5.6).

## AVOID
Gradients, emoji, blue, heavy shadows, invented colours or data, boxed inputs, the agent as approver or transmitter, an Accrued mark on anything the client sees.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| D1 | File-mode chip semantics (T-01 §5.3 table): Synced means a person marked the export or approved an import | ADR-231 | DEC-1160 |
| D2 | DF-08: Import pending approval is its own chip state | DF-08 | T-01 §2.1 |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, a2, b, c, d, d2, e | C (lock) | — | measured with the screen build |
| host | D | — | chip 29 h, 15 px glyph, no tinted fill; popover 462 wide, tray `#EFEEEB`, padding 6, radius 15; sheet inset 14, top 60, radius 14; columns 360 · 150 · 150 · flex · 70; footer 56 h |

## Open gaps
- Status objects live in the registry since T-01-T06; the contracts move from `Literal` types to the registry's enums when the routes go live.
