---
id: TASK-305
title: "Audit log explorer"
spec: SPEC-304
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5]
risk_zone: amber
status: done
branch: task-305-audit-log
worktree: spec005
created: 2026-10-20
updated: 2026-10-20
---

## Plan
- `kernel.uow`: `AuditFilter`, `AuditRow`, `audit_page` (static SQL) and `audit_facets`.
- New `audit_trail` routes and service, registered in `api/app.py`.
- Matrix: `audit.read`.
- Web: `screens/AuditLog.tsx` at `/admin/audit-log`, with the Security group always shown.
- No migration.

## Definition of done
- [x] `tests/unit/audit_trail/test_explorer.py`, `spec304auditlog.test.tsx`, the router test and the gate list pass; check-fast passes.

## Progress log
- 2026-10-20: built and merged.
