---
id: TASK-8107
title: "C-01-T19: Close intake: BD1 RequestPublishWorkflow, incorporation re-run offer, summary VM"
spec: SPEC-655
acceptance_criteria: [AC-2]
risk_zone: amber
status: in-review
branch: c01-t19-close-intake
worktree: /Users/ayushkbhatia/Accrued/abacus-s46
created: 2026-11-15
updated: 2026-11-15
plan_key: C-01-T19
---

## Objective
At BD1 09:00 firm time, pin each close to the plan version effective for its month and publish
that version's request templates into the close's `close_intake` binder, once; serve CLS-03's
request tree (with the "Re-run affected tasks" offer on incorporated requests) and questionnaire.

## Plan (amber: written before the build)
1. `requests/close_intake.py` (+ `requests.api`): `generate_close_intake` (binder per close, part
   1; one request per template, idempotent on `linked_ref.close_template_id`; bank-feed templates
   internal; due dates; sent stamps under the plan publisher's authority), `intake_items`.
2. `closes/intake.py`: `seconds_until_publish`, `publish_requests` (pin → generate → emit
   `close_requests.published`), `request_tree`, `close_questionnaire`, activities,
   `schedule_publish`; `request_publish_types.py`, `request_publish_workflow.py`.
3. `closes/kind.py` emits `close.created`; `closes/api.py` subscribes it to `schedule_publish`
   (after commit, in the worker) and exposes `WORKFLOWS`/`ACTIVITIES`/`SUBSCRIPTIONS`.
4. `contract_work.py`: `RequestNodeOut.rerun_plan_row_ids` (additive); the tree and questionnaire
   routes served.
5. Tests: `tests/integration/test_c01t19_close_intake.py`,
   `tests/workflows/test_c01t19_request_publish_timer.py`.
Rollback: revert; behind `closes.engine` (default off).

## Progress log
- `2026-11-15` — Planned at the S46 kickoff (#2053); plan written above before building.
- `2026-11-15` — Built (DEC-5078). App and worker import cleanly. Tests run at the end pass.
- **Partial within the row:** the intake summary VM (`/evidence-versions/{id}/close-summary`)
  stays 501: its `sheet_cell` totals read P-11's extracted tables of an uploaded file and its
  paragraph is `close.agent` mode `intake` (C-01-T29, S47). Client email for new close requests
  is POR-20's DB template (C-01-T42). Reminders reuse P-06 follow-ups v2 unchanged (the close
  binder's requests are ordinary request items, so `FollowUpCadence` already covers them).
- Replay history for `RequestPublishWorkflow`: recorded at the end pass with the ledger sync's.
- `2026-11-16` — Rechecked after the S46 merge: the summary VM stays blocked. Its figures name file columns ("Gross sales", "Processing fees") that P-11's sheet classification supplies; building it now would invent the mapping.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-5078 | BD1 generation acts on the plan publisher's authority; idempotence key; read-time re-run offer | no |
