# SHT-01 · BH-FS-430 Search for Unrecorded Liabilities — sheet

| Field | Value |
|---|---|
| Route and params | /engagements/$engagementId/sheets/$sheetId |
| Template and host frame | T18 Sheet in the audit cockpit (audit bar 59 · toolbar 44 · grid 1376 · status bar 30) + O2 row drawer 480 |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/SHT-01 BH-FS-430 Search for Unrecorded Liabilities - sheet/` |
| Epic and tasks | K-03 · SPEC-721; K-03-T04 (TASK-8803); stubs K-03-T08/T09; build per `docs/plan/epics/K-03.tasks.csv` |
| Manifest status | planned |

Parity tier target: C (K-03 §5.5). Copy keys live in `apps/web/src/screens/SHT-01/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures`, never hand-written.

## States
| Letter | Artboard | Persona | Clock (CT) | Figures that must foot | Build | Owner |
|---|---|---|---|---|---|---|
| a | Default | Cole Hart | Wed Sep 30, 10:15 AM | Wed Sep 30, 10:15 AM · Cole Hart · 40 suggestions not yet adopted · Simone on SURL-12 | planned | AY |
| b | Empty from template | Cole Hart | Thu Sep 24, 10:12 AM | Thu Sep 24, 10:12 AM · created from FS v5 at the 10:05 Board move | planned | AY |
| c | Filled from the sample | Cole Hart | Thu Sep 24, 11:10 AM | Thu Sep 24, 11:10 AM · 40 rows, nothing tested yet | planned | AY |
| d | Agent column running | Cole Hart | Fri Sep 25, 3:20 PM | Fri Sep 25, 3:20 PM · 11 tested · 3 running · 26 waiting | planned | AY |
| e | Row drawer · SURL-05 | Cole Hart | Wednesday 30 September 2026, 10:15 AM CT | The one exception, with its citations | fixture (K-03-T22, `?ov=row:SURL-05`) | AY |
| f | Locked | Cole Hart | Thu Oct 1 | Thu Oct 1 · after Hannah Leclerc’s reviewer sign-off | planned | AY |

## AVOID
gradients in product UI, emoji, saturated blue, heavy shadows, invented colours, lorem ipsum, the words Accrual/Arc/ACME/LSA, Fieldguide and its product names (Field Board, Field Auditor, Field Planner, Field Reviewer, Field Financials, Field Orchestrator, AI Actions, Prompt Library, Agent Knowledge), "task" for a to-do, the agent approving/signing/sending anything, spreadsheet column letters or row numbers, zebra rows, a tinted background on the exception row (chip and flag only), agent values in full ink before adoption, sparkle glyphs instead of the atom, stratum totals that do not foot to 3,698,700.00.

## Deviations (chosen truth)
- T18 reads as T6's sibling: no column letters, row numbers or zebra rows.
- "Open in Excel" downloads a deterministic xlsx; the add-in is W-04. "Link request…" and "Review in package…" render only when K-04's capabilities are on.
- Status bar totals foot: 31 + 8 + 1 + 0 = 40; 3,286,400.00 + 412,300.00 = 3,698,700.00.
- K-03-T22 (DEC-6033): the row drawer is `?ov=row:<rowKey>`, opened from the row's key cell. A live row's Details are its columns; the source-only facts (payment method, invoice number, AP aging) arrive with the sample binding. The Agents tab omits "Auto-started by trigger: …" until K-03-T47's triggers; the Requests tab names requests once K-04 links them; the sources' quotes are withheld (the handoff gives none).

## Walls and agent
- Walled users: 404, absent from lists, no hidden counts (INV-3, DEC-43).
- The agent never publishes, applies, holds, adopts, signs or raises an exception here (INV-1); attribution "‹person› via Agent" (INV-5).

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen (K-03-T11/T12).

| From | To | Status |
|---|---|---|
| tooltip or toast inside kits/SHT01 Sheet | SHT-02 | designed (handoff link graph) |
| tooltip or toast inside kits/SHT01 Sheet | SHT-04 | designed (handoff link graph) |
| tooltip or toast inside kits/SHT01 Sheet | SHL-08 | designed (handoff link graph) |
| tooltip or toast inside kits/SHT01 Sheet | SHL-18 | designed (handoff link graph) |
| tooltip or toast inside kits/SHT01 Sheet | SHL-14 | designed (handoff link graph) |
| tooltip or toast inside kits/SHT01 Sheet | SHL-17 | designed (handoff link graph) |
| tooltip or toast inside kits/SHT01 Sheet | SHL-07 | designed (handoff link graph) |
| tooltip or toast inside kits/SHT01 Sheet | AUD-15 | designed (handoff link graph) |
| tooltip or toast inside kits/SHT01 Sheet | AUD-01 | designed (handoff link graph) |
| tooltip or toast inside kits/SHT01 Sheet | ENG-11 | designed (handoff link graph) |
| tooltip or toast inside kits/SHT01 Sheet | SHT-03 | designed (handoff link graph) |
| tooltip or toast inside kits/SHT01 Sheet | SHL-12 | designed (handoff link graph) |
| tooltip or toast inside kits/SHT01 Sheet | SHL-13 | designed (handoff link graph) |
| tooltip or toast inside kits/SHT01 Sheet | XLA-01 | designed (handoff link graph) |
