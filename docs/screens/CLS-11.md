# CLS-11 · GL sync console · Copperleaf · QuickBooks Online

| Field | Value |
|---|---|
| Route and params | None yet: fixture mode only. Route `/closes/ledger-sync?client=`. |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/CLS-11 GL sync console - Copperleaf - QuickBooks Online/` (README.md, spec.md, screenshots) |
| Epic and tasks | C-02 · contract stub C-02-T06 (C20 v2.1); design deltas C-02-T10; screen and live swap per `docs/plan/epics/C-02.tasks.csv` |
| Manifest status | planned (this file holds the C-02-T10 design deltas until the screen task writes the full contract) |

## Design deltas (C-02-T10, DEC-5509)
Each row is the frame it amends (an annotated handoff screenshot) and the build answer; none needs a backend change outside the C-02 backlog.

| Frame | Handoff | Build | Why |
|---|---|---|---|
| `screenshots/CLS-11a.png` Write scope row | "Journal entries · recategorizations · attachments" | "Journal entries · closing date" | W1 v1 writes only JEs and the closing date (ADR-344 §1; SPEC-700 Q2) |
| `CLS-11a.png` Authorized by | Mar 9, 2026 | Mar 9, 2026 is the write grant; the connection is Mar 4, 2026 (POR-16e) | seed contradiction settled (DEC-5508) |
