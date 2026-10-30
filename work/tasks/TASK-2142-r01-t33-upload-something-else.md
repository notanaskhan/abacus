---
id: TASK-2142
title: R-01-T33 Upload something else and emailed receipts live
spec: SPEC-000  # R-01-T33 row
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
epic: R-01
plan_key: R-01-T33
branch: s16-r01-t33
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Acceptance (backlog row): "Claire's unsolicited file reaches the firm Inbox and the emailed
1095-C reads Received by email full stack on staging."

## Plan
- `portal.settings.upload_something_else`: the published client experience's toggle.
  `PortalBinderOut` gains `upload_something_else` (toggle and `portal.intake_upload` both on) and
  `engagement_id` (the scope an unsolicited batch is sent under). `POST /v1/portal/intake-uploads`
  answers 404 while the toggle is off.
- `evidence.portal_files._arrived`: a version filed from an emailed intake (N-01: `source=inbox`,
  `channel=email`) reads `email`, so POR-03 shows "Received by email …".
- POR-03: the kit's "Upload something else" is shown only when allowed (`uploadOther`); files go
  to `createIntakeUpload` then `addIntakeUploadFile`; toast "Sent to Brightwater Hale" (the
  firm's name, never "Accrued").
- Fixtures: the Feld binder publishes the toggle; intake-upload routes answer.
- Tests: POR-03 behaviour test; `tests/unit/evidence/test_r01t33_emailed_channel.py`.

## Progress log
- 2026-10-30: built; unit test passes (2); tsc and eslint clean. The staging walk is a human
  to-do (needs N-01's mailbox and a published toggle).
