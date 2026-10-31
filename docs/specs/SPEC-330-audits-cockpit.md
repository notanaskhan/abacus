---
id: SPEC-330
title: "Audits cockpit, A-01 wave 1: screen contracts, the audits family stub, record-mode phases and the cockpit L3 - outline"
status: draft
owner: ayushkbhatia
risk_zone: red
related_adrs: [ADR-005, ADR-013, ADR-018, ADR-024, ADR-031, ADR-036, ADR-139]
related_specs: [SPEC-314, SPEC-321]
created: 2026-10-24
updated: 2026-10-25
---

> **Outline.** Written with the S7 rows of A-01 (T01, T02, T03, T05, T06; TASK-1100 to TASK-1104).
> The epic is the source until this spec is final: `docs/plan/epics/A-01.md` §3.1, §3.2, §3.5
> (stories), §4 (backend), §5 (frontend), §8 (contracts). The contract is
> `docs/contracts/audits-cockpit.md`; the screen contracts are `docs/screens/AUD-01.md`,
> `AUD-02.md` and `AUD-03.md`.

## 1. Summary
An audit team sees its assurance portfolio (AUD-01), opens one engagement into a cockpit whose
rail later epics extend by registration (AUD-02), and triages the PBC list beside the documents
(AUD-03). Phases move in record mode, by a named person, while Accrued computes no gate for them.

## 2. Problem and context
`assurance_work_items` carries a phase (migration 0068) that only SPEC-314's release and archive
write. There is no audits index, no cockpit projection, no way for a person to record Fieldwork,
and no EBP profile facts. The screens are built in fixture mode first, so the contract comes
first (AGENTS 15).

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Every firm role | Reads the index (metadata) and the cockpit (content roles) after walls |
| Engagement partner, manager | Record a phase; edit the EBP profile |
| Engagement partner | Records an external release (A-01-T23) |
| Agent, system, support | Denied every record and profile action (INV-1) |
| Client principals | Denied every `/v1/audits` route (INV-4) |

## 4. Goals and non-goals
**Goals:** the three screen contracts; the `engagement_export` status words; the audits routes,
models, matrix rows and flag `audits.cockpit`; the registration slots; consumer tests; migration
`assurance_profile_phase` and the phase service; the cockpit L3 in `apps/web/src/domain/audits`.
Wave 2 (S8: A-01-T07 to T10) adds the Brightwater Hale assurance slice through A-01's services,
the index and cockpit read models and the C5 v1.1 request facts with the Source Documents
aggregate. **Non-goals:** exports (A-01-T17 onward), release and archive records (A-01-T23), the
screens (A-01-T11, T12, T15).

## 5. User stories and acceptance criteria
### Story 1 · Screen contracts (A-01-T01)
- **AC-1** Every artboard letter of AUD-01 (a–i), AUD-02 (a–i) and AUD-03 (a–g) is listed as built, fixture-only or deferred with its owning epic, and every designed link of the three screens names a manifest ID.
- **AC-2** The registry emits the export words (`engagement_export`: queued, packaging, ready, failed, expired, undone) beside the existing phase, archive (`audit_engagement`) and rail (`audit_section`) words.

### Story 2 · Audits family stub (A-01-T02)
- **AC-3** Every audits route in `docs/contracts/audits-cockpit.md` §2 exists with exactly one matrix action and documents 404 and 501; the record writes take an `Idempotency-Key`.
- **AC-4** With `audits.cockpit` off every audits route answers 404; with it on, a stubbed route answers 501 `not_implemented`.
- **AC-5** Phases, rail states and request words are C2's generated enums; every field carries a classification tag; no model carries a hidden-count or hidden-by-wall field (INV-3, DEC-43); no index field carries an amount or materiality.
- **AC-6** `assurance.record_phase` and `assurance.record_archive` allow the engagement partner and manager; `assurance.record_release` the engagement partner only; release and archive require `mfa_recent`; all three require independence and deny agent, system and every client role.
- **AC-7** `register_audit_section`, `register_index_tag` and `register_audit_segment` refuse a second, different registration of a key and a section without a state provider; an unregistered section is never projected.

### Story 3 · Consumer contract tests (A-01-T03)
- **AC-8** The consumer suite asserts the index envelope (tiles foot to `total`, `counts` minus the active tile), the registry codes of every status field, the absence of hidden-count fields, and the C5 v1.1 additive request-row fields as optional.

