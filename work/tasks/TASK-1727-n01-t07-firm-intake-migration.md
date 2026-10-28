---
id: TASK-1727
title: N-01-T07 Firm intake migration (inbox tables)
spec: N-01 §4.2
acceptance_criteria: [N-01-T07]
risk_zone: red
status: in-review
epic: N-01
plan_key: N-01-T07
branch: s14-n01-t07
created: 2026-10-28
updated: 2026-10-28
---

## Objective
The firm inbox's six tables in `communications` (migration 0293). Acceptance (backlog row):
"Upgrade and downgrade pass and an UPDATE or a non-human insert on triage_decisions is refused by
the database."

## Plan (red)
- Migration `0293_firm_intake` (down `0292`, stacked on N-02-T07): `inbox_threads`,
  `inbound_messages` (insert-only, sealed body), `inbox_attachments`, `triage_decisions`
  (insert-only, human CHECK bound to the GUCs), `inbox_sender_rules`, `inbox_attachment_flags`
  (insert-only). Forced RLS; trigram indexes on subject and sender.
- `communications/registry.py`, `schema_check.IMMUTABLE_TABLES`, the schema-check pin, the
  generated tenant-isolation list.
- No routes or flags (T08 and T09). DEC-817.
- Rollback: downgrade 0293.

## Acceptance
| Check | Test |
|---|---|
| Upgrade and downgrade pass | `backend/tests/integration/test_n01t07_firm_intake_schema.py::test_ac_upgrade_and_downgrade_pass` |
| A non-human insert on triage_decisions is refused | `…::test_ac_a_non_human_insert_on_triage_decisions_is_refused` |
| An UPDATE on triage_decisions is refused | `…::test_ac_an_update_on_triage_decisions_is_refused` |
| Insert-only grants and triggers, matching, tenant isolation | three tests |

## Progress log
- `2026-10-28` — Built. ruff and pyright clean. Tests written, not run (end-of-batch review).

## Handoff
- **Current state:** PR open, held for the batch, stacked on #588.
- **Next:** N-02-T08.
