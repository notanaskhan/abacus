# BND-02 · Binder builder & tracker · Feld 2025 Binder

| Field | Value |
|---|---|
| Route and params | `/binders/$binderId` (P-06 §5.1). `?tab=requests\|questions\|activity`, `?category=<id>`, `?request=<requestItemId>` (the selected row loads the dock). Overlays: `?ov=request:new\|<requestItemId>` opens SHL-14; the SHL-20 card, the O3 follow-up sheet and the O4 "Preview as client" sheet are local state. Artboards: `/components/screens/BND-02?st=a…g` |
| Template and host frame | T2 `RecordCockpit` (rail 330 · canvas 696 · Request dock 330) · `Wave 2 - Home & Records.dc.html#bnd02` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/BND-02 Binder builder and tracker - Feld 2025 Binder/` (README.md, spec.md, revision.md R2; revision wins) · HANDOFF_VERSION 2026-10-21 |
| Epic and tasks | P-06 · contract P-06-T03 (TASK-404); a–f P-06-T12; g and the R2 rows (Linked (n), glyph, dock ScreeningCard) P-06-T22; fixture → live P-06-T16; data P-06-T08; parity P-06-T26 |
| Manifest status | planned (`routes/manifest/bnd.ts`) |

Code to come (P-06 §5.2): `src/domain/requests/` (`RequestRow.tsx`, `CategoryRail.tsx`, `ReturnDialog.tsx`, `FollowUpSheet.tsx`, `ClientPreviewSheet.tsx`, `live.ts`), `src/domain/screening/ScreeningCardHost.tsx`, `src/screens/BND-02/{index.tsx, scenarios.ts, copy.ts, BND-02.test.tsx}`.

## States

7 artboards in the handoff (6 + R2 g), 7 built here.

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | kevin-osei (Kevin Osei, preparer) | Mon Sep 14, 2026, 9:24 AM CT | E0 | Feld 2025 Binder `published`, 5 of 7 satisfied; row 5 has 2 inbox attachments waiting; row 7 has an upload intent of 2 files; row 3 (Ridgeline K-1, `firm_provided`) selected | built · fixture (T12) |
| b | kevin-osei | same | E0 | TY2026 roll-forward: Draft binder created from the Feld 2025 Binder, 7 requests in `draft` | built · fixture (T12) |
| c | kevin-osei | Mon Sep 14, 2026, 9:24 AM CT (data at Sep 15, 9:02 AM) | E0 | Claire Feld marked the binder done Sep 15, 9:02 AM; 7 of 7; the 1095-C filed from the Inbox, the estimate confirmations matched | built · fixture (T12) |
| d | kevin-osei | same | E0 | Thornbury binder: 3 requests past due Aug 31 (derived `overdue`) | built · fixture (T12) |
| e | kevin-osei (README: Paul Thornbury; DV-4) | same | E0 | Thornbury binder: one request with `client_ignored_at` and the reason "Not applicable this year" | built · fixture (T12) |
| f | kevin-osei | same | E0 | Feld binder, row 3 with client visibility off | built · fixture (T12) |
| g (R2) | kevin-osei | Mon Sep 14, 2026, 9:31 AM CT | E0 | Row 7 selected after Claire's two files land: status `uploaded`; screening aggregate `passed`, both checks pass | built · fixture (T22) |

R2 on every state: Linked (n) on each row, the 12 px screening glyph on rows received from the client, and the dock ScreeningCard after "Uploaded Document". Loading: F-05 skeletons in rail, canvas and dock. Not-allowed: a walled or out-of-scope binder answers 404. `client_service` sees file names and request status, never evidence content, screening text or the summary (DEC-20, DV-5). Flag off (`binders.engine`): F-05's flag-off ViewState.

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/binders/{id}` | Record projection: rail KV, categories with counts, publish-bar facts, `allowed_actions` | `binder.read` | every firm engagement role; `client_service` metadata only |
| read | `GET /v1/binders/{id}/requests?category=` | Rows by category: status, client words, screening glyph, Linked (n), due, visibility, tags | `request_item.read` | — |
| read | `GET /v1/binders/{id}/live` | Poll every 5 s while visible: upload intents, inbox "Waiting n", screening running (DEC-23, DV-3) | `request_item.read` | — |
| read | `GET /v1/binders/{id}/client-preview` | POR-03 view-as-client projection for the 1400 preview sheet | `binder.read` | — |
| read | `GET /v1/binders/{id}/activity` | Binder and item audit events (Activity tab) | `activity.read` | — |
| read | `GET …/request-items/{id}/screening` | SHL-20 aggregate for the dock card | `upload_review.read` | `client_service` and client principals 403/404: glyph without text |
| write | `POST /v1/binders/{id}/publish` (+ `/undo`) · `/unpublish {reason}` | "Publish to client…" (b), "Unpublish" (a) | `binder.publish` | partner, manager; senior and `client_service` by firm setting (OQ-1 may add the preparer); 409 `binder_gate_unmet`, 422 `due_date_required`, 422 `reason_required` |
| write | `PUT …/request-items/{id}/client-visibility` | Eye toggle (f) | `request_item.update` | — |
| write | `POST …/request-items/{id}/waive {na_reason, note}` | "Waive (Not applicable)" | `request_item.waive` | partner, manager; Staff does not see the entry |
| write | `POST …/request-items/{id}/return-to-client {note}` | "Return to client…" (e) | `request_item.return` | agent deny |
| write | `DELETE …/request-items/{id}` | "Delete" (never-sent drafts only) | `request_item.update` | 409 `request_already_sent` |
| write | `POST /v1/follow-ups/drafts {request_item_ids[]}` · `POST /v1/follow-ups/{id}/send` | "Send reminder…" (open items only) | `follow_up.draft` · `follow_up.send` | agent deny on send |
| write | `POST …/evidence-versions/{vid}/decision/accept` · `send-back` | Dock "Accept" · "Return…" (g) | `evidence.accept` · `evidence.reject` | staff by `firm_setting(staff_can_accept_evidence)`, seeded on (DEC-37); agent deny |

