# ADM-12 · Monitoring & inspections

| Field | Value |
|---|---|
| Route and params | `/settings/monitoring` (Q-05 §5.1); artboards `/components/screens/ADM-12?st=…` |
| Template and host frame | T1 inside the T12 settings frame |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/ADM-12 Monitoring and inspections/` |
| Epic and tasks | Q-05 · SPEC-711; Q-05-T01 (TASK-8608); stubs Q-05-T03; screens and live swap per `docs/plan/epics/Q-05.tasks.csv` |
| Manifest status | planned (built a–g on fixtures at `/settings/monitoring`, Q-05-T23, DEC-5935) |

Parity tier target: C (Q-05 §5.5). Copy keys live in `apps/web/src/screens/ADM-12/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures` (F-04-T31), never hand-written.

## States
| Letter | Artboard | Scenario | Persona | Clock (CT) | Build | Owner |
|---|---|---|---|---|---|---|
| a | Default · Margaret Okonkwo | `qm_e0` | Margaret Okonkwo | Mon Sep 14, 9:24 AM | planned | AY |
| b | Select engagements… | `qm_e0` | Margaret Okonkwo | Mon 14 Sep 2026, 9:24 AM | planned | AY |
| c | Record finding… | `qm_e0` | Margaret Okonkwo | Mon 14 Sep 2026, 9:24 AM | planned | AY |
| d | Conclude evaluation · Dec 14, 2026 | `qm_evaluation` | Margaret Okonkwo | Mon 14 Sep 2026, 9:24 AM | planned | AY |
| e | Empty cycle · 2027 | `qm_e0` | Margaret Okonkwo | Mon 14 Sep 2026, 9:24 AM | planned | AY |
| f | Evaluation concluded | `qm_evaluation` | Margaret Okonkwo | Mon 14 Sep 2026, 9:24 AM | planned | AY |
| g | Finding detail · actions | `qm_e0` | Margaret Okonkwo | Mon 14 Sep 2026, 9:24 AM | planned | AY |

## Deviations
- S53 end pass: the handoff's "Add remediation task…" reads "Add remediation to-do…" (the copy lint bans "task" for a to-do; glossary).
- Q-05-T23 (DEC-5935): built a–g at `/settings/monitoring` behind `quality.management`; copy in `screens/ADM-12/copy.ts`, scenarios in `fixtures/scenarios/ADM-12.ts` over the seed `fixtures/seed/adm12.ts` (footings in `adm12.foot.test.ts`). The plan's nine columns are 84/230/150/70/76/220/70/140/64 = 1,104 px. d's clock reads Dec 14, 2026 (the artboard's label) and its evaluation has no open inspection, so Conclude is enabled there; a, b, c, e and g keep it disabled with "Available once all planned inspections conclude."
- Q-05-T23: tax rows open TAX-02 on the inspection's work item; audit rows wait for AUD-25's route (DV-8). FIL-01 → ADM-12 is unwired (the files drawer has no QM-finding link kind), so the manifest stays planned.
- DV-8: inspection rows open AUD-25 or TAX-02 in read-only inspector mode (banner undesigned, inferred).
- DV-10: ADM-12d renders the P-04 card with 'Reserved to the individual with ultimate responsibility' as its reserved label.
- Tax inspections are labelled 'firm policy under Circular 230 §10.36'.

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen.

| From | To | Status |
|---|---|---|
| Opens ADM-01 · Settings home | ADM-01 | designed (handoff link graph) |
| Opens ADM-02 · People | ADM-02 | designed (handoff link graph) |
| Opens ADM-03 · Offices & teams | ADM-03 | designed (handoff link graph) |
| Opens ADM-06 · Security | ADM-06 | designed (handoff link graph) |
| Opens ADM-04 · AI policy | ADM-04 | designed (handoff link graph) |
| Opens ADM-05 · Consents | ADM-05 | designed (handoff link graph) |
| Opens ADM-09 · Developer | ADM-09 | designed (handoff link graph) |
| Opens ADM-08 · Integrations | ADM-08 | designed (handoff link graph) |
| Opens ADM-10 · Portal | ADM-10 | designed (handoff link graph) |
| Opens ADM-11 · Quality | ADM-11 | designed (handoff link graph) |
| Opens ADM-07 · Audit log | ADM-07 | designed (handoff link graph) |
| Opens AUD-25 · Meridian Tool & Die archived record · read-only inspector mode · AUD-29 activity log | AUD-25 | designed (handoff link graph) |
| Opens TAX-02 · Cedar Hollow Farms 2025 Form 1065 · read-only inspector mode | TAX-02 | designed (handoff link graph) |
| Opens AUD-02 · Sterling Freight 401(k) Plan cockpit · read-only inspector mode · AUD-29 activity log | AUD-02 | designed (handoff link graph) |
| Opens KNW-03 · BH Audit Methodology · EBP v3 · BH-EBP-140 step 8 | KNW-03 | designed (handoff link graph) |