### Story 4 · Record-mode phases (A-01-T05)
- **AC-9** A person records only the next phase of the record-mode sequence: a backward move answers 409 `phase_backward`, a skipped phase 409 `phase_skip`, the current phase 409 `phase_backward`.
- **AC-10** A phase whose gate has a registered provider cannot be recorded (409 `phase_follows_gate`); it is derived from `gate.met` (mode `derived`, actor `system`).
- **AC-11** An agent or system context is refused (403), and the table refuses a `recorded` row whose actor is not human.
- **AC-12** A recorded move writes one insert-only `assurance_phase_events` row, moves the projection (`phase`, `phase_source`, `phase_changed_at`, `version`), audits `assurance.phase_recorded` and emits `assurance.phase_changed`, in one unit of work.
- **AC-13** A derived move audits `assurance.phase_derived` and emits `assurance.phase_changed`; replaying the same `gate.met` moves nothing.
- **AC-14** The EBP profile accepts plan kinds `dc`, `403b`, `db` only (no health and welfare plan), keeps the §103(a)(3)(C) label as a boolean, answers 409 `stale_version` on a stale `seen_version`, and audits `assurance.profile_updated`.

### Story 5 · Cockpit L3 (A-01-T06)
- **AC-15** The section rail renders only the rows it is given, every disc carries text, the sub-line and idle-pill grammars follow the registry, and the TPL-02 specimen still passes.

### Story 6 · The Brightwater Hale assurance slice (A-01-T07)
- **AC-16** The loaded E0 tenant's 27 assurance work items stand at Planning 7 · Fieldwork 9 · In review 6 · Ready to release 2 · Released 3, and every phase past Planning was reached through `assurance_phase_events` written by A-01's services, one step per event: Fieldwork and In review recorded by the engagement partner, Ready to release and Released derived with their gate named; the loader writes no phase.
- **AC-17** The EBP profile facts are set through the profile service: 12 defined-contribution and 2 403(b) plans, Northwind's §103(a)(3)(C) label, each audited `assurance.profile_updated`.

### Story 7 · The AUD-01 index (A-01-T08)
- **AC-18** `GET /v1/audits` foots: with no tile pressed the phase tiles (`counts`) sum to `total` (E0: 27 = 7 + 9 + 6 + 2 + 3); a pressed tile filters the rows and every tile keeps its count; segments count the base without the segment (E0: FS 6 · EBP 14 · Review & compilation 7, no SOC & IT or Internal audit without the entitlement); the caption reads EBP 14 · FS audit 6 · Review 4 · Compilation/preparation 3.
- **AC-19** A walled audit is absent from rows, tiles, segments, caption and facets, the totals foot without it, its cockpit answers 404, and no field counts it; the keyset cursor walks every row once.
- **AC-20** PBC reads received of asked client-visible requests of published PBC binders and is null without one (Fairhaven before G3); report due is the work item's due date with its tone on `kernel.clock` (DEC-263); a released row's archive clock counts 60 days from its release (Bayside "Archive in 13 days" at E0); archived rows group under Released.
- **AC-21** A metadata-only reader (firm admin) sees every `metadata` tag and no `content` tag; a client principal, an agent or the system is refused before anything is read.

