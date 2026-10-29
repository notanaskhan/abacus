---
id: TASK-1729
title: N-01-T08 Intake scope
spec: SPEC-380
acceptance_criteria: [AC-8]
risk_zone: red
status: in-review
epic: N-01
plan_key: N-01-T08
branch: s14-n01-t08
created: 2026-10-28
updated: 2026-10-28
---

## Objective
The firm-level intake scope. Acceptance (backlog row): "Grace Holloway in the Intake team reads
unmatched threads and a walled or non-intake user gets 404 on them."

## Plan (red)
- Migration `0295_intake_team_kind` (down 0294): `teams.kind` adds `intake`; `TeamKind` in the
  settings contract; `make regenerate`.
- `identity.slots`: `register_intake_scope` and `in_intake_scope` (fail closed).
- `organisations.intake_team.on_intake_team` registered at import; `rosters._change` emits
  `access.changed` for intake teams.
- `communications.intake_scope`: `unmatched_threads`, `readable_thread` (DEC-75), for T13's read
  models. DEC-819.
- Rollback: revert; downgrade 0295 (refused while an intake team exists).

## Acceptance
| Check | Test |
|---|---|
| Grace in the Intake team reads unmatched threads | `backend/tests/integration/backfill/test_n01t08_intake_scope.py::test_ac_grace_in_the_intake_team_reads_unmatched_threads` |
| A non-intake user gets 404 | `…::test_ac_a_non_intake_user_gets_404_on_unmatched_threads` |
| A walled user gets 404 | `…::test_ac_a_walled_user_gets_404_on_the_clients_thread` |
| Matched thread reach; leaving the team ends the scope with `access.changed` | two tests |

## Progress log
- `2026-10-28` — Built. ruff, pyright, lint-imports clean; `make regenerate`. Tests written, not
  run (end-of-batch review).

## Handoff
- **Current state:** PR open, held for the batch, stacked on #590.
- **Next:** N-02-T09.