## Status
`binder`: Draft (neutral) · Published (state) · Unpublished (muted) · Complete (green-tint) · Closed (soon). `request` (DEC-09): `draft` Draft · `requested` ring "Requested" · `uploaded` amber "Uploaded – needs review" · `received` green solid "Received ✓" · `returned` · `not_applicable` · derived `overdue`; client words To do · Done · Ignored. `document.approved` micro "✓ 1" (ink, never green). `evidence_screening` glyph: olive ✓ Passed · amber triangle Flagged · ring Not screened. Row-level states drawn from data: "Draft K-1 · pre-release" (amber, firm-provided draft), "Waiting 2" (amber dot), "Uploading 2 files…" (spinner), "Not published", "Ignored" (muted).

## Copy
Copy keys live in `screens/BND-02/copy.ts`; strings verbatim from spec.md and revision.md.

| Key | String |
|---|---|
| `subbar.back` | "‹ All Binders" |
| `subbar.openReturn` | "Open return ›" |
| `tabs` | "Requests" · "Questions" · "Activity" |
| `rail.title` | "Binder" |
| `rail.keys` | "Published" · "Created from" · "Visible to" · "Marked done" · "Reminders" · "Template" |
| `rail.categoriesBand` | "Categories" |
| `rail.categories` | "Personal & Household Information" · "Income Sources" · "Home & Property" · "Health & Medical" · "Education & Student" · "Retirement" · "Charitable & Donations" · "Business & Self-Employment" · "Other Activity" |
| `rail.open` | "{n} open" |
| `canvas.title` | "Requests" |
| `canvas.preview` | "Preview as client" |
| `canvas.sendReminder` | "Send reminder…" |
| `canvas.newRequest` | "+ Request" |
| `publishBar.published` | "Published Feb 3 · 5 of 7 satisfied · 2 open · last client activity 9:12 AM" |
| `publishBar.unpublish` | "Unpublish" |
| `publishBar.draft` | "Draft · 7 requests from the 2025 return" |
| `publishBar.publish` | "Publish to client…" |
| `publishBar.complete` | "Marked done by Claire Feld · Sep 15, 9:02 AM · 7 of 7" |
| `publishBar.overdue` | "3 overdue" |
| `row.fromPriorYear` | "From 2024 return" |
| `row.requested` | "Requested" |
| `row.notPublished` | "Not published" |
| `row.received` | "Received ✓" |
| `row.k1Draft` | "Draft K-1 · pre-release" |
| `row.k1Pending` | "final pending Ridgeline approval (due Sep 15)" |
| `row.waiting` | "Waiting 2" |
| `row.uploading` | "Uploading 2 files…" |
| `row.uploadedByClient` | "Claire uploaded Aug 7" / "Claire uploaded Sep 14" |
| `row.lateDue` | "Due Aug 31 · 14 days late" |
| `row.ignored` | "Ignored" |
| `row.ignoredReason` | "Not applicable this year — Paul Thornbury" |
| `row.internalOnly` | "Internal only — the client won't see this request." |
| `row.linkedNone` | "—" (R2; "Linked (n)" shows the count) |
| `row.screeningTooltip` | "Evidence screening · Passed · 2 checks" |
| `row.menu` | "Edit" · "Waive (Not applicable)" · "Return to client…" · "Delete" |
| `dock.title` | "Request" |
| `dock.requestCard` | "Document Request"; keys "Request" · "Category" · "Visible to client" · "Requested by" · "Source" · "Client wording" |
| `dock.uploadCard` | "Uploaded Document"; keys "Document" · "Status" · "File" · "Type" · "Summary" · "Uploaded by" |
| `dock.openViewer` | "Open in viewer" |
| `dock.replaceK1` | "Replace with final K-1" |
| `dock.accept` | "Accept" (g) |
| `dock.return` | "Return…" (g) |
| `dock.notScreened` | "Internal handoff from TXP-12 — screening runs on client uploads." |
| `g.uploadedBy` | "Uploaded by Claire Feld · via portal · 9:31 AM" |
| `g.document` | "IRS Direct Pay and New York estimated payment confirmations (2 files)" |
| `g.uploaded` | "Uploaded – needs review" |

