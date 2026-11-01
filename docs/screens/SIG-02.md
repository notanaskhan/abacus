# SIG-02 · Envelope builder

| Field | Value |
|---|---|
| Route and params | O4 full sheet over SIG-01 or its source screen: `?ov=envelope:<uuid>` (the overlay registry's arg form, `routes/firm/envelope.tsx`; N-02-T21). Artboards: `/components/screens/SIG-02?st=a…g` |
| Template and host frame | O3 sheet (wide) with document preview and field placement · `Wave 2 - Intake & Admin.dc.html#sig02` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/SIG-02 Envelope builder - Form 8879-PE - Harborview/` · HANDOFF_VERSION 2026-10-21; DF-12 applied (fields placed with provider tagging) |
| Epic and tasks | N-02 · contract T05; stub T03; builder T20, T21, T30; dated letters T31; parity T40 |
| Spec and ADRs | SPEC-381 AC-7, AC-8, AC-16; ADR-149, ADR-161 |
| Flags | `signatures.envelopes`; sends behind `signatures.esign_provider` and, for the 8879 family, `signatures.kba_8879` |
| Manifest status | built on C7's draft, field placement and send (N-02-T20/T21/T30, DEC-1174, DEC-1178, DEC-1374), opened as the O4 sheet from SIG-01 (`?ov=envelope:`); no path of its own. `live` with SIG-01 |

## States
Clock Mon Sep 14, 2026, 9:40 AM CT.

| Artboard | Viewer | Data condition | Parity tier | Status |
|---|---|---|---|---|
| a | grace-holloway | (built · fixture, T21) Harborview 8879-PE draft, ready; line 4 traces to the exported Schedule K; identity KBA (policy `efile_authorization`) | C report; C lock before M10 | live with T22 (send needs `signatures.esign_provider`) |
| b | grace-holloway | Joint 8879 (Feld) from TAX-12: parallel signers, each with KBA | C report | live with T25 |
| c | grace-holloway | Rep letter (Northwind) from AUD-21, `date_as_of_mode = report_date` | C report | live with T31 |
| d | grace-holloway | Notice response (Whitley) from NOT-03 | C report | **fixture-only** until N-04 registers the `notice_response` source |
| e | grace-holloway | (built · fixture, T21; the viewer is the sender, not Owen Calder) Engagement letter Ridgeline E13: Owen signs, Daniel Reyes countersigns | C report | live with T28 |
| f | grace-holloway | Validation: Sofia Lindqvist has no email; Send disabled | C report | built · fixture (T21); live with T20 |
| g | grace-holloway | Sent: the sheet closes; SIG-01 Out gains the row; Undo for 10 s (ADR-161) | C report | live with T22 |

Non-artboard: agent-drafted envelope (the draft shows "{person} via Agent"; Send is a person's, AC-16); flag off (C-20).

## Copy (key strings)
| Key | String |
|---|---|
| `header.send` | "Send" (human-only control; never on an agent-owned surface) |
| `toast.sent` | "Sent to {names}" + "Undo" (10 s) |
| `validation.noEmail` | "{name} has no email on file." |
| `identity.kba` | "Identity questions (KBA)"; no SMS option exists for the 8879 family |
| `dated.reportDate` | "Dated as of the report date" |

## Deviations (N-02-T46)
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| D1 | page previews are the evidence viewer's masked pages, not the provider's | C4 masked viewer | DEC-1181 |
| D2 | signer reorder and field placement by keyboard are not built (their keyboard suite is fixme); the mouse paths are | N-02-T43 | DEC-1672 |
| D3 | b, c, d and g have no built artboard yet | N-02-T21 | DEC-1174 |

Every deviation above is closed: each has its decision recorded (N-02-T46, 2026-11-01).

## Links
Inbound: SIG-01, TAX-12, AUD-21, NOT-03, ENG-04 Send. Outbound: SIG-01, SHL-08.

## Built in N-02-T21 (DEC-1174)
Code: `src/domain/signatures/{builder.ts,index.ts}`, `src/screens/SIG-02/{index.tsx,copy.ts,scenarios.ts,SIG-02.test.tsx}`, `src/fixtures/{seed/envelopes.ts,scenarios/SIG-02.ts}`.
Contract additions (additive, defaults): `SignerOut.title`, `SignerOut.email`, `DraftUpdateIn.document_order`, `ValidationOut.checks[{code, ok}]`; `problems` carry `signer_email_missing:<signer_id>`.
Open: field placement by clicking the preview and the purple trace outline on traced values need placement and trace regions in the contract (T30); the document sub-lines ("Generated from CCH Axcess · …") need a document subtitle the contract doesn't carry; the header's Draft pill waits on FullSheet taking a meta slot.
