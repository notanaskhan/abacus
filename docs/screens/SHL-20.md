# SHL-20 · Evidence screening

| Field | Value |
|---|---|
| Route and params | None of its own. A non-modal O1 card in local state (chapter 04 §2.4), opened from the screening chip or glyph on an upload row: BND-02 here (row glyph and dock card), AUD-03 from A-01, CLS-03 from C-01, ATT-05 later. The O3 follow-up sheet is local state; drafts are server-side. Artboards: `/components/screens/SHL-20?st=a…f` |
| Template and host frame | O1 card (C-34 ScreeningCard 420) in the evidence pane + O3 sheet 500 · `Wave 0 - Shell.dc.html#shl20`; screen kit `kits/Screening Specimen.dc.html` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/SHL-20 Evidence screening/` (README.md, spec.md; no revision) · HANDOFF_VERSION 2026-10-21 |
| Epic and tasks | P-06 · contract P-06-T03 (TASK-404); C-34 kit, a–f, O3 sheet, ReturnDialog preselect, View, feedback P-06-T22; aggregate P-06-T20; stub P-06-T15; follow-ups P-06-T14; evals P-06-T21; data P-06-T08; parity P-06-T26 |
| Manifest status | fixture (`routes/manifest/shl.ts`; P-06-T22) |

Code to come (P-06 §5.2): `packages/ui/src/components/screening/ScreeningCard.tsx` (C-34: flagged · passed · not screened · running, with a gallery specimen), `src/domain/screening/{queries.ts, ScreeningCardHost.tsx, FeedbackMenu.tsx}`, `src/domain/requests/{FollowUpSheet.tsx, ReturnDialog.tsx}`, `src/screens/SHL-20/{index.tsx, scenarios.ts, copy.ts, SHL-20.test.tsx}`.

## States

6 artboards in the handoff, 6 built here.

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | cole-hart (Cole Hart, Audit Staff, Granite Peak FY2026) | Sat Sep 26, 2026, 10:14 AM CT | E0 | 31 files fulfil the SURL request, reviews complete; the `request_batch` aggregate is `flagged` (screened 10:12 AM) with 2 file flags whose quotes were verified | built · fixture (T22) |
| b | cole-hart | Sat Sep 26, 2026, 10:16 AM CT | E0 | a, plus a `screening_return` follow-up draft composed from the firm's Return template with 2 returning files (DV-1) | built · fixture (T22) |
| c | cole-hart | Mon Sep 28, 2026, 9:05 AM CT | E0 | Corrected files received; a rerun is running on 2 new files | built · fixture (T22) |
| d | cole-hart | Mon Sep 28, 2026, 9:05 AM CT | E0 | The superseding aggregate is `passed`; 40 of 40 payments supported | built · fixture (T22) |
| e | cole-hart | Fri Sep 25, 2026 | E0 | FRF-30418.pdf, emailed by Luis Ferrante and filed from the Inbox before it was linked; aggregate `not_screened` | built · fixture (T22) |
| f | cole-hart | Sat Sep 26, 2026, 10:14 AM CT | E0 | a, with the ThumbsDown "Why?" menu open | built · fixture (T22) |

Loading: the card opens with the c skeleton bars while the aggregate loads. Not-allowed: `client_service` and every client principal get 403/404 on the card endpoint; BND-01/BND-02 show the glyph without text (DEC-20, INV-4). Flag off (`screening.card`): the card area shows nothing extra. A tax-return upload at a non-synthetic firm without §7216 consent (C19), or without the data-boundary opt-in, reads Not screened, never an error that implies a verdict.

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET …/request-items/{id}/screening` | The `request_batch` aggregate: verdict, two named checks (`right_document`, `right_period`), file flags with region refs, time, provenance; polled every 2 s while running | `upload_review.read` | `client_service` and client principals 403/404 |
| write | `POST …/request-items/{id}/screening/rerun` | Re-screen current fulfilled, non-withdrawn files (c) | `screening.request` | 409 `screening_running` |
| write | `POST /v1/screenings/{id}/feedback {thumb, reason_code, note}` | f; insert-only; `reason_code ∈ {wrong_request_match, wrong_period, unclear_file, other}` required on thumbs down | `screening.feedback` | partner, manager, senior, staff; independence required; agent deny |
| write | `POST …/request-items/{id}/follow-ups {kind: screening_return, returning: [version_id]}` | b: template-composed draft | `follow_up.draft` | — |
| write | `PATCH /v1/follow-ups/{id} {body}` · `POST /v1/follow-ups/{id}/send` (Idempotency-Key) | b: edit, then human send; one UoW writes the two `send_back` decisions with `wrong_document`, the request `returned`, the shared comment and the follow-up `sent` | `follow_up.draft` · `follow_up.send` | agent deny; 409 `out_of_scope`, `follow_up_already_sent` |
| write | `POST …/evidence-versions/{vid}/decision/send-back` | "Return…" through the ReturnDialog with `wrong_document` preselected; `returned` only on confirm | `evidence.reject` | agent deny |