The ScreeningCard strings of g ("Evidence screening · 9:31 AM", the two questions and answers, "Draft follow-up", "Rerun", "Screened by Accrued Agent · screener@v3 · 2 s") are SHL-20's copy keys, rendered by the shared C-34 kit; the g answers are revision.md verbatim in fixture mode and code-generated on live data (DV-2). Request titles, file names, rail values, client wording and the K-1 summary are seed data (P-06-T08), copied from spec.md, never from `copy.ts`.

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| "‹ All Binders" | BND-01 `to.BND01()` ("Opens BND-01 · all binders") | planned (P-06-T09) |
| "Open return ›" | TAX-03 ("Opens TAX-03 · return intake") | planned (T-02) |
| "Preview as client" | POR-03 in a 1400 preview sheet ("Opens POR-03 as the client sees it, in a 1400 preview sheet") | planned; P-06 renders the C-16 portal variant from `client-preview` |
| "+ Request", "Edit" | SHL-14 ("Opens SHL-14 · request composer") via `?ov=request:…` | planned (P-06-T13) |
| "Waiting 2" (row 5) | INB-02 ("Opens INB-02 · filing for Claire’s 9:12 AM email") | planned (N-01, S13) |
| Linked (n) | SHL-21 ("Linked fulfilments · opens SHL-21") | planned (K-04; DV-6) |
| Questions tab | BND-03 | planned (T-03); the tab is hidden when no questionnaire exists (spec-level link) |
| "Open in viewer" | SHL-08 | planned (P-03; spec-level link) |
| Rail "Created from" › | TXP-12 / the prior-year return | planned (T-02; spec-level link, DV-9) |
| Screening glyph | the dock ScreeningCard (SHL-20) | in-screen (P-06-T22) |

Inbound: BND-01, TAX-02, TAX-03, TXP-00, CLI-01, CLI-02, ENG-03, ENG-07, BND-03, INB-03, INB-04, FIL-01, TPL-10. All targets are manifest IDs that `link-contract.test.ts` knows.

## Acceptance
- BND-02 acceptance: the canvas cards match `platform-portal.png`: radius 12 section cards on a #F8F8F6 well, padding 8 / gap 8, 44px group headers, gray filled glyphs, green-ink upload receipts; the rail uses the same nine category names, glyphs and olive ticks.
- BND-02 acceptance: the dock cards match `close-intake.png`'s "Document Request" / "Uploaded Document" rows (35px, "Visible to client" toggle, summary paragraph, amber status pill, two-line "Requested by").
- BND-02 acceptance: counts foot: 7 requests = 3 + 1 + 1 + 1 + 1; 5 satisfied (4 Received ✓ + the firm-provided draft K-1) and 2 open; progress 5 / 7 = 71%.
- BND-02 acceptance: the K-1 figures equal 01 §9.4 Jonah Feld (307,900 · 4,600 · 1,550 · 150,000) and Item L 1,912,500 → 1,914,050; the draft never appears on the portal.
- BND-02 acceptance: no digital-asset request or issue exists.
- BND-02 acceptance: "From 2024 return" appears on rows 1–6 only; row 7 was added Sep 1 from the organizer answer.
- BND-02 acceptance (R2): every request row carries Linked (n); open rows show "—".
- BND-02 acceptance (R2): the dock shows a ScreeningCard under the upload card; the internal K-1 handoff reads "Not screened".
- BND-02 acceptance (R2): state g shows two passed checks with the period rule (Apr 2025 – Jan 2026).
- BND-02 acceptance (R2): Accept and Return stay with a person; states a–f are unchanged.

