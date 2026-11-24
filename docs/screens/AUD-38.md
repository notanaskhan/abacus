# AUD-38 · Hand off audited TB to tax · Granite Peak FY2026

| Field | Value |
|---|---|
| Route and params | sheet over `/audits/$engagementId/tb` (`?ov=handoff`) (T-06 §5.1); artboards `/components/screens/AUD-38?st=…` |
| Template and host frame | O3 sheet (500) over AUD-06; CLS-12 grammar |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/AUD-38 Hand off to tax - Granite Peak FY2026 Final TB  FY2026 Form 1120/` |
| Epic and tasks | T-06 · SPEC-702; gate and contract T-06-T01 (TASK-8510); stubs T-06-T05/T07/T08; screens and live swap per `docs/plan/epics/T-06.tasks.csv` |
| Manifest status | planned |

Parity tier target: C (T-06 §5.4). Copy keys live in `apps/web/src/screens/AUD-38/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures` (F-04-T31), never hand-written.

## States
| Letter | Artboard | Scenario | Persona | Clock (CT) | Build | Owner |
|---|---|---|---|---|---|---|
| a | Ready (both Send blank; 10:29) | `granite-peak-handoff` | Hannah Leclerc | Nov 9, 2026 10:29 AM | built | AY |
| b | Needs review (first open) | `granite-peak-handoff` | Hannah Leclerc | 10:12 AM | built | AY |
| c | Handed off (toast) | `granite-peak-handoff` | Hannah Leclerc | 10:30 AM | built | AY |
| d | Not available (before G8) | `granite-peak-pre-release` | Hannah Leclerc | Oct 21, 2026 | built | AY |
| e | Superseded | `granite-peak-superseded` | Hannah Leclerc | Nov 9, 10:29 AM (illustrative) | built | AY |

## Deviations
- T-06-T45 (DEC-5937): built a–e as the O3 sheet (`?ov=tax-handoff:<auditWorkItemId>`); copy in `screens/AUD-38/copy.ts`; fixtures from the Python slice (`tb_handoff_slice.aud38_rows`, `seed/scenario.aud38.json`). Preview and create stay C12 stubs until T-06-T59, so the manifest reads fixture. Segmented `active={null}` draws b with neither option chosen.
- DV-13: e is built and reachable through the supersede event on staging.
- Plus AUD-06 h (the ··· menu item) on AUD-06's contract.

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen.

| From | To | Status |
|---|---|---|
| tooltip or toast inside kits/AUD38 Tax Handoff | TXP-13 | designed (handoff link graph) |
