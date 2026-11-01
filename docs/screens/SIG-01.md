# SIG-01 · Signatures hub & evidence drawer

| Field | Value |
|---|---|
| Route and params | `/signatures` (nav "Signatures"); `?tab=to_send|out|completed|expired`, `?envelope=<uuid>` opens the O2 evidence drawer, `?ov=import` opens Import signed package (SIG-01 r, DF-12). Artboards: `/components/screens/SIG-01?st=a…g,r` |
| Template and host frame | T1 list with tiles + O2 drawer · `Wave 1 - Workbench & Ops.dc.html#sig01` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/SIG-01 Signatures hub - evidence drawer/` (README.md, spec.md) · HANDOFF_VERSION 2026-10-21; DF-11 and DF-12 applied |
| Epic and tasks | N-02 · contract N-02-T05 (this file); stub T03; import T08; hub and drawer T11, T13; evidence T14; reminders T14, T28; wet signature T27; parity T40 |
| Spec and ADRs | SPEC-381 AC-1..AC-6, AC-11, AC-16; ADR-149 |
| Flags | `signatures.envelopes` (hub, import); `signatures.esign_provider` (provider rows and sends) |
| Manifest status | routed at `/signatures` (DEC-1582) and reading C7 live (N-02-T13, DEC-1055); manifest `planned` only until its designed links are all wired (as ENG-02). `live` for a firm is its `signatures.esign_provider` flip after RB-18's staging rehearsal (M11 letters, M13 8879s) |

## States
Clock E0, Mon Sep 14, 2026, 9:24 AM CT; viewer Grace Holloway (Firm Admin, `client_service` on the envelopes she handles, DEC-20).

| Artboard | Viewer | Data condition | Parity tier | Status |
|---|---|---|---|---|
| a | grace-holloway | Out for signature; E2 drawer: Irene Kowal `verification_failed` after three KBA attempts → "Needs a handwritten signature" with "Upload signed 8879…" (DF-11); "1 of 2 signed"; e-file waits on both spouses | C report; C lock before M10 | live (T13 drawer; T27 wet signature); provider rows from `signatures.esign_provider` (T18+) |
| b | grace-holloway | To send: two drafts, Harborview's 8879-PE and an agent-drafted Form 2848 (drafted "via Agent"; Send is Grace's) | C report | live (T13) |
| c | grace-holloway | Completed, last 30 days, with what each unblocked (G3, e-file) | C report | live (T13; record-mode rows from T08) |
| d | grace-holloway | Expired: an optional consent left to expire | C report | live (T28) |
| e | grace-holloway | Declined, with the signer's reason | C report | live (T28) |
| f | grace-holloway | E5, E8, E9 checked; the reminder is a template preview a person sends | C report | fixture (T15, DEC-1057); live (T28) |
| g | grace-holloway | Empty To send | C report | live (T13) |
| **r (added, DF-12)** | grace-holloway | Import signed package sheet: files, signer facts (name, signed date, identity method), provider name, attestation checkbox; Import writes a `record` envelope, Completed | report-only (no artboard; DF-12 design) | live (T08) |

Non-artboard: walled (no row, no count, 404 on id); metadata-only firm admin outside the envelope's engagement (rows without document previews); flag off (C-20; record-mode rows only once `signatures.envelopes` is on and `signatures.esign_provider` off); error and loading (F-05 ViewStates).

## Status
`envelope` codes (draft, sent, viewed, "{signed} of {total} signed", completed, declined, expired, voided); `envelope_signer` (Waiting, Viewed, Signed, Declined, "Needs a handwritten signature"). **Superseded marker:** a completed 8879 superseded by an amount change (DEC-85) shows a muted "Superseded" micro-pill with the `letter`/`envelope` superseded word.

## Copy (key strings; DF-11 text pending counsel)
| Key | String |
|---|---|
| `tabs` | "To send" · "Out for signature" · "Completed" · "Expired" |
| `drawer.evidence` | "Evidence" |
| `drawer.ipMasked` | "IP {masked}" + "Reveal (logged)" |
| `df11.needsHandwritten` | "Needs a handwritten signature" **(pending counsel)** |
| `df11.upload` | "Upload signed 8879…" **(pending counsel)** |
| `import.title` | "Import signed package" |
| `import.attest` | "I confirm these documents were signed by the people listed, on the dates shown." **(pending counsel)** |
| `remind.preview` | "Preview reminder" · "Send {n} reminders" |
| `empty.toSend` | "Nothing to send." |

## Deviations (N-02-T46)
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| D1 | DF-11 copy for a locked identity check reads "Needs a handwritten signature"; the counsel-approved wording replaces it as database content | DF-11 | DEC-1055 |
| D2 | f and r as built (the Out tab's check column; the import's states) | N-02-T15 | DEC-1057 |
| D3 | the provider frame, signature images and DF-11 copy are masked at Tier C | N-02-T43 | DEC-1672 |

Every deviation above is closed: each has its decision recorded (N-02-T46, 2026-11-01).

## Links
Inbound: SHL-01 nav, HOME-01 `signatures_out` tile, TAX-12, AUD-21, NOT-03. Outbound: SIG-02 (drafts), SHL-08 (documents), FIL-01 (signed copies), ENG-04.
| Opens SIG-02 · envelope builder (designed link, handoff link graph) | SIG-02 | as the target's manifest status |
| Opens INB-03 with the firm reminder template (designed link, handoff link graph) | INB-03 | as the target's manifest status |
| Opens TAX-02 · return overview (designed link, handoff link graph) | TAX-02 | as the target's manifest status |
| Opens ENG-02 · engagement record (designed link, handoff link graph) | ENG-02 | as the target's manifest status |
| Opens AUD-02 · audit cockpit (designed link, handoff link graph) | AUD-02 | as the target's manifest status |
| Opens NOT-02 · notice workspace (designed link, handoff link graph) | NOT-02 | as the target's manifest status |

