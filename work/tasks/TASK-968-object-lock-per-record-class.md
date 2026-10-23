---
id: TASK-968
title: Object Lock per record class — retain-until from the record's policy, extend at anchor events, COMPLIANCE records and chain anchors (Q-02-T24)
spec: SPEC-051
acceptance_criteria: [AC-2]
risk_zone: red
status: in-progress
epic: Q-02
plan_key: Q-02-T24
branch: s5-object-lock
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"Every stored object's retain-until is at or after its policy expiry, anchors land in COMPLIANCE mode, and BypassGovernanceRetention is denied to the app role on staging."

Q-02 AC-32 has no SPEC yet: it lives in `docs/plan/epics/Q-02.md` §3. SPEC-051 (compliance setup) is the nearest spec.

## Plan (red zone)
- **Code:**
  - `evidence/storage.py`: `put(..., retain_until=)` and `extend_retention`;
  - `evidence/retention.py`: `RECORD_TYPES`, `retain_until_for` and `extend_retention_for`;
  - `evidence/records.py`: the COMPLIANCE records writer and `anchor_chain`;
  - `evidence/uploads.py`: uploads take the `client_document` expiry;
  - config: `records_bucket`;
  - exports in `evidence.api` and `engagements.api.service_line_of`.
- **Tests:** `tests/integration/test_retention_object_lock.py` (4) against the local S3 Object Lock container.
- **Rollback:** revert the commit; no migration.

## Progress log
- 2026-10-23: the code half is built (DEC-168). **Status is in progress, not done.** Two parts remain, both outside a session:
  - Terraform for the records bucket (Object Lock COMPLIANCE default) and the app role's explicit deny on `s3:BypassGovernanceRetention`. A plan-only session can write these; applying them is the human's.
  - The staging check that the app role cannot bypass GOVERNANCE retention.

  The daily `RetentionClock` waits for Temporal Schedules.
