---
id: TASK-2418
title: T-01-T30 Independent AC tests for consents (T-01-T10, T-01-T16, T-01-T17)
spec: SPEC-000  # the backlog row; C19 and SPEC-501
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
epic: T-01
plan_key: T-01-T30
branch: s19-t01-t30
worktree: /Users/ayushkbhatia/Accrued/abacus-s19
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Acceptance: "The suite passes on main from the contract and SPEC alone, including a planted
combined use-and-disclosure document that is refused."

## Progress log
- `2026-10-30` — Off main. The plant found no refusal: `consent_capture` now raises 422
  `one_purpose_per_document` (DEC-1466). Unit 2/2 and integration 4/4 pass on this branch.
