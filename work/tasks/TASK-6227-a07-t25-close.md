---
id: TASK-6227
title: A-07-T25 close, AUD-19's blocker sentences and going-concern wording
spec: SPEC-644
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: A-07
plan_key: A-07-T25
branch: s31c-a07-t25
worktree: /Users/ayushkbhatia/Accrued/abacus-s31
created: 2026-11-08
updated: 2026-11-08
---

## Plan
- `ChecklistItemIn.blocker` (template content; items are JSON, so no migration).
- `AuditCompletionItemOut.blocker_text` and `GoingConcernOut.subject`, both additive.
- The seed template carries the handoff's blocker sentences.
- AUD-19 reads both.
- Tests: `test_a07t25_checklist_blockers.py` and `AUD-19.test.tsx`.

## Left
- The summary's run line (A-07-T32); live reads (A-07-T47).

## Progress log
- 2026-11-08: built; runs at the close end pass.
