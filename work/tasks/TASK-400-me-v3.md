---
id: TASK-400
title: /v1/me v3, PUT /v1/me/preferences, capability nav keys, migration 0091 (P-01-T04)
spec: SPEC-024
acceptance_criteria: [AC-2.1.2, AC-2.1.3]
risk_zone: red
status: done
epic: P-01
plan_key: P-01-T04
branch: p01-t04-me-v3
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"The four personas get the SHL-03a–d capability sets and a preference change is audited."

## Plan
- Migration 0091.
- `identity/me.py`, `/v1/me` v3 and `PUT /v1/me/preferences`.
- The matrix and role edit (DEC-132) and the `nav` capability keys.
- `make regenerate` and `make generate`.
- Rollback: `alembic downgrade 0090`, then revert.

## What changed
- **Migration 0091:**
  - `memberships.job_title`;
  - `memberships.default_office_filter_id`, with an FK to the same firm's offices; the app may update only this column;
  - `firms.sandbox_of_firm_id`, the inferred sandbox marker from P-01 R9.
- **`GET /v1/me` v3:**
  - Each membership carries `firm {region, time_zone, seats_total, is_sandbox, sandbox_of}`; seats count the active staff memberships.
  - For the active tenant it adds `initials`, `job_title`, `default_office_id` and `offices[{id, name}]`. The active tenant is the one named in `X-Abacus-Tenant` when the person holds it, or else their only one.
- **`PUT /v1/me/preferences {default_office_id}`** (`OWN`): writes the caller's own row through the unit of work and audits `user_preference.updated`. An office of another firm is refused with 422 `office_not_in_firm`.
- **`/v1/me/capabilities.nav`:**
  - `firm_settings` is write, read or none, from `firm.manage_settings` and `firm.read_settings`;
  - `users_roles` comes from `firm.manage_users`, `audit_log` from `audit_event.read`, and `security_center` from `security.manage`, which is not in the matrix yet;
  - `developer_api` is `none`;
  - on an engagement's capabilities, every key is `none`.
- **DEC-132:** the derived firm-level role `firm_partner` (a staff member at partner level, on firm resources only) is allowed `firm.read_settings`. The plan's `level_in(partner)` can't widen anything, because conditions only narrow.

## Progress log
- 2026-10-22: built per the S3 batch rules. ruff and pyright are clean. The new `tests/unit/platform/test_nav_access.py` covers the admin, partner and manager sets.
- 2026-10-22: Felix's `security_center` waits on `security.manage` (G-02-T02). His scenario membership is `firm_admin`, but SHL-03d wants `security_admin`, so the scenario data (P-01-T07) should set it.
