---
id: RB-80
title: Firm intake backlog (Inbox waiting or unmatched piling up)
owner: builder
owning_epic: N-01
alarms: []
last_rehearsed: never
rehearse_by: 2027-06-25
---
# RB-80 · Firm intake backlog

| Field | Value |
|---|---|
| Owner | builder (N-01-T30) |
| Severity range | SEV3; SEV2 when a deadline week is open (`make windows`) |
| Linked from | `backend/src/abacus/modules/communications/README.md` (Firm intake and triage) |
| SLO affected | none formal; the Inbox summary's `waiting` and `unmatched` counts |
| Kill switches that apply | `matching.firm_intake` (matcher candidates); `inbox.firm_intake` only as a last resort (it hides the Inbox) |
| Related | RB-06 (queue backlog), RB-24 (scanner down), RB-23 (workflow engine), RB-04 (connector outage) |

A backlog is attachments that stay `new` or `waiting`, or threads that stay unmatched. Two very
different causes: people have not triaged yet (a staffing matter, not an incident), or
AttachmentTriage is stuck, so nothing reaches Waiting. This runbook tells them apart.

## 1. Recognise it
- The firm's Inbox summary (`GET /v1/inbox/summary`) shows `waiting` or `unmatched` rising across a
  day, or a firm reports files "stuck on processing".
- `attachment_triage:<tenant>:<id>` workflows running long on the worker queue (Temporal UI).

## 2. Contain
- Stuck triage: nothing to contain; files are stored and scanned, only the derived steps wait.
  Do not restart workers blindly: each step is idempotent but a failing one fails again.
- Matcher cost or errors: `matching.firm_intake` off for the firm (`make flag … FLAG=matching.firm_intake VALUE=false`). Cards then show code's flags and no candidates; filing still works.

## 3. Preserve
Note the attachment ids and workflow ids (never file names, senders or subjects) in the
incident timeline.

## 4. Assess
1. Are attachments `new` with a finished triage run? Then the thread is unmatched: people match
   the client (`POST /v1/inbox/threads/{id}/match-client`), or the sender rule is missing.
2. Is the triage run stuck on a step? Read its failing activity:
   - the PII scan or masked preview: RB-43 (document services);
   - extraction or OCR: RB-47;
   - the scan at ingest refused files: RB-24 (they were never stored; the sender re-sends).
3. Many `waiting` with finished runs: a people backlog. Tell the firm; nothing is broken.

## 5. Notify
The firm's intake team lead, in the firm's words: "Files you received are stored and safe; they
are taking longer to prepare for filing."

## 6. Recover
Fix the failing step's cause (its own runbook), then let the workflow's retry carry on. A run that
exhausted its retries is restarted with the same id (`attachment_triage:<tenant>:<id>`), which
resumes at the failed step.

## 7. Verify
The firm's `waiting` count moves and new attachments reach Waiting within minutes.

## 8. Review
If the cause was a step, add a regression test to that step's module; if it was staffing, note
it in the support review (Q-04).

## Rehearsal log
| Date | Kind (drill, staging walk-through, tabletop) | Result | Changes made |
|---|---|---|---|
