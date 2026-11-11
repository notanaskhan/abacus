# TAX-08 · Assistant panel (Feld 2025 Form 1040)

| Field | Value |
|---|---|
| Route and params | per T-04 §5.1 (`/tax-returns/$returnId/…`) |
| Template and host frame | O2 right drawer, dock 420, over TAX-05, no scrim |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TAX-08 …/` |
| Epic and tasks | T-04 · T-04-T02 (contract), T-04-T07 (fixtures), screen rows per §9 |
| Priority | P0 |
| Manifest status | fixture (T-04-T34: `screens/TAX-08`; live thread with T-04-T37's `tax.assistant`) |

## States
| Artboard | Data condition that produces it | Status |
|---|---|---|
| a | Proposal pending | fixture |
| a2 | Proposal pending · change (Reasoning, diff, "2 citations") | fixture |
| b | Idle (three suggested prompts) | fixture |
| c | Thinking ("Reading 41 documents, 3 workpapers and the 2024 return…") | fixture |
| d | Applied (9:31; Undo 10 s; Issues 4→3) | fixture |
| e | Rejected ("reason: wait for the final K-1") | fixture |
| f | Follow-up answer (2024 / 2025 inline table) | fixture |
| g | Saved prompt picker (R2) | deferred (W-03) |
| h | Save to saved prompts (R2) | deferred (W-03) |
| loading | skeleton per the handoff | fixture |
| not allowed | walled or out of scope: 404 (INV-3) | fixture |

## API
RW-1 and WS-1 (T-04-T05); matrix actions from `permission-matrix/tax.yaml` (T-04-T03).

## Links
Designed links from the handoff (`handoff-links.json`); the screen is planned, so none is wired yet.

| From | To | Status |
|---|---|---|
| Opens TXI-02 (later) | TXI-02 | planned (handoff link; T-04-T08 onward wires it) |
| Box 18A is not on the worksheet · open issue in TAX-06 | TAX-06 | planned (handoff link; T-04-T08 onward wires it) |

## Notes
Revision R2 (wave 5) adds g and h and the "Load saved prompt" chip; `saved_prompts` and the picker contract belong to **W-03** (S63–S69, DF-32), so g/h and the chip are **deferred** and hidden (T08) until **W-03-T37** (S68) mounts `SavedPromptPicker` and `SavePromptSheet` in this dock composer and covers g and h at Tier C parity. Approve is the inline E7 ApprovalCard on the same `proposal.approve` API as SHL-10 (open question Q2). DF-04 states added

## Acceptance
SPEC-649's criteria for this screen (T-04 §3); each becomes a test named "<ID> acceptance: <criterion>".
