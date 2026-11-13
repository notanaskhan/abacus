---
id: TASK-7904
title: T-05-T53 Entity-return final-approval guards
plan_key: T-05-T53
spec: SPEC-651
acceptance_criteria: [AC-F12]  # each blocker in words until all clear; an agent principal refused
risk_zone: red
status: in-review
branch: t05-t53-final-approval-guards
worktree: /Users/ayushkbhatia/Accrued/abacus-s42
created: 2026-11-13
updated: 2026-11-13
---

## Objective
Final approval of an entity return is blocked, in words, by unmapped accounts, an unapproved
allocation structure, off tie-outs without a signed note, and an open workbook run.

## Plan (red)
- Files: `tax/entity_guards.py` (new provider), `tax/approval.py` (`BLOCKER_WORDS`,
  `blocker_words`, `first_blocker` fact), `tax/engine_contract.py` (`words` on each blocker),
  `tax/api.py` (register). Reuses `tax/entity_gates.py` facts (T-05-T52).
- No migration. Tests: `backend/tests/unit/tax/test_t05t53_final_approval_guards.py`.
- Rollback: revert the PR (the provider only adds blockers; approval stays approval.py's).
- Security review: at the S42 end pass (red).

## Partial
- The 409 carries the count and the first blocker's code (facts are identifiers only); the full
  list with words is the GET's (`/final-approval`, TAX-05 and SHL-12 h read it).

## Progress log
- 2026-11-13: built; tests written, not run (S42 end pass).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4907 | one provider, coded blockers with fixed words, section sign-off as the note | no |
