---
id: TASK-1603
title: C5 v1.2 intake half and Files browser contract stubs (N-01-T02)
spec: SPEC-380
acceptance_criteria: [AC-1, AC-4, AC-5, AC-12, AC-18, AC-24]
risk_zone: red
status: in-review
epic: N-01
plan_key: N-01-T02
branch: s13-ready
created: 2026-10-27
updated: 2026-10-27
---

## Objective
Contract first for INB-01, INB-02, FIL-01 and POR-03 intake: classified models and 501 routes, matrix rows, four flags, error codes, two contract docs, the generated client.

## Plan
- `communications/intake_contract.py`: `/v1/inbox/*` and `/v1/destinations` (14 routes) and the intake error classes; `portal/intake_contract.py`: `/v1/portal/intake-uploads*` (4); `evidence/files_contract.py`: `/v1/files/*`, drawer, access log (4). Registered in each module's `ROUTERS`.
- Matrix: `communications.yaml` (inbox.* and inbox_sender_rule.create; agent and system denied on every write), `portal.yaml` (portal_intake.*, `scope_only`), `evidence.yaml` (evidence.read_metadata, evidence.read_access_log). The `intake_scope` condition waits for N-01-T08 (DEC-701); firm-level cells are `firm_admin` meanwhile, narrowed in the service.
- Flags: `inbox.firm_intake`, `portal.intake_upload`, `files.browser`, `matching.firm_intake` (all off, expire 2027-01-25).
- Uploads: batch then one raw-body request per file (DEC-703), as every upload in the repo.
- Contracts `docs/contracts/firm-intake.md`, `files-browser.md`; register rows; `make regenerate`, error catalogue `--write`.
- Not here: the human-only audit register (`human-only-actions.yaml` and the SQL list) gains the intake audit actions with N-01-T18, when they are written.
- Rollback: revert; every flag stays off.

## Progress log
- 2026-10-27: built; 22 routes in the OpenAPI document. Tests in the end-of-batch targeted pass.
