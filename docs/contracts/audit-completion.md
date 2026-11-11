# Audit completion, release and archive v1 (module interface)

| Field | Value |
|---|---|
| Owner | assurance and evidence (A-07; SPEC-644) |
| Status | **v1 final** (A-07-T52, S36, 2026-11-11; DEC-3416). Skeleton A-07-T01 (DEC-2260, DEC-2261); stubs A-07-T04, T05; live handlers T18 to T47 |
| Code | `backend/src/abacus/modules/assurance/completion_contract.py` (T04), `release_contract.py` (T05) |
| Tests | `backend/tests/contracts/audit_completion/` (A-07-T06) |
| Flags | `audits.completion`, `audits.letters`, `audits.report_release`, `audits.archive` (A-07-T33, Thu Jan 27, 2028 train); until then every route answers 501 |
| Consumers | AUD-18, AUD-19, AUD-21, AUD-22, AUD-23, AUD-24, AUD-25; Q-05 (post-issuance, reissue, ADM-12); X-01 (attest release); A-08 and A-09 (release and archive); T-06 (`report.released`); R-02 (`record_acknowledgement`, C10 publish); I-01 (HOME-02 gate kinds); K-04 (Board phases) |

No C1–C21 register contract: A-07 §8.1. Additive changes go in place; a breaking change ships as
v2 with one sprint of overlap.

## Rules
- Every route is under `/v1/audits/{work_item_id}` (the assurance work item) with exactly one
  matrix action, `allowed_actions` on every record projection, identifier-only error facts,
  `seen_version` or `seen_hash` on every edit, and an Idempotency-Key on every client-visible or
  external effect.
- Code computes every figure, date and hash (ADR-050): the digest, the checklist counts, the
  clocks (release + 60 days; retention floor release + 5 years), the gate snapshot and the seal.
- Final verbs are five-layer human-only (matrix `agent: deny`, `require_live_human`, database
  CHECK, banned pattern, approval grant): `eqr.concur`, `eqr.mark_reviewed`, `rep_letter.approve`,
  `rep_letter.send`, `governance_comm.approve_send`, `report.release`, `archive.lock`,
  `archive_addition.approve`, and `decision.decide` on `going_concern` and `opinion` cards.
- Release takes no DEC-24 hold and no Undo (DEC-2260, OQ-1). Reissue writes only under Q-05's
  `post_issuance` kind (OQ-4).
- After lock, `archived_guard()` refuses every write to a guarded table with `409 archived`
  except under `archived_write` kinds `archive_addition`, `post_issuance`, `retention_extend`
  and `destruction_tombstone` (ADR P-43; A-07-T13).
- The record-mode routes of SPEC-314 (`/v1/engagements/{id}/completion`) stay live until
  A-07-T33 (DEC-2261).

## Operations
| Family | Section | Task |
|---|---|---|
| EQR (AUD-18) | *T04* | A-07-T04 |
| Completion, subsequent events, legal letters, going concern (AUD-19) | *T04* | A-07-T04 |
| Representation letter (AUD-21) | *T05* | A-07-T05 |
| Governance communications (AUD-22) | *T05* | A-07-T05 |
| Report builder (AUD-23) | *T05* | A-07-T05 |
| Issuance, release and filings (AUD-24) | *T05* | A-07-T05 |
| Assembly, archive, manifest and additions (AUD-25) | *T05* | A-07-T05 |

## EQR (AUD-18) — stub, A-07-T04
Code: `assurance/completion_contract.py`. Every route answers 501 until A-07-T18 and 404 for a
firm with `audits.completion` off once A-07-T33 creates it.

The reads are live (S35 follow-up, TASK-6742; DEC-3307): `GET …/eqr`, `…/completion`,
`…/subsequent-events`, `…/legal-letters` and `…/going-concern` answer from the rows the services
write (`assurance/completion_reads.py`), titles from the firm's templates. A procedure's title is
its key until the firm's procedure list carries wording; the bring-down reads `completed` from the
newest `audit.bring_down` run, `queued` once a report date is set. The writes stay 501.

| Operation | Method and path | Action | Live in |
|---|---|---|---|
| The review | `GET /v1/audits/{work_item_id}/eqr` → `EqrReviewOut` | `eqr.read` | T18 |
| Build the digest | `POST …/eqr/digest:build` (Idempotency-Key) → 202 `CompletionRunAcceptedOut` | `eqr.build_digest` | T18, T32 |
| Mark a card reviewed | `POST …/eqr/digest/{card_id}/reviewed` `{reviewed}` | `eqr.mark_reviewed` (human, `function_in: eqr`) | T18 |
| Update a checklist item | `PATCH …/eqr/checklist/{item_key}` `{status, sub_line, seen_version}` | `eqr.checklist_update` (human, `function_in: eqr`) | T18 |
| Concur (G6) | `POST …/eqr/concur` `{not_involved: true, concurrence_date, seen_version}` (Idempotency-Key) | `eqr.concur` (human, fresh MFA) | T18 |
| Request EQR (DF-05) | `POST …/eqr/request` `{message?}` | `eqr.request` | T18 |
| EQR notes | C3's `POST /v1/review-notes {kind: eqr}` and its messages, clear and reopen | P-04's actions | T18 |

