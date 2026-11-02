---
id: TASK-3016
title: K-01-T24 independent acceptance tests for K-01-T18's import review
spec: SPEC-000  # K-01-T24 row; K-01 §3.4, §6, §7
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: K-01
plan_key: K-01-T24
branch: s25-k01-t24 (stacked on s25-a06-t08)
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-02
updated: 2026-11-02
---

## Objective
"Every amber AC in section 3.6 and the backend half of section 3.7 has a passing test written."

## Built
`backend/tests/integration/backfill/test_k01t24_import_review_independent.py`: write-once source
files and scan before parse (AC7.9), the diff over two imports (AC6.1), a resolution keeps key,
text and citation (AC3.4), `checklist_changed` (AC3.4), no issuer set offered (AC6.2). K-01-T18's
suite already holds 4/9/1/54, `flags_open`, `unverified_sources` and the document-import boundary.

## Progress log
- 2026-11-02: written; run at the S25 end review.
