# AUD-28 · Consultations log

| Field | Value |
|---|---|
| Route and params | `/audits/consultations` and `/audits/$auditId/consultations` (Q-05 §5.1); artboards `/components/screens/AUD-28?st=…` |
| Template and host frame | T9 close-review preset at firm level |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/AUD-28 Consultations log/` |
| Epic and tasks | Q-05 · SPEC-711; Q-05-T01 (TASK-8608); stubs Q-05-T03; screens and live swap per `docs/plan/epics/Q-05.tasks.csv` |
| Manifest status | planned |

Parity tier target: C (Q-05 §5.5). Copy keys live in `apps/web/src/screens/AUD-28/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures` (F-04-T31), never hand-written.

## States
| Letter | Artboard | Scenario | Persona | Clock (CT) | Build | Owner |
|---|---|---|---|---|---|---|
| a | Default · Margaret Okonkwo | `consultations_oct6` | Margaret Okonkwo | Tue Oct 6, 11:30 AM | planned | AY |
| b | Difference of opinion | `consultations_oct6` | Margaret Okonkwo | Tue 6 Oct 2026, 11:30 AM | planned | AY |
| c | Open · C-01 | `consultations_oct6` | Margaret Okonkwo | Tue 6 Oct 2026, 11:30 AM | planned | AY |
| d | Filtered by engagement | `consultations_oct6` | Margaret Okonkwo | Tue 6 Oct 2026, 11:30 AM | planned | AY |
| e | Empty | `consultations_oct6` | Margaret Okonkwo | Tue 6 Oct 2026, 11:30 AM | planned | AY |
| f | New consultation… | `consultations_oct6` | Margaret Okonkwo | Tue 6 Oct 2026, 11:30 AM | planned | AY |
| g | Record conclusion… | `consultations_oct6` | Margaret Okonkwo | Tue 6 Oct 2026, 11:30 AM | planned | AY |

## Deviations
- f and g were added during build (no spec letters).
- Kits drawn inline (C-01…C-04) are rebuilt from the real components; the timeline reads the audit trail.

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen.

| From | To | Status |
|---|---|---|
| Opens SHL-11 · decision card (read-only) | SHL-11 | designed (handoff link graph) |
| Opens AUD-15 · findings register · F-01 | AUD-15 | designed (handoff link graph) |
| Opens AUD-22 · governance communications · AU-C 265 letter | AUD-22 | designed (handoff link graph) |
| Opens AUD-02 · Northwind Robotics 401(k) Plan · PY2025 | AUD-02 | designed (handoff link graph) |
| Opens AUD-12 · testing workspace · revenue | AUD-12 | designed (handoff link graph) |
| Opens AUD-18 · EQR workspace · Oakline | AUD-18 | designed (handoff link graph) |
| Opens AUD-19 · completion checklist · going concern | AUD-19 | designed (handoff link graph) |