Refusals: `403 eqr_only` (not the assigned EQR), `409 checklist_incomplete` (an item or an EQR
note open), `409 eqr_ineligible` (P-07 eligibility re-check), `401 mfa_required`,
`409 stale_version`.

## Completion, subsequent events, legal letters, going concern (AUD-19) — stub, A-07-T04

| Operation | Method and path | Action | Live in |
|---|---|---|---|
| The checklist | `GET /v1/audits/{work_item_id}/completion` → `AuditCompletionOut` (counts exclude N/A) | `completion.read` | T22 |
| Manual not applicable | `POST …/completion/items/{item_key}/not-applicable` `{basis, seen_version}` | `completion.update` | T22 |
| Reopen | `POST …/completion/items/{item_key}/reopen` `{seen_version}` | `completion.update` | T22 |
| Subsequent events | `GET …/subsequent-events` → procedures, events, bring-down | `completion.read` | T23 |
| Add or perform a procedure | `POST …/subsequent-events/procedures` · `PATCH …/procedures/{id}` | `subsequent_event.update` | T23 |
| Record an event | `POST …/subsequent-events` | `subsequent_event.create` | T23 |
| Legal letters | `GET …/legal-letters` · `PUT …/legal-letters` `{not_applicable, basis, seen_version}` | `completion.read` · `legal_letter.update` | T23 |
| Request a legal letter | `POST …/legal-letters/request` `{counsel_contact_id, message?}` (Idempotency-Key) | `legal_letter.request` | T23 |
| Going concern | `GET …/going-concern` → `GoingConcernOut` | `completion.read` | T23 |
| Request the EP's decision | `POST …/going-concern/request-decision` | `going_concern.request_decision` | T23 |

The `going_concern` card is decided only through C3 (`POST /v1/decisions/{id}/decide`), reserved
to the engagement partner. Refusals: `409 item_derived` (N/A on a projected item),
`409 decision_required`, `409 stale_version`.

## Letters, report, release and archive (AUD-21 to AUD-25) — stub, A-07-T05
Code: `assurance/release_contract.py`. Every route answers 501 until its task and 404 for a firm
with its flag off once A-07-T33 creates `audits.letters`, `audits.report_release` and
`audits.archive`. The letter's reads (`GET …/representation-letter`, `…/versions`,
`…/versions/{version_no}`) are live (TASK-6742): the stored representations with the clause
titles, the included clauses' standard wording or the person's edit, no signers yet (C7 owns them).

| Operation | Method and path | Action | Live in |
|---|---|---|---|
| Representation letter | `GET …/representation-letter` · `…/versions` · `…/versions/{version_no}` | `rep_letter.read` | T24 |
| Compose | `POST …/representation-letter/compose` (Idempotency-Key) → 202 | `rep_letter.draft` | T24 |
| Toggle a representation | `PATCH …/representations/{key}` `{included, seen_version}` | `rep_letter.draft` | T24 |
| Edit a firm-editable paragraph | `PUT …/paragraphs/{key}` `{text, seen_version}` | `rep_letter.draft` | T24 |
| Request approval | `POST …/representation-letter/request-approval` | `rep_letter.request_approval` | T24 |
| **Approve (human only, fresh MFA)** | `POST …/versions/{version_no}/approve` `{seen_hash}` | `rep_letter.approve` | T24 |
| **Send (human only)** | `POST …/representation-letter/send` `{signer_contact_ids, seen_version}` (Idempotency-Key) | `rep_letter.send` | T24 |
| Remind · re-date | `POST …/remind` · `POST …/re-date` (Idempotency-Key) | `envelope.remind` (N-02) · `rep_letter.send` | T24 |
| Governance communications | `GET …/governance-communications` · `GET …/{id}` | `governance_comm.read` | T26 |
| Create · compose · edit | `POST …/governance-communications {kind}` · `POST …/{id}/compose` (202) · `PATCH …/{id}/sections/{key}` | `governance_comm.draft` | T26 |
| Request approval | `POST …/{id}/request-approval` | `governance_comm.request_approval` | T26 |
| **Approve and send (human only, fresh MFA)** | `POST …/{id}/approve-and-send` (Idempotency-Key) | `governance_comm.approve_send` | T26 |
| Recipients | `GET` · `PUT …/governance-recipients` | `governance_comm.read` · `governance_comm.manage_recipients` | T26 |
| Report | `GET …/report` · `…/report/versions` · `…/versions/{a}/diff/{b}` · `…/report/reason-codes` | `report.read` | T27 |
| A choice | `PATCH …/report/choices` `{field, value, reason_code?, seen_version}` | `report.draft` | T27 |
| Request the opinion decision | `POST …/report/request-decision` `{field: opinion}` | `report.request_decision` | T27 |
| Draft render | `POST …/report/documents` `{format, report_version}` (Idempotency-Key) → 202 | `report.generate` | T27 |
| Report approval | C3's `POST /v1/sign-offs {target: audit_report_version, level: L4}` | `sign_off.l4` (P-04) | T27 |
| Release readiness | `GET …/release` → gates, also-required, `gate_hash`, `viewer_can_release` | `report.read` | T30 |
| **Release (human only, fresh MFA)** | `POST …/release` `{authorize: true, seen_gate_hash}` (Idempotency-Key) → 202 | `report.release` | T30 |
| Filings | `GET …/filings` · `PATCH …/filings/{id}` | `report.read` · `filing.update` | T36 |
| Archive | `GET …/archive` · `GET …/archive/manifest` · `GET …/archive/additions` | `archive.read` † | T31, T37 |
| Binder index | `POST …/archive/binder-index` (202) | `archive.build_index` | T31 |
| Request lock | `POST …/archive/request-lock` | `archive.request_lock` | T31 |
| **Lock (human only, fresh MFA)** | `POST …/archive/lock` `{assembly_complete: true, then_roll_forward, seen_checklist_hash}` (Idempotency-Key) → 202 | `archive.lock` | T37 |
| Add after lock | `POST …/archive/additions` (Idempotency-Key) | `archive_addition.create` † | T42 |
| **Approve or reject an addition (human only, fresh MFA)** | `POST …/additions/{id}/approve` · `…/reject` | `archive_addition.approve` † | T42 |
| Verify the seal | `POST …/archive/verify` (202) | `archive.verify` † | T42 |

