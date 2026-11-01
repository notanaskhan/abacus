# SHL-09 · Field provenance popover

| Field | Value |
|---|---|
| Route and params | none: an O1 layer the E2 `AnchoredPopoverHost` opens on a field's ⓘ (`ProvenanceTray`, `screens/SHL-09`) |
| Template and host frame | O1 tray variant (420) over the TPL-03 / TXI-01 worksheet · `Wave 0 - Shell.dc.html` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/SHL-09 Field provenance popover/` |
| Epic and tasks | P-04 · routes P-04-T35 · fixtures P-04-T34 · tray P-04-T55 · AC tests P-04-T56 |
| Manifest status | fixture (P-04-T55) |

## States
| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | samuel-ito | Mon Sep 14, 2026, 9:24 AM | E0 | Halvard taxable interest: agent version 2 (2,310) over the import (2,190); KO's tick on the old hash (stale); SI's open flag | fixture |
| b | samuel-ito | 9:24 AM | E0 | 2025 federal estimated payments: one `estimate` version (≈ 48,000) linked to its open issue | fixture |
| c | kevin-osei | 9:24 AM | E0 | a human `edit` version with its citation note on top of the agent's | fixture |
| d | samuel-ito | 9:24 AM | E0 | KO and SI ticks both on the current hash; no flags | fixture |
| e | samuel-ito | 9:24 AM | E0 | one agent version with no citation (`unsupported`); `field.sign_off` not allowed | fixture |
| f | samuel-ito | 9:24 AM | E0 | a's data; Previous collapsed (the host opens it so) | fixture |
| loading | any | — | — | the provenance read has not answered: the empty tray, `aria-busy` | built |

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/fields/{type}/{id}/{key}/provenance` | `FieldProvenanceOut` | the host record's read | `field.edit`, `field.add_reference`, `field.sign_off` |
| write | `PUT …/value` (value, value kind, required citation note, seen seq) | `FieldProvenanceOut` | `field.edit` | Pencil only with `field.edit` |
| write | `POST …/references` (document, page, seen seq; verified through C4) | `FieldProvenanceOut` | `field.add_reference` | Add reference only with it |
| write | `POST …/ticks` (level, seen hash) | `FieldProvenanceOut` | `field.sign_off` | Sign off field disabled without it or while the value is Unsupported |

## Status
Field value states (`workpaper_value_state`): updated, edited, estimate, unsupported; a tick is current or stale ("Changed after sign-off").

## Copy
`screens/SHL-09/copy.ts`, verbatim from spec.md: "Updated", "Previous", "Value", "Citation", "References", "Sign-offs", "Edit value", "Edited", "No source cited", "Unsupported", "Changed after sign-off", "(before this change)", "<n> versions", "Sign off field", "Add reference", "Add a reference before signing off", "Open issue: <title>".

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| A reference row's ArrowRight (Opens SHL-08 with the region lit) | SHL-08 `useOpenSourceViewer` on the reference's version and citation | live (P-03) |
| The estimate's issue row (Opens TAX-06 · return issues) | SHL-15 `?ov=issue:<id>` over the host (TAX-06 is the host's) | live (P-04) |
| Inbound: TXI-01, EBP-07, AUD-14, AUD-33, TXP-03, TXP-04, TXP-08, TXP-09, TXT-04 ⓘ | the host's E2 popover with `ProvenanceTray` | planned with each host |

## Acceptance
- SHL-09 acceptance: Updated (time, Value with struck prior value, Citation, References) above Previous.
- SHL-09 acceptance: 2,190 → 2,310 on the corrected 1099-INT; the stale sign-off is struck and labelled "Changed after sign-off".
- SHL-09 acceptance: the estimate uses the ≈ badge and links to the open Feld issue.
- SHL-09 acceptance: agent versions carry the Accrued monogram; human versions a person glyph.
- P-04-T55: SHL-09 e keeps Sign off field disabled with "Add a reference before signing off".

## Deviations
| ID | What differs from the handoff | Why | Decision |
|---|---|---|---|
| DV-1 | Add reference lists the documents the host hands in (`documents`), not a search of the return | C3 has no per-return document list; each host owns its documents | DEC-1854 |
| DV-2 | The issue row opens SHL-15 over the host; TAX-06 is the host screen | the tray has no route of its own | DEC-1854 |
| DV-3 | Sign off field signs at the level the host passes (`level`, reviewer by default) | the tray does not read the ladder | DEC-1854 |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a–f | C | not run (P-04-T58: the Playwright visual project runs at the S24 batch end) | report-only; axe and keyboard in `apps/web/e2e/screens/SHL-review.spec.ts` |

Gate: chapter 04 §9.3 keeps Tier C report-only, so the locks are listed and reported, not blocking (DEC-1970). Keyboard: Escape closes the topmost layer and focus returns to the opener.

## Open gaps
None.
