---
title: R-01 portal flips per firm (documents, drops, the room, settings, sender domain, scheduled follow-ups)
owner: builder
alarms: []
last_rehearsed: never
rehearse_by: 2027-07-06
---
# R-01 portal flips per firm (Tue Jul 13, 2027 window)

| Field | Value |
|---|---|
| Owner | the builder (every founder role under the solo amendment); Q-04 runs the window |
| Task | R-01-T36 (TASK-7802); Q-04's Tue Jul 13, 2027 per-firm flip (M10, `docs/ops/gates/M10-client-facing.md`) |
| Window | Tuesday 19:00 CT train (ADR P-29); no flip in a deadline week (`make windows`) |
| Related | `firm-rollback.md`, RB-20 (deliverability and the client-mail gate), RB-43 §15 (drops), RB-35/RB-36 (portal sign-in), `docs/plan/status/flag-renewals-2027.md` (the R-01 flags) |

Each flag is flipped per firm with `make flag FIRM=<code> FLAG=<flag> VALUE=true OPERATOR=<you>
REASON="<change record>" APPROVED_BY=<approver> ROLLBACK="<this file's row>"`; the flip guard asks
for the approver and the rollback. Flip in the order below; stop at the first row whose check
fails, roll that row back, and leave the rows before it on. No firm flips while M10's "delta #1
closed" clause is open (pen tests deferred, DEC-1389), and none without a live firm (DEC-1391):
until then this plan runs on PF-X1 only, reported as synthetic.

| # | Flag | Turns on | Before | Check after | Rollback |
|---|---|---|---|---|---|
| 0 | client-mail gate (not a flag) | the firm's client, third-party and respondent mail | the firm's templates imported and linted (`template_import`, dry run first); sender domain `verified` or the neutral sender accepted | a test send to the acting person's own address arrives | `python -m abacus_tools.client_mail close --tenant <id> --operator <you> --request-ref <ref>`: sends are recorded `blocked`, nothing is lost |
| 1 | `portal.settings_editor` | POR-20 template edits and ADM-10 settings for the firm's admins | one published version per key the firm uses | an admin previews a template at 600 and 390 with a sample contact | flag off: edits stop; published versions keep serving |
| 2 | `communications.firm_sender_domain` | From the firm's verified domain | ADM-10 shows the domain `verified` | a test send shows From `<local>@<domain>`; DKIM passes in its headers | flag off: From falls back to the neutral sender under the firm's name (RB-20) |
| 3 | `portal.drop_sort` | automatic linking of dropped files | the binder published; leads know unsorted drops come to them | a drop on a test binder links to its request or waits with `portal.drop_unsorted` | flag off: drops still arrive and wait for the firm (RB-43 §15) |
| 4 | `portal.third_party_room` | POR-14 for delegates and invitations on delegation | the delegations in scope reviewed by the engagement's lead | a delegate sees only their requests (n of N) | flag off: delegates' room answers 404; their uploads already made stay; re-invite after |
| 5 | `portal.intake_upload` | POR-03 "Upload something else" (N-01's portal intake) | `inbox.firm_intake` on; an intake team named | an upload reaches the Inbox as a matched thread | flag off: the button goes; uploads already made stay in the Inbox |
| 6 | `follow_ups.scheduled_send` | reminders sent on schedule (`send_on_schedule`) | the firm's policy published with that mode by its admin; rows 0 and 1 on | the next `next_send_at` matches the policy; the first scheduled send arrives | flag off: reminders return to drafts a person sends; nothing already sent is recalled |

After the window: write each row's flag-event id in M10's file, and record the flags' renewal or
retirement in `flag-renewals-2027.md`.

## Rehearsals

| Date | Where | Rows | Result |
|---|---|---|---|
| — | PF-X1 on staging | 0–6 | not run: no staging deploy of these flags yet |
