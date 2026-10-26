---
id: TASK-1352
title: Email template versions, drafts, publish and send_templated (R-01-T19; C16 v1.1)
spec: SPEC-345
acceptance_criteria: [AC-9, AC-10, AC-11]
risk_zone: red
status: in-review
epic: R-01
plan_key: R-01-T19
branch: s10c-red
created: 2026-10-26
updated: 2026-10-27
---

## Objective
R-01-T19's acceptance: the same version and variables render byte-identical HTML and text, a key
with no published version blocks the send, and v3 stays readable after v4 publishes. The
contract (`docs/contracts/email-templates.md`, C16 v1.1) and the slot were stubbed by R-01-T16;
this task builds the list, read, draft save and discard, publish, the block renderer and
`send_templated`, registers the six keys and retires the legacy invitation text constant.

## Plan
- **Migration 0196 `communications_templates_v2`** (down_revision 0182):
  - `email_templates`: the `tenant_id IS NULL` check goes (a firm override row has the firm's
    `tenant_id`, FK to `firms`); the key check widens to dot-less keys (`reminder`);
    `firm_editable bool`, `audience text[]` (subset of client, third_party, respondent, staff);
    `UNIQUE (tenant_id, id)` so drafts can reference only their firm's override.
  - `email_template_versions`: `format` (`text` for P-01-T05's versions, `blocks` for v2),
    `preheader`, `blocks jsonb`, `sealed bytea`, `cta_label`, `cta_target` (the eight targets),
    `source` (`handoff_seed`, `editor`, `import`). `subject` and `body_text` become nullable
    under a shape check: a text version keeps both; a platform block version keeps subject,
    preheader and blocks in clear; a firm block version keeps its wording only in `sealed`
    (AES-GCM under the firm's key, bound to template, version and content hash). Still
    insert-only (0092's trigger).
  - **New** `email_template_drafts(tenant_id, template_id, base_version_id, sealed, cta_target,
    draft_version, updated_by, updated_at)`, PK `(tenant_id, template_id)`, FK
    `(tenant_id, template_id)` to the firm's override row, RLS forced; the app inserts, updates
    the content columns and deletes (discard and publish).
  - `messages` gains `template_version_id` (FK) and `kind` (`client`, `test`, `staff`).
  - Definer functions (tenant from `app.tenant_id`, never an argument):
    `email_template_firm_row(key, locale, audience)` (the override row, created on first edit),
    `email_template_resolve(key, locale)` (the firm's current version, else the platform's),
    `email_template_version_at(key, locale, version)` (any published version, the firm's first),
    `email_template_publish(...)` (insert-only n+1 for the firm, moves `current_version_id`;
    n+1 is above both the firm's and the platform's highest). No template text in the migration.
- **Code** (`communications`): `render.py` (block model to HTML and text, deterministic, every
  value HTML-escaped, `{portal_link}` only as the button's href, 600 or 390 wide);
  `lint.py` (the publish-time text lint: unregistered variable, amount, TIN shape, account
  number, platform name; T23 adds attachments, links and scope guards); `template_store.py`
  (definer calls, sealing); `template_service.py` (list, read, save draft with
  `expected_version` and 409 `stale_version`, discard, publish with lint and 409); the six keys
  in `template_keys.py` (registered at import); `send_templated` in `template_send.py`.
- **send_templated**: person: `authorise(message.send)` on the engagement in one unit of work,
  then resolve (firm, then platform; none: `blocked template_missing`), values only the key's
  variables and all the version uses (`template_lint_failed`), `lint_values`, render,
  `check_scope` on the text (`out_of_scope`), suppression (`suppressed`); one `messages` row
  (`template_version_id`, `kind`), its body with the link removed; delivery after commit. The
  message id derives from the idempotency key, so a retry sends nothing twice. System: only
  `scheduled_follow_up`, the `reminder` key, `follow_ups.scheduled_send` on, and a version the
  firm published (attributed to its publisher, who must still be a member); otherwise Forbidden.
  The client-mail gate (`firm_not_client_facing`) and the policy's mode wait for T27 and T24.
- **Routes**: list, read, draft PUT and DELETE, publish (Idempotency-Key, fresh MFA by the
  matrix). Authorise first, then the flag (404 off) for writes, as the contract says. Audited
  `email_template.draft_saved`, `.draft_discarded`, `.published`; outbox
  `email_template.published {key, version}`. Target type `email_template` is firm-level.
- **Legacy constants**: `invitations.SUBJECT` / `TEMPLATE` (the engagement invitation's text in
  code) are retired: the engagement invitation renders the database `invitation` key through the
  same renderer and fails closed (logged by invitation id) without a published version. The
  follow-up keys (`notification.follow_up_sent*`) are database content already; only their key
  names are constants, which stay. `STAFF_TEMPLATE` is a staff email outside R-01's keys and stays.
- **Contract and generate**: the stub test moves T19's routes from 501 to live; `make generate`.
- **Tests first**: `tests/integration/test_r01t19_email_template_versions.py` (determinism,
  fail closed, v3 after v4, stale draft 409, sealing at rest, agent and staff denied, cross-firm),
  unit `tests/unit/communications/test_template_render.py`.
- **Registry and checks**: `registry.py` (drafts table, messages columns), `schema_check.py`
  (`DEFINER_FUNCTIONS`), `test_schema_check_db.py` expected sets, generated isolation tests.
- **Rollback**: downgrade drops the drafts table, functions and columns and restores the checks;
  it refuses when firm override rows or block versions exist (versions are insert-only).

## Progress log
- 2026-10-26: planned (S10 wave C red backend).
- 2026-10-27: built; targeted pass green after two test fixes (the agent principal is an
  `AgentContext`, not an `AuthContext`, so the reader case replaced it; probe titles without form
  numbers, which the scope check reads as amounts). DEC-450 defers the legacy constants.
