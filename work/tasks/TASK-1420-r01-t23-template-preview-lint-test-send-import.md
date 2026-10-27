---
id: TASK-1420
title: Email template preview, lint, test send and import (R-01-T23; C16 v1.1)
spec: SPEC-345
acceptance_criteria: [AC-6, AC-8]
risk_zone: red
status: in-review
epic: R-01
plan_key: R-01-T23
branch: s11-comms
created: 2026-10-27
updated: 2026-10-27
---

## Objective
R-01-T23's acceptance: a draft containing $3,200 or the word Accrued cannot be test-sent,
published or imported, and a test send to any address but the admin's is refused. The routes
were stubbed by R-01-T16 (`templates_contract.py`); T19 built list, read, drafts, publish and
`send_templated`. This task builds preview, test send and the onboarding import, and completes
the lint (Story 7.2).

## Plan
- **Lint** (`communications/lint.py`): T19's rules plus `attachment` (attach, attachment,
  enclosed), `second_button` (a bracketed label, "click here", a block that repeats the button
  label) and `banned_word` (new code, additive to v1.1's `LintCode`: the glossary's client-email
  bans "agent", "AI", "confidence", "task", "issue", "password", "materiality", firm status
  words, plus `scope-guards.yaml`'s banned terms). The scope-guards terms reach the runtime as
  `communications/scope_guard_terms.gen.json`, written by `scope_guards --write` and checked for
  drift by the gate (a Python constant would trip the guard itself). Run server-side at preview
  (findings), test send, publish and import (refusals), never only in the UI.
- **Preview** (`template_preview.py`, `POST …/{key}/preview`): authorise `email_template.read`;
  key must be registered firm-editable (404); `source` draft (404 when none) or published (404
  when none); render at 600 or 390 with sample values; findings = text lint (block ids) plus
  `lint_values` (variables). Writes nothing. The button's link is a fixed, token-free preview
  address (no secure link is issued for a preview or a test).
- **Sample values**: no `sample_contact_id`: the sample client (fixed neutral values, the firm's
  real name). With one: the contact must relate (client or third party) to an engagement on the
  viewer's own team, read through `my_engagements` and `recipient_relations`, else 404 (unknown
  and invisible answer the same); open requests only through `request_items_for` under the
  viewer's own authorisation (walls, independence), assigned to the contact or unassigned,
  client-visible, Requested or Returned, at most 10 then "and n more"; nothing readable: the
  sample client (`viewer_scoped`, DEC-379).
- **Test send** (`POST …/{key}/test-send`, Idempotency-Key, 202): authorise
  `email_template.test_send` (fresh MFA, onshore, matrix), editor flag (404), key; the draft if
  there is one, else the published version; text lint and value lint (422
  `template_lint_failed`); recipient is the acting person's own account address read from the
  session's user id, never from the request (the body has only `sample_contact_id`,
  `extra="forbid"`); subject "[Test] …"; delivered through `send_email` (synthetic firms: the
  sink; suppression and pause apply); no `messages` row (a message needs an engagement; a test
  is about none); audited `email_template.test_sent {key, message_id}`. Replays answer the stored
  result after authorising again.
- **Import** (`template_import.py`, `POST …/import`): authorise `email_template.import` (fresh
  MFA by the matrix, dry run included); each entry: key registered firm-editable, `check_content`
  (invalid: refused), lint (findings: refused), change `add` / `update` / `unchanged` against
  the firm's draft or published content. Dry run writes nothing and is not audited. Apply is all
  or nothing: any refused entry answers 422 `template_lint_failed` and nothing is written;
  otherwise each changed entry saves the draft and, with `publish: true`, publishes it (source
  `import`) in one unit of work per entry, then one `email_template.imported {keys, changes}`.
  The import never depends on `portal.settings_editor` (contract).
- **Contract and generate**: `LintCode` gains `banned_word`; preview, test send and import go
  live (501 dropped from their `errors`); `make generate`; contract doc §2, §3, §6, §11.
- **Registry**: `activity_reviewed.py` gains `email_template.test_sent`, `.imported`.
- **Tests first**: `tests/integration/test_r01t23_email_template_preview.py` (AC: $3,200 and
  Accrued refused at test send, publish and import; test send only to the admin; dry run
  writes nothing; staff and practice leader denied writes; sample contact scoping; no TIN in
  audit metadata), unit `tests/unit/communications/test_template_lint_t23.py`.
- **Rollback**: revert; no migration.

## Progress log
- 2026-10-27: planned (S11 lane 5).
