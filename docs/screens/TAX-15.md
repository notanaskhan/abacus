# TAX-15 · Planning opportunities · TY2025 portfolio

| Field | Value |
|---|---|
| Route and params | `/tax-returns/planning` (T-08 §5.1); artboards `/components/screens/TAX-15?st=…` |
| Template and host frame | T9 QueueDetailLayout close-review preset under a 52 px strip |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TAX-15 Planning opportunities - TY2025 portfolio/` |
| Epic and tasks | T-08 · SPEC-710; T-08-T01 (TASK-8600); stubs T-08-T04; screens and live swap per `docs/plan/epics/T-08.tasks.csv` |
| Manifest status | fixture (T-08-T32, `/tax-returns/planning`, behind `tax.planning`) |

Parity tier target: C (T-08 §5.5). Copy keys live in `apps/web/src/screens/TAX-15/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures` (F-04-T31), never hand-written.

## States
| Letter | Artboard | Scenario | Persona | Clock (CT) | Build | Owner |
|---|---|---|---|---|---|---|
| a | Default | `planning-e0` | Daniel Reyes | Mon Sep 14, 9:24 AM | fixture (T-08-T32) | AY |
| b | Raised | `planning-feld-raised` | Daniel Reyes | Mon 14 Sep 2026, 9:31 AM | fixture (T-08-T32) | AY |
| c | Accepted → project | `planning-ridgeline-accepted` | Daniel Reyes | Mon 14 Sep 2026, 8:52 AM | fixture (T-08-T32) | AY |
| d | Consent-blocked | `planning-e0` | Daniel Reyes | Mon 14 Sep 2026, 9:24 AM | fixture (T-08-T32) | AY |
| e | Dismissed | `planning-e0` | Daniel Reyes | Mon 14 Sep 2026, 9:24 AM | fixture (T-08-T32) | AY |
| f | Per-return view | `planning-e0` | Daniel Reyes | Mon 14 Sep 2026, 9:24 AM | fixture (T-08-T32) | AY |

## Deviations
- OQ-10: 'Raise with client…' opens an O3 send sheet over message.send until INB-04 (N-03).
- P-25 is not accepted: the send sheet opens on the firm's database template; an agent draft prefills only on a synthetic tenant.
- PRJ-01 is a planned link until T-09; the catalogue's 'draft proposal (ENG-09)' is not built.

## Design deltas (T-08-T02, DEC-5601)
Each row is the frame it amends (a handoff screenshot) and the build answer; no new token or colour is introduced.

| Frame | Handoff | Build | Why |
|---|---|---|---|
| `TAX-15b.png` raise | INB-04 thread composer | O3 send sheet over `message.send` on the firm's "Planning conversation" database template until N-03 lands INB-04 | OQ-10; DEC-79 (P-25 not accepted) |
| `TAX-15d.png` consent banner | amber banner | banner adds the glyph and the words "Consent-blocked"; no outreach control on the row | non-colour risk cue; R-03 |
| composed DF-04 | no frame | planning narrative off: code-templated rationale and talking points labelled "Template" | DF-04; cut item 3 fallback |

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen.

| From | To | Status |
|---|---|---|
| Opens TAX-01 · Tax returns | TAX-01 | designed (handoff link graph) |
| Opens CLI-02 · Jonah & Claire Feld · client record | CLI-02 | designed (handoff link graph) |
| Opens TAX-02 · Jonah & Claire Feld · 2025 Form 1040 | TAX-02 | designed (handoff link graph) |
| Opens SHL-08 · Feld_2025_Donations.pdf · the six receipts lit | SHL-08 | designed (handoff link graph) |
| Opens KNW-02 · Research · OBBBA individual changes for TY2026 · memo v2 | KNW-02 | designed (handoff link graph) |
| Opens INB-04 · thread with Claire Feld | INB-04 | designed (handoff link graph) |
| 8:52 AM, earlier the same morning: Create advisory project… on the accepted cost segregation item opens ENG-03 prefilled | ENG-03 | designed (handoff link graph) |
| Opens TXP-01 · Ridgeline preparer memo · opportunities | TXP-01 | designed (handoff link graph) |
| Opens CLI-05 · Elena Varga · tax profile | CLI-05 | designed (handoff link graph) |

## T-08-T32 deviations (DEC-6038)
- The route is `/tax-returns/planning`. The per-return view (f) is the same screen with a client chip; removing the chip shows the portfolio.
- Queue sub-lines read "client · est. savings" from the server. The handoff's longer sub-lines ("waiting on Owen Calder", "project Scoping") are not in the read.
- "Talking points (draft)" is the planning agent's draft (`talking_points_suggestion_id`). It renders once T-08-T28 or T-08-T29 serve it; until then the band is absent.
- The evidence pane links the 2-Year Comparison (TAX-10) and the preparer memo (TXP-01) and lists the sources. The Schedule A statement and "Same pattern for 14 other clients" wait on reads that carry them.
- Raise with client… is an O3 sheet until INB-04 exists. Its draft sends nothing; only Send does, a person's click.
- The consent banner gives the server's state (half-signed). The envelope's signers and due date are on SIG-02.
- Links wired (link-contract rule 1): TAX-15 → TXP-01 and → CLI-05, and TXP-01's opportunity → TAX-15.

