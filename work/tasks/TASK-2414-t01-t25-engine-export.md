---
id: TASK-2414
title: T-01-T25 Engine export file (W2 file mode) and Mark exported
spec: SPEC-000  # the backlog row; T-01 §3.9 and the tax-engine-bridge contract
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
epic: T-01
plan_key: T-01-T25
branch: s19-t01-t25
worktree: /Users/ayushkbhatia/Accrued/abacus-s19
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Engine export file (W2 file mode): consume the single-use grant, read the approved checkpoint, map
through integration settings, render a deterministic workbook stored write-once with a
write_operations row; audited download; a person's Mark exported moving the chip to Synced;
idempotent regeneration; per-firm and per-capability kill switches; agent and system refused at
all five layers.

Acceptance: "Samuel Ito exports 2025I:FeldJ:V3 only after final approval, the same checkpoint
yields byte-identical files, and a second consume of the grant is refused."

## Plan (red)
Migration 0561 (on 0560: merge after #886): write_operations, engine_exports, human-only register.
`tax/export.py`, routes in `engine_contract.py`, `identity.api.latest_grant`,
`integrations.api.export_settings`. Security: grant consumed once on the content hash; person
only at matrix, service, database, audit register and grant; TRI never logged. Rollback: the
routes answer `export_disabled` while W2 is disabled; downgrade drops both tables.

## Progress log
- `2026-10-30` — Built on `s19-t01-t25` off main; tests run at the end review. DEC-1462.
