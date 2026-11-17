# CLS-07 · Adjustments and thresholds · Copperleaf August 2026

| Field | Value |
|---|---|
| Route and params | None yet: fixture mode only. Route `/closes/$closeId/adjustments` (C-02 §5.1). |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/CLS-07 Adjustments and thresholds - Copperleaf August 2026/` (README.md, spec.md, screenshots) |
| Epic and tasks | C-02 · contract stub C-02-T06 (C8 v2); design deltas C-02-T10; screen and live swap per `docs/plan/epics/C-02.tasks.csv` |
| Manifest status | planned (this file holds the C-02-T10 design deltas until the screen task writes the full contract) |

## Design deltas (C-02-T10, DEC-5509)
Each row is the frame it amends (an annotated handoff screenshot) and the build answer; none needs a backend change outside the C-02 backlog.

| Frame | Handoff | Build | Why |
|---|---|---|---|
| `screenshots/CLS-07c.png` row state | no Rejected row | a Rejected row: soon pill "Rejected", the reason, and the CLS-06 issue link | DF-23; SPEC-700 AC-11 |
| `CLS-07g.png` footer | implies posting for the attest client | no Post control at all; "Send to client for approval…" only; rows read "Client approved" then "Recorded by ‹client›" | DEC-69, ADR-344 §4 |
| `CLS-07a.png` primary without W1 | "Post 4 approved…" | "Export approved entries…" when `posting_enabled` is off; rows reach "Recorded in ledger" | DF-19; SPEC-700 AC-20 |
| `CLS-07f.png` | "Accepted by Policy" sub-line | fixture-only frame in `/components`; never live | DEC-53, ADR-187 |
