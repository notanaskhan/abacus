---
id: TASK-3288
title: A-07-T01 SPEC-644 audit completion, release and archive; kickoff reconcile; contract skeleton; live-path list
spec: SPEC-644
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: A-07
plan_key: A-07-T01
branch: s27-a07-t01
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
"Both founders accept the SPEC on Mon Nov 1, 2027, it cites only chapter-09 IDs, and the
live-path list names every pre-existing file A-07 edits." (AMENDMENT-solo: the one builder accepts.)

## Plan (red)
- Kickoff reconcile: diff SPEC-314 (TASK-332, migration 0077), A-01-T23's interim G8/G9 and
  P-04's sign-off and review-note services against the 53 A-07 acceptance lines; mark each
  built, partial or missing (SPEC-644 §4).
- SPEC-644 with the ACs, the OQ-1 and OQ-4 positions, the record-mode reconcile and the
  live-path file list; `docs/contracts/audit-completion.md` skeleton.
- Decisions DEC-2260 (OQ-1, OQ-4, ADR delta check) and DEC-2261 (routes, actions and 0077 tables).
- `docs/plan/status/S27.md`: the sprint's ordered session list (runbook sprint start).
- Tests: none (docs); `validate_docs` at the end review.
- Rollback: revert the commit.

## Progress log
- 2026-11-04: built. Every live-path file exists on main except the new ones listed as new.

## Decisions made during this task
DEC-2260, DEC-2261.
