---
id: TASK-417
title: Human-only guard - register, generated list and audit_events trigger [mig 0097] (Q-02-T17)
spec: SPEC-304
acceptance_criteria: [AC-1]
risk_zone: red
status: done
epic: Q-02
plan_key: Q-02-T17
branch: q02-t17-human-only-guard
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"Inserting sign_off.recorded, report.released or any listed action with actor_kind agent or policy raises at the database, and the generated list matches the YAML." (Q-02 AC-17)

## Plan
- `docs/architecture/human-only-actions.yaml`.
- `abacus_tools/codegen/human_only_actions.py`, generating `kernel/_human_only_actions.py`; it runs in `make regenerate` and `make check-generated`.
- Migration 0097.
- Drift and guard tests.
- Protected-paths and hook entries.
- Rollback: `alembic downgrade 0096`, then revert.

## What changed
- **The register:** 18 audit actions, each with its I-AGENT-NEVER verb. 15 are written today, among them `sign_off.recorded`, `report.released`, `review.decided`, `materiality.decided`, `risk.approved` and `independence.confirmed`. Three are named in AC-17 ahead of their writers: `legal_hold.placed`, `firm_export.approved` and `firm.ai_client_data_opted_in`.
- **What's left out on purpose:** the sends an automation may make under SPEC-027 autonomy (`reminders.sent`, `digest.sent`, `message.sent`) and `grouping_set.published`, which records its actor kind.
- **The generator:** validates verbs, the action shape and duplicates. It is added to `GENERATORS`.
- **Migration 0097:**
  - `abacus_human_only_actions()` is IMMUTABLE and returns this list;
  - the BEFORE INSERT `audit_events_human_only` trigger refuses an agent or policy actor on a listed action (`insufficient_privilege`, `human_only_action`);
  - changing the list needs a new migration that redefines the function.
- `_human_only_actions.py` is listed as generated in `protected-paths.md` and the edit hook, and the YAML is listed as a binding policy file.

## Progress log
- 2026-10-22: the new `tests/integration/test_human_only_guard.py` passes:
  - the drift test holds the database function, the generated module and the YAML equal;
  - every listed action is refused for agent and policy and allowed for a person;
  - an agent can still write its own actions.
- 2026-10-22: `test_schema_check_db` passes. 200 tests in all.
