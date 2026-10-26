---
id: TASK-1252
title: The SHL-20 screening-return draft and its send (P-06-T22 backend leftover; C5 §12)
spec: SPEC-319
acceptance_criteria: [AC-24]
risk_zone: red
status: in-review
epic: P-06
plan_key: P-06-T22
branch: lo-screening-followup
created: 2026-10-26
updated: 2026-10-26
---

## Objective
`POST /v1/engagements/{eid}/request-items/{item_id}/follow-ups` answers 501 today. Make it
draft a screening-return follow-up from the firm's published Return template, and make the
follow-ups v2 send and Undo carry out the return: two `send_back` decisions with the reason, the
request `returned`, and a shared comment carrying the sender's final text (C5 §12, DEC-220
"Deferred", DEC-351 b).

## Plan
- **Draft** (`agents/follow_up_drafts.py: draft_return`): behind `screening.card` (route).
  `follow_up.draft` on the engagement (agent: `task_scope`, as the contract says). The request
  must be client-visible, not deleted, Uploaded or Returned, in a Published binder; each
  returned file must be a live fulfilment of that request (else 404). The title is
  scope-checked (409 `out_of_scope`); the body is composed from
  `notification.follow_up_sent.screening_return` (409 `follow_up_template_missing` until
  imported). One follow-up, kind `screening_return`, `drafted_by_kind = 'agent'`, to the
  request's first recipient (DEC-220's order), its files in `follow_up_returns` with the reason.
  Audited `follow_up.drafted`.
- **Reads** (`requests/follow_up_reads.py`): `follow_up_candidates(..., returning=True)` reads
  Uploaded or Returned requests, so a return's view and send see its request.
- **Send** (`_send_one`, same unit of work as the grant): for `screening_return`, after the scope
  check, `evidence.return_files` records one `send_back` per file (a person serving a request,
  `evidence.reject` with its independence; a file need not be the request's newest, since
  returning never accepts an older file over a newer one), moves the request to `returned`, and
  `requests.authorise_return_comment` checks `comment.share` for the sender.
- **Delivery** (`on_follow_up_sent`, after the Undo window): the email and the shared comment
  (the body as sent, by the sender, one per follow-up: its id is derived from the follow-up's),
  so Undo never leaves a comment the client already read. Audited `comment.posted`.
- **Undo**: voids the grant, then `evidence.undo_returned_files` undoes each send-back in reverse
  order (P-01-T13's rule: the sender, within 10 s), putting the request back.
- **History**: a return is not a reminder: `follow_up_history` leaves `screening_return` out of
  POR-20's count.
- **Contract**: C5 §12 behaviour text; the SHL-20 consumer tests stop expecting 501.
- No migration (0128 has the kind, `follow_up_returns` and the template key), no flag, no matrix
  row. DEC-368 records the split between send and delivery.
- **Tests first**: `tests/integration/test_screening_return.py`.
- **Rollback**: revert the commit; the route answers 501 again. Rows written stay valid (the kind
  and tables already exist).

## Progress log
- 2026-10-26: planned.
- 2026-10-26: built. `evidence.return_files` / `undo_returned_files` reuse `decide`'s row writer
  (`_write_decision`); delivery posts the comment before the email. Tests first
  (`test_screening_return.py`), then the SHL-20 contract tests moved the route from STUBBED to
  LIVE; `make generate` dropped the 501. Gates and the affected suites green.
- 2026-10-26: security review (changes requested). Fixed: H1, a return could mark the request
  Returned over a newer upload or move another request a file also answers (now 409
  `superseded` / `file_answers_other_requests`); M1, the sender never saw the files
  (`FollowUpOut.returning`, additive) and bulk send could return them (409
  `follow_up_send_alone`); M3, tests for both plus a sender without `evidence.reject`; L1, the
  comment is audited on the sender's behalf; L2, the body is checked as a comment at the send.
  Accepted and recorded in DEC-368: M2 (a refused delivery grant leaves the send-backs), L3
  (delivery re-checks only `follow_up.send`), L4 (the decisions' Undo window starts a few ms
  earlier), L5 (Returned shows in the portal during the window).
- 2026-10-26: P-06-T23's independent suite covers the screening return (`backfill/test_p06t23_follow_ups_v2_independent.py`, TASK-1280).
