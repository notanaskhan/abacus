# CLS-13 · 1099 / W-9 tracker · Copperleaf 2026

| Field | Value |
|---|---|
| Route and params | None yet: fixture mode only. Route `/closes/1099?client=&year=` (alias `/closes/$closeId/1099`). |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/CLS-13 1099 W-9 tracker - Copperleaf 2026/` (README.md, spec.md, screenshots) |
| Epic and tasks | C-02 · contract stub C-02-T07 (closes-delivery); design deltas C-02-T10; screen and live swap per `docs/plan/epics/C-02.tasks.csv` |
| Manifest status | planned (this file holds the C-02-T10 design deltas until the screen task writes the full contract) |

## Design deltas (C-02-T10, DEC-5509)
Each row is the frame it amends (an annotated handoff screenshot) and the build answer; none needs a backend change outside the C-02 backlog.

| Frame | Handoff | Build | Why |
|---|---|---|---|
| `screenshots/CLS-13d.png` actions | e-file wording | "Export IRIS file", "Mark filed", "Record acceptance"; no Transmit | R-04, IRIS-001; SPEC-701 AC-18, AC-19 |
| `CLS-13b.png` channel | "Email the vendor a secure W-9 link" selectable | shown unavailable until R-03's link principal | C-02 §2.4 |
| `CLS-13a.png` vendor row | "Elena Ruiz Design" | kept verbatim; the contamination scan allows the exact vendor string | DEC-5508 |

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen.

| From | To | Status |
|---|---|---|
| Opens CLS-01 · Closes | CLS-01 | designed (handoff link graph) |
| Opens SHL-08 · the signed Form W-9 | SHL-08 | designed (handoff link graph) |
