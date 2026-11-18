# AUD-30 · Post-issuance & subsequent discovery

| Field | Value |
|---|---|
| Route and params | `/audits/$auditId/post-issuance` (Q-05 §5.1); artboards `/components/screens/AUD-30?st=…` |
| Template and host frame | T2 record cockpit with dock |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/AUD-30 Post-issuance and subsequent discovery/` |
| Epic and tasks | Q-05 · SPEC-711; Q-05-T01 (TASK-8608); stubs Q-05-T03; screens and live swap per `docs/plan/epics/Q-05.tasks.csv` |
| Manifest status | planned |

Parity tier target: C (Q-05 §5.5). Copy keys live in `apps/web/src/screens/AUD-30/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures` (F-04-T31), never hand-written.

## States
| Letter | Artboard | Scenario | Persona | Clock (CT) | Build | Owner |
|---|---|---|---|---|---|---|
| a | Under evaluation · Margaret Okonkwo | `post_issuance_jan` | Margaret Okonkwo | Mon Jan 25, 2027, 9:24 AM | planned | AY |
| b | Decided · no action | `post_issuance_jan` | Margaret Okonkwo | Mon 25 Jan 2027, 9:24 AM | planned | AY |
| c | Reissue chosen | `post_issuance_jan` | Margaret Okonkwo | Mon 25 Jan 2027, 9:24 AM | planned | AY |
| d | PI-02 · omitted procedure | `post_issuance_jan` | Margaret Okonkwo | Mon 25 Jan 2027, 9:24 AM | planned | AY |
| e | Archive additions | `post_issuance_jan` | Margaret Okonkwo | Mon 25 Jan 2027, 9:24 AM | planned | AY |
| f | New case… | `post_issuance_jan` | Margaret Okonkwo | Mon 25 Jan 2027, 9:24 AM | planned | AY |

## Deviations
- DV-1: "Locked · WORM" reads "Locked · sealed" (DF-20) unless the SOC 2 auditor accepts WORM.
- DV-5: AUD-30 keeps three case types; the list shows only the types present.
- DV-9: 'Comparison unavailable' is composed (undesigned).
- AUD-23 g goes live through this screen (A-07 DV-9).

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen.

| From | To | Status |
|---|---|---|
| Opens WB-09 · run trace · #4511 | WB-09 | designed (handoff link graph) |
| Opens AUD-25 · locked archive | AUD-25 | designed (handoff link graph) |
| Opens SHL-08 · the corrected certification beside the original | SHL-08 | designed (handoff link graph) |
| Opens ADM-12 · monitoring inspections | ADM-12 | designed (handoff link graph) |
