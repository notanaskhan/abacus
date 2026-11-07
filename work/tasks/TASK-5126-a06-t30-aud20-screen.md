---
id: TASK-5126
title: A-06-T30 AUD-20 financial statements and disclosure checklist, a to f
spec: SPEC-000  # row (A-06-T30)
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: A-06
plan_key: A-06-T30
branch: s29-a06-t30
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-06
updated: 2026-11-06
---

## Objective
AUD-20 on T3's Prepare preset under Evaluation: outline, FS paper with linked figures and fanned sources, checklist, tie pill, mismatch card to AUD-16, client preview.

## Plan
screens/AUD-20; fixtures/seed/aud20, scenarios/AUD-20; EvaluationPage renders it on /fs-disclosure; manifest fixture. Reads FsStatements and the checklist; tie-out POST; answer PUT.

## Progress log
- 2026-11-06: built. `apps/web/src/screens/AUD-20/AUD-20.test.tsx` written, not run (end pass). tsc and eslint clean.

## Decisions made during this task
DEC-2422
