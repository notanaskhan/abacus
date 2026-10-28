# POR-03 · Documents (Feld 2025 Binder)

| Field | Value |
|---|---|
| Route and params | `/documents` in the portal entry (DEC-59: origin root of `<slug>.<neutral-portal-domain>`); `?binder=<binder id>` (default the newest binder the contact can see), `?filter=requested\|all\|uploaded_by_me\|needs_follow_up` (default `requested`), `?category=<category code>`; `?period=` for a close binder belongs to POR-11 (C-01). Same path P-08-T07 mounted the legacy `ClientEngagement.tsx` on; R-01-T18 removed that page (DEC-443). Artboards: `/components/screens/POR-03?st=a…i`, `?st=c2`, `?st=motion` (`&static=1` freezes it) and `?st=M` |
| Template and host frame | T7 split (F-05 `PortalLayout variant="split"`: rail 336 + documents 1030) with `PortalToolbar` (Documents active); T7-M (`variant="mobile"`, `MobileTabBar`) at 390; finalises specimen TPL-07 · `Wave 1 - Client Portal.dc.html#por03` |
| Surface | portal (white-labelled: the firm's mark, name and people; nowhere "Accrued") |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/POR-03 Documents - Feld 2025 Binder/` (README.md, spec.md; no revision.md) · HANDOFF_VERSION 2026-10-21 |
| Epic and tasks | R-01 · contract R-01-T03; contract stub R-01-T01 (C5 section `portal-pbc`); consumer tests R-01-T02; fixtures R-01-T05; part 1 (a, c, e, f, g, h, rail, filter, ignore, Mark as Done, Withdraw) R-01-T06; read model R-01-T07; ignore note and undo R-01-T08; drop sort R-01-T09 (N); part 2 (b, motion, c from polling, c2, d, i, M, live swap) R-01-T10; scenario slice R-01-T11; live swap and legacy retirement R-01-T18; parity and accessibility R-01-T31; "Upload something else" and c2 live R-01-T33 |
| Manifest status | planned in `routes/manifest/por.ts` (see Part 2 notes): all twelve artboards render in the gallery on fixtures (R-01-T06, TASK-1045; R-01-T10, TASK-1220), and R-01-T10 mounts the screen at the portal's `/documents` with POR-02's "Go to Documents →" and "Open binder" wired through the portal entry (DEC-347) |

Code to come (R-01 §5.2): `src/screens/POR-03/{index.tsx, scenarios.ts, copy.ts, POR-03.test.tsx}`, `src/domain/portal/{documents.ts, drops.ts, messages.ts}`, `src/routes/portal/documents.tsx`, `src/fixtures/handlers/portal-documents.ts`, `src/fixtures/seed/portal-documents.ts`.

**White label (AGENTS frontend rule 7, DEC-01, ADR-133, DEC-59).** Portal code never renders "Accrued": not in copy, `title`, alt text, aria labels or bundle strings. The toolbar's mark and name come from `GET /v1/portal/branding`. Nothing on the page names the agent, a confidence figure, a match percentage or a firm status word: a code-rule link reads "Suggested — Brightwater Hale will confirm" (DEC-58 a), never "Matched 94%". No bell (DEC-58 d).

## States

Fixture scenarios (R-01-T05, `fixtures/scenarios/POR-03.ts`, data in `fixtures/seed/portal-documents.ts`), footed by `fixtures/portal-documents.foot.test.ts` (21 = 19 + 2 = Intake 2; 37 sorted).

12 artboards in the handoff (a–i; the sub-states motion and c2; M at 390), 12 built here.

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | claire-feld (Claire Feld, taxpayer, Feld household) | Mon Sep 14, 2026, 9:24 AM CT | E0 | Feld 2025 Binder published: 21 requests, 19 done (received, uploaded or firm-provided), 2 requested (1095-C, estimated payments); two upload intents at 64% and 38%; filter `requested` shows the 7 groups with activity | fixture (T06) |
| motion | claire-feld | same | E0 | A three-file drop in flight: packet of 3 chips and the "3 files" badge → espresso ring → rows reveal 135 ms apart → c and d. `?static=1` and `prefers-reduced-motion` freeze at the sorted frame | fixture (T10, built) |
| b | claire-feld | same | E0 | Three files dragged over the list (drag over the documents pane or the DropZone): list on `--nested` with the 2 px espresso inset ring | fixture (T10, built) |
| c | claire-feld | same | E0 | Drop batch sorted: the two estimated-payment files are `rule_linked` to their request (receipt kind `rule_linked_pending`), Other Activity ticks, the 1095-C stays requested, Mark as Done tonal | fixture (T06 static; T10 from drop polling, built) |
| c2 | claire-feld | **Mon Sep 14, 2026, 9:12 AM** (README clock, the time of the email) | E0 | INB-02 filed Claire's 9:12 AM email to the 1095-C (channel `email`, receipt kind `emailed`): no Withdraw, Health & Medical ticks, Mark as Done olive | fixture only until N-01 files email (T10, built; live T33) |
| d | claire-feld | Mon Sep 14, 2026, 9:24 AM CT | E0 | `Scan_0914.pdf` had no decisive match (drop outcome `waiting`): the card "Brightwater Hale will sort this" | fixture (T10, built) |
| e | claire-feld | same | E0 | Binder `complete` with `marked_done_by_contact` Claire Feld at Sep 14: the green-tint banner with Undo | fixture (T06) |
| f | claire-feld | same | E0 | Ignore pill on the 1095-C pressed: O1 popover with the three reasons and the optional note | fixture (T06) |
| g | claire-feld | same | holdout | Alternate path, not the seeded day: Claire uploaded the 2024 1095-C in the portal and Kevin Osei returned it with reason `wrong_year` and a client-visible note | fixture (T06) |
| h | claire-feld | same | E0 | Filter `requested` matches nothing (no requested item is client-visible) | fixture (T06) |
| i | dana-kowalski (Dana Kowalski, plan administrator, Northwind Robotics 401(k) Plan) | same | E0 | Northwind "PY2025 Audit requests" binder (24 requests): only Dana's own client-visible requests, in folder bands with 18 px discs; delegations to Keystone, Harborline, PayGrid and Summit name only the organisations | fixture (T10, built) |
| M | claire-feld | same | E0 | Viewport 390 × 844: the binder of a in T7-M, "2 to do" pill, sticky Mark as Done above the tab bar | fixture (T10, built) |

Personas: `claire-feld` and `dana-kowalski` exist in the TS seed (P-08-T08); none is added for this screen.

Non-artboard states (data conditions, never an `st` prop):

| State | Data condition | Rendering |
|---|---|---|
| Loading | `GET /v1/portal/binders/{id}` pending | skeleton drawn from tokens (the kit's product-word ViewState is not used in the portal bundle, DEC-196), status label "Loading" |
| Error | the binder read fails | C-20 `ErrorRow` with the portal line (as POR-02) |
| Binder not found | `?binder=` names a binder outside the contact's scope, a draft or a forged id: `404` | not-found (same as any unknown id; INV-4) |
| Closed binder | the picker's "2024 Binder (closed)" | read-only: no DropZone, Upload…, Ignore, Withdraw or Mark as Done (`allowed_actions` empty) |
| Third party | Sam Ortiz opens `/documents` | `404`; the SPA lands on POR-14 (`/requests`) |
| Upload refused | `413 file_too_large` / `415 type_not_allowed` | the upload row reads the fixed words in `domain/portal/messages.ts` (R-01-T09 writes them; see Open gaps) |
| Undo refused | `409 firm_already_acted` | Undo absent from `allowed_actions`; a stale click reads the fixed message from `messages.ts` |
| Flag off | none since R-01-T18 retired `portal.documents_v2` (DEC-510) | the routes are served to every firm; a 404 now means only a binder or request outside the caller's grant, which the screen shows as its load error, as before. The legacy `ClientEngagement.tsx` was removed by R-01-T18 (DEC-443) |
| Drop sort off | `portal.drop_sort` false for the firm | every dropped file takes the d path |

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/portal/binders?scope_id=` | Binder picker: `items[{id, title, year, closed, read_only}]` for every binder the contact can see | `portal.documents.read` · `scope_only` | client roles on the scope; `third_party` denied (room only); every firm role and the agent deny |
| read | `GET /v1/portal/binders/{id}?filter=&category=` | `PortalBinderOut`: `binder {id, title, closed}`, `categories[{code, label, complete, requested}]` (code-computed: every request done or ignored), `groups[{code, label, rows[]}]` (or `bands[]` with discs for the audit variant), rows `{id, title, kind ∈ request\|firm_provided\|provided_by_connection, client_status ∈ to_do\|done\|ignored\|returned, files[], receipt {kind, by_contact?, at}, returned {reason_code, note, by, at}?, uploading_count, allowed_actions[]}`, `open_count`, `mark_done {state ∈ tonal\|ready\|marked, marked_at?, marked_by?}`, `other_parties[]` (organisation names; admin grants only), `upload_intents[]`, `allowed_actions[]` | `portal.documents.read` · `scope_only` | `allowed_actions` from the vocabulary `upload`, `ignore`, `undo_ignore`, `withdraw`, `mark_done`, `undo_mark_done`, `comment`; empty for a closed binder |
| write | `POST /v1/portal/binders/{id}/drops` (raw body per file; `X-Drop-Batch`; `Idempotency-Key`) | stores a dropped file in the engagement inbox for sorting; `202 {batch_id, file_id}` | `evidence.upload` | client roles with `upload` on the binder |
| read | `GET /v1/portal/drops/{batch_id}` | per-file outcome `rule_linked {request_item_id}` · `waiting` · `duplicate_flagged` · `refused {code}` | `portal.documents.read` | the dropper |
| write | `POST /v1/engagements/{eid}/request-items/{id}/uploads` (existing) | per-request upload from "Upload…" | `evidence.upload` | `upload` |
| write | `POST /v1/portal/request-items/{id}/upload-intents` (P-06) | "Uploading 2 files…" | `evidence.upload` | `upload` |
| write | `POST /v1/portal/request-items/{id}/ignore {reason, note?}` (P-06; R-01 additive `note`) | `IgnoredOut`; the note becomes a shared comment with origin `ignore_note` | `request_item.ignore` | `ignore` |
| write | `POST /v1/portal/request-items/{id}/ignore/undo` | compensating `request_item.ignore_undone`; `409 firm_already_acted` | `request_item.ignore` | `undo_ignore` until the firm acts (DEC-24) |
| write | `POST /v1/engagements/{eid}/evidence-versions/{vid}/withdraw` (P-06; P-31) | voids and hides an unaccepted own upload; `409 evidence_accepted` | `evidence.withdraw` | `withdraw` only on the contact's own unaccepted uploads (never on emailed or accepted files) |
| write | `POST /v1/portal/binders/{id}/mark-done` (P-06) | binder → `complete` with `marked_done_by_contact/at` | `binder.mark_done` | `mark_done` |
| write | `POST /v1/portal/binders/{id}/mark-done/undo` | compensating `binder.mark_done_undone`; `409 firm_already_acted` | `binder.mark_done` | `undo_mark_done` until the firm returns or sends a request |

One read model serves POR-02, POR-03 and TAX-03, so `open_count` 2 = POR-02 "Upload 2 documents" = TAX-03 "Intake 2". No response field carries a firm status code ("Uploaded – needs review", "Received ✓"), an amount, a confidence, a screening verdict, an agent name or another client's data (R-01-T02 contract tests; R-01-T20 security cases).

## Status
Status objects shown, from `docs/product/status-vocabulary.yaml`, always in their `client_label` wording:
- `request` `requested` → "To do" (empty ring disc in i; outline File glyph and Upload… in the list).
- `request` `uploaded` and `received` → "Done" (receipt line with the 13 px olive disc; the firm words "Uploaded – needs review" and "Received ✓" never reach the portal).
- `request` `not_applicable` and a client ignore (`client_ignored_at`, status stays `requested`) → "Ignored" ("Marked not applicable · Sep 14" with Undo).
- `request` `returned` → "Returned" (red-tint pill "Returned · wrong year", the only red besides overdue).
- `request` `overdue` (derived) → red-tint, never stored.
- `binder` `complete` with the `mark_as_done` context → the banner "Marked done Sep 14 · Brightwater Hale will review your documents"; the firm side reads "Marked done by Claire Feld" (BND-02, TAX-03).
- Category complete → 19 px olive disc with a white check (code rule: every request done or ignored).

## Copy
Copy keys live in `screens/POR-03/copy.ts`; every string below is verbatim from spec.md and the built artboards. Names, files and dates are seed data (R-01-T05).

| Key | String |
|---|---|
| `nav` | "Home" · "Documents" · "Questions" · "Sign" · "Messages" · "Deliverables" |
| `rail.binder` | "2025 Binder" (template `{year} Binder`); picker rows "2025 Binder" · "2024 Binder (closed)" |
| `drop.title` | "Documents" |
| `drop.body` | "Drop your files and they'll be automatically sorted into the right categories" |
| `rail.uploading` | "Uploading" |
| `rail.categories` | "Categories" |
| `category.*` | "Personal & Household Information" · "Income Sources" · "Home & Property" · "Health & Medical" · "Education & Student" · "Retirement" · "Charitable & Donations" · "Business & Self-Employment" · "Other Activity" |
| `category.nothingRequested` | "Nothing requested" (hover on a category with no request) |
| `pane.title` | "Documents" |
| `filter` | "Requested" · "All" · "Uploaded by me" · "Needs follow-up" |
| `action.uploadElse` | "Upload something else" |
| `action.markDone` | "Mark as Done" |
| `row.upload` | "Upload…" |
| `row.ignore` | "Ignore" |
| `row.uploadingN` | "Uploading 2 files…" (template `Uploading {n} files…`) |
| `receipt.emailed` | "Received by email Aug 3" (template `Received by email {date}`) |
| `receipt.uploaded` | "You uploaded Aug 7" (template `You uploaded {date}`) |
| `receipt.otherContact` | "Jonah uploaded Aug 5" (template `{first_name} uploaded {date}`) |
| `receipt.suggested` | "Suggested — Brightwater Hale will confirm" (DEC-58 a; replaces the design's "Matched to this request") |
| `row.firmProvided` | "Brightwater Hale prepares this K-1 and adds it for you. Nothing to upload." |
| `row.providedByConnection` | "Provided from your accounting system" (DEC-58 f; no artboard) |
| `sort.title` | "Brightwater Hale will sort this" |
| `sort.body` | "We couldn't tell which request this belongs to. Your team will file it." |
| `motion.badge` | "3 files" (template `{n} files`) |
| `banner.marked` | "Marked done Sep 14 · Brightwater Hale will review your documents" |
| `banner.undo` | "Undo" |
| `ignore.reasons` | "Not applicable this year" · "Already sent another way" · "I don't have this" |
| `ignore.note` | "Add a note for Kevin (optional)" (template `Add a note for {staff_first_name} (optional)`; POR-04b's label, used in the O1 popover too) |
| `ignore.marked` | "Marked not applicable · Sep 14" (template `Marked not applicable · {date}`) |
| `returned.pill` | "Returned · wrong year" (template `Returned · {reason}`) |
| `returned.note` | "This is the 2024 form. We need the 2025 Form 1095-C. — Kevin Osei" (seed: a client-visible send-back note) |
| `withdraw.confirm` | "Withdraw this file? Brightwater Hale's team won't use it. It's kept securely for 30 days, then erased." (DF-15) |
| `withdraw.action` | "Withdraw" |
| `empty.title` | "You're all caught up." |
| `empty.body` | "Brightwater Hale hasn't requested anything new." |
| `audit.binder` | "PY2025 Audit requests" |
| `audit.otherParties` | "Some requests go to Keystone, Harborline, PayGrid and Summit directly." (organisation names from the delegations) |
| `audit.due` | "Due Sep 18" (template `Due {date}`) |
| `toast.sentToFirm` | "Sent to Brightwater Hale" ("Upload something else", T33) |
| `mobile.toDo` | "2 to do" (template `{n} to do`) |
| `mobile.drop` | "Tap to upload or take a photo" |
| `mobile.tabs` | "Home" · "Documents" · "Sign" · "Messages" · "More" |

Per-artboard data (seed rows, R-01-T05; verbatim from the artboards):
- **a** groups and rows: "W-2s" — "2025 W-2 From Mercer Hill Health" / `Claire_Feld_2025_W2_MercerHill.pdf` / "Received by email Aug 3" · "1099s (all types), interest, dividends" — "2025 Consolidated 1099 From Halvard Securities (Acct ••3318)" / `Jonah_Feld_2025_1099_Composite_Halvard.pdf` / "Jonah uploaded Aug 5" · "Partnership K-1s" — "Schedule K-1 from Ridgeline Property Partners, LP" (firm-provided) · "Mortgage interest and property taxes" — "2025 Form 1098 From Hudson Mutual Savings (co-op loan)" / `Claire_Feld_2025_1098_HudsonMutual.pdf` / "Received by email Aug 3" · "Health insurance" — "Form 1095-C From Mercer Hill Health" (open) · "Charitable contributions" — "2025 donation receipts and acknowledgment letters" / `Feld_2025_Donations.pdf` / "You uploaded Aug 7" (Withdraw) · "Estimated tax payments" — "2025 federal (1040-ES) and New York (IT-2105) estimated payment confirmations" (open, "Uploading 2 files…"). Uploads `Feld_2025_Estimated_Payments.pdf` 1.1 MB 64% · `Feld_2025_IT2105_Confirmations.pdf` 380 KB 38%. Ticks: Personal & Household Information, Income Sources, Home & Property, Charitable & Donations; no tick on Health & Medical or Other Activity; Education & Student, Retirement and Business & Self-Employment muted ("Nothing requested").
- **c** the estimated-payments row shows `Feld_2025_Estimated_Payments.pdf` and `Feld_2025_IT2105_Confirmations.pdf` with "You uploaded Sep 14" and "Suggested — Brightwater Hale will confirm"; Other Activity ticks.
- **c2** the 1095-C row reads `Feld_1095C_2025.pdf` / "Received by email Sep 14"; Health & Medical ticks.
- **d** `Scan_0914.pdf` in the "Brightwater Hale will sort this" card (Inbox glyph).
- **g** the 1095-C row: "Returned · wrong year", Kevin Osei's note, `Feld_1095C_2024.pdf` struck, "Upload…".
- **i** bands and rows: Census & Payroll — "Employee census file — 2025" ✓ "You uploaded Sep 2" · "W-3 for 2025" ○ "Due Sep 18" · "Opt-out elections — auto-enrolled employees" ○ · "Pay rate authorizations" ○; Plan documents — "IRS opinion letter on the pre-approved plan document" ○; Compliance — "Participant complaints log and support" ○.

Accessibility labels (R-01 §5.6): the DropZone has a focusable "Choose files…" button (key `drop.choose`; the string is the kit's) and every open row has "Upload…"; sort results announce in a polite live region "2 files matched a request. 1 file sent to Brightwater Hale to sort." (key `live.sorted`, template `{n} files matched a request. {m} file sent to Brightwater Hale to sort.`); upload progress is `role="progressbar"` with values; the ignore reasons are a radio group with a visible legend; discs carry accessible names ("Done", "To do").

Copy bans on this screen (glossary portal bans, L2/L7): never "Accrued", "agent", "AI", "confidence", "task", "issue", a match percentage, a firm status word ("Uploaded – needs review", "Received ✓", "Pending incorporation"), an amount or materiality.

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Row title (open request or any row) | POR-04 `to.POR04({ requestId })` (O3 sheet over `/documents`) | planned (R-01-T12) |
| Mobile DropZone "Tap to upload or take a photo" (designed: "Opens POR-19 · mobile capture") | POR-19 | planned (R-03); in R-01 the control opens the native file input with camera capture (DEC-45, Deviations) |
| Nav Home, brand | POR-02 `to.POR02()` | per manifest (P-08) |
| "Upload something else" (the file goes to the firm Inbox; notices to NOT-01, firm-side) | INB-01 · NOT-01 (firm-side destinations; no portal navigation) | planned (N-01-T14; wired by R-01-T33) |
| Nav Questions · Sign · Messages · Deliverables | POR-05 · POR-06 · POR-07 · POR-09 | planned (T-02, N-02, N-03, R-02) |
| Binder picker | the same screen with `?binder=` | in-screen |
| Requested ⇕ filter, category rows | the same screen with `?filter=` / `?category=` | in-screen |

Inbound: POR-02 ("Go to Documents →", "Open binder"), POR-20 Reminder CTA, BND-02 "Preview as client", POR-19 (R-03), mobile tab "Documents". Firm mirrors (not links): TAX-03 "Marked done by Claire Feld", AUD-03, BND-02. In fixture builds a `planned` target renders "Not built yet"; in production a control whose target is `planned` is hidden. All targets are manifest IDs that `link-contract.test.ts` knows, and the one designed link of POR-03 in `handoff-links.json` (POR-19) is named above.

## Acceptance
- POR-03 acceptance: geometry matches `platform-portal.png`: 336 rail (title, drop zone with amber ring, Uploading band, 9 categories with 19 px olive ticks) and the 1030 documents pane with section cards on the `#F8F8F6` well.
- POR-03 acceptance: the header carries "Requested ⇕", centered "Documents", "Upload something else" and "Mark as Done" (tonal until ready, olive after).
- POR-03 acceptance: exactly 2 open requests (1095-C, estimated payments) = firm "Intake 2"; category ticks follow the rule (no tick on Health & Medical or Other Activity while open).
- POR-03 acceptance: motion reproduces `client-upload.png`: packet of 3 chips and badge, 2 px espresso inset ring, 135 ms row stagger, ticks, olive button once the emailed 1095-C is filed.
- POR-03 acceptance: the 1095-C is never uploaded in the portal on the seeded day: it arrives in Claire's 9:12 AM email as `Feld_1095C_2025.pdf`, INB-02 files it, and the row then reads "Received by email Sep 14"; any portal upload of the 1095-C is the alternate path (g).
- POR-03 acceptance: the Ridgeline K-1 row is firm-provided with no action; nothing internal (match %, agent) appears.
- POR-03 acceptance: the audit variant uses the `bento-audit-client` band and disc grammar and shows only Dana's own requests.
- R-01 Story 1.1: the closed 2024 binder opens read-only with no upload, ignore or Mark as Done control.
- R-01 Story 1.2: the other-parties note lists organisation names only, never delegated request titles; a contributor-equivalent grant has no note.
- At 390 (Story 1.3; DEC-463): the other-parties note shows above the bands too, and a row's title and status line open POR-04's full-screen sheet when the route passes `onOpen`.
- R-01 Story 3.1: Ignore with a reason and note shows "Marked not applicable · Sep 14" with Undo; Undo returns the row to "To do"; after the firm acts, Undo is absent.
- R-01 Story 3.3: Withdraw asks with the DF-15 copy and renders only on the contact's own unaccepted uploads.
- R-01 Story 4.1: Mark as Done is tonal while requests are open and olive when none remain; after it, the banner with Undo.
- R-01-T06 acceptance: no firm status word, agent name or bell in the DOM; axe clean (serious and critical = 0).

## Figures
| Figure | Foots | Proven by |
|---|---|---|
| Binder | 21 requests = 19 done + 2 open | R-01-T05 footing test (`portal-documents.foot.test.ts`) |
| Open | 2 = POR-02 "Upload 2 documents" = TAX-03 "Intake 2" | same, against P-08-T08's home seed |
| Sorted | 37 files sorted to date (= POR-02 "Brightwater Hale sorted 37 of your files") | same |
| Category ticks (a) | 4 of 9 ticked; 3 with nothing requested; Health & Medical and Other Activity open | scenario test a |
| Ticks (c, c2) | c: Other Activity ticks (5); c2: Health & Medical ticks (6) | scenario tests c, c2 |
| Uploads (a) | 64% of 1.1 MB, 38% of 380 KB | scenario test a |
| Drop (c, d) | 3 files = 2 `rule_linked` + 1 `waiting` | scenario tests c, d |

## AVOID
Each becomes a test in `POR-03.test.tsx` ("POR-03 avoid: …"): gradients in product UI, emoji, saturated blue, heavy shadows, invented colors, lorem ipsum, red for missing items (only Returned and Overdue use red-tint), checkboxes, modal upload flows, confidence percentages, firm words ("Pending incorporation", "Matched 94%"), Accrued branding.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DEC-58(a) | c's receipt sub-line reads "Suggested — Brightwater Hale will confirm" instead of "Matched to this request" | A code-rule link is provisional until a named person accepts it (ADR-005 kept) | decision-log DEC-58 |
| DEC-58(c) | Upload limits 50 MB; PDF · JPG · PNG · HEIC · XLSX · DOCX · CSV accepted; HEIC stored as-is until P-11-T25 renders it | Client uploads from phones | decision-log DEC-58; R-01 §11 OQ-3 |
| DEC-58(d) | No bell in the PortalToolbar | No portal bell | decision-log DEC-58 |
| DEC-58(f) | A request fulfilled by a connection reads "Provided from your accounting system" (no artboard) | Connected sources are not client uploads | decision-log DEC-58 |
| DEC-58(g) | A duplicate file is accepted with a normal receipt and flagged for a person firm-side ("Possible duplicate"), never refused | Duplicates accepted and flagged | decision-log DEC-58 |
| DF-15 | The Trash2 control is **Withdraw**, and its confirm reads "Withdraw this file? Brightwater Hale's team won't use it. It's kept securely for 30 days, then erased." instead of "Remove this file? Brightwater Hale will no longer see it." | Client withdrawal of unaccepted uploads (ADR P-31) | 09 DF-15 |
| DF-03 / DEC-45 | M's "take a photo" opens the native file input with camera capture; POR-19 is R-03's | Portal responsive scope | 09 DF-03; decision-log DEC-45 |
| DEC-59 | Served at the origin root of `<slug>.<neutral-portal-domain>`; mark and name from branding | White label | decision-log DEC-59 |
| — | i has no spec letter in the README auto-check; the spec lists it and the built artboard is canonical | Handoff README rule | R-01 §2.1 |
| — | c2's clock is 9:12 AM (the time of the email), kept by the fixture | README clock | R-01 §2.1 |
| — | c2 and "Upload something else" are fixture-only until N-01 files email and ships the intake route (S15–S16) | Upstream order | R-01 §2.2 |
| DEC-471 (seed) | i, c and g on the live seed carry synthetic fills: the census title and "PY2025 Audit requests" are bootstrapped, delegations to Keystone, Harborline, PayGrid and Summit have no grant, Claire's 9:12 AM file is bootstrapped into the Feld Inbox (the firm channel: no email channel until N-01), and g loads as the opt-in slice `portal_pbc_returned`; a and M's "19 of 21 · 37 sorted" stay fixture figures (the seed reads 5 of 7) | No source or service gives these values; the user chose to fill them | decision-log DEC-471; TASK-1221 |

### Part 2 notes (R-01-T10)
- **Mounted at `/documents`** in the portal entry, with `?binder=` and T7-M below 768 px (DEC-346); POR-02's "Go to Documents →" (a request target of POR-03) and "Open binder" open it, and the PortalToolbar's Home and Documents route. The link checker's rule 1 cannot see the portal's tree (manifest paths resolve in the firm's route tree, and a POR path there fails rule 2), so the manifest entry stays `planned` with a null path until the checker learns the portal tree (DEC-347; R-01-T31).
- **Drop polling:** a drop posts each file to `POST /v1/portal/binders/{id}/drops` in one `X-Drop-Batch`, then polls the batch the server names (`GET /v1/portal/drops/{batch}`, every second until `settled`) and reads the binder again once. `rule_linked` files show on their request with "Suggested — … will confirm"; `waiting` and `duplicate_flagged` files show in "Brightwater Hale will sort this"; the outcome is announced in a polite live region ("2 files matched a request. 1 file sent to Brightwater Hale to sort."). A 413 or 415 at the door lists the file under the drop zone with the words in `domain/portal/messages.ts` (`refused.file_too_large`, `refused.type_not_allowed`; no handoff frame; ink, never red).
- **Motion:** the packet (three chips, "3 files") hangs over the ringed list for 900 ms, then the rows rise 135 ms apart (`motion-reveal`, the kit's `reveal`); under `prefers-reduced-motion` or `?static=1` the screen opens on the sorted frame with no animation class. The motion frame's rail upload sizes (1.9 MB, 2.7 MB, 1.5 MB) are not drawn: the seed's sizes are a's.
- **i:** the kit's `bands` (folder band, "n of m", 17 px discs: the largest StatusDisc size, the handoff's 18 waits for the kit), the other-parties note from `other_parties`, "Due Sep 18" from `due_on`, the rail lists the bands with "n open". Band rows draw the folder glyph, not per-band icons: the projection carries none (parity mask, R-01-T31). The census row's receipt "You uploaded Sep 2" comes from a seeded file the band grammar does not name.
- **M:** `RequestMobile` with the native file input accepting DEC-58 c's types (the phone offers the camera for images; POR-19 is R-03's), Mark as Done full width in the sticky footer above the tab bar.

### Part 1 notes (R-01-T06)
- Built on the C-16 Request kit (`useRequestBinder`, `RequestDocuments`, `CategoryRail`, `DropZone`, `UploadList`) with three portal opt-ins added to the kit: `withdraw` (the DF-15 "Withdraw" menu and line), `suggested` on a row (DEC-58 a's "Suggested — Brightwater Hale will confirm" in place of "Matched to this request") and `readOnly` (a closed binder). The kit's defaults, and so the TPL-07 specimen, are unchanged.
- The rail is the screen's own composition of the kit's parts, so the binder picker lists every binder the person can see ("2024 Binder (closed)" opens read-only).
- Category ticks come from the server (`categories[].complete`, the kit's `doneCats`), because the Requested view does not list every request a category holds.
- An ignored row reads "Marked not applicable · Sep 14" (the day the projection carries), with Undo.
- The load error has no handoff frame: "Couldn’t load your documents." / "We could not reach the server. Nothing was lost; try again in a moment." / "Retry", on POR-02's error grammar.
- Firm-provided group glyphs come from their category (the Partnership K-1s group draws the Income Sources glyph, where the handoff draws a briefcase): the projection carries no group icon. Parity masks it until the read model does.

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, b, c, c2, d, e, f, g, h, i | C (threshold 0.20, maxDiffPixelRatio 3 %), locked (R-01-T31) | a 1.93 · b 1.95 · c 1.65 · c2 1.63 · d 1.60 · e 1.52 · f 1.71 · g 1.61 · h 0.50 · i 0.87 (2026-10-28, handoff 2026-10-21) | the 1400 × 860 window (`[data-shell="app"]`), all within C's 3 %; c masks the receipt sub-line (DEC-58 a) |
| motion | C | not run | at `?static=1` |
| M | C + D | C not run (the PNG is the 470 phone board, not a window) | Tier D (`e2e/visual/tier-d-portal.spec.ts`): header 56 and the 64 px tab bar hold; "2025 Binder" is 36 tall (targets, Open gaps); no sticky Mark as Done on M's frame |
| host | D | — | toolbar 46, rail 336, documents 1030, pane header 46 with a 14.5/500 title, DropZone radius 12, UploadRow 42, category rows 39 with a 19 px disc, row padding 12 14, File glyph 17 |

Tier B for T7 and T7-M is F-05's (F-05-T49).

## Open gaps
- **390 targets (R-01-T31).** M's binder picker is 112 × 36, under the contract's 44 × 44; recorded in `tier-d-portal.spec.ts` with POR-04's and POR-14's as expected failures until the portal's mobile controls grow.
- No handoff string exists for the upload refusals (`file_too_large`, `type_not_allowed`), the stale Undo (`firm_already_acted`) or the binder load error. R-01-T10 wrote the refusals ("‹name› is larger than 50 MB. Send a smaller copy or split it into parts." · "‹name› can't be uploaded here. Send a PDF, a photo, a spreadsheet, a Word document or a CSV."); the stale Undo's words remain R-01-T08's.
- The DropZone copy lists HEIC only once renditions exist (R-01 §11 R7, OQ-3); until then POR-04's line reads as designed and the firm side shows "Preview not available yet" for HEIC.
- The ignore note label names the preparer ("Add a note for Kevin (optional)"); the binder's client-facing contact is the source of the name (R-01-T07 projects it).
