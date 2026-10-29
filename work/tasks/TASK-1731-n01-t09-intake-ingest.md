---
id: TASK-1731
title: N-01-T09 Intake ingest service
spec: SPEC-380
acceptance_criteria: [AC-2]
risk_zone: red
status: in-review
epic: N-01
plan_key: N-01-T09
branch: s14-n01-t09
created: 2026-10-28
updated: 2026-10-28
---

## Objective
`communications.api.record_inbound_message` and `add_attachment` for every channel, and the
staff-logged routes live. Acceptance (backlog row): "A staff-logged batch creates one thread with
its attachments as New or Waiting, and a scanner outage stores nothing."

## Plan (red)
- `communications/intake.py`: threading, deterministic matching, sealed bodies, HMAC addresses,
  scanned files, duplicate flags; events `inbound_message.recorded`,
  `inbox_attachment.received`; audit actions in the reviewed list.
- `intake_contract.py`: `POST /v1/inbox/intake` and `/intake/{message_id}/files` live (intake
  scope or `inbox.log_intake`; Idempotency-Key). `make regenerate`. DEC-821.
- Rollback: flag `inbox.firm_intake` off; revert.

## Acceptance
| Check | Test |
|---|---|
| One thread with Waiting (matched) or New (unmatched) attachments | `backend/tests/integration/backfill/test_n01t09_intake_ingest.py::test_ac_a_staff_logged_batch_creates_one_thread_with_waiting_attachments`, `…::test_ac_an_unmatched_batch_holds_new_attachments` |
| A scanner outage stores nothing | `…::test_ac_a_scanner_outage_stores_nothing` |
| Duplicates flagged, logger-only files, replay, sealed note and HMAC, threading, sender rule | five tests |

## Progress log
- `2026-10-28` — Built. ruff, pyright, lint-imports clean; `make regenerate`. Tests written, not
  run (end-of-batch review).

## Handoff
- **Current state:** PR open, held for the batch, stacked on #594.
- **Next:** P-07-T61.
