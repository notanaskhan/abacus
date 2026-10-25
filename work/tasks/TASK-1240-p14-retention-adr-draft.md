---
id: TASK-1240
title: Draft P-14 as ADR-179 (proposed) - retention per record type and service line, counsel-set floors as reference data, reference-counted holds, dual-approved destruction, dual-control firm export (Q-02-T05)
spec: SPEC-341
acceptance_criteria: [AC-30, AC-31, AC-32, AC-34, AC-35, AC-37, AC-40]
risk_zone: red
status: in-review
epic: Q-02
plan_key: Q-02-T05
branch: s8b-docs-compliance
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"P-14 is Accepted on origin/main by Fri Nov 27 with both founders as deciders and counsel's floor input recorded." (Q-02-T05) This task drafts it; acceptance is the deciders' and waits on counsel.

## Plan (red zone: ADR draft, no code)
- `docs/adr/ADR-179-retention-holds-destruction-export-dual-control.md`, status `proposed`, deciders both handles. Six rules: record type × service line; floors as two-person reference data (placeholders `FLOOR-*` only, never numbers); Object Lock extends only; reference-counted holds placed by firm admin, security admin or partner level (amends ADR-033); dual-approved destruction (Q-05); dual-control firm export (amends ADR-036; epic OQ-4: no separate ADR).
- Records the parts already built under DEC-156, DEC-168, DEC-228, DEC-229 rather than restating them as new.
- Index: `docs/adr/README.md` row; `docs/adr/backlog.md` P-14 row (ADR-179, proposed).
- **Rollback:** revert the commit; the number stays burned.

## Progress log
- 2026-10-25: drafted. No accepted ADR edited: ADR-032, 033, 034 and 036 are amended on acceptance by reference. Counsel's floors are named placeholders with the authority counsel is asked to confirm. `validate_docs` green.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| Destruction approvers are the firm admin and the security admin | FIL-02's handoff story and state c name exactly these two | This ADR |
| Whole-firm export amends ADR-036 inside P-14 | Epic OQ-4's recommended answer: it only adds a control | This ADR |

## Questions for the human
- [ ] Accept ADR-179 (both deciders) once counsel's floor input is recorded; due Fri Nov 27.
- [ ] Counsel: every `FLOOR-*` value; basis text per record type (314.4(c)(6)); whether the permanent file and messages need a floor at all.

## Handoff
- **Current state:** proposed on this branch.
- **Exact next step:** counsel's floor input (F-09-T38), then acceptance.
