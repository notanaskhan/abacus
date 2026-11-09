---
id: TASK-6540
title: "R-02-T14 finish: the approval-requested and governance-letter-sent emails"
spec: R-02
acceptance_criteria: [AC-36]
risk_zone: amber
status: in-review
branch: s33r-r02-t14
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-10
updated: 2026-11-10
plan_key: R-02-T14
---

## Objective
AC-36's two new client emails are sent: `approval_requested` on a provider's
`client_approval.requested`, and `governance_letter_sent` on `governance_communication.sent`.
Both use the firm's published template (database content); an unpublished one blocks the email
(recorded `blocked`, logged) while the item still shows on Home.

## Plan (amber)
- `engagements.ClientApprovalRequested`: optional identifiers `engagement_id`,
  `recipient_contact_id`, `sent_by`, `send_id`; A-06's delivery fills them (its
  `EntriesSentToClient` now carries `sent_by`).
- `portal/approval_emails.py`: subscribes to `client_approval.requested`; sends in the sender's
  name (`member_context`, None once they left: nothing sent) under `message.send`; one email per
  send and contact (idempotency key from the send). Refusals are logged, never raised.
- `assurance/governance_comms.approve_and_send`: after the send commits, each room recipient
  gets `governance_letter_sent`, authorised by the EP's `governance_comm.approve_send`
  (`SEND_AUTHORITIES`, DEC-1580 pattern). The envelope channel's email stays C7's.
- Test `tests/unit/portal/test_s33r_r02t14_emails.py`.
Rollback: revert.

## Left partial
- `client_entries_journal` (Download entries, `GET /portal/approvals/{kind}/{item_id}/journal`)
  needs a C11 journal layout; the backlog places it in R-02-T15. The route stays 501.

## Progress log
- `2026-11-10` — Built; unit tests pass (9). Gates at the end pass.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3140 | Client approval and governance emails: who sends, under which action, once per send | no |
