---
id: TASK-1513
title: R-01-T26 portal settings and the read-only preview
spec: SPEC-345
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: R-01
branch: s12b-r01t26
created: 2026-10-28
updated: 2026-10-28
---

## Objective
ADM-10's draft, publish (one unit of work), logo and read-only preview (DEC-653).

## Plan (amber)
- Migration 0251 (down 0244; renumber on rebase): `portal_settings_drafts`, `portal_settings_versions` (insert-only). Rollback: downgrade drops both.
- `portal/settings.py`, live routes in `portal/settings_contract.py`, `portal/events.py`; communications `write_follow_up_policy` inside the caller's unit of work.
- Tests: `tests/integration/backfill/test_r01t26_portal_settings.py`; the C16 v1.1 stub test moves the settings routes to built.

## Open
- `next_reminder` and `portal_host` wait for their readers; item-level preview filtering (DEC-653).

## Progress log
- 2026-10-28: built; lint and pyright clean; app and worker import. Tests run in the S12 batch pass.
