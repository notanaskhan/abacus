---
id: TASK-2306
title: T-01-T10 §7216 consent capture service
spec: SPEC-501
acceptance_criteria: [AC-32, AC-33, AC-34, AC-35, AC-36, AC-37, AC-38]
risk_zone: red
status: in-review
epic: T-01
plan_key: T-01-T10
branch: s18-t01-t10
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Consent capture: request (one document per purpose from the published template, recipients
from the provider-terms register, both spouses for a joint filing unit), renew (keeps purpose,
recipient and years; 409 consent_declined on a decline), record mode (signed PDF into COMPLIANCE
storage), decline and revocation, C7 envelope-event consumers, copy-delivered tracking, expiry
rule (stated expiry wins, else one year), access.changed on every change. Acceptance (row):
Feld's two documents arrive in one envelope as two consents, Kai Ferris unsigned leaves the set
Requested with 1 of 2 signed, and a renewal for Harold Stein answers 409.

## Plan (red: written before the build)
- Stacked on #819 (T-01-T17, itself on #816 and #818).
- organisations: `consents.py` (filing unit and signers, request rows, envelope completion,
  record, decline, revoke, renewal basis, consent rows); capture slot in `slots.py`; C19 routes
  for requests, renewals, records (slot), declines, revocations (direct); api exports.
- tax: `consent_capture.py` (template, render in the isolated child, COMPLIANCE storage, C7 draft
  from the `consent_set` source, rows), `envelope.completed` consumer; registered in `tax/api.py`.
- methodology: `published_consent_template`, `consent_expiry_months`.
- signatures api: export `create_draft`, source types, `staged_files` (new in imports.py).
- reporting api: export the render core and consent recipients.
- Migration 0462: consents.provider_terms_version CHECK 40 → 64 (material hash).
- Tests: `tests/unit/tax/test_t01t10_consent_capture.py`; DB-level ACs in T-01-T30 (S19).
- Rollback: revert; 0462 downgrade restores the 40-char CHECK.

## Not done here
- Per-signer progress ("1 of 2 signed"), declined/voided/expired envelopes: C7 emits only
  `envelope.completed` today (DEC-1353); the consumer takes the others when N-02 emits them.
- Production consents need a Bedrock entry in the provider-terms register (empty today).

## Progress log
- `2026-10-30` — built (DEC-1353). Tests written, not yet run (S18 end review). Per Ayush, no CI
  until the end: commits carry `[skip ci]`.

## Handoff
- **Current state:** built, PR open, held for the S18 batch (merge after #816, #818, #819).
- **Exact next step:** T-01-T16 consent registry read API on these rows.
