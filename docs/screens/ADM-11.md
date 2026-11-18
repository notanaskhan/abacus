# ADM-11 · Quality management dashboard

| Field | Value |
|---|---|
| Route and params | `/settings/quality` (Q-05 §5.1); artboards `/components/screens/ADM-11?st=…` |
| Template and host frame | T11 inside the T12 settings frame |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/ADM-11 Quality management dashboard/` |
| Epic and tasks | Q-05 · SPEC-711; Q-05-T01 (TASK-8608); stubs Q-05-T03; screens and live swap per `docs/plan/epics/Q-05.tasks.csv` |
| Manifest status | planned |

Parity tier target: C (Q-05 §5.5). Copy keys live in `apps/web/src/screens/ADM-11/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures` (F-04-T31), never hand-written.

## States
| Letter | Artboard | Scenario | Persona | Clock (CT) | Build | Owner |
|---|---|---|---|---|---|---|
| a | Default · Margaret Okonkwo | `qm_e0` | Margaret Okonkwo | Mon Sep 14, 9:24 AM | planned | AY |
| b | Office · Denver | `qm_e0` | Margaret Okonkwo | Mon 14 Sep 2026, 9:24 AM | planned | AY |
| c | Agent row expanded | `qm_e0` | Margaret Okonkwo | Mon 14 Sep 2026, 9:24 AM | planned | AY |
| d | Before the first inspection · Feb 2, 2026 | `qm_pre_inspection` | Margaret Okonkwo | Mon 14 Sep 2026, 9:24 AM | planned | AY |
| e | Read-only · Laura Kemp | `qm_e0` | Laura Kemp | Mon 14 Sep 2026, 9:24 AM | planned | AY |
| f | Draft-vs-final accuracy | `qm_e0` | Margaret Okonkwo | Mon 14 Sep 2026, 9:24 AM | planned | AY |

## Deviations
- DV-4: WB-08, WB-13 and INS-02 are planned links (ghost buttons with a tooltip).
- DV-7: 'Update…' opens a small risk-assessment review drawer (undesigned, inferred).
- R2 delta (no new state): 'AI adoption →' link, tile 3 caption with 'Insights →', footer second line, 'Open learned context' on c.

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen.

| From | To | Status |
|---|---|---|
| Opens ADM-01 · Settings home | ADM-01 | designed (handoff link graph) |
| Opens INS-02 · AI adoption | INS-02 | designed (handoff link graph) |
| Opens ADM-02 · People | ADM-02 | designed (handoff link graph) |
| Opens ADM-03 · Offices & teams | ADM-03 | designed (handoff link graph) |
| Opens ADM-06 · Security | ADM-06 | designed (handoff link graph) |
| Opens ADM-04 · AI policy | ADM-04 | designed (handoff link graph) |
| Opens ADM-05 · Consents | ADM-05 | designed (handoff link graph) |
| Opens ADM-09 · Developer | ADM-09 | designed (handoff link graph) |
| Opens ADM-08 · Integrations | ADM-08 | designed (handoff link graph) |
| Opens ADM-10 · Portal | ADM-10 | designed (handoff link graph) |
| Opens ADM-12 · Monitoring | ADM-12 | designed (handoff link graph) |
| Opens ADM-07 · Audit log | ADM-07 | designed (handoff link graph) |
| Opens AUD-28 · Consultations log | AUD-28 | designed (handoff link graph) |
| Opens CLI-08 · Independence & conflicts · Ana Cruz · Northwind 401(k) | CLI-08 | designed (handoff link graph) |
| Opens WB-08 · run history · EBP Audit Workpapers | WB-08 | designed (handoff link graph) |
