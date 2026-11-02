---
id: TASK-3000
title: N-04-T01 S25 protected bundle for Notices
spec: SPEC-000  # row
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: N-04
plan_key: N-04-T01
branch: s25-n04-t01
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-02
updated: 2026-11-02
---

## Objective
- **[AC-1]** "The bundle merges first in the Oct 21 batch with your approval, and generated tests
  deny the agent and portal principals every notices write."

## Plan (red)
- `docs/architecture/permission-matrix/notices.yaml`: the eighteen N-04 §4.3 actions (DEC-2050).
- `docs/architecture/feature-flags/notices.yaml`: `notices.workspace`, `notices.responder`.
- Glossary rows; status objects `notice_intake`, `notice_analysis`, `notice_response_readiness`;
  `awaiting_irs` context label "Awaiting agency".
- Seven C16 kinds in `notifications/catalogue.py` (codes; events come with their producers).
- `protected-paths.md`: `notices/compute/notice_types.yaml` and `rate_schedules/*.yaml`.
- `make regenerate`: `_matrix.py`, `actions.gen.ts`, `_flags.py`, `_statuses.py`, `status.gen.ts`,
  generated security suites.
- Not here (DEC-2050): `TABLE_OWNERS` / `IMMUTABLE_TABLES` with migration 0650 (N-04-T03).
- Rollback: revert the branch; no route, table or data reads it yet.

## Acceptance
| Check | Test |
|---|---|
| Agent, system and portal principals denied every notices write | `tests/security/test_n04t01_notices_bundle.py::test_ac1_*`; generated matrix suites |
| No `notice.decide` action; reads at task scope for the agent | same file |
| Flags default off | same file |

## Progress log
- 2026-11-02: built; generators run. Tests and gates at the S25 end review (build first, test last).

## Decisions made during this task
DEC-2050.
