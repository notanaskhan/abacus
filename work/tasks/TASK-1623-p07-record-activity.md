---
id: TASK-1623
title: Activity projection lines for client and engagement records (P-07-T57)
spec: SPEC-349
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: P-07
plan_key: P-07-T57
branch: s13-p07-t57
created: 2026-10-28
updated: 2026-10-28
---

## Objective
CLI-02's and ENG-02's Activity lines from the G-02 audit-trail read API, in the actor grammar, never showing a walled client's events.

## Plan (amber)
- Files: `audit_trail/explorer.py` (`record_events`, `RECORD_READ`), `audit_trail/record_activity_routes.py` (two routes), `audit_trail/api.py` (ROUTERS), `organisations/live.py` + `api.py` (`readable_client`).
- Registry: matrix row `record_activity.read` in `permission-matrix/audit_trail.yaml`; `make regenerate` (matrix, route introspection, OpenAPI client).
- Flags: existing `clients.v2` and `engagements.v2`; no new flag. No migration (indexes `audit_events_client`, `audit_events_engagement` exist).
- Tests: `tests/integration/test_p07t57_record_activity.py`.
- Rollback: revert the commit; no data change.
- DEC-718.

## Progress log
- 2026-10-28: built; tests run in the S13 batch pass.
