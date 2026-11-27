# TAX-11 · Form preview with K-1s · Ridgeline 2025 Form 1065

| Field | Value |
|---|---|
| Route and params | `/tax/returns/$returnId/preview` (T-06 §5.1); artboards `/components/screens/TAX-11?st=…` |
| Template and host frame | T17 (thumbnails 120 · form flex · package 330) |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TAX-11 Form preview - Ridgeline 2025 Form 1065 with K-1s/` |
| Epic and tasks | T-06 · SPEC-702; gate and contract T-06-T01 (TASK-8510); stubs T-06-T05/T07/T08; screens and live swap per `docs/plan/epics/T-06.tasks.csv` |
| Manifest status | fixture (T-06-T53, `/tax-returns/$returnId/preview`, behind `tax.form_preview`) |

Parity tier target: C (T-06 §5.4). Copy keys live in `apps/web/src/screens/TAX-11/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures` (F-04-T31), never hand-written.

## States
| Letter | Artboard | Scenario | Persona | Clock (CT) | Build | Owner |
|---|---|---|---|---|---|---|
| a | Page 1 (2 blocking diagnostics + §754 pending) | `ridgeline-e0` | Daniel Reyes | 9:24 AM | built | AY |
| b | K-1 · Jonah Feld (Item L 1,550 expected) | `ridgeline-e0` | Daniel Reyes | 9:24 AM | built | AY |
| c | Schedule K page | `ridgeline-e0` | Daniel Reyes | 9:24 AM | built | AY |
| d | Diagnostics clear (Approve return… enabled) | `ridgeline-m2-accepted` | Daniel Reyes | 9:51 AM | built | AY |
| e | Loading (form-rule skeleton) | `ridgeline-e0` | Daniel Reyes | 9:24 AM | built | AY |

## Deviations
- DV-2: README viewer for b reads "Jonah Feld"; the viewer is Daniel Reyes.
- DV-8: watermark "Draft — not for filing" on every page; K-1 faces add "· pre-release".
- DV-9: non-1065 forms show "Preview available after export from the engine".
- Download only in the ⋯ menu, fresh MFA, audited; no transmit control (R-04).
- T-06-T53 (DEC-6035): the route is `/tax-returns/$returnId/preview`, the repo's return prefix. Diagnostics read in code's words (the rule's statement while it fails, its passed wording once clear), not the handoff's sample sentences. The M-2 rule is code's line 9 against Schedule L line 21, so "Schedule M-2 line 4 blank" reads that way. "2 blocking diagnostics" holds: Σ K-1 Item L and the §754 position block, and M-2 warns. Typed values are listed under the page image, each opening SHL-09 (which opens SHL-08); a click on the face waits for region clicks on the E5 viewer. No K-1 face template is published per partner yet, so b selects the partner, says so and opens the K-1 package (TXP-12). "→ issue" opens TXP-10, which has no selected-issue route parameter yet. Captions are the face templates' titles.

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen.

| From | To | Status |
|---|---|---|
| Opens TXP-10 with this issue selected | TXP-10 | designed (handoff link graph) |
| Opens SHL-12 · final approval (Daniel Reyes, BH-TAX-02) | SHL-12 | designed (handoff link graph) |
