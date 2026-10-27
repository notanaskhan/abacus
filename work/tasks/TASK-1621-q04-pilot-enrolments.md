---
id: TASK-1621
title: Pilot enrolments and metric snapshots (Q-04-T007)
spec: none (Q-04 §4)
acceptance_criteria: [Q-04-T007]
risk_zone: amber
status: in-review
epic: Q-04
plan_key: Q-04-T007
branch: s13-q04-t007
created: 2026-10-28
updated: 2026-10-28
---

## Objective
Record which work items are in a pilot and how far, and the metrics computed for them.

## Plan
- Migration 0276 (down 0275); platform registry; `platform/pilots.py`; `platform.api` exports; `abacus_tools/pilots.py`; `make pilot-enrol`, `make pilot-mode`; glossary rows.
- Test `tests/integration/test_q04t007_pilot_enrolments.py`. DEC-716.
- Rollback: downgrade 0276.

## Progress log
- 2026-10-28: built; tests in the batch pass.
