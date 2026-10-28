---
id: TASK-1853
title: Q-02-T48 real-data rehearsal system test on staging
spec: SPEC-036
acceptance_criteria: [Q-02-T48]
risk_zone: red
status: in-review
epic: Q-02
branch: s12r-q02-t48
created: 2026-10-28
updated: 2026-10-28
---

## Objective
The rehearsal passes three consecutive nights on staging before Fri Apr 16; it also asserts the
live-stage guard (Q-02-T50).

## Plan (red)
- `abacus_tools/rehearsal.py`: the walk and the operator command (staging only).
- `OPS_COMMANDS` and `ops-task.yml`: `abacus_tools.rehearsal run`.
- `.github/workflows/rehearsal-nightly.yml`: off until `REHEARSAL_NIGHTLY` is on.
- `backend/tests/system/test_real_data_rehearsal.py` (skipped without the tenant's ids);
  `tests/unit/tools/test_rehearsal.py`.
- Rollback: revert; the command and workflow have no state of their own.

## Decisions
DEC-958.

## Human to-dos
- Provision the rehearsal tenant on staging (real, synthetic content only), turn on
  `agents.client_data_optin` for it, create the two engagements, set the five repository
  variables and `REHEARSAL_NIGHTLY=on`.
- Three green nights before Fri Apr 16.

## Progress log
- 2026-10-28: built; unit tests written, not run (end review). The system test needs staging.