### Story 8 · The cockpit (A-01-T09)
- **AC-22** The rail holds only registered sections: a later epic registers a row (A-02's Trial Balance) without editing A-01, and a provider that answers `None` or fails leaves its row out.
- **AC-23** A-01's Overview rows read Client, Methodology (hidden without a pinned version), Standards set (hidden until it has a name), Source Documents "n of N received", Team in role order ("MO · TW · HL · MD · AC") and Activity; A-01's tags are Letter sent, EQR (from In review) and No report; "Started …" and "Processing" appear only from a registered C6 v1 engagement-run provider.
- **AC-24** A metadata-only reader gets the audit bar and overview only (no bands, dock or actions); an archived work item reads `read_only_reason: archived` with no actions.

### Story 9 · C5 v1.1 request facts and Source Documents (A-01-T10)
- **AC-25** P-06's binder request rows carry `owed_by` (an open delegation's contact as `third_party`, else the client assignee as `client_contact`, open requests only), `latest_upload` (the newest live fulfilment: label, date, channel), `match_confidence` (the matcher's shown pick for that request) and `linked_count` for the firm; a client principal's rows never carry the first three.
- **AC-26** The Source Documents aggregate groups the work item's asked PBC requests by category in binder and category order with "n of N" that foot to its totals; Missing first orders needs review, requested, received; `q` narrows rows, never totals.
- **AC-27** `requests.api.pbc_counts` answers only for work items with a published PBC binder, filtered by `visible(engagement.read_metadata)`.

## 6. Data
Migration `0134_assurance_profile_phase`: `assurance_work_items` + `ebp_plan_kind`,
`limited_scope_103a3c`, `phase_source`, `phase_changed_at`, `version`; new insert-only
`assurance_phase_events`. See A-01 §4.2 and the contract.

## 7. Open questions
Recorded in `docs/product/decision-log.md` DEC-260 to DEC-264 and DEC-310 to DEC-313.

## 8. Legacy evidence assertions superseded (A-01-T21)
A-01-T21 retired `legacy/Board.tsx`, `legacy/ItemDetail.tsx` and `legacy/AIReviewPanel.tsx` with
their tests (`Board.test.tsx`, `spec021.test.tsx`, `spec022.test.tsx`, `spec030review.test.tsx`).
`/engagements/$id/requests` and `/engagements/$id/items/$itemId` now only redirect to AUD-03 on the
engagement's assurance work item (`?item=` for one request); with `audits.cockpit` off they show
F-05's flag-off state, and an engagement with no assurance work item opens its record (DEC-442).
`EvidencePreview.tsx` (SourceHover), `DecisionActions.tsx` (Review) and `CheckResults.tsx`
(POR-04's planned pre-check reuse, R-01 §8) stay: something live still imports them, or a later
task reuses them, and their own tests (`spec029*`) keep running unchanged. `InboxPanel.tsx`,
`InboxAIMatch.tsx` and `matchingMessages.ts` were retired by N-01-T29 (DEC-1390): no route mounted
them; their tests (`spec023`, `spec033matching`, `spec033matcher`) map below.

Each old assertion maps to the test that now carries it, or is retired with its behaviour
(DEC-442). "AUD-03 …" and "SHL-20 …" name tests in `screens/AUD-03/AUD-03.test.tsx` and
`screens/SHL-20/SHL-20.test.tsx`; "T21 …" names the tests A-01-T21 added to AUD-03.

| Old test (file · AC) | Assertion | Now carried by |
|---|---|---|
| spec021 · ac1 | every version newest first with how it arrived | AUD-03b / AUD-03f (the upload row names the file, its upload date and the match); the version history is SHL-08's (P-03) |
| spec021 · ac2 | download with the token; a failed verification explained | retired with ItemDetail: AUD-03's viewer serves page images through C4, no download control is designed (DEC-442) |
| spec021 · ac3 | citations marked verified; model text as plain text with the AI tag | SHL-20 "the flag reasons are the verified citations, verbatim, as agent text" |
| spec021 · ac4 | a manager decides the newest version; staff see the state only | AUD-03b (Accept moves the rail) · AUD-03 "staff accept off: the strip shows only Return…" · AUD-03 acceptance "needs a human click" |
| spec021 · ac5 ac6 | not allowed; empty state without evidence | AUD-03 "not found … 404 with no hint (INV-3)" · AUD-03e "Not received yet" |
| spec021 · SPEC-024 | Screen now starts screening | SHL-20 "reads the one line, with Screen now and Link to request… held off" and "Rerun asks the server to screen again (a)" |
| spec021 · route | an item opens on its own page | T21 "SPEC-021 (item route): … opens AUD-03 on that request" |
| spec022 · ac1 ac3 | retrievability tiers A–E, unavailable A items, unclassified | retired by design: the AUD-03 handoff draws no tier (DEC-442) |
| spec022 · ac5 | the summary strip | AUD-03 acceptance (R2) "counts stay 24 requests · 11 received · 1 needs review · 12 requested" and the group-count footing test |
| spec022 · ac5 | filters narrow by text; the URL carries them; no-match state | T21 "SPEC-022 ac5: the search narrows the rows …" · `?q=`, `?sort=`, `?item=` in `routes/firm/audits.tsx` |
| spec022 · ac2 | tier override and Automatic | retired by design (no tier on AUD-03, DEC-442) |
| spec022 · board | the legacy board answers with the flag off | T21 "SPEC-022 (flag off): … the flag-off state, never a board" |
| spec023 · ac2 ac3 ac4 ac6 | the inbox: add files, suggestions with a score, match, removed, refused | retired with InboxPanel (N-01-T29, DEC-1390); the rules are the server's, see the N-01-T29 rows below; AUD-03c carries the matcher's held proposal ("match 62%") |
| Board.test · ac18 | engagement and item with status, source and screening | AUD-03a/b (row status, file, screening glyph) · AUD-03 acceptance (R2) "Linked (n) and the screening glyph" |
| Board.test · ac18 | hostile rationale, quote, note, citation as text only | SHL-20 "flag reasons … as agent text" (AgentText); `agent-text.test.tsx` |
| Board.test · ac18 | Screening… while running; nothing without evidence | SHL-20 "c: the spinner line …" · AUD-03 acceptance (R2) "requested rows show — and no glyph" |
| Board.test · ac18 | loading skeleton; alert with Retry; empty list | AUD-03 "loading" · AUD-03 "error … offers a retry"; the empty audit is DEC-341's `canvas.empty` |
| Board.test · ac18 | add a request item | SHL-14 over AUD-03 ("+ Add", P-06-T13 tests) |
| Board.test · ac18 | retrieve the trial balance; queued for capacity; polling | retired with the Board: retrieval moves to A-02's Trial Balance (DEC-442) |
| Board.test · ac18 | stops polling for screening after two minutes | SHL-20 "c: … polled every 2 s" (the card owns the poll) |
| Board.test · ac18 | offers nothing that accepts, approves, rejects or waives an agent proposal | AUD-03 avoid "agent-owned decisions" · AUD-03 acceptance "nothing is accepted on load" |
| Board.test · TASK-105 | counts by status; a request opens beside the list | AUD-03 group counts · AUD-03a (the selected row opens the viewer dock) |
| Board.test · TASK-110 | a citation opens the source at its cell | SHL-20 "View opens SHL-08 on the flagged file with its region lit" |
| spec030 · ac6 ac10 | the AI review panel: flags with quotes, Review now, unavailable, data boundary, states | the C-34 screening card on AUD-03: SHL-20 a–f, "View opens SHL-08 …", "Rerun …", "c: …"; the data-boundary wording is the screener's (Q-02) |

### N-01-T29: the engagement inbox panel (DEC-1390)

No route mounted `InboxPanel` (the engagement drop zone's old panel) or `InboxAIMatch`; the firm
files attachments in INB-02 and the client uploads in POR-03. Each assertion of their tests maps
to the test that carries the rule now. "q03t047 …" names `backend/tests/integration/backfill/
test_q03t047_requests_client_hub.py`, "q03t033 …" `test_q03t033_matcher.py`, "uploads …"
`test_client_uploads_and_processing.py`.

| Old test (file · AC) | Assertion | Now carried by |
|---|---|---|
| spec023 · ac2 | several files added at once; a refused one explained | q03t047 "spec023_ac2 dropped files wait unassigned and a duplicate is refused" · uploads "ac9 too large, wrong type by content and duplicate are refused"; INB-01's log sheet "says a refused file in the design's words" (`domain/inbox/LogIntakeSheet.test.tsx`) |
| spec023 · ac3 ac4 | a suggestion with its score and matched words; assigning it records a followed suggestion with its source and rank | q03t047 "spec023_ac3 suggestions show score and words and a contributor sees only theirs" · q03t033 "ac6 the audit records a followed content or file-name suggestion" |
| spec023 · ac4 ac5 | match by choosing a request; remove a file | q03t047 "spec023_ac4 assigning makes evidence, audits and empties the inbox" · "spec023_ac5 a discarded file leaves the inbox and becomes no evidence"; INB-02 "b: … Apply stays disabled until one is chosen" |
| spec023 · ac4 | "Someone already matched or removed this file." | q03t047 "spec023_ac4 a file someone already matched answers inbox_file_gone" (new in N-01-T29) |
| spec023 · ac6 | the panel shows nothing when the inbox is refused | retired with the panel (no screen draws it); q03t033 "ac5 a walled member and another firm get 404" |
| spec033matching · ac1 | the fixed reason labels; a content suggestion with its reasons, source and rank | q03t033 "ac1 an extracted statement is suggested by its contents with fixed reasons" · "ac1 the code rules keep their reasons beside a matcher pick" · "ac6 the audit records …"; the labels' only reader was the panel |
| spec033matcher · ac3 | each proposal with its rationale and verified quote | q03t033 "ac3 only verified in-list proposals above the floor are shown" · "ac3 a verified proposal under half confidence is not shown"; AUD-03c on the firm side |
| spec033matcher · ac4 | no suggestion for real client data, and why | q03t033 "ac4 a real firm is refused at the boundary and keeps its content suggestions" |
| spec033matcher · ac3 | "None of the requests fit" with its reason | q03t033 "ac3 none fit is shown with its rationale and no proposal" |
| spec033matcher · ac3 | ask the matcher when nothing ran; a refusal explained | q03t033 "ac3 suggest with AI is for partner, manager, senior and staff" · "ac3 suggest with AI without a real route is ai_match_unavailable" |
| spec033matcher · ac5 | the client sees "Suggested" with no AI words and never asks for matches | q03t033 "ac5 a client gets the pick without rationale or quotes and no firm read" (the server never returns them to a client role) · POR-03 "POR-03c: the estimated payments read Suggested — Brightwater Hale will confirm" |
