# TAX-16 · Amendments & administrative adjustment requests

| Field | Value |
|---|---|
| Route and params | `/tax-returns/$returnId/amendments` (T-08 §5.1); artboards `/components/screens/TAX-16?st=…` |
| Template and host frame | T6 in the return frame |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TAX-16 Amendments and administrative adjustment requests/` |
| Epic and tasks | T-08 · SPEC-710; T-08-T01 (TASK-8600); stubs T-08-T04; screens and live swap per `docs/plan/epics/T-08.tasks.csv` |
| Manifest status | planned |

Parity tier target: C (T-08 §5.5). Copy keys live in `apps/web/src/screens/TAX-16/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures` (F-04-T31), never hand-written.

## States
| Letter | Artboard | Scenario | Persona | Clock (CT) | Build | Owner |
|---|---|---|---|---|---|---|
| a | Draft · Yusuf Kaya | `okafor-amendment-e0` | Yusuf Kaya | Mon Sep 14, 9:24 AM | planned | AY |
| b | Approved | `okafor-amendment-approved-sep15` | Yusuf Kaya | Mon 14 Sep 2026, 9:24 AM | planned | AY |
| c | Illinois IL-1040-X | `okafor-amendment-e0` | Yusuf Kaya | Mon 14 Sep 2026, 9:24 AM | planned | AY |
| d | Filed · accepted | `okafor-amendment-accepted` | Yusuf Kaya | Mon 14 Sep 2026, 9:24 AM | planned | AY |
| e | BBA AAR · Vantage Point Realty | `vantage-point-aar` | Yusuf Kaya | Mon 14 Sep 2026, 9:24 AM | planned | AY |
| f | Route for approval… | `okafor-amendment-e0` | Yusuf Kaya | Mon 14 Sep 2026, 9:24 AM | planned | AY |

## Deviations
- OQ-11: b renders at Tue Sep 15, 2026.
- DEC-77: tax lines show engine-imported values or a labelled 'Accrued tie-out (shadow)'.
- DF-08: the TAX-07 'Amend…' entry and the 1065 BBA path are composed from kits (T-08-T02).
- OQ-7: reviewed-year K-1s stay unchanged with a 'Form 8986 statement' note.

## Design deltas (T-08-T02, DEC-5601)
Each row is the frame it amends (a handoff screenshot) and the build answer; no new token or colour is introduced.

| Frame | Handoff | Build | Why |
|---|---|---|---|
| TAX-07 "Amend…" entry | undesigned | an overflow-menu item on TAX-07 for accepted returns only, opening `?ov=amend` with kind and jurisdictions | DF-08 |
| 1065 BBA path | undesigned beyond e | TAX-07 "Amend…" on a BBA 1065 opens the AAR variant (e); the note "BBA partnerships cannot file an amended Form 1065; the AAR is the only route." | DF-08 |
| `TAX-16b.png` clock | rendered Sep 14 | scenario b runs at Tue Sep 15, 2026 | OQ-11; TAX-16 b clock |
| `TAX-16e.png` reviewed-year K-1s | "Superseded (amended K-1)" | unchanged reviewed-year K-1s with a "Form 8986 statement" note until the tax CPA answers | OQ-7 |

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen.

| From | To | Status |
|---|---|---|
| Opens SHL-16 · original vs amendment | SHL-16 | designed (handoff link graph) |
| Opens TAX-09 · export to CCH Axcess | TAX-09 | designed (handoff link graph) |
| Opens TAX-02 · the accepted 2025 Form 1040, read-only, with a Superseded banner | TAX-02 | designed (handoff link graph) |
| Opens SHL-08 · Form 1098 — Lakeview Credit Union · mortgage interest lit | SHL-08 | designed (handoff link graph) |
| Opens FIL-01 · 2025 Form 1040 as filed · read-only PDF | FIL-01 | designed (handoff link graph) |
| Sep 15: Neil Ashcroft approved it; the sync chip reads Ready for export, and Prepare 8879… opens TAX-12 for Ruth and Daniel | TAX-12 | designed (handoff link graph) |
