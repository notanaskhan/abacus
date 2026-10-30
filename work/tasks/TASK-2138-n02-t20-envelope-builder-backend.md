---
id: TASK-2138
title: N-02-T20 SIG-02 backend (drafts, edits, checks, Send and Undo)
spec: SPEC-381
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
epic: N-02
plan_key: N-02-T20
branch: s16-n02-t20
created: 2026-10-30
updated: 2026-10-30
---

## Objective
SIG-02's backend (N-02 §3.4). Acceptance (backlog row): "A signer without an email blocks Send
with 409 validation_failed, and a send undone inside 10 seconds makes no provider call."

## Plan
- Migration `0405_envelope_drafts` (revises 0404, so the branch stacks on N-01-T17's): the
  `(envelope_id, "order")` uniques on documents and signers become deferrable; the app may delete a
  signer of an unsent draft only (`envelope_draft_signer_delete`).
- `signatures/sources.py`: typed `SourceDraft`, `SourceDocument`, `SourceSigner` and an optional
  `draft` provider on `EnvelopeSource`; a source without one answers 409 `source_cannot_draft`.
- `signatures/builder.py`: `create_draft`, `update_draft` (If-Match, party-matched signers,
  document order), `validate` (seven code checks), `send` (live human, grant `not_before` +10 s,
  `sent_by`/`sent_at`), `undo_send` (voids the grant; `envelope.send_undone`).
- Routes in `signatures/contract.py` go live; the drawer fills signer `title` and `email`
  (DEC-1174). `organisations.signer_contacts`, `evidence.tin_exposure` added to the APIs.
- Error catalogue and the generated client regenerated; C7 contract test lists the live routes.
- Tests: `tests/integration/backfill/test_n02t20_envelope_builder.py`.
- Rollback: the routes return to stubs; 0405's downgrade restores the plain uniques and revokes
  the delete.

## Decisions
- DEC-1178.

## Progress log
- 2026-10-30: built. Integration tests run at the end review (build-first). The page-preview route
  stays a stub (N-02-T21's renderer); EnvelopeWorkflow starts after the window in N-02-T22.
