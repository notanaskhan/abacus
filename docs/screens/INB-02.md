# INB-02 · Attachment triage & File-to

| Field | Value |
|---|---|
| Route and params | Overlay over INB-01: `/inbox?thread=<uuid>&ov=file&message=<uuid>`. Artboards: `/components/screens/INB-02?st=a,a2,b…g` |
| Template and host frame | O3 sheet modal (500) over INB-01 · `Wave 2 - Intake & Admin.dc.html#inb02` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/INB-02 Attachment triage and File-to/` (README.md, spec.md; no revision) · HANDOFF_VERSION 2026-10-21 |
| Epic and tasks | N-01 · contract N-01-T05 (this file); stub T02; classifier and flags T17; triage apply T18; frontend T15; journeys and parity T23–T28 |
| Spec and ADRs | SPEC-380 (Stories 4–6); ADR-005, ADR-050, ADR-210; DEC-24, DEC-37, DEC-79 |
| Flags | `inbox.firm_intake`; `matching.firm_intake` (matcher candidates) |
| Manifest status | live as INB-01's sheet (N-01-T23): `/inbox?thread=…&ov=file&message=…` from the reading header's File… item; fixture artboards with N-01-T15 (DEC-1062) |

Code to come: `src/screens/INB-02/{index.tsx, scenarios.ts, copy.ts, INB-02.test.tsx}`, `src/domain/inbox/{TriageSheet.tsx, AttachmentCard.tsx, DestinationPicker.tsx, FlagRows.tsx, LogIntakeSheet.tsx}`.

## States

INB-02 has 8 artboards. Clock Mon Sep 14, 2026, 9:25 AM CT; viewer Grace Holloway.

| Artboard | Viewer | Clock | Snapshot | Data condition that produces it | Parity tier | Status |
|---|---|---|---|---|---|---|
| a | grace-holloway | 9:25 AM | E0 | Feld message with two attachments: 2025 1095-C top destination the open request "Form 1095-C From Mercer Hill Health" at 0.96, no flags; 2024 copy flags `wrong_year` and `duplicate_hash` (identical hash to Claire_Feld_2024_1095C_MercerHill.pdf received Mar 3, 2025), default Ignore | C report; C lock before M10 | live (T17, T18) |
| a2 | grace-holloway | 9:25 AM | E0 | a with "Rename to" edited, then ✕ → "Discard decisions?" | C report | live (T15) |
| b | grace-holloway | 9:25 AM | E0 | Copperleaf receipt: two candidates 0.61 and 0.58 (`ambiguous_candidates`); Apply disabled until one is chosen | C report | live for request destinations; the close-receipt destination and card-charge candidates are **fixture-only** until C-01-T58 (DV-7) |
| c | grace-holloway | 9:25 AM | E0 | Collins W-2c: `tin_mismatch` (last four 7713 on the form vs 7731 on the client record), severity `force_hold`; decision forced to Hold; "Tell the client" on with the template preview | C report | live (T17, T18) |
| d | grace-holloway | 9:25 AM | E0 | Stein: destination kind `notice` | C report | **fixture-only** until N-04 (DV-7) |
| e | grace-holloway | 9:25 AM | E0 | Northwind census: destination is a PBC request with an accepted version 1 (Aug 28); `possible_replacement`; "Keep both versions" on (OQ-3) | C report | live (T18) |
| f | grace-holloway | 9:25 AM | E0 | Apply returned `{filed: 1, ignored: 1, notified_user_ids: [kevin-osei]}`; the sheet closes onto INB-01 d with the toast | C report | live (T18) |
| g | grace-holloway | 9:25 AM | E0 | Iyer corrected 1099-DIV: `possible_replacement` of Iyer_2025_1099DIV_Halvard.pdf (portal upload Mar 2, 2026); "Supersede earlier" on; the work item is In review | C report | live with DV-8's code-only wording; the CORRECTED tag and box diff wait for P-11 |

Non-artboard states: Flag off (C-20); AI unavailable (DF-04: "AI isn't available for real client data yet"; code suggestions only, DV-16); §7216 agents off (DF-04 second state, DV-16); stale proposal (409 `proposal_changed` → "This changed while you were deciding. Review again."); destination closed or archived (409 `item_closed`, `destination_archived`); withdrawn by the client (409 `attachment_withdrawn`); not allowed (agent, system, client: 403).

## Log received documents (new O3 sheet, DV-1)
Designed from existing kits (O3 Sheet, Fieldset, ValueRow, Segmented sm, Picker chip, FileChip, DateField); no new component. 500 wide, header "Log received documents" with primary "Log {n}".

| Row | Control | Copy |
|---|---|---|
| Files | Drop zone (C-08 FileChip list, ≤ 20, ≤ 50 MB each) | "Drop files or choose…" · helper "PDF, JPG, PNG, HEIC, XLSX, DOCX or CSV · up to 50 MB each" |
| Client | Picker chip, optional | "Client │ Select ⇕" · helper "Leave empty if you're not sure. It waits in Inbox, unmatched." |
| Received via | Segmented sm | "Email" · "Mail" · "Fax" · "In person" · "Other" |
| From | Contact picker or free text | "From │ Select ⇕" |
| Received | DateField | "Received │ {date}" (defaults to today on `kernel.clock`) |
| Subject | Text | "Subject" |
| Note | Textarea, optional | "Note for the team (optional)" |

Footer 11.5 ink-3: "Logged as {viewer}. Files are scanned before they're stored." Errors: `unsupported_media_type` "This file type isn't accepted.", `file_too_large` "This file is over 50 MB.", `scanner_unavailable` "We can't check files right now. Try again in a few minutes."

## API
| Read or write | Endpoint | Shape | Matrix action |
|---|---|---|---|
| read | `GET /v1/inbox/messages/{id}/triage` | per attachment: classification with confidences and citations, top destination and candidates, flags, supersede candidate, defaults, `seen_proposal` ids | `inbox.triage` |
| read | `GET /v1/destinations?client_id&kind&parent&q` | picker tree, nodes re-authorised, closed nodes with a reason code | `inbox.triage` |
| write | `POST /v1/inbox/messages/{id}/triage/apply` | `{decisions[], seen_proposals}` → `{filed, ignored, held, notified_user_ids, undo_grant_id?}` | `inbox.file` · `inbox.triage` · `inbox.ask_client` |
| read | `GET /v1/inbox/attachments/{id}/viewer` | C4 manifest (masked pages) | `inbox.read_content` |

## Status
Flag severities: `info` (olive ✓ row), `block_bulk` (red-tint row), `force_hold` (red-tint row; Decision fixed to Hold). Confidence pills: green-tint ≥ 0.90, amber below, computed by code.

## Copy
| Key | String |
|---|---|
| `sheet.title` | "File attachments" |
| `sheet.subtitle` | "Re: 2025 tax documents · Claire Feld" (template `{subject} · {sender}`) |
| `sheet.apply` | "Apply 2" (template `Apply {n}`) |
| `card.destination` | "Suggested destination" |
| `card.openRequest` | "Open request · Requested Feb 3" (template `Open request · Requested {date}`) |
| `card.alreadyOnFile` | "Already on file" |
| `card.flags` | "Flags" |
| `card.noFlags` | "No flags." (code-composed; form-specific explanations only from extracted fields, DV-9) |
| `flag.wrongYear` | "Tax year 2024 ≠ 2025 (the open return)." |
| `flag.duplicate` | "Duplicate of {file_name} (identical hash, received {date})." |
| `flag.tinMismatch` | "SSN differs from the client record (last four {form_last4} vs {record_last4})" |
| `flag.ambiguous` | "Two charges match this amount; the receipt date is not legible." |
| `flag.replacement` | "Possible replacement for {file_name} ({channel} {date})" (DV-8) |
| `row.supersede` | "Supersede earlier" · helper "No 2025 Form 1095-C on file to replace." |
| `row.keepBoth` | "Keep both versions" |
| `row.renameTo` | "Rename to" |
| `row.decision` | "File" · "Ignore" · "Hold — ask client" |
| `row.reason` | "Reason ⇕" (e.g. "Wrong year · duplicate") |
| `row.tellClient` | "Tell the client" · helper "Off: nothing is sent. Ignored attachments stay in the email record." |
| `footer` | "Accrued Agent classified these attachments at 9:12 AM. Filing is recorded as Grace Holloway. Kevin Osei (preparer) is notified." (template; "Suggested from the file's name and contents" when no matcher ran) |
| `discard.title` | "Discard decisions?" |
| `toast.applied` | "Filed 1 · Ignored 1 · Kevin Osei notified" (template) + "Undo" for 10 s when a client email is queued (DEC-24) |
| `helper.inReview` | "Filing adds a document to the return's Intake and notifies Dina Sato (preparer)." |

## Deviations (N-01 §2.4)
DV-4, DV-7, DV-8, DV-9, DV-16. The Hold email preview line is a database template's rendering, never model text (DEC-79).

## Links
Inbound: INB-01 "File…", "Review →", a thumbnail's status disc. Outbound: SHL-08 (thumbnail, live), FIL-01 (filed destination, live), BND-02, TAX-03, AUD-03 (live as built), NOT-01/NOT-02 and CLS-03 (planned).
| Opens SHL-08 (designed link, handoff link graph) | SHL-08 | as the target's manifest status |

## Parity
| Artboard | Tier | Diff % | Notes |
|---|---|---|---|
| a | C (locked) | — | N-01-T28; write controls masked (Approve, File, Ignore, Reveal and the bulk bar) |
| a2 | C (locked) | — | N-01-T28; write controls masked (Approve, File, Ignore, Reveal and the bulk bar) |
| b | C | — | report |
| c | C | — | report |
| d | C | — | report |
| e | C (locked) | — | N-01-T28; write controls masked (Approve, File, Ignore, Reveal and the bulk bar) |
| f | C (locked) | — | N-01-T28; write controls masked (Approve, File, Ignore, Reveal and the bulk bar) |
| g | C | — | report |
| host | D | — | N-01-T28: O2 popover and O3 sheet, computed styles (e2e/visual/tier-d.spec.ts) |
