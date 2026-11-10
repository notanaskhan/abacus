---
id: TASK-6543
title: Governance letters as final C11 documents; the acknowledgement envelope; the room's letter PDF
spec: SPEC-314  # A-07 (letters); R-02 §3 POR-15
acceptance_criteria: []  # remainders of A-07-T26, A-07-T19 and R-02-T12 (see DEC-3145, DEC-3146)
risk_zone: red
status: in-progress
epic: A-07
plan_key: A-07-T26
branch: s32r-letters-render
worktree: /Users/ayushkbhatia/Accrued/abacus-s32
created: 2026-11-10
---

## Objective
No letter renders through C11 yet, so the governance letter has no final document: the ack_envelope
channel cannot draft its SIG-02 envelope (A-07-T26, A-07-T19) and the room's letter PDF answers 501
(R-02-T12). Build the letter's final-render path and both consumers.

## Plan
1. C11 `governance_letter` kind (a07_registrations): a body provider (the version's sealed
   sections as heading and paragraph blocks, read by code) and an approval provider (the send in
   flight, held in a context variable while the engagement partner's own request renders, as
   notices' response letter does).
2. approve_and_send: inside the send's unit of work, a DRAFT render of the approved version, then
   `render_final` on that draft's content hash with the send as the approval (ApprovalRef kind
   `governance_send`, id = send id). The partner already approved the version's content hash with
   a fresh second factor; the draft is that version's deterministic rendering, so approving the
   version is approving its draft. No migration: the document is found by its owner
   (`governance_communication_version`).
3. ack_envelope: after the send commits, a C7 draft from the `governance_letter` source
   (signatures.create_draft) prefilled with the final document and the recipient contacts as
   email-code signers; the communication's `envelope_id` is set. A person sends it from SIG-02.
4. Envelope source providers (draft, documents, signers) for `governance_letter`.
5. Portal `GET …/communications/{id}/pdf` (R-02-T12): a room member's letter; C10 publishes the
   final as a `governance_letter` deliverable (audience: the governance room) on first read once the
   final render has succeeded (idempotent per sent version), then the 60-second signed download;
   409 `rendering` while the job runs.
6. Tests: body blocks, approval provider, the send's draft-then-final order, the draft provider's
   prefill, the PDF route's member/non-member/rendering cases.
Rollback: revert; sends then record without a document, as before.

## Progress log
- `2026-11-10` — PR 1 (branch s32r-letters-render, DEC-3145): final render at send; envelope source and ack_envelope draft; unit tests. PDF route next.
- `2026-11-10` — PR 2 (branch s32r-room-pdf, DEC-3146): the room's letter PDF via C10 publish on first read; unit test.
