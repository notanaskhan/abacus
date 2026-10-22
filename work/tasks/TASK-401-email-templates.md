---
id: TASK-401
title: C16 email-template half - tables, renderer, staff import route, migration 0092 (P-01-T05)
spec: SPEC-013
acceptance_criteria: [AC-7]
risk_zone: red
status: done
epic: P-01
plan_key: P-01-T05
branch: p01-t05-email-templates
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"The same template version and variables render byte-identical output, and an unknown variable
is refused."

## Plan
- Migration 0092.
- `communications/templates.py` (renderer and import) and `communications/routes.py` (the staff route).
- `kernel.db.platform_transaction`.
- Registries and the schema_check lists.
- Tests.
- Rollback: `alembic downgrade 0091`, then revert.

## What changed
- **Migration 0092:**
  - `email_templates`: platform defaults only for now (`tenant_id IS NULL`), unique per key and locale.
  - `email_template_versions`: insert-only, enforced by triggers for every role.
  - Both tables are global with no app privilege.
  - Definers: `email_template_import(...)`, idempotent on the content hash, and `email_template_current(key, locale)`.
- **Renderer:**
  - Only the C16 whitelist (`recipient_first_name`, `kind_sentence`, `engagement_display_name`, `app_link`), each declared by the template.
  - It refuses any unknown, undeclared or missing value, stray braces, and line breaks in values or the subject.
  - Its output is deterministic.
- **`POST /v1/platform/email-templates/import`:** carries the `STAFF` marker (DEC-133) and returns the version and content hash. Importing the current content again writes nothing.
- **`kernel.db.platform_transaction(actor)`:** a committed transaction with no tenant, used only for the platform-wide definers.
- **Contract:** `docs/contracts/notifications.md` names the staff route.

## Progress log
- 2026-10-22: the unit tests for the renderer whitelist and byte-identity pass. An integration test covers import idempotence, versions, the current read and insert-only. It runs with `test_schema_check_db`, which migrates up, down and up.
