# CLS-08 · Close deliverables · Copperleaf August 2026 statements

| Field | Value |
|---|---|
| Route and params | None yet: fixture mode only. Route `/closes/$closeId/deliverables`. |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/CLS-08 Close - Deliverables - Copperleaf August 2026 statements/` (README.md, spec.md, screenshots) |
| Epic and tasks | C-02 · contract stub C-02-T07 (closes-delivery); design deltas C-02-T10; screen and live swap per `docs/plan/epics/C-02.tasks.csv` |
| Manifest status | planned (this file holds the C-02-T10 design deltas until the screen task writes the full contract) |

## Design deltas (C-02-T10, DEC-5509)
Each row is the frame it amends (an annotated handoff screenshot) and the build answer; none needs a backend change outside the C-02 backlog.

| Frame | Handoff | Build | Why |
|---|---|---|---|
| `screenshots/CLS-08d.png` close pill | Delivered shown alone | Approved shown before Delivered in the release sequence (the reviewer's sign-off inside the dialog) | DF-23; SPEC-701 Q3 |
| `CLS-08c.png` "Entries not posted" | posted only | the precondition accepts posted or Recorded externally | DF-19; SPEC-701 Q6 |