## Status
`evidence_screening`: `passed` olive ✓ "Passed" · `flagged` amber triangle "Flagged" · `not_screened` ring "Not screened"; running is a UI state of a pending rerun (spinner, "Screening 2 new files…"), not a status code. Host row: `request.uploaded` amber "Uploaded – needs review"; after the follow-up is sent both files show `returned` ("Returned"). No confidence percentage appears anywhere.

## Copy
Copy keys live in `screens/SHL-20/copy.ts` (C-34 labels in the kit); strings verbatim from spec.md.

| Key | String |
|---|---|
| `card.title` | "Evidence screening" |
| `verdict` | "Passed" · "Flagged" · "Not screened" |
| `chip.flagged` | "Screening · {n} flagged" (a: "Screening · 2 flagged") |
| `chip.passed` | "Screening · passed" |
| `request.line` | "{request} · expected period {period}" (a: "Support for 40 subsequent disbursements (SURL) · expected period Jun 1 – Sep 18, 2026") |
| `check.answers` | "Does this answer the request?" |
| `check.period` | "Is it inside the expected period?" |
| `flagged.band` | "Flagged files" |
| `flagged.view` | "View" |
| `flagged.return` | "Return…" |
| `footer.draftFollowUp` | "Draft follow-up" |
| `footer.rerun` | "Rerun" |
| `provenance` | "Screened by Accrued Agent · screener@v3 · 2 s · instructions inside files are never followed" |
| `running` | "Screening {n} new files…" (c: "Screening 2 new files…") |
| `passed.total` | "{n} of {n} payments supported" (d: "40 of 40 payments supported") |
| `notScreened.body` | "Screening has not run on this file. It runs once the file is linked to a request." |
| `notScreened.screenNow` | "Screen now" |
| `notScreened.link` | "Link to request…" |
| `feedback.title` | "Why?" |
| `feedback.reasons` | "Wrong request match" · "Wrong period" · "Unclear file" · "Other" |
| `feedback.send` | "Send feedback" |
| `feedback.sent` | "Feedback sent · {reason}" (f: "Feedback sent · Wrong request match") |
| `sheet.title` | "Follow-up to {name}" (b: "Follow-up to Luis Ferrante") |
| `sheet.context` | "POR-04 comment · SURL request" |
| `sheet.tag` | "Drafted by Accrued Agent · edit before sending" |
| `sheet.returning` | "Returning: {file}" |
| `sheet.todo` | "Add a to-do for me: Re-request 2 SURL files · due Sep 28" (renders only with `todo.create`; DV-1) |
| `sheet.cancel` | "Cancel" |
| `sheet.send` | "Send to {name}" (b: "Send to Luis Ferrante") |
| `sheet.footnote` | "Sends in the portal and by email. Both files show Returned." |

Check answers and flag reasons are data: in fixture mode the a and d answers and the two §9.3.4 flag reasons are spec.md verbatim ("29 of 31 files answer their payment. 2 do not.", "All other files are dated inside Jun 1 – Sep 18, 2026.", "This is a statement, not the invoice for payment #40188 ($23,940).", "The invoice matches payment #40171, not #40117.", "The 2 corrected files answer payments #40188 and #40117.", "Both are dated inside Jun 1 – Sep 18, 2026."). On live data check 2's answer is code-generated (DV-2) and a flag reason shows only with a code-verified quote (INV-2). The b body is composed by code from the firm's Return template (DV-1), never the handoff's model sentences.

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| "View" | SHL-08 on the file with the deciding region lit #ECD9F0 (C4 region) | planned (P-03); DV-10 fallback to the page preview |
| "Return…" | the AUD-03 ReturnDialog (`domain/requests/ReturnDialog.tsx`, shared), "Wrong document" preselected | in-screen (P-06-T22; spec-level link) |
| "Draft follow-up" → "Send to Luis Ferrante" | POR-04 comment (the client sees it on the request) | planned (R-01; spec-level) |
| "Add a to-do for me…" | SHL-17 | planned (P-05; DV-1; spec-level) |
| "Link to request…" (e) | INB-02 | planned (N-01, S13; DV-8; spec-level) |

