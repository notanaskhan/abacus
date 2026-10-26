---
id: TASK-1353
title: Brightwater Hale's six email templates in the scenario (R-01-T22; POR-20, ADM-10)
spec: SPEC-345
acceptance_criteria: [AC-12]
risk_zone: amber
status: in-review
epic: R-01
plan_key: R-01-T22
branch: s10c-red
created: 2026-10-27
updated: 2026-10-27
---

## Objective
`make seed-demo` shows POR-20's and ADM-10's template states with no template text in a
migration, a constant or a fixture outside the scenario package.

## Plan
- **Slice** `email_templates` (`abacus_tools/synthetic/scenarios/brightwater_hale/email_templates.py`),
  opt-in, so `SCENARIO_HASH` is unchanged: the `portal.settings_editor` flag, then the six keys'
  versions as POR-20's figures give them (Invitation v3, Reminder v3 published and a v4 draft,
  Signature request v2, Deliverable ready v2, Confirmation request v1, Reconnect request v1), as
  Grace Holloway (firm admin), source `handoff_seed`.
- **Copy**: POR-20's "Seeded template content" verbatim, client words as the key's whitelisted
  variables; words the whitelist cannot carry stay literal (DEC-451 records each gap).
- **Loader**: two handlers that call `communications.api`'s editor service (draft save, publish);
  no SQL. No migration, no new constant outside the scenario package.
- **Tests**: `tests/unit/scenarios/test_email_templates_slice.py` (registered, opt-in,
  deterministic, every kind handled, flag first, every seeded version passes `check_content` and
  the lint).
- **Not here** (their tables arrive later): the portal settings draft (R-01-T26), the follow-up
  policy (T24), the sending domain verified on the sink (T27), preview personas (T23's preview).
  The TypeScript scenarios per artboard arrive with the screens (R-01-T25, T28).
- **Rollback**: revert; the slice is opt-in and writes only through the service.

## Progress log
- 2026-10-27: planned and built (S10 wave C). Partial against the row: templates only.
- 2026-10-27: unit slice tests green.