† `archived_exempt`: these act on a locked work item (kind `archive_addition` for the addition
verbs; reads and verify change nothing). Every other mutating route answers `409 archived`.

### Human-only actions and their audit events
| Action | Fresh MFA | Audit event (identifiers and fingerprints only, DEC-60) |
|---|---|---|
| `eqr.concur` | yes (A-07-T18) | `eqr.concurred` |
| `eqr.mark_reviewed` | — | `eqr.card_reviewed` |
| `rep_letter.approve` | yes | `rep_letter.approved` |
| `rep_letter.send` | — (live human) | `rep_letter.sent` |
| `governance_comm.approve_send` | yes | `governance_communication.sent` |
| `report.release` | yes (A-07-T30) | `report.released` |
| `archive.lock` | yes (A-07-T37) | `archive.locked` |
| `archive_addition.approve` | yes | `archive.addition_approved` · `archive.addition_rejected` |
| `decision.decide` on `going_concern` and `opinion` | yes (C3) | `going_concern.decided` · `opinion.decided` |

Refusals: `409 gates_not_met`, `409 content_changed`, `409 approval_required`,
`409 decision_required`, `409 date_mismatch`, `422 internal_amount_in_text`, `409 archived`,
`409 checklist_incomplete`, `403 ep_only`, `401 mfa_required`, `409 seal_mismatch`,
`409 release_mode_external`, `409 stale_version`.

## Events (outbox; identifiers and enums only)
`report.released`, `archive.locked`, `archive.addition_logged`,
`governance_communication.sent`, `governance_communication.acknowledged` (A-07 §4.6).

## Service API
`assurance.api.record_acknowledgement(ctx, communication_id)`, called by R-02's portal route
(`tcwg.acknowledge`, client role `tcwg`, `scope_only` on the governance room).

## Consumer notes (A-07-T52, v1)
What each consumer may rely on in v1, and what stays with the consumer:
- **Q-05.** Post-issuance events and reissue write through the `post_issuance` archived-write kind
  only (ARCHIVE-001). AUD-23 g Reissue is fixture-only until Q-05 (DV-9). ADM-12's retention reads
  `archives.retention_until`, which is never below release + 5 years.
- **X-01.** An attest release reuses G8's grammar: one original per work item, a fresh second
  factor and the engagement partner only. X-01 registers its own gate cards and must not write
  `report_releases` directly (RELEASE-001).
- **A-10.** FSP-06's templates replace AUD-23's inline list (DV-8). The report's C11 document and
  its approval grant stay A-07's.
- **A-08.** AUD-26's review and compilation reports (SSARS) use the same release and archive. J05
  step 6 waits on AUD-26 (fixme in `J05-ssars.spec.ts`).
- **A-09.** Group audits archive per component work item. `archive_state` is per work item.
- **T-06.** Subscribes to `report.released`. The event carries identifiers only.
- **R-02.** `record_acknowledgement` for TCWG acknowledgements; C10 publishes the released report's
  deliverables. Portal text never says "Accrued".
- **I-01.** HOME-02's gate kinds for G6 to G9 come from C13 (`human_gates`). The projection is
  exempt from `archived_guard()`.

## Flag retirement (A-07-T52)
The four rollout flags (`audits.completion`, `audits.letters`, `audits.report_release` and
`audits.archive`; `expires: 2028-04-26`) retire into the `assurance_completion` entitlement
after the M16 flip. This is the same path A-06 took (RB-66, migration 0713):
1. A migration gives every firm with any of the four flags on an `assurance_completion` row.
2. The routes' `require_live` reads the entitlement instead of the flag.
3. The flags are deleted on the Tue Apr 25, 2028 train, before they expire.

Until then each flag is renewed per `docs/runbooks/RB-26-flag-expiry-wave.md`.
