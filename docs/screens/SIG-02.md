# SIG-02 · Envelope builder

| Field | Value |
|---|---|
| Route and params | O3 sheet over SIG-01 or its source screen: `?ov=envelope&envelope=<uuid>`. Artboards: `/components/screens/SIG-02?st=a…g` |
| Template and host frame | O3 sheet (wide) with document preview and field placement · `Wave 2 - Intake & Admin.dc.html#sig02` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/SIG-02 Envelope builder - Form 8879-PE - Harborview/` · HANDOFF_VERSION 2026-10-21; DF-12 applied (fields placed with provider tagging) |
| Epic and tasks | N-02 · contract T05; stub T03; builder T20, T21, T30; dated letters T31; parity T40 |
| Spec and ADRs | SPEC-381 AC-7, AC-8, AC-16; ADR-149, ADR-161 |
| Flags | `signatures.envelopes`; sends behind `signatures.docusign` and, for the 8879 family, `signatures.kba_8879` |
| Manifest status | planned; `fixture` with T20; `live` with T22 |

## States
Clock Mon Sep 14, 2026, 9:40 AM CT.

| Artboard | Viewer | Data condition | Parity tier | Status |
|---|---|---|---|---|
| a | grace-holloway | Harborview 8879-PE draft, ready; line 4 traces to the exported Schedule K; identity KBA (policy `efile_authorization`) | C report; C lock before M10 | live with T22 (send needs `signatures.docusign`) |
| b | grace-holloway | Joint 8879 (Feld) from TAX-12: parallel signers, each with KBA | C report | live with T25 |
| c | grace-holloway | Rep letter (Northwind) from AUD-21, `date_as_of_mode = report_date` | C report | live with T31 |
| d | grace-holloway | Notice response (Whitley) from NOT-03 | C report | **fixture-only** until N-04 registers the `notice_response` source |
| e | owen-calder | Engagement letter Ridgeline E13: Owen signs, Daniel Reyes countersigns | C report | live with T28 |
| f | grace-holloway | Validation: Sofia Lindqvist has no email; Send disabled | C report | live with T20 |
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

## Links
Inbound: SIG-01, TAX-12, AUD-21, NOT-03, ENG-04 Send. Outbound: SIG-01, SHL-08.