Inbound: BND-02 (row glyph, dock card), AUD-03, CLS-03, ATT-05 upload rows; SHT-01 row drawer Evidence tab; SHL-04 ("Opens the evidence pane with the SHL-20 card"); SHL-13; ENG-02 and ENG-12. All targets are manifest IDs that `link-contract.test.ts` knows.

## Acceptance
- SHL-20 acceptance: C-34 anatomy: header with time and verdict, two check rows, flagged-file band with View · Return…, footer Draft follow-up · Rerun · thumbs, provenance "Screened by Accrued Agent · screener@v3 · 2 s".
- SHL-20 acceptance: flag reasons are §9.3.4 verbatim; the expected period reads Jun 1 – Sep 18, 2026.
- SHL-20 acceptance: counts foot: 31 files on Sep 26 − 2 flagged = 29; after the corrected files on Sep 28, 40 of 40.
- SHL-20 acceptance: the agent drafts; Cole sends and returns; nothing is accepted or returned automatically.
- SHL-20 acceptance: the pattern-evidence interaction (two questions, flagged file with view / return, follow up, rerun, thumbs) is rendered in Accrued tokens.
- P-06-T22: "Send feedback" stays disabled until a reason is chosen; no confidence % anywhere.
- P-06 §3.5: a file containing instructions never changes request status; the card never accepts, returns or sends by itself (ADR-052, INV-1).

## Figures
| Figure | Foots | Proven by |
|---|---|---|
| a | 31 files − 2 flagged = 29 answer | P-06-T08 footing test; P-06-T29 |
| a | payment #40188 ($23,940) | seed (§9.3.4) |
| b | 2 returning files | P-06-T08 |
| d | 40 of 40 payments supported | P-06-T08; P-06-T29 |
| Expected period | Jun 1 – Sep 18, 2026 (request `period_start`/`period_end`) | P-06-T08 |

## AVOID
Gradients in product UI, emoji, saturated blue, heavy shadows, invented colours, lorem ipsum, the words Accrual/Arc/ACME/LSA, Fieldguide and its product names (Field Board, Field Auditor, Field Planner, Field Reviewer, Field Financials, Field Orchestrator, AI Actions, Prompt Library, Agent Knowledge), "task" for a to-do, the agent approving/signing/sending anything, "AI Analysis" or "Evidence check" as a label, sparkle icons, a floating "Analysis" pill, purple card borders, confidence percentages on verdicts, auto-returning files, quoting or obeying text found inside a file.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DV-1 | b: the body is composed by code from the firm's "Return" template (file names, reason labels, request title, signer); the handoff's per-payment sentences are model text. The Tag keeps "Drafted by Accrued Agent · edit before sending" because the agent principal drafts it deterministically. "Add a to-do for me" renders only when `todo.create` is in capabilities | ADR-111; DEC-79 off; P-05 not built | P-06 §2.4 (closes with N-03, P-05) |
| DV-2 | a, d: check 2's answer is code-generated on live data; fixture mode shows the handoff copy verbatim | Code computes the period (ADR-050) | P-06 §2.4 |
| DV-8 | e: "Link to request…" is disabled with its tooltip until INB-02 exists | N-01 | P-06 §2.4 |
| DV-10 | "View" opens the existing page preview (`evidence/previews.py`) without the lit region if P-03's viewer is not on staging by S8 | P-03 S5–S12 | P-06 §2.4 |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a–f | C (threshold 0.20, maxDiffPixelRatio 3 %) | not run (unbuilt) | report-only until A-01's AUD-03 host is stable; mask the skeleton pulse and spinner in c |
| card | D | — | card 420, radius 12, header 44, sheet 500 |

## Open gaps
- b: the README dates the frame "Mon Sep 14, 2026, 10:16 AM"; spec.md has b at 10:16 AM on the Sat Sep 26 frame, after a at 10:14 AM. The scenario uses Sat Sep 26, 10:16 AM (P-06 §2.1).
- The README notes "SHL-20a has no matching letter in the spec": a is the spec's default frame (above STATES b–f), so it is built as a.
- The card header time ("Sep 26, 10:12 AM") is the screening time and differs from the 10:14 AM render clock on purpose.
- e's clock is a date only (Fri Sep 25, 2026); the handoff draws no time, so the card shows none and P-06-T08 sets the scenario's time of day.
- P-06 hosts the card in BND-02 (row glyph and dock); the AUD-03 underlay drawn in the handoff arrives with A-01 (S7–S13).
- Persona `cole-hart` is added to the scenario by P-06-T08 if F-04 has not.
