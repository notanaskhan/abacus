---
id: TASK-6527
title: "P-11-T37: independent AC tests for form extraction (ADR-078)"
spec: SPEC-029
acceptance_criteria: [AC8.1, AC8.3, AC8.4, AC8.5, AC8.6]
risk_zone: red
status: in-review
branch: s33-p11-t37
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-09
updated: 2026-11-09
plan_key: P-11-T37
---

## Objective
Each extraction rule is proven by tests written outside the implementing session, including an
unsupported tax year that yields manual entry rather than guessed values.

## Plan (red, tests only)
`tests/unit/evidence/test_p11t37_form_extraction_independent.py`, from P-11 F8 and SPEC-029 over
the synthetic scanned corpus through the public functions: identification; each year's own map;
an unsupported year identifies nothing and writes nothing; the 0.90 rule stores values as read;
an unreadable amount stays text and is flagged; CORRECTED on and off; no TIN is a field value or
key and a TIN page is the one read for label masking; statement tables only under `all`; no
UPDATE, DELETE or evidence write in the extraction modules; every variant writes only the
families it covers. No production code changes.
Rollback: revert.

## Progress log
- `2026-11-09` — Written; not run (end pass). Solo edition: "outside the implementing session"
  is this separate task and session (DEC-3127), and the corpus goldens still carry
  `requires_review` for a CPA.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3127 | Solo independence for P-11's AC tests: a separate task and session | no (ADR-078) |
