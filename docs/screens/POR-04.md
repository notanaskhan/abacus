# POR-04 · Request detail / ignore reason sheet

| Field | Value |
|---|---|
| Route and params | `/documents/requests/$requestId` in the portal entry: an O3 modal route over POR-03 `/documents` (it keeps POR-03's `?binder=`, `?filter=`, `?category=`); below 768 px a full-screen sheet. ✕, the scrim and Esc return to `/documents` and focus to the invoking row. POR-11 (C-01) opens the same sheet over `/documents?period=`. Artboards: `/components/screens/POR-04?st=a…g` |
| Template and host frame | O3 `SheetModal` 500 wide from y52 (radius 16 16 0 0, `--shell` body, white 56 px header) over T7 POR-03 under the scrim; full-screen sheet at 390 (specified, not built) · `Wave 2 - Client Portal.dc.html#por04` |
| Surface | portal (white-labelled: the firm's mark, name and people; nowhere "Accrued") |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/POR-04 Request detail - ignore reason sheet/` (README.md, spec.md; no revision.md) · HANDOFF_VERSION 2026-10-21 |
| Epic and tasks | R-01 · contract R-01-T03; contract stub R-01-T01; consumer tests R-01-T02; fixtures R-01-T05; read model R-01-T07; ignore note and undo R-01-T08; sheet R-01-T12; live swap R-01-T18; parity and accessibility R-01-T31. e goes live with C-01 (transaction questions), f with T-06 / T-09 (client decision) |
| Manifest status | built on fixtures (R-01-T12, 2026-10-26): every artboard in the gallery, and the portal entry's `/documents/requests/$requestId` over POR-03 (a row's title opens it); the manifest entry stays `planned` with a null path, as POR-03's (DEC-347) |

Code to come (R-01 §5.2): `src/screens/POR-04/{index.tsx, scenarios.ts, copy.ts, POR-04.test.tsx}`, `src/routes/portal/documents.requests.tsx`, `src/domain/portal/{documents.ts, messages.ts}`; reused and restyled: `ClientUploadChecks` (`screens/CheckResults.tsx`) for the pre-checks, `CommentThread` (`screens/CommentThread.tsx`) for the shared thread.

**White label (AGENTS frontend rule 7, DEC-01, ADR-133, DEC-59).** Portal code never renders "Accrued". "Why we need it" is firm-written guidance only (SPEC-031 fields or an approved SPEC-035 draft; never unapproved model text, ADR-111). No internal code, agent, confidence or issue taxonomy reaches the client.

## States

Fixture scenarios (R-01-T05, `fixtures/scenarios/POR-04.ts`, data in `fixtures/seed/portal-documents.ts`).

7 artboards in the handoff (a–g), 7 built here; the 390 full-screen sheet is specified, not drawn (Tier D only).

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | claire-feld (Claire Feld, taxpayer) | Mon Sep 14, 2026, 9:24 AM CT | E0 | The 1095-C request `requested` (client words "To do"), requested Feb 3; firm guidance present; prior-year fulfilment `Claire_Feld_2024_1095C_MercerHill.pdf` on Mar 3, 2025; one shared comment from Kevin Osei on Jul 20 | fixture (T12) |
| b | claire-feld | same | E0 | "This doesn't apply to me…" pressed on a: the reasons card with the note; on save POR-03 shows "Marked not applicable · Sep 14" with Undo | fixture (T12) |
| c | claire-feld | **Mon Sep 14, 2026, 9:12 AM** (README clock) | E0 | The firm filed Claire's 9:12 AM email to the 1095-C (receipt kind `emailed`, `Feld_1095C_2025.pdf`, 412 KB): no Withdraw. Portal-upload variant (alternate path): receipt "You uploaded Sep 14" with Withdraw | fixture (T12; emailed receipt live with N-01) |
| d | claire-feld | Mon Sep 14, 2026, 9:24 AM CT | holdout | Alternate path: the 2024 form uploaded in the portal and returned by Kevin Osei with reason `wrong_year` and a client-visible note | fixture (T12) |
| e | ben-ashby (Ben Ashby, Copperleaf Coffee Roasters, Inc.) | **Mon Sep 14, 2026, 1:10 PM CT** | E0 | Raj Malhotra's transaction question on the Sound Electric payment (asked Sep 11), over POR-11 "August 2026 Close": the `question` variant slot | fixture only (C-01 wires it) |
| f | owen-calder (Owen Calder, Managing Member of Ridgeline GP LLC) | Mon Sep 14, 2026, before 5:00 PM CT | E0 | The §754 election decision due today at 5:00 PM CT; explanation figures computed in the fixture by the pure function T-06 will own: the `decision` variant slot | fixture only (T-06 / T-09 wire it) |
| g | claire-feld | Mon Sep 14, 2026, 9:24 AM CT | E0 | A portal upload on a at 46%, held for review; on completion the portal-upload variant of c | fixture (T12) |

Personas: `ben-ashby` and `owen-calder` are added to the TS seed by R-01-T05 if absent; `claire-feld` exists.

Non-artboard states (data conditions, never an `st` prop):

| State | Data condition | Rendering |
|---|---|---|
| Loading | `GET /v1/portal/request-items/{id}` pending | the sheet frame with a token skeleton, status label "Loading" |
| Error | the read fails | C-20 `ErrorRow` inside the sheet |
| Not found | the request is outside the contact's scope, a draft, internal-only, delegated to a third party, or the id is forged: `404` | not-found inside the sheet (INV-4); no oracle |
| Pre-check messages | the mechanical pre-checks flag a portal upload (wrong period, unreadable) | the fixed words from `ClientUploadChecks` inside the Upload card (DEC-58 e) |
| Upload refused | `413 file_too_large` / `415 type_not_allowed` | fixed words from `domain/portal/messages.ts` on the UploadRow |
| Closed binder | the request's binder is closed | read-only: no Upload…, "This doesn't apply to me…" or composer |
| 390 | viewport under 768 px | full-screen sheet from y44, header ✕ / "Request" / "Upload…" text button, composer pinned above the safe area; "Take a photo" opens the native file input with camera (DEC-45) |

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/portal/request-items/{id}` | `PortalRequestOut`: `id`, `binder_id`, `category {code, label}`, `title`, `client_status ∈ to_do\|done\|ignored\|returned`, `requested_on`, `guidance` (firm-written), `prior_year {file_name, sent_on}?`, `files[{id, name, size_bytes, receipt {kind, at}, withdrawable}]`, `returned {reason_code, note, by, at}?`, `pre_checks[{code}]`, `comment_count`, `upload_intents[]`, `variant ∈ request\|question\|decision` (question and decision are fixture-only), `allowed_actions[]` | `portal.documents.read` · `scope_only` | client roles on the scope; the agent and every firm role deny |
| write | `POST /v1/engagements/{eid}/request-items/{id}/uploads` (existing) | the upload ("Upload…" or drop on the sheet) | `evidence.upload` | `upload` |
| write | `POST /v1/portal/request-items/{id}/upload-intents` (P-06) | the UploadRow while in flight | `evidence.upload` | `upload` |
| write | `POST /v1/portal/request-items/{id}/ignore {reason, note?}` (P-06; R-01 additive `note`) | the note is stored as a shared comment with origin `ignore_note` | `request_item.ignore` | `ignore` |
| write | `POST /v1/portal/request-items/{id}/ignore/undo` | compensating event; `409 firm_already_acted` | `request_item.ignore` | `undo_ignore` until the firm acts (DEC-24) |
| write | `POST /v1/engagements/{eid}/evidence-versions/{vid}/withdraw` (P-06; P-31) | withdraw an own unaccepted upload; `409 evidence_accepted` | `evidence.withdraw` | `withdraw` (never on an emailed or accepted file) |
| read / write | `GET`/`POST /v1/engagements/{eid}/request-items/{id}/comments` (existing, SPEC-032) | the shared thread and composer | `comment.read` / `comment.create` | `comment` |

The question (e) and decision (f) variants have **no endpoint in R-01**. They are a typed prop contract of `RequestSheet` (below) that C-01 and T-06 / T-09 wire to their own routes.

### Variant-slot contract (`RequestSheet`, for C-01 and T-06 / T-09)
- `variant: "request" | "question" | "decision"`; exactly one primary button in every variant (AVOID).
- `question`: `title`, `context: {label, value}[]` (code-supplied key-values; the amount is a figure the firm already shows the client in its own question), `note?`, `options: {code, label}[]` (one radio group), `text?`, `attachments: {name, size_bytes, done}[]`, `onSend({option, text, attachment_ids}) → "Send answer"`, `answered?: {at, follow_up_by}` → "✓ You answered {date}, {time} · {name} will follow up if needed".
- `decision`: `title`, `due: {at, label}` (amber pill), `explanation` (firm-written text with code-computed figures supplied by the caller; never model arithmetic, ADR-050), `options: {code, label}[]`, `footnote?`, `onSend({option}) → "Send decision"`.
- Both variants post through their owning epic's route and end with the toast "Sent to Brightwater Hale".

## Status
Status objects shown, from `docs/product/status-vocabulary.yaml`, in their `client_label` wording:
- `request` `requested` → "To do · requested Feb 3" (15 px empty ring).
- `request` `uploaded` / `received` → "Done": "✓ Received by email Sep 14" or "✓ You uploaded Sep 14" (olive disc).
- client ignore → "Ignored" ("Marked not applicable · Sep 14" on POR-03).
- `request` `returned` → red-tint pill "Returned · wrong year".
- Decision due → amber-tint pill "Answer by 5:00 PM CT today" (state, never red).

## Copy
Copy keys live in `screens/POR-04/copy.ts`; strings verbatim from spec.md and the built artboards.

| Key | String |
|---|---|
| `header.request` | "Request" |
| `header.question` | "Question" |
| `header.decision` | "Decision" |
| `action.upload` | "Upload…" |
| `card.why` | "Why we need it" |
| `status.toDo` | "To do · requested Feb 3" (template `To do · requested {date}`) |
| `drop.title` | "Drop the file here" |
| `drop.types` | "PDF, JPG, PNG, HEIC, XLSX · up to 50 MB" |
| `drop.lastYear` | "Last year you sent Claire_Feld_2024_1095C_MercerHill.pdf on Mar 3, 2025." (template `Last year you sent {file_name} on {date}.`) |
| `comments.title` | "Comments" |
| `comments.visibility` | "Visible to you and Brightwater Hale" |
| `comments.placeholder` | "Write a comment…" |
| `action.notApplicable` | "This doesn't apply to me…" |
| `ignore.title` | "Why doesn't this apply?" |
| `ignore.reasons` | "Not applicable this year" · "Already sent another way" · "I don't have this" |
| `ignore.note` | "Add a note for Kevin (optional)" |
| `ignore.save` | "Mark not applicable" |
| `ignore.marked` | "Marked not applicable · Sep 14" |
| `received.emailed` | "Received by email Sep 14" |
| `received.uploaded` | "You uploaded Sep 14" |
| `received.next` | "Brightwater Hale will check it and let you know if anything is missing." |
| `returned.pill` | "Returned · wrong year" |
| `returned.note` | "This is the 2024 form. We need the 2025 Form 1095-C. — Kevin Osei, Sep 14" |
| `withdraw.action` | "Withdraw" |
| `withdraw.confirm` | "Withdraw this file? Brightwater Hale's team won't use it. It's kept securely for 30 days, then erased." (DF-15) |
| `mobile.photo` | "Take a photo" |
| `question.send` | "Send answer" |
| `question.answered` | "You answered Sep 14, 1:12 PM · Raj Malhotra will follow up if needed" |
| `decision.due` | "Answer by 5:00 PM CT today" |
| `decision.send` | "Send decision" |
| `decision.footnote` | "If you choose yes, Brightwater Hale attaches the election statement to the return. The statement doesn't need a separate signature." |
| `toast.sent` | "Sent to Brightwater Hale" |

Per-artboard data (seed rows, R-01-T05; verbatim):
- **a** category "Health insurance"; title "Form 1095-C From Mercer Hill Health"; guidance "Form 1095-C shows the health coverage Mercer Hill Health offered you each month of 2025. You don't attach it to your return, but we use it to confirm your coverage and that no premium tax credit needs to be repaid."; comment "Kevin Osei · Brightwater Hale" · "Jul 20" · "Mercer Hill usually posts these in the employee portal by early March. A PDF download is perfect."
- **c** file `Feld_1095C_2025.pdf` · "412 KB".
- **d** struck `Feld_1095C_2024.pdf`.
- **e** title "What was the $3,200 payment to Sound Electric?"; context Paid "Aug 18, 2026 · check #2285" · From "Front Range Bank ••4410" · Amount "$3,200.00" · Recorded as "Repairs & maintenance"; note "Repairs were $640 in July, so we want to be sure this isn't new equipment."; options "A repair or routine maintenance" (selected) · "New equipment or an improvement" · "Something else"; text "Two breakers failed on Aug 14; Sound Electric replaced them and rewired the espresso bar circuit. The panel was not replaced and nothing new was added."; attachment `SoundElectric_INV-SE-1187.pdf` · "188 KB".
- **f** title "Should Ridgeline make a section 754 election for 2025?"; explanation "On June 30, 2025 Pell Street Ventures LLC sold 5 points to Pell Street II LLC for $360,000. Pell Street II's share of the partnership's basis in its property was $331,405 — 5/35 of Pell Street Ventures' 6/30 capital of $2,319,835 (including $1,085 of first-half tax-exempt interest, per Reg. §1.704-1(b)(2)(iv)(l)). With a section 754 election, Pell Street II's share of that basis steps up by the $28,595 difference. The election is made by the partnership with a statement attached to its timely filed 2025 Form 1065 (extended due date September 15, 2026), and it also applies to all later transfers and distributions until revoked. Daniel Reyes recommends making the election."; options "Yes — make the election" · "No — don't make the election" · "We'd like to talk first".
- **g** UploadRow at 46%.

Accessibility (R-01 §5.6): the sheet traps focus, is labelled by the request title, closes on Esc and returns focus to the invoking row; the reasons are a radio group with the visible legend "Why doesn't this apply?"; the note field is labelled "Add a note for Kevin (optional)"; "Returned · wrong year" carries text, not colour alone; UploadRow is `role="progressbar"`.

Copy bans on this screen: never "Accrued", "issue", "TXP-10", "review point", "Action required", a confidence figure, the agent's name, a firm status word.

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| ✕, scrim, Esc | POR-03 `to.POR03()` (focus returns to the row) | planned (R-01-T06) |
| Host for e (question over the close) | POR-11 | planned (C-01) |
| Mobile "Take a photo" | POR-19 | planned (R-03); the native file input with camera in R-01 (DEC-45) |
| f: the election statement rides with the 1065 e-file authorization | POR-06 | planned (N-02) |
| Attachment rows | read-only preview (server-rendered, `EvidencePreview` path) | in-screen |

Inbound: POR-03 row title, POR-11 "Answer…", POR-02 overdue to-do, POR-07 linked request card, POR-20 Reminder, and the designed links SHL-13, TXI-03, POR-21 and PRJ-01 (each opens the sheet as the client sees it). Firm side (not links): INB-04 threads, CLS-06, TXP-10, TAX-06, PRJ-01. POR-04 has no outbound designed link in `handoff-links.json`; every ID above is a manifest screen.

## Acceptance
- POR-04 acceptance: O3 geometry: 500 px sheet from y52, radius 16 16 0 0, `#F8F8F6` body, white 56 px header with ✕ · title · dark action.
- POR-04 acceptance: the plain-language "Why we need it" is tax-correct (the 1095-C is not attached; PTC reconciliation).
- POR-04 acceptance: Ignore requires a reason from the three canonical options; the result shows "Marked not applicable" with Undo.
- POR-04 acceptance: the returned state uses red-tint "Returned · wrong year" and quotes the firm note with a name and date; it and the portal-upload variant of c are the alternate path; on the seeded day the 1095-C reads "Received by email Sep 14".
- POR-04 acceptance: the Sound Electric question ties to CLS-10 flux (Repairs $3,200 vs $640), check #2285 on Aug 18 and invoice SE-1187; the §754 decision ties to the Ridgeline seed (5/35 × 2,319,835 = 331,405; 360,000 − 331,405 = 28,595; 1065 extended due Sep 15).
- POR-04 acceptance: no internal codes, agent or issue taxonomy visible to the client.
- R-01-T12 acceptance: e and f render from fixtures with exactly one primary button each, and Esc returns focus to the invoking row.
- R-01 Story 3.3: no Withdraw on an emailed or accepted file; Withdraw on the portal-upload variant asks with the DF-15 copy.
- R-01 Story 5.1: the mechanical pre-check messages show inside the sheet in fixed words (DEC-58 e).

## Figures
| Figure | Foots | Proven by |
|---|---|---|
| Upload (g) | 46% | scenario test g |
| File (c) | `Feld_1095C_2025.pdf` 412 KB | R-01-T05 seed test |
| Question (e) | $3,200 vs July repairs $640; check #2285 on Aug 18 | R-01-T05 seed test (fixture only) |
| Decision (f) | 5/35 × 2,319,835 = 331,405; 360,000 − 331,405 = 28,595 | R-01-T05 footing test (the fixture computes, never hard-codes, the two results) |

## AVOID
Each becomes a test in `POR-04.test.tsx` ("POR-04 avoid: …"): gradients in product UI, emoji, saturated blue, heavy shadows, invented colors, lorem ipsum, firm jargon ("issue", "TXP-10", "review point", "Action required"), confidence scores, the agent's name, red except for Returned, more than one primary button.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DEC-58(e) | Mechanical pre-check messages sit inside the sheet in fixed words (no artboard) | Client-facing checks never use model text | decision-log DEC-58 |
| DEC-58(c) | "PDF, JPG, PNG, HEIC, XLSX · up to 50 MB" is kept as designed; HEIC files are stored as-is until P-11-T25 renders them | Upload limits | decision-log DEC-58; R-01 §11 OQ-3 |
| DF-15 | The portal-upload variant's Trash2 is **Withdraw** with the DF-15 confirm | Client withdrawal (ADR P-31) | 09 DF-15 |
| DF-03 / DEC-45 | The 390 full-screen sheet is specified, not drawn: Tier D only; "Take a photo" is the native camera input | Portal responsive scope | 09 DF-03; decision-log DEC-45 |
| — | e and f ship as typed variant slots of one sheet in fixture mode only; R-01 adds no question or decision endpoint | They go live with C-01 and T-06 / T-09 | R-01 §2.4 |
| — | The README's viewer column reads "—" for b, c, d and g; the viewer is Claire Feld | The spec's default viewer | R-01 §5.4 |
| — | The header shows "Request" (as designed) and the sheet is described by the request's title for assistive technology, rather than named by it | The O3 header's centred title is the kind of sheet; the title is the first card's heading | R-01-T12 |
| — | "Add a note for Kevin (optional)" names the newest firm commenter of the thread by first name, else the firm ("Add a note for Brightwater Hale (optional)") | `PortalRequestOut` carries no request owner; no shape change in R-01-T12 | R-01-T12 |
| — | "Mark not applicable" is a secondary button, not a primary | The header's "Upload…" is the sheet's one primary (AVOID: more than one primary) | R-01-T12 |
| — | The portal-upload variant's in-flight row shows 0% until the file is stored, then the receipt | The upload is one request with no progress events; g's 46% is the fixture's held frame | R-01-T12 |
| DEC-471 (seed) | d loads as the opt-in slice `portal_pbc_returned`: Claire's 2024 upload (8:40 AM) and Kevin Osei's bootstrapped `wrong_period` return (9:05 AM) with g's note; the times are synthetic | A loader cannot take a person's review decision (ADR-005); the user chose to fill it | decision-log DEC-471; TASK-1221 |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, b, c, d, g | C (threshold 0.20, maxDiffPixelRatio 3 %) | not run (unbuilt) | locked before M8 (R-01-T31) |
| e, f | C | not run | reported in fixture mode; locked by C-01 and T-06 / T-09 |
| 390 | D | — | full-screen sheet from y44, header 56, targets ≥ 44 × 44 |
| host | D | — | sheet 500 from y52, header 56, fieldset cards radius 10, DropZone 112, composer 44, radio rows 40 |

## Open gaps
- No handoff string for the not-found sheet, the load error, a failed write or the pre-check messages. R-01-T12 wrote them in `domain/portal/messages.ts` (`SHEET_WORDS`) on the C-20 grammar: "This request isn't available." (404, no oracle); "Couldn’t load this request. Nothing was lost; try again in a moment." with Retry; "That didn't go through. Nothing changed; try again in a moment." (a toast); the pre-checks in `ClientUploadChecks`' fixed words for a file of no known kind ("This file isn't for the year end." for `wrong_period` and `stale_as_of`; "This looks like it's for a different company."; "The totals in this file don't add up. Please check it and upload it again."). The question's text field is labelled "Tell us more" and its radio group "Your answer"; the decision's "Your decision".
- The question and decision variants' toasts reuse "Sent to Brightwater Hale" (the spec's interaction line); their routes and allowed actions are C-01's and T-06's.
