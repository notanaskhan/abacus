# Audit completion, release and archive v1 (module interface)

| Field | Value |
|---|---|
| Owner | assurance and evidence (A-07; SPEC-644) |
| Status | skeleton (A-07-T01, 2026-11-04; DEC-2260, DEC-2261); stub sections land with A-07-T04 and A-07-T05; final with A-07-T52 |
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

## Events (outbox; identifiers and enums only)
`report.released`, `archive.locked`, `archive.addition_logged`,
`governance_communication.sent`, `governance_communication.acknowledged` (A-07 §4.6).

## Service API
`assurance.api.record_acknowledgement(ctx, communication_id)`, called by R-02's portal route
(`tcwg.acknowledge`, client role `tcwg`, `scope_only` on the governance room).