## Figures
| Figure | Foots | Proven by |
|---|---|---|
| Requests | 3 + 1 + 1 + 1 + 1 = 7 | P-06-T08 footing test; P-06-T29 |
| Satisfied | 4 Received ✓ + 1 firm-provided draft = 5; 2 open; 5 / 7 = 71% | same |
| Categories | 9 portal categories | same |
| K-1 (row 3 dock) | 307,900 · 4,600 · 1,550 · 150,000; Item L 1,912,500 → 1,914,050 (+1,550) | same |
| Thornbury (d) | 6 of 15, 3 overdue; Aug 31 + 14 days = Sep 14 | same |
| g | 4 TY2025 installments, Apr 2025 – Jan 2026 | same |
| Linked (n) | rows 1, 2, 3, 4, 6 read 1; rows 5, 7 read "—" | scenario test |

## AVOID
Gradients in product UI, emoji, saturated blue, heavy shadows, invented colors, lorem ipsum, red for client-missing items, checkboxes, showing a draft K-1 as client-visible content, the words Accrual/Arc/ACME. R2: the agent accepting an upload; amounts the seed does not give; changing states a–f; "task" for a to-do.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DV-2 | g: check 2's answer is code-generated on live data ("Yes: dated Apr 15, 2025 – Jan 15, 2026, inside the expected period"); fixture mode shows the handoff copy verbatim | Code computes the period (ADR-050) | P-06 §2.4 |
| DV-3 | a: "Uploading 2 files…" and "Waiting 2" are polled every 5 s while the binder is open, not pushed | DEC-23 polling first | P-06 §2.4 (closes with P-10 SSE) |
| DV-4 | e: viewer is Kevin Osei; the README's "Paul Thornbury" is a client and this is a firm screen | Firm screen | P-06 §2.4 |
| DV-5 | a, g: the "Uploaded Document" summary row renders only when a summary exists, and never for `client_service` | P-11/T-02 produce summaries; DEC-20 | P-06 §2.4 |
| DV-6 | R2: "Linked (n)" shows the count; the click to SHL-21 is a planned link | SHL-21 is K-04's | P-06 §2.4 |
| DV-7 | "Send reminder…" stays the UI word; identifiers say `follow_up` | DEC-74; handoff copy final | P-06 §2.4 |
| DV-9 | Rail "Created from 2024 return (CCH Axcess)" is the seeded `prior_year_source_ref` label; P-06 itself creates from the prior-year binder | CCH bridge is T-01/T-02 | P-06 §2.4 |
| DV-10 | "Open in viewer" opens the existing page preview (`evidence/previews.py`) without the lit region if P-03's viewer is not on staging by S8 | P-03 S5–S12 | P-06 §2.4 |
| — | The spec's C-16 rows are drawn inline (README note); "Preview as client" uses the C-16 portal variant | README build detail | P-06 §5.3 |
| — | "Replace with final K-1" stays disabled until T-02 releases the K-1 package (TXP-12) | T-02 | P-06 §2.1 |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a–g | C (threshold 0.20, maxDiffPixelRatio 3 %) | not run (unbuilt) | locked (blocking) at the end of S10; mask the "Uploading" spinner |
| host | D | — | toolbar 46, subbar 42, pane header 46 with a 14.5/500 title, rows 38/44, pills 21/19/18, radius 12, card 420, drawer 480, sheet 500 |

## Open gaps
- README "Rendered" says 9:24 AM for g; revision.md says 9:31 AM. Revision wins (DEC-15 precedence): the g scenario clock is 9:31 AM.
- c's data is dated Sep 15, 9:02 AM while the artboard renders at the E0 clock; the scenario keeps E0 and seeds the mark-done stamp at Sep 15, 9:02 AM as the handoff draws it.
- "Publish to client…" in b: whether the return's preparer may publish a tax binder is P-06 OQ-1 (recommended: `binder.publish` adds `function_in(preparer)` on `tax_return` binders), decided with the C5 stub (P-06-T01). Fixture mode renders the control as designed; live mode follows `allowed_actions`.
- Persona `kevin-osei` is added to the scenario by P-06-T08 if F-04 has not.
