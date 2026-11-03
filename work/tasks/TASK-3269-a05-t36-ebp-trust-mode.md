---
id: TASK-3269
title: A-05-T36 mode ebp_trust on the section drafter (spec v11)
spec: SPEC-000  # row (SPEC-640 AC-36)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: A-05
plan_key: A-05-T36
branch: s27-a05-t36
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
Certified Summary of Net Trust Assets pages to fund lines for both dates and certification-point
answers with page citations; proposed TB lines for `record_document_snapshot`.

## Plan (red)
- Prompt `workpapers.section_draft.ebp_trust@v1` (copy values as printed, never total, quote the
  certification without judging it; untrusted-block rule; reserved words incl. rely).
- `assurance/ebp_trust_mode.py`: the mapping (trust, investments and certification documents;
  no facts to total), registered.
- Spec v11; `_specs.py` and `_eval_suites.py` regenerated; A-05-T33's cases grade it.
- Tests: `tests/unit/assurance/test_a05t36_ebp_trust_mode.py`.

## Progress log
- 2026-11-04: built.

## Decisions made during this task
DEC-2249.
